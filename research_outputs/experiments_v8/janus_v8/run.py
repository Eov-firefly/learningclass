import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import traceback
import uuid

from .audit import dump


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_cases(data, model, stage, n, seed):
    rows = [json.loads(s) for s in (Path(data)/f'{model}.jsonl').read_text().splitlines()]
    rows = [r for r in rows if r['stage']=='main']
    selected=[]
    for task in ['gsm8k','arc']:
        task_rows = [r for r in rows if r['task']==task]
        if stage in {'timing','timing_pilot','trace'}:
            task_rows = [r for r in task_rows if r['timing_member']]
        task_rows.sort(key=lambda r:hashlib.sha256((str(seed)+r['question_id']).encode()).hexdigest())
        if len(task_rows)<n:raise ValueError('Not enough eligible cases; no silent undersampling')
        selected.extend(task_rows[:n])
    return selected


def code_hashes():
    root=Path(__file__).parent.parent
    return {str(p.relative_to(root)):sha(p) for p in sorted((root/'janus_v8').glob('*.py'))}


def device_snapshot():
    try:
        return subprocess.check_output(['nvidia-smi'],text=True,stderr=subprocess.STDOUT,timeout=10)
    except (OSError,subprocess.SubprocessError) as exc:
        return 'nvidia-smi unavailable: '+str(exc)


@contextmanager
def gpu_lock(device):
    import torch
    props=torch.cuda.get_device_properties(device)
    if not getattr(props,'uuid',None):
        raise RuntimeError('CUDA device UUID unavailable; cannot certify selected-device isolation')
    identity=str(props.uuid).replace('/','_')
    path=Path('/tmp')/('janus-v8-'+identity+'.lock')
    with path.open('a') as h:
        try:fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another v8 process is using this GPU')
        try:
            busy=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader'],text=True,timeout=10)
        except (OSError,subprocess.SubprocessError) as exc:
            raise RuntimeError('Cannot verify isolated GPU; fix nvidia-smi before measurement') from exc
        for line in busy.splitlines():
            fields=[x.strip() for x in line.split(',')]
            if len(fields)==2 and fields[0].lower().removeprefix('gpu-')==identity.lower().removeprefix('gpu-') and fields[1]!=str(os.getpid()):
                raise RuntimeError('Selected GPU has another compute process: '+line)
        yield


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--stage',required=True,choices=['smoke','trace','quality','timing_pilot','timing'])
    ap.add_argument('--model',required=True,choices=['qwen','mistral'])
    ap.add_argument('--session',type=int,default=0)
    ap.add_argument('--plan',type=Path,default=Path('plan.json'))
    ap.add_argument('--data',type=Path,default=Path('data'))
    ap.add_argument('--out',type=Path,default=Path('runs'))
    ap.add_argument('--label',default='')
    ap.add_argument('--device',default='cuda:0')
    ap.add_argument('--local-model',type=Path,help='Optional offline snapshot; provenance must be confirmed independently')
    a=ap.parse_args()
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from .engine import generate_one
    if not a.device.startswith('cuda') or not torch.cuda.is_available():
        raise RuntimeError('This CLI requires a CUDA GPU; CPU fixtures are tests only')
    plan=json.loads(a.plan.read_text()); spec=plan['stages'][a.stage]
    if not 0 <= a.session < spec['sessions']:raise ValueError('Session outside frozen plan')
    manifest=json.loads((a.data/'manifest.json').read_text())
    for filename,digest in manifest['files'].items():
        if sha(a.data/filename)!=digest:raise ValueError('Prepared data hash mismatch: '+filename)
    cases=select_cases(a.data,a.model,a.stage,spec['n_per_task'],plan['seed'])
    protocol=json.loads((a.data/'protocol.json').read_text())
    model_spec=protocol['models'][a.model]
    # Output directory is exclusive. Partial sessions remain inspectable; never silently resume timing.
    label=('-'+a.label) if a.label else ''
    if a.label and (Path(a.label).name!=a.label or a.label in {'.','..'}):raise ValueError('Label must be a filename component')
    run_dir=a.out/f'{a.stage}-{a.model}-s{a.session}{label}'
    run_dir.mkdir(parents=True,exist_ok=False)
    tasks=[(i,p,r) for i in range(len(cases)) for p in spec['policies'] for r in range(spec['repeats'])]
    rng=random.Random(plan['seed']+a.session*1009+(0 if a.model=='qwen' else 1))
    rng.shuffle(tasks)
    meta=dict(status='prepared',started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
              run_uuid=uuid.uuid4().hex,experiment_id=plan['experiment_id'],stage=a.stage,model=a.model,
              session=a.session,plan=plan,plan_sha256=sha(a.plan),data_manifest_sha256=sha(a.data/'manifest.json'),
              source_hashes=code_hashes(),model_spec=model_spec,local_snapshot_override=str(a.local_model) if a.local_model else None,
              expected_calls=len(tasks),selected_question_ids=[c['question_id'] for c in cases],
              job_order=[{'question_id':cases[i]['question_id'],'policy':p,'repeat':r} for i,p,r in tasks],
              python=platform.python_version(),platform=platform.platform(),
              packages={p:importlib.metadata.version(p) for p in ['torch','transformers','tokenizers','numpy','scipy','safetensors']},
              cuda=torch.version.cuda,device_before=device_snapshot())
    dump(run_dir/'meta.json',meta)
    try:
        with gpu_lock(a.device):
            torch.set_num_threads(plan['runtime']['torch_threads'])
            torch.set_num_interop_threads(plan['runtime']['torch_interop_threads'])
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.benchmark=False
            torch.manual_seed(plan['seed'])
            torch.cuda.set_device(a.device)
            if not torch.cuda.is_bf16_supported():raise RuntimeError('BF16 required by this plan; revise plan explicitly for other hardware')
            location=str(a.local_model) if a.local_model else model_spec['id']
            kwargs={'local_files_only':True} if a.local_model else {'revision':model_spec['revision']}
            tok=AutoTokenizer.from_pretrained(location,trust_remote_code=False,**kwargs)
            model=AutoModelForCausalLM.from_pretrained(location,trust_remote_code=False,
                torch_dtype=torch.bfloat16,attn_implementation='sdpa',**kwargs).to(a.device).eval()
            meta.update(status='running',model_config=model.config.to_dict(),generation_config=model.generation_config.to_dict(),
                        cuda_device=str(torch.cuda.get_device_properties(a.device)),device_after_load=device_snapshot())
            dump(run_dir/'meta.json',meta)
            def write_record(handle,r):
                handle.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
                handle.flush();os.fsync(handle.fileno())
            with (run_dir/'warmups.jsonl').open('x') as wh:
                for task in ['gsm8k','arc']:
                    cs=[c for c in cases if c['task']==task]
                    for policy in spec['policies']:
                        for i in range(spec['warmups_per_task_policy']):
                            c=cs[i%len(cs)]
                            r=generate_one(model,tok,c,policy,plan['cap'],plan['entropy'],a.device)
                            write_record(wh,dict(warmup=True,question_id=c['question_id'],**r))
            count=0
            with (run_dir/'records.jsonl').open('x') as h:
                for order,(index,policy,repeat) in enumerate(tasks):
                    c=cases[index]
                    r=generate_one(model,tok,c,policy,plan['cap'],plan['entropy'],a.device)
                    write_record(h,dict(model=a.model,task=c['task'],kind=c['kind'],gold=c['gold'],choices=c['choices'],
                        question_id=c['question_id'],stage=a.stage,session=a.session,repeat=repeat,order=order,
                        run_uuid=meta['run_uuid'],**r))
                    count+=1
                    print(f'{a.stage} {a.model} session={a.session} {count}/{len(tasks)}',flush=True)
            meta.update(status='complete',completed_calls=count,finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                        records_sha256=sha(run_dir/'records.jsonl'),device_after=device_snapshot())
            dump(run_dir/'meta.json',meta)
    except BaseException:
        meta.update(status='failed',error=traceback.format_exc(),device_after_failure=device_snapshot())
        dump(run_dir/'meta.json',meta)
        raise


if __name__=='__main__':main()
