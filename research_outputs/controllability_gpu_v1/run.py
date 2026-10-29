"""Two/four single-GPU workers; immutable protocol; explicit resume, no retries."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from common import (ROOT, ENGINE, MODEL_SPECS, POLICIES, CONDITIONS, compile_case,
                    digest, sha, read_jsonl, atomic, load_protocol, assignment, jobs)


def resume_records(path, expected, protocol_hash):
    rows = read_jsonl(path) if path.exists() else []
    by_id = {j['request_id']: j for j in expected}
    seen = {}
    for row in rows:
        rid = row['request_id']
        if rid in seen or rid not in by_id:
            raise ValueError('duplicate/unexpected request in ' + str(path))
        if row.get('protocol_sha256') != protocol_hash or any(row.get(k) != v for k, v in by_id[rid].items()):
            raise ValueError('raw record differs from frozen protocol')
        if row.get('error'):
            raise ValueError('a failed request is retained in raw; diagnose before a separately identified rerun')
        seen[rid] = row
    return seen


def worker(a):
    plan, public, languages, models = load_protocol(a.protocol)
    protocol_hash = sha(a.protocol / 'protocol.json')
    expected = jobs(public, languages, a.model, a.shard, a.shards)
    name = f'{a.model}.s{a.shard}'
    raw = a.output / f'{name}.raw.jsonl'
    seen = resume_records(raw, expected, protocol_hash)
    if len(seen) == len(expected):
        return
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from janus_min.engine import run_matched
    from janus_min.controllers import XGrammarRuntime
    from janus_min.spec import load_public
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for formal inference')
    torch.set_num_threads(2); torch.manual_seed(20261029)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    location = models[a.model]['local_path']
    tokenizer = AutoTokenizer.from_pretrained(location, local_files_only=True, trust_remote_code=False)
    # Detect tokenizer/language mutation before loading weights or making model calls.
    for case in public:
        frozen = languages[a.model][case['question_id']]
        actual = compile_case(tokenizer, case, 'option_text')
        if any(actual[k] != frozen[k] for k in actual):
            raise ValueError('actual tokenizer paths differ from frozen input')
    manifest = models[a.model]['manifest']
    import hashlib
    for relative, info in manifest['files'].items():
        file = Path(location) / relative
        if not file.is_file() or file.stat().st_size != info['bytes']:
            raise ValueError('model file missing or size changed: ' + relative)
        if 'sha256' in info:
            h = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    h.update(chunk)
            if h.hexdigest() != info['sha256']:
                raise ValueError('model file hash mismatch: ' + relative)
    t0 = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(location, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.bfloat16, low_cpu_mem_usage=True, attn_implementation='sdpa').to('cuda:0').eval()
    eos = model.generation_config.eos_token_id
    xr = XGrammarRuntime(tokenizer, model.config.vocab_size, eos if isinstance(eos, list) else [eos])
    env = dict(model=a.model, location=location, spec=MODEL_SPECS[a.model], python=platform.python_version(),
        torch=torch.__version__, transformers=importlib.metadata.version('transformers'),
        xgrammar=importlib.metadata.version('xgrammar'), cuda=torch.version.cuda,
        gpu=torch.cuda.get_device_name(), device=os.environ.get('CUDA_VISIBLE_DEVICES'),
        model_load_seconds=time.perf_counter()-t0, protocol_sha256=protocol_hash,
        mode='BF16 SDPA greedy batch1; sequence_score batches finite candidates; no TP/DDP',
        weight_hash_scope='all files with manifest sha256 verified; weights without sha256 verified by size only')
    # Separate session environments on resume, preserve prior runtime provenance.
    session = f'{time.time_ns()}-{os.getpid()}'
    atomic(a.output / f'{name}.{session}.environment.json', env)
    calibration = []
    dev = load_public('dev')[a.shard % 16]
    for _ in range(2):
        result = run_matched(model, tokenizer, dev,
            dict(track='matched', policy='full', encoding='option_text', cap=64), 'cuda:0', xr)
        if result['error']:
            raise RuntimeError('warmup failed: ' + result['error'])
    devlang = compile_case(tokenizer, dev, 'option_text')
    caps = dict(fixed8=8, exact_min=min(map(len, devlang['paths'])), wide=max(map(len, devlang['paths'])))
    for condition in CONDITIONS:
        for policy in POLICIES:
            j = dict(track='matched', encoding='option_text', cap=caps[condition], policy=policy)
            result = run_matched(model, tokenizer, dev, j, 'cuda:0', xr)
            calibration.append(dict(condition=condition, policy=policy, **result))
            if result['error']:
                raise RuntimeError('calibration failed: ' + result['error'])
    atomic(a.output / f'{name}.{session}.calibration.json', calibration)
    remaining = [j for j in expected if j['request_id'] not in seen]
    rates = {(r['condition'], r['policy']): r['request_ms'] for r in calibration}
    seconds = sum(rates[j['condition'], j['policy']] for j in remaining) / 1000
    atomic(a.output / f'{name}.eta.json', dict(remaining_requests=len(remaining), point_minutes=seconds/60,
        planning_range_minutes=[seconds/120, seconds/20],
        excludes='loading, weight-hash checks and downloads; extrapolation from one old dev case, not a confidence interval'))
    if a.calibrate_only:
        return
    cases = {r['question_id']: r for r in public}
    completed = len(seen)
    with raw.open('a', buffering=1) as stream:
        for job in remaining:
            torch.cuda.reset_peak_memory_stats()
            result = run_matched(model, tokenizer, cases[job['question_id']], job, 'cuda:0', xr)
            row = dict(**job, **result, protocol_sha256=protocol_hash, code_sha256=plan['source_sha256'],
                worker=name, session=session, device_provenance=env['device'],
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                measurement_scope='instrumented correctness run, includes canonical compilation/audit; not isolated latency benchmark')
            stream.write(json.dumps(row, ensure_ascii=False) + '\n'); stream.flush(); os.fsync(stream.fileno())
            completed += 1
            atomic(a.output / f'{name}.progress.json', dict(completed=completed, total=len(expected)))
            if result['error']:
                raise RuntimeError('formal request error preserved; no retry: ' + result['error'])


def launch(a):
    plan, public, languages, models = load_protocol(a.protocol)
    assign = assignment(a.devices.split(','))
    print(json.dumps(dict(workers=assign, records=plan['total_records'],
        neural_request_upper_bound=plan['neural_request_upper_bound'],
        evidence_label=plan['evidence_label'], warning='No model result exists until actually run.'), indent=2), flush=True)
    if a.plan:
        return
    a.output.mkdir(parents=True, exist_ok=True)
    lock = a.output / 'launch.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    procs, logs = [], []
    try:
        config = dict(protocol_sha256=sha(a.protocol / 'protocol.json'), assignment=assign,
                      source_sha256=plan['source_sha256'])
        cfg = a.output / 'execution_config.json'
        if cfg.exists() and json.loads(cfg.read_text()) != json.loads(json.dumps(config)):
            raise ValueError('resume requires identical source, protocol and GPU assignment; use new output')
        atomic(cfg, config)
        for model, shard, shards, device in assign:
            env = os.environ.copy()
            env.update(CUDA_VISIBLE_DEVICES=device, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                       TOKENIZERS_PARALLELISM='false')
            cmd = [sys.executable, str(ROOT / 'run.py'), '--worker', '--model', model,
                   '--shard', str(shard), '--shards', str(shards), '--protocol', str(a.protocol),
                   '--output', str(a.output)]
            if a.calibrate_only:
                cmd.append('--calibrate-only')
            log = (a.output / f'{model}.s{shard}.log').open('a'); logs.append(log)
            procs.append(subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT))
        last_report = 0
        while any(proc.poll() is None for proc in procs):
            if any(proc.poll() not in (None, 0) for proc in procs):
                raise RuntimeError('worker failed; inspect *.log; failed/partial raw retained')
            if time.monotonic() - last_report > 30:
                progress = {f.stem: json.loads(f.read_text()) for f in a.output.glob('*.progress.json')}
                eta = {f.stem: json.loads(f.read_text()) for f in a.output.glob('*.eta.json')}
                print(json.dumps(dict(progress=progress, calibration_eta=eta), ensure_ascii=False), flush=True)
                last_report = time.monotonic()
            time.sleep(1)
        if any(proc.returncode for proc in procs):
            raise RuntimeError('worker failed; inspect *.log')
        if not a.calibrate_only:
            print('Inference finished. Run analyze.py separately; outputs have not yet been scored.', flush=True)
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
        for log in logs:
            log.close()
        lock.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--devices', default='0,1')
    p.add_argument('--plan', action='store_true')
    p.add_argument('--calibrate-only', action='store_true')
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--model', choices=MODEL_SPECS, help=argparse.SUPPRESS)
    p.add_argument('--shard', type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument('--shards', type=int, default=1, help=argparse.SUPPRESS)
    a = p.parse_args(); a.protocol=a.protocol.resolve(); a.output=a.output.resolve()
    worker(a) if a.worker else launch(a)


if __name__ == '__main__':
    main()
