"""New retrospective analyses; no model calls, no new latency intervals."""
from pathlib import Path
import json,csv,hashlib
import argparse
from collections import defaultdict
from statistics import mean

ROOT=Path(__file__).resolve().parent


def write_csv(path,rows):
    with path.open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw-root',type=Path,required=True,help='Original results/revision_v5_1 directory')
    ap.add_argument('--followup-summary',type=Path,default=ROOT/'evidence/v83_results_summary.json')
    args=ap.parse_args()
    (ROOT/'analysis').mkdir(exist_ok=True)
    pairs=defaultdict(dict);sources={}
    for m in ['qwen','mistral']:
        f=args.raw_root/f'{m}.main.s0-of-1.jsonl';sources[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
        for line in f.open():
            r=json.loads(line)
            if r['policy'] in {'uniform','complete'}:
                key=(r['model'],r['task'],r['question_id'])
                assert r['policy'] not in pairs[key]
                pairs[key][r['policy']]=r
    grouped=defaultdict(list)
    for (model,task,qid),by in pairs.items():
        u,c=by['uniform'],by['complete']
        assert c['output_ids']==u['output_ids'][:c['tokens']]
        grouped[model,task].append((u,c))
    rows=[]
    for (model,task),ps in sorted(grouped.items()):
        assert len(ps)==600
        vg=[(u,c) for u,c in ps if c['valid'] and not u['valid']]
        vl=[(u,c) for u,c in ps if u['valid'] and not c['valid']]
        correct_repairs=sum(c['correct'] for u,c in vg)
        row=dict(model=model,task=task,n=len(ps),uniform_valid=sum(u['valid'] for u,c in ps),
            complete_valid=sum(c['valid'] for u,c in ps),validity_gains=len(vg),validity_losses=len(vl),
            newly_valid_correct=correct_repairs,newly_valid_incorrect=len(vg)-correct_repairs,
            correctness_gains=sum(c['correct'] and not u['correct'] for u,c in ps),
            correctness_losses=sum(u['correct'] and not c['correct'] for u,c in ps),
            shorter_outputs=sum(c['tokens']<u['tokens'] for u,c in ps),
            mean_tokens_saved=mean(u['tokens']-c['tokens'] for u,c in ps),
            shortened_equals_validity_repair=all((c['tokens']<u['tokens'])==(c['valid'] and not u['valid']) for u,c in ps))
        assert row['newly_valid_correct']==row['correctness_gains']
        assert not row['validity_losses']
        assert row['shortened_equals_validity_repair']
        rows.append(row)
    write_csv(ROOT/'analysis/validity_transitions.csv',rows)
    s=json.loads(args.followup_summary.read_text());sources['v83_results_summary.json']=hashlib.sha256(args.followup_summary.read_bytes()).hexdigest()
    formal=s['formal_contrasts'];cost=[]
    for model in ['qwen','mistral']:
        for task in ['gsm8k','arc']:
            for session in range(3):
                get=lambda p,c:next(r for r in formal if (r['model'],r['task'],r['session'],r['policy'],r['control'])==(model,task,session,p,c))
                b=get('boundary_observe','uniform');d=get('complete','uniform')
                cost.append(dict(model=model,task=task,session=session,
                    boundary_path_ms=1000*b['mean'],net_completion_ms=1000*d['mean'],
                    boundary_arm_difference_ms=1000*(b['mean']-d['mean']),
                    net_completion_ci_lo_ms=1000*d['lo'],net_completion_ci_hi_ms=1000*d['hi'],
                    derived_difference_ci='not_identifiable_from_marginal_intervals',
                    interpretation='algebraic contrast, not isolated generation cost or transferable speedup bound'))
    write_csv(ROOT/'analysis/cost_decomposition.csv',cost)
    result=dict(source_hashes=sources,n_pairs=sum(r['n'] for r in rows),
        validity_gains=sum(r['validity_gains'] for r in rows),validity_losses=sum(r['validity_losses'] for r in rows),
        newly_valid_correct=sum(r['newly_valid_correct'] for r in rows),
        newly_valid_incorrect=sum(r['newly_valid_incorrect'] for r in rows),
        validity_transitions=rows,cost_decomposition=cost,
        status='retrospective analysis of existing outputs and formal timing point estimates; no new inference',
        pooled_counts='model-question pairs, not independent questions; no pooled population inference',
        runtime_limit='new timing raw records absent; derived contrast uncertainty not recomputed')
    (ROOT/'analysis/new_analyses.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['cost_decomposition','source_hashes']},indent=2))


if __name__=='__main__':main()
