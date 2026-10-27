"""Separate scoring process. This is the only module that opens gold labels."""
import argparse
from collections import Counter,defaultdict
import csv
import json
import math
from pathlib import Path
import numpy as np
from scipy.stats import beta
from .spec import ROOT,load_public,jobs,validate_artifact,record_id,digest

def write_csv(path,rows):
    if not rows:path.write_text('');return
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def wilson(k,n):
    if not n:return [None,None]
    z=1.95996398454;p=k/n;den=1+z*z/n
    middle=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,middle-half),min(1,middle+half)]

def paired_binary(a,b,alpha=.05):
    wins=sum(x>y for x,y in zip(a,b));losses=sum(x<y for x,y in zip(a,b));n=len(a)
    def bounds(k):
        return (0. if not k else float(beta.ppf(alpha/4,k,n-k+1)),
                1. if k==n else float(beta.ppf(1-alpha/4,k+1,n-k)))
    wl,wu=bounds(wins);ll,lu=bounds(losses)
    return dict(n_question_clusters=n,wins=wins,losses=losses,difference=float(np.mean(np.array(a)-b)),
                ci_low=wl-lu,ci_high=wu-ll,confidence=1-alpha)

def mean_ci(values):
    x=np.asarray(values,dtype=float)
    if not len(x):return [None,None]
    means=x[np.random.default_rng(20261027).integers(0,len(x),(5000,len(x)))].mean(axis=1)
    return np.quantile(means,[.025,.975]).tolist()

def score(row,case,gold):
    text=row.get('returned_text','');prediction=None;valid=False;preserved=True
    if row['track']=='wrapper_e2e':
        from prototype.reference_contracts import parse
        prediction=parse(text,'choice',''.join(case['options']),eos=row.get('ended_with_eos',False),contract='closure_balanced')
        valid=prediction is not None
        bound=row.get('bound_value');preserved=bound is None or prediction==bound
    elif row['track']=='format':
        label=sorted(case['options'])[int(digest(case['question_id'])[:8],16)%len(case['options'])]
        canonical=json.dumps({'id':record_id(case),'answer':label},separators=(',',':'),ensure_ascii=False)+'\n'
        base=canonical[:-2];accepted={base+s for s in ['}\n','\n}\n','  }\n']}
        valid=text.rstrip() in {t.rstrip() for t in accepted};prediction=label if valid else None
        preserved=valid
    else:
        prediction=validate_artifact(text,case,row['encoding']);valid=prediction is not None
    declared=row['status'] in {'COMMIT','SUBMIT'}
    certified=declared and valid and preserved
    return dict(declared=int(declared),valid=int(valid),preserved=int(preserved),certified=int(certified),
         correct=int(certified and prediction==gold),prediction=prediction,
         invalid_submission=int(declared and not certified),
         budget_overrun=int(row.get('generated_tokens',0)+row.get('inserted_tokens',0)>row.get('effective_cap',row['cap'])))

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--allow-incomplete',action='store_true')
    a=p.parse_args();a.run.mkdir(exist_ok=True);out=a.run/'analysis';out.mkdir(exist_ok=True)
    cases={r['question_id']:r for r in load_public('eval')}
    manifest=json.loads((ROOT/'data/manifest.json').read_text())
    import hashlib
    assert hashlib.sha256((ROOT/'data/scoring.jsonl').read_bytes()).hexdigest()==manifest['files']['scoring.jsonl']
    gold={r['question_id']:r['gold'] for r in map(json.loads,(ROOT/'data/scoring.jsonl').read_text().splitlines())}
    rows=[];seen=set();duplicates=[];reachability=[]
    for f in sorted(a.run.glob('*.raw.jsonl')):
        for line in f.open():
            r=json.loads(line)
            if r['request_id'] in seen:duplicates.append(r['request_id'])
            seen.add(r['request_id']);r.update(score(r,cases[r['question_id']],gold[r['question_id']]))
            rows.append(r)
            if r['track']=='matched' and r.get('candidate_lengths'):
                labels=list(cases[r['question_id']]['options']);ref_index=labels.index(gold[r['question_id']])
                ref_len=r['candidate_lengths'][ref_index]
                reachability.append(dict(request_id=r['request_id'],question_id=r['question_id'],model=r['model'],
                  encoding=r['encoding'],budget=r['cap'],policy=r['policy'],canonical_reference_suffix_tokens=ref_len,
                  canonical_reference_path_fits=int(ref_len<=r['cap']),correct=r['correct'],certified=r['certified'],
                  scope='offline canonical-path diagnostic, not exact XGrammar-language distance'))
    expected={j['request_id'] for model in ['qwen','mistral'] for j in jobs(model)}
    missing=sorted(expected-seen);unexpected=sorted(seen-expected)
    groups=defaultdict(list)
    for r in rows:
        budget=r['condition'] if r['track']=='format' else str(r['cap'])
        groups[(r['model'],r['track'],r['encoding'],budget,r['policy'])].append(r)
    summary=[];failures=[]
    for key,rs in sorted(groups.items()):
        model,track,encoding,budget,policy=key;n=len(rs)
        byq=defaultdict(list)
        for r in rs:byq[r['question_id']].append(r)
        qmeans=[np.mean([r['correct'] for r in vals]) for vals in byq.values()]
        ci=wilson(sum(qmeans),len(qmeans)) if all(x in {0,1} for x in qmeans) else mean_ci(qmeans)
        qtimes=[np.mean([r['request_ms'] for r in vals]) for vals in byq.values()]
        time_ci=mean_ci(qtimes);nc=sum(r['certified'] for r in rs);correct=sum(r['correct'] for r in rs)
        summary.append(dict(model=model,track=track,encoding=encoding,budget=budget,policy=policy,
          n_requests=n,n_question_clusters=len(byq),n_declared=sum(r['declared'] for r in rs),n_certified=nc,
          n_correct=correct,correct_commit_rate=correct/n,quality_ci_low=ci[0],quality_ci_high=ci[1],
          certified_coverage=nc/n,conditional_accuracy=correct/nc if nc else None,
          invalid_submissions=sum(r['invalid_submission'] for r in rs),budget_overruns=sum(r['budget_overrun'] for r in rs),
          inference_errors=sum(bool(r.get('error')) for r in rs),mean_request_ms=float(np.mean(qtimes)),
          latency_ci_low=time_ci[0],latency_ci_high=time_ci[1],p50_ms=float(np.quantile([r['request_ms'] for r in rs],.5)),
          p95_ms=float(np.quantile([r['request_ms'] for r in rs],.95)),
          mean_generated_tokens=float(np.mean([r['generated_tokens'] for r in rs])),
          mean_inserted_tokens=float(np.mean([r['inserted_tokens'] for r in rs])),
          mean_candidate_score_tokens=float(np.mean([r.get('candidate_score_tokens',0) for r in rs])),
          mean_scoring_input_tokens=float(np.mean([r.get('scoring_input_tokens',0) for r in rs])),
          mean_forward_calls=float(np.mean([r['forward_calls'] for r in rs if r['forward_calls'] is not None])) if any(r['forward_calls'] is not None for r in rs) else None,
          mean_compile_ms=float(np.mean([r['compile_ms'] for r in rs if r.get('compile_ms') is not None])) if any(r.get('compile_ms') is not None for r in rs) else None,
          oracle_checks=sum(r.get('oracle_checks',0) for r in rs),legal_tokens_removed=sum(r.get('legal_tokens_removed',0) for r in rs)))
        counts=Counter(r['reason'] for r in rs if not r['certified'])
        for reason,count in sorted(counts.items()):failures.append(dict(model=model,track=track,encoding=encoding,budget=budget,policy=policy,reason=reason,count=count))
    contrasts=[]
    cells={key[:4] for key in groups}
    for model,track,encoding,budget in sorted(cells):
        for comparator in ['grammar','deterministic','xgrammar','uniform','early','sequence_score']:
            full=groups.get((model,track,encoding,budget,'full'));base=groups.get((model,track,encoding,budget,comparator))
            if not full or not base:continue
            def qmap(rs):
                result=defaultdict(list)
                for r in rs:result[r['question_id']].append(r)
                return {q:dict(correct=np.mean([r['correct'] for r in vals]),ms=np.mean([r['request_ms'] for r in vals])) for q,vals in result.items()}
            f,b=qmap(full),qmap(base);ids=sorted(f.keys()&b.keys())
            if not ids:continue
            primary=track=='matched' and encoding=='option_text' and budget=='24' and comparator=='grammar'
            diff=[f[q]['ms']-b[q]['ms'] for q in ids];timing=mean_ci(diff)
            aa=[f[q]['correct'] for q in ids];bb=[b[q]['correct'] for q in ids]
            if all(v in {0,1} for v in aa+bb):stats=paired_binary(aa,bb,.025 if primary else .05)
            else:
                ci=mean_ci(np.array(aa)-bb);stats=dict(n_question_clusters=len(ids),wins=None,losses=None,difference=float(np.mean(np.array(aa)-bb)),ci_low=ci[0],ci_high=ci[1],confidence=.95)
            contrasts.append(dict(model=model,track=track,encoding=encoding,budget=budget,comparator=comparator,
                primary=primary,**stats,mean_latency_difference_ms=float(np.mean(diff)),latency_ci_low=timing[0],latency_ci_high=timing[1]))
    format_mismatches=[]
    format_pairs=defaultdict(dict)
    for r in rows:
        if r['track']=='format' and r['policy'] in {'full','deterministic'}:
            format_pairs[(r['model'],r['question_id'],r['condition'])][r['policy']]=r
    for key,pair in format_pairs.items():
        if set(pair)=={'full','deterministic'}:
            f,d=pair['full'],pair['deterministic']
            if (f.get('provided_prefix_ids')!=d.get('provided_prefix_ids') or f['certified']!=d['certified']
                or (f['certified'] and f['prediction']!=d['prediction'])):format_mismatches.append(key)
    errors=[r['request_id'] for r in rows if r.get('error')]
    badcommits=[r['request_id'] for r in rows if r['policy']!='uniform' and r['status']=='COMMIT' and not r['certified']]
    overruns=[r['request_id'] for r in rows if r['budget_overrun']]
    checks=dict(expected_records=len(expected),actual_records=len(rows),missing=missing,unexpected=unexpected,duplicates=duplicates,
       inference_errors=errors,invalid_constrained_commits=badcommits,budget_overruns=overruns,
       format_reduction_mismatches=format_mismatches,
       status='COMPLETE' if not (missing or unexpected or duplicates or errors or badcommits or overruns or format_mismatches) else 'REQUIRES_REVIEW',
       scope='minimal known-cohort one-dataset validation; not novelty proof or powered small-effect confirmation',
       primary_family='full minus grammar, option_text budget24, two model cells; each 97.5% conservative paired interval',
       timing_scope='dedicated phase after four-worker barrier; isolated per GPU, shared host, batch1')
    write_csv(out/'summary.csv',summary);write_csv(out/'paired_contrasts.csv',contrasts);write_csv(out/'failure_breakdown.csv',failures)
    write_csv(out/'offline_reference_reachability.csv',reachability)
    with (out/'scored.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v if not isinstance(v,list) else len(v) for k,v in checks.items()},ensure_ascii=False,indent=2))
    if checks['status']!='COMPLETE' and not a.allow_incomplete:raise SystemExit(2)

if __name__=='__main__':main()
