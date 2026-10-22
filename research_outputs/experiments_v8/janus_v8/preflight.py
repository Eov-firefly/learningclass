"""Validate prepared input integrity and display a frozen workload before GPU use."""
import argparse
import json
from pathlib import Path
from .run import select_cases,sha,code_hashes
from .audit import dump


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--plan',type=Path,default=Path('plan.json'))
    ap.add_argument('--data',type=Path,default=Path('data'))
    ap.add_argument('--out',type=Path,default=Path('preflight.json'))
    a=ap.parse_args()
    p=json.loads(a.plan.read_text());manifest=json.loads((a.data/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        if sha(a.data/name)!=digest:raise ValueError('Prepared input changed: '+name)
    result={'plan_sha256':sha(a.plan),'source_hashes':code_hashes(),'stages':{}}
    for stage,spec in p['stages'].items():
        selection={m:select_cases(a.data,m,stage,spec['n_per_task'],p['seed']) for m in ['qwen','mistral']}
        if [r['question_id'] for r in selection['qwen']] != [r['question_id'] for r in selection['mistral']]:
            raise ValueError('Model cohorts differ')
        calls=2*2*spec['n_per_task']*len(spec['policies'])*spec['repeats']*spec['sessions']
        warmups=2*2*spec['warmups_per_task_policy']*len(spec['policies'])*spec['sessions']
        result['stages'][stage]={'scored_calls_both_models':calls,'warmups_both_models':warmups,
             'sessions_per_model':spec['sessions'],'question_ids':[r['question_id'] for r in selection['qwen']]}
        print(f'{stage}: scored={calls}, warmups={warmups}, sessions/model={spec["sessions"]}')
    if a.out.exists():raise FileExistsError('Preflight output already exists; use --out with a new filename')
    dump(a.out,result)


if __name__=='__main__':main()
