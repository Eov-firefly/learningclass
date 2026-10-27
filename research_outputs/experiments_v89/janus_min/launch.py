"""Four independent single-GPU workers; resident-model barrier before timing."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .spec import MODEL_SPECS,jobs,ROOT

def assignment(devices):
    if len(devices)!=4:raise ValueError('this frozen minimal plan requires exactly four GPU IDs')
    return [('qwen',0,devices[0]),('qwen',1,devices[1]),('mistral',0,devices[2]),('mistral',1,devices[3])]

def complete_records(path):
    """Read committed JSONL lines while a worker may be appending the next line.

    An unfinished trailing record is ignored in memory for ETA only. The raw
    file is never altered, and malformed newline-terminated records still fail.
    """
    if not path.exists():return []
    data=path.read_bytes()
    complete,separator,_=data.rpartition(b'\n')
    if not separator:return []
    return [json.loads(line) for line in complete.splitlines()]

def estimate(output,assign):
    estimates=[]
    for model,shard,device in assign:
        p=output/f'{model}.s{shard}.calibration.jsonl'
        if not p.exists():return None
        samples=complete_records(p)
        rates={(s['policy'],s['encoding']):s['request_ms']/max(1,s['generated_tokens']+s['inserted_tokens']) for s in samples}
        raw=output/f'{model}.s{shard}.raw.jsonl'
        done={row['request_id'] for row in complete_records(raw)}
        seconds=0
        for j in jobs(model,shard,2):
            if j['request_id'] in done:continue
            policy=j['policy'];encoding=j['encoding'];cap=j['cap']
            if j['track']=='wrapper_e2e':policy='uniform';cap=128
            if j['track']=='format':cap=12
            per_token=rates.get((policy,encoding),max(rates.values(),default=100))
            seconds+=per_token*max(cap,1)/1000
        estimates.append(dict(worker=f'{model}.s{shard}',conservative_seconds=seconds))
    point=max(e['conservative_seconds'] for e in estimates)
    report=dict(method='calibration request_ms per emitted token times formal caps; conservative cap envelope, not a confidence interval',
        remaining_point_minutes=point/60,planning_range_minutes=[point*.7/60,point*1.7/60],workers=estimates,
        excludes='model loading already completed; downloads/install; pathological retries')
    (output/'calibrated_eta.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('runs/minimal'))
    p.add_argument('--devices',default='0,1,2,3');p.add_argument('--qwen-path');p.add_argument('--mistral-path')
    p.add_argument('--plan',action='store_true');p.add_argument('--calibrate-only',action='store_true')
    p.add_argument('--skip-xgrammar',action='store_true');p.add_argument('--local-files-only',action='store_true')
    a=p.parse_args();assign=assignment(a.devices.split(','))
    from collections import Counter
    grid=Counter((j['track'],j['policy']) for m in MODEL_SPECS for j in jobs(m))
    print(json.dumps({'workers':assign,'formal_records':sum(grid.values()),'counts':{str(k):v for k,v in grid.items()},
        'GPU_parallelism':'one model instance/GPU; qwen 2 shards + mistral 2 shards; no DDP/TP',
        'scope':'96 known ARC eval questions, two output encodings; not two independent tasks'},indent=2),flush=True)
    if a.plan:return
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
    lock=a.output/'launch.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('run directory locked; confirm old processes stopped before removing launch.lock')
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    barrier=a.output/'release_timing';barrier.unlink(missing_ok=True)
    processes=[];logs=[];eta_done=False;last_print=0
    try:
        from .worker import code_hash
        from .spec import digest
        protocol=dict(version='8.9.1',code_sha256=code_hash(),data_manifest=digest(json.loads((ROOT/'data/manifest.json').read_text())),
          model_specs=MODEL_SPECS,qwen_path=a.qwen_path,mistral_path=a.mistral_path,skip_xgrammar=a.skip_xgrammar,
          assignment=assign,formal_records=sum(grid.values()),primary='full-grammar, option_text, remaining budget24, two model cells')
        protocol_file=a.output/'frozen_run_config.json'
        if protocol_file.exists():
            if json.loads(protocol_file.read_text())!=json.loads(json.dumps(protocol)):
                raise RuntimeError('frozen run configuration differs; use a new output directory')
        else:protocol_file.write_text(json.dumps(protocol,indent=2)+'\n')
        for model,shard,device in assign:
            # Remove stale progress/calibration only; completed raw records are preserved.
            (a.output/f'{model}.s{shard}.progress.json').unlink(missing_ok=True)
            (a.output/f'{model}.s{shard}.calibration.jsonl').unlink(missing_ok=True)
            cmd=[sys.executable,'-m','janus_min.worker','--model',model,'--shard',str(shard),
                 '--output',str(a.output),'--local-files-only'] if a.local_files_only else [sys.executable,'-m','janus_min.worker','--model',model,'--shard',str(shard),'--output',str(a.output)]
            local=getattr(a,model+'_path')
            if local:cmd+=['--model-path',local]
            if a.calibrate_only:cmd+=['--calibrate-only']
            if a.skip_xgrammar:cmd+=['--skip-xgrammar']
            env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES=device,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false')
            log=(a.output/f'{model}.s{shard}.log').open('a');logs.append(log)
            processes.append(subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT))
        while True:
            for proc in processes:
                if proc.poll() not in {None,0}:raise RuntimeError(f'worker failed (exit {proc.returncode}); see *.log; no failed record is silently retried')
            progress=[]
            for model,shard,_ in assign:
                file=a.output/f'{model}.s{shard}.progress.json'
                if file.exists():progress.append(json.loads(file.read_text()))
            if not eta_done and len(progress)==4:
                report=estimate(a.output,assign)
                if report:print('CALIBRATED ETA '+json.dumps(report),flush=True);eta_done=True
            if len(progress)==4 and all(r['phase'] in {'waiting_timing_barrier','done'} for r in progress):
                barrier.touch(exist_ok=True)
            if time.monotonic()-last_print>30:
                print('PROGRESS '+json.dumps(progress),flush=True);last_print=time.monotonic()
            if all(proc.poll() is not None for proc in processes):break
            time.sleep(1)
        if not a.calibrate_only:
            subprocess.run([sys.executable,'-m','janus_min.analyze','--run',str(a.output)],cwd=ROOT,check=True)
    finally:
        for proc in processes:
            if proc.poll() is None:proc.terminate()
        for proc in processes:
            try:proc.wait(timeout=15)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        for log in logs:log.close()
        lock.unlink(missing_ok=True)

if __name__=='__main__':main()
