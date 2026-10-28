"""Exploratory reuse of completed v8.9 matched-prefix outputs; no GPU inference.

Gold is optional and read only for scoring. Exact prefix/dead-end diagnostics
need the actual local tokenizer. Missing diagnostics are NA, never assumed zero.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path


def artifacts(case,encoding):
    ident=case['question_id'].split(':')[-1][:8]
    return {label:json.dumps({'id':ident,'answer':label if encoding=='label' else text},
            separators=(',',':'),ensure_ascii=False)+'\n' for label,text in case['options'].items()}

def compile_paths(tokenizer,texts):
    paths=[tokenizer.encode(s,add_special_tokens=False) for s in texts.values()]
    decode=lambda ids:tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)
    if any(decode(p)!=s for p,s in zip(paths,texts.values())):raise ValueError('round-trip mismatch')
    common=0
    while common<min(map(len,paths)) and len({p[common] for p in paths})==1:common+=1
    return paths[0][:common],[p[common:] for p in paths]

def path_diagnostics(paths,generated,budget,forward_calls):
    minimum=min(map(len,paths));first_dead=None;first_escape=None
    for j in range(len(generated)+1):
        compatible=[p for p in paths if p[:j]==generated[:j] and len(p)>=j]
        if not compatible:first_escape=j;break
        distance=min(len(p)-j for p in compatible)
        if distance>budget-j and first_dead is None:first_dead=j
    return dict(initially_feasible=int(minimum<=budget),first_dead_step=first_dead,
        first_language_escape_step=first_escape,
        entered_dead_after_feasible=int(minimum<=budget and first_dead is not None),
        calls_after_dead=max(0,forward_calls-first_dead) if first_dead is not None and forward_calls is not None else (0 if first_dead is None else None))

def write_csv(path,rows):
    if not rows:path.write_text('');return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def score(row,case,gold):
    text=row.get('returned_text','').rstrip()
    prediction=next((label for label,s in artifacts(case,row['encoding']).items() if s.rstrip()==text),None)
    declared=row.get('status') in {'COMMIT','SUBMIT'}
    certified=int(declared and prediction is not None)
    return dict(certified=certified,invalid_submission=int(declared and not certified),
        correct=int(certified and prediction==gold) if gold is not None else None)

def paired_bounds(wins,losses,n,alpha=.05):
    """Conservative paired binary CI from simultaneous exact binomial bounds."""
    if not n:return None,None
    tail=alpha/4
    def cdf(k,p):return sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k+1))
    def inverse(k,target):
        lo,hi=0.,1.
        for _ in range(65):
            mid=(lo+hi)/2
            if cdf(k,mid)>target:lo=mid
            else:hi=mid
        return (lo+hi)/2
    def bounds(k):return (0. if k==0 else inverse(k-1,1-tail),1. if k==n else inverse(k,tail))
    wl,wu=bounds(wins);ll,lu=bounds(losses)
    return wl-lu,wu-ll

def pair_summary(full,grammar):
    paired=full.keys()&grammar.keys()
    gc=[q for q in paired if grammar[q]['certified']]
    failed=[q for q in paired if not grammar[q]['certified']]
    context=['provided_prefix_ids','language_sha256','effective_cap','code_sha256','compiled_minimum_tokens']
    def same_ids(a,b):
        keys=['provided_prefix_ids','generated_ids','returned_ids']
        return all(k in a and k in b and a[k]==b[k] for k in keys)
    cw=sum(full[q]['certified'] and not grammar[q]['certified'] for q in paired)
    cl=sum(grammar[q]['certified'] and not full[q]['certified'] for q in paired)
    low,high=paired_bounds(cw,cl,len(paired))
    feasible=[q for q in paired if full[q].get('initially_feasible')==grammar[q].get('initially_feasible')==1]
    fw=sum(full[q]['certified'] and not grammar[q]['certified'] for q in feasible)
    fl=sum(grammar[q]['certified'] and not full[q]['certified'] for q in feasible)
    flow,fhigh=paired_bounds(fw,fl,len(feasible))
    return dict(n_pairs=len(paired),full_only=len(full.keys()-grammar.keys()),grammar_only=len(grammar.keys()-full.keys()),
      certified_difference=(cw-cl)/len(paired) if paired else None,
      certified_ci_low=low,certified_ci_high=high,
      feasible_n_pairs=len(feasible),feasible_difference=(fw-fl)/len(feasible) if feasible else None,
      feasible_ci_low=flow,feasible_ci_high=fhigh,
      interval_scope='descriptive paired 95%; unadjusted across settings; not a confirmatory result',
      context_missing=sum(any(k not in full[q] or k not in grammar[q] for k in context) for q in paired),
      context_mismatches=sum(any(k in full[q] and k in grammar[q] and full[q][k]!=grammar[q][k] for k in context) for q in paired),
      grammar_certified=len(gc),
      lost_certified=sum(not full[q]['certified'] for q in gc),
      same_token_records=sum(full[q]['certified'] and same_ids(full[q],grammar[q]) for q in gc),
      ids_missing=sum(any(k not in full[q] or k not in grammar[q] for k in ['provided_prefix_ids','generated_ids','returned_ids']) for q in gc),
      lost_correct=sum(grammar[q]['correct']==1 and full[q]['correct']!=1 for q in gc) if all(grammar[q]['correct'] is not None and full[q]['correct'] is not None for q in gc) else None,
      new_certified=sum(full[q]['certified'] for q in failed),
      new_correct=sum(full[q]['correct'] for q in failed) if all(full[q]['correct'] is not None for q in failed) else None)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--public',type=Path,required=True)
    p.add_argument('--scoring',type=Path)
    p.add_argument('--qwen-tokenizer');p.add_argument('--mistral-tokenizer')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cases={r['question_id']:r for r in map(json.loads,a.public.read_text().splitlines())}
    gold={r['question_id']:r['gold'] for r in map(json.loads,a.scoring.read_text().splitlines())} if a.scoring else {}
    tokenizers={}
    for model in ['qwen','mistral']:
        local=getattr(a,model+'_tokenizer')
        if local:
            from transformers import AutoTokenizer
            tokenizers[model]=AutoTokenizer.from_pretrained(local,local_files_only=True,trust_remote_code=False)
    rows=[];seen=set();paths_cache={};sources={};ignored=0
    for file in sorted(a.run.rglob('*.raw.jsonl')):
        data=file.read_bytes();sources[str(file)]=hashlib.sha256(data).hexdigest()
        if data and not data.endswith(b'\n'):raise ValueError('unfinished raw file: '+str(file))
        for line in data.splitlines():
            r=json.loads(line)
            if r.get('track')!='matched':ignored+=1;continue
            if r['request_id'] in seen:raise ValueError('duplicate request_id: '+r['request_id'])
            seen.add(r['request_id']);case=cases[r['question_id']]
            s=score(r,case,gold.get(r['question_id']));r.update(s)
            minimum=r.get('compiled_minimum_tokens')
            r['initially_feasible']=int(minimum<=r['effective_cap']) if minimum is not None else None
            r['entered_dead_after_feasible']=None;r['first_dead_step']=None
            r['first_language_escape_step']=None;r['calls_after_dead']=None
            r['distance_check']='not_reconstructed';r['distance_error']=None
            if r['model'] in tokenizers and r['policy'] in {'full','grammar'}:
                key=(r['model'],r['question_id'],r['encoding'])
                try:
                    if key not in paths_cache:paths_cache[key]=compile_paths(tokenizers[r['model']],artifacts(case,r['encoding']))
                    prefix,paths=paths_cache[key]
                    language=artifacts(case,r['encoding'])
                    expected_hash=hashlib.sha256(json.dumps(language,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    if r.get('language_sha256')!=expected_hash:raise ValueError('actual compiled language is unverified or differs')
                    if prefix!=r['provided_prefix_ids']:raise ValueError('actual prefix differs from reconstruction')
                    r['compiled_minimum_tokens']=min(map(len,paths))
                    r.update(path_diagnostics(paths,r['generated_ids'],r['effective_cap'],r['forward_calls']))
                    r['distance_check']='reconstructed'
                except Exception as exc:r['distance_error']=f'{type(exc).__name__}: {exc}'
            rows.append(r)
    if not rows:raise ValueError('no matched-track raw records found')
    groups=defaultdict(list)
    for r in rows:groups[(r['model'],r['encoding'],r['cap'],r['policy'])].append(r)
    summary=[]
    for (model,encoding,cap,policy),rs in sorted(groups.items()):
        if len({r['question_id'] for r in rs})!=len(rs):
            raise ValueError('matched-track repeats require an explicit question-cluster analysis; not silently collapsed')
        n=len(rs);feasible=[r for r in rs if r['initially_feasible']==1]
        checked=[r for r in rs if r['distance_check']=='reconstructed']
        checked_feasible=[r for r in checked if r['initially_feasible']==1]
        failed=[r for r in rs if not r['certified']]
        summary.append(dict(model=model,encoding=encoding,cap=cap,policy=policy,n=n,
          certified=sum(r['certified'] for r in rs),coverage=sum(r['certified'] for r in rs)/n,
          correct=sum(r['correct'] for r in rs) if all(r['correct'] is not None for r in rs) else None,
          inference_errors=sum(bool(r.get('error')) for r in rs),
          initial_feasibility_known=sum(r['initially_feasible'] is not None for r in rs),
          initially_feasible=len(feasible),
          feasible_completion_rate=sum(r['certified'] for r in feasible)/len(feasible) if feasible else None,
          invalid_submissions=sum(r['invalid_submission'] for r in rs),
          exact_distance_checked=len(checked),dead_entry_denominator=len(checked_feasible),
          dead_entries=sum(r['entered_dead_after_feasible'] for r in checked_feasible) if checked_feasible else None,
          prefix_language_escapes=sum(r['first_language_escape_step'] is not None for r in checked) if checked else None,
          post_dead_calls=sum(r['calls_after_dead'] for r in checked if r['calls_after_dead'] is not None) if checked else None,
          failed_request_forward_calls=sum(r['forward_calls'] for r in failed) if all(r.get('forward_calls') is not None for r in failed) else None,
          failed_request_ms=sum(r['request_ms'] for r in failed),
          distance_reconstruction_errors=sum(bool(r['distance_error']) for r in rs)))
    pairs=[]
    for model,encoding,cap,policy in sorted(groups):
        if policy!='full':continue
        f={r['question_id']:r for r in groups[(model,encoding,cap,'full')]}
        g={r['question_id']:r for r in groups.get((model,encoding,cap,'grammar'),[])}
        if g:pairs.append(dict(model=model,encoding=encoding,cap=cap,**pair_summary(f,g)))
    write_csv(a.out/'control_summary.csv',summary);write_csv(a.out/'trajectory_preservation.csv',pairs)
    with (a.out/'control_scored.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    report=dict(scope='exploratory matched-track reanalysis, not a new predeclared result or raw-grid integrity certification',
       analyzed=len(rows),ignored_other_tracks=ignored,raw_sources=sources,
       exact_distance_models=list(tokenizers),note='NA means unavailable. Canonical dead-end diagnostics apply only to the same reconstructed token trie, not alternative XGrammar tokenizations.')
    (a.out/'analysis_scope.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='raw_sources'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
