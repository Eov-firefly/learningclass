import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time
import traceback

from .spec import ROOT,MODEL_SPECS,jobs,load_public,digest

def atomic(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)

def code_hash():
    import hashlib
    paths=sorted(list((ROOT/'janus_min').glob('*.py'))+list((ROOT/'prototype').glob('*.py')))
    return digest({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',choices=MODEL_SPECS,required=True);p.add_argument('--model-path')
    p.add_argument('--shard',type=int,required=True);p.add_argument('--shards',type=int,default=2)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--device',default='cuda:0')
    p.add_argument('--calibrate-only',action='store_true');p.add_argument('--skip-xgrammar',action='store_true')
    p.add_argument('--local-files-only',action='store_true');p.add_argument('--allow-cpu',action='store_true')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    name=f'{args.model}.s{args.shard}';progress=args.output/f'{name}.progress.json'
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from .controllers import XGrammarRuntime
    from .engine import run_matched,run_wrapper
    torch.set_num_threads(2)
    torch.manual_seed(20261027)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.benchmark=False
    try:torch.set_num_interop_threads(2)
    except RuntimeError:pass
    if not torch.cuda.is_available() and not args.allow_cpu:raise RuntimeError('CUDA required; use --allow-cpu only for controlled tests')
    spec=MODEL_SPECS[args.model];location=args.model_path or spec['id']
    kw=dict(local_files_only=args.local_files_only,trust_remote_code=False)
    if not args.model_path:kw['revision']=spec['revision']
    t0=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(location,**kw)
    model=AutoModelForCausalLM.from_pretrained(location,torch_dtype=torch.bfloat16 if str(args.device).startswith('cuda') else torch.float32,
             low_cpu_mem_usage=True,attn_implementation='sdpa',**kw).to(args.device).eval()
    eos=model.generation_config.eos_token_id;eos=eos if isinstance(eos,list) else [eos]
    xr=None;x_error=None
    if not args.skip_xgrammar:
        # Fail preflight before expensive formal work if the required engine cannot initialize.
        xr=XGrammarRuntime(tok,model.config.vocab_size,eos)
    else:x_error='explicitly skipped: experiment incomplete for E4'
    env=dict(model=args.model,location=location,revision=spec['revision'],model_load_seconds=time.perf_counter()-t0,
      python=platform.python_version(),torch=torch.__version__,transformers=importlib.metadata.version('transformers'),
      xgrammar=importlib.metadata.version('xgrammar') if xr is not None else None,
      cuda=torch.version.cuda,device=args.device,gpu=torch.cuda.get_device_name() if torch.cuda.is_available() else 'CPU',
      visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),code_sha256=code_hash(),
      model_config=model.config.to_dict(),generation='BF16/SDPA/greedy/batch1/no tensor parallel',
      weight_hash_scope='pinned HF revision or user local path; full weight checksums optional in prepare command',
      xgrammar_error=x_error)
    atomic(args.output/f'{name}.environment.json',env)
    public={r['question_id']:r for r in load_public('eval')}
    dev=load_public('dev');calibration=[]
    with (args.output/f'{name}.calibration.jsonl').open('w') as f:
        for index,encoding in enumerate(['label','option_text']):
            case=dev[(args.shard*2+index)%len(dev)]
            warm=dict(track='matched',policy='uniform',encoding=encoding,cap=16,condition='ordinary')
            run_matched(model,tok,case,warm,args.device,xr)
            for policy in ['uniform','grammar','full','xgrammar','deterministic','sequence_score']:
                job=dict(track='matched',policy=policy,encoding=encoding,cap=64,condition='ordinary')
                if policy=='xgrammar' and args.skip_xgrammar:continue
                result=run_matched(model,tok,case,job,args.device,xr)
                item=dict(model=args.model,question_id=case['question_id'],**job,**result)
                calibration.append(item);f.write(json.dumps(item,ensure_ascii=False)+'\n');f.flush()
                if result['error']:raise RuntimeError('Calibration failed: '+result['error'])
    atomic(progress,dict(phase='calibrated',completed=0,total=0))
    if args.calibrate_only:return
    all_jobs=jobs(args.model,args.shard,args.shards)
    raw=args.output/f'{name}.raw.jsonl';seen={}
    if raw.exists():
        for line in raw.open():
            row=json.loads(line)
            if row['request_id'] in seen:raise RuntimeError('duplicate request in existing shard')
            if row['code_sha256']!=env['code_sha256']:raise RuntimeError('code changed: use a new output directory')
            seen[row['request_id']]=row
    remaining=[j for j in all_jobs if j['request_id'] not in seen]
    completed=len(seen)
    with raw.open('a',buffering=1) as f:
        for phase in ['quality','timing']:
            if phase=='timing':
                atomic(progress,dict(phase='waiting_timing_barrier',completed=completed,total=len(all_jobs)))
                deadline=time.monotonic()+3600
                while not (args.output/'release_timing').exists():
                    if time.monotonic()>deadline:raise TimeoutError('timing barrier timed out')
                    time.sleep(.5)
            selected=[j for j in remaining if (j['track']=='timing')==(phase=='timing')]
            for job in selected:
                started=time.perf_counter()
                if args.skip_xgrammar and job['policy']=='xgrammar':
                    result=dict(status='ABSTAIN',reason='missing_engine',error=x_error,
                      returned_text='',generated_ids=[],inserted_ids=[],generated_tokens=0,inserted_tokens=0,
                      forward_calls=0,request_ms=0,effective_cap=job['cap'])
                else:
                    try:
                        fn=run_wrapper if job['track']=='wrapper_e2e' else run_matched
                        result=fn(model,tok,public[job['question_id']],job,args.device,**({} if fn is run_wrapper else {'xruntime':xr}))
                    except Exception as exc:
                        result=dict(status='ABSTAIN',reason='outer_runtime_error',error=f'{type(exc).__name__}: {exc}',
                          returned_text='',generated_ids=[],inserted_ids=[],generated_tokens=0,inserted_tokens=0,
                          forward_calls=None,request_ms=(time.perf_counter()-started)*1000,effective_cap=job['cap'],traceback=traceback.format_exc())
                row=dict(**job,**result,shard=args.shard,worker=name,device_provenance=env['visible_devices'],
                    code_sha256=env['code_sha256'],raw_source='real model run; not trace replay')
                f.write(json.dumps(row,ensure_ascii=False)+'\n');completed+=1
                atomic(progress,dict(phase=phase,completed=completed,total=len(all_jobs),last_request=job['request_id']))
                if completed%50==0:os.fsync(f.fileno())
    atomic(progress,dict(phase='done',completed=completed,total=len(all_jobs)))

if __name__=='__main__':main()
