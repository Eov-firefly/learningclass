"""Verify new run completeness, analyze output identity, and replay trace gates.

Only measured policies have measured latency. Replay never estimates runtime.
"""
import argparse
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path
from statistics import mean
from .audit import dump, csv_dump
from .contracts import EntropyGate, same_answer, score
from .run import sha
from .stats import paired_binary, paired_bootstrap


def replay_trace(record, plan):
    trace=record['trace']
    ids=record['generated_ids']
    if len(trace)!=len(ids) or any(t['step']!=i+1 for i,t in enumerate(trace)):
        raise ValueError('Incomplete or misindexed trace')
    end=len(ids)
    boundaries=[t for t in trace if t['completion'] and not t['eos'] and t['step']<end]
    tc=boundaries[0]['step'] if boundaries else end
    results=[]
    grid=plan['trace_replay_grid']
    for threshold,window,min_steps in itertools.product(grid['thresholds'],grid['windows'],grid['min_steps']):
        gate=EntropyGate(threshold=threshold,window=window,min_steps=min_steps,alpha=plan['entropy']['alpha'])
        events=[]; stable_count=0; before_complete=0; opportunities=0
        min_step_blocked=0; stability_blocked=0; latch_events=[]
        for t in trace:
            opened=gate.update(t['step'],t['entropy'])
            if boundaries and t['step']>=tc and t['step']<end and opened:
                latch_events.append(t['step'])
            if opened and t['step']<end:stable_count+=1
            if t['completion'] and not t['eos'] and t['step']<end:
                opportunities+=1
                if not opened:before_complete+=1
                if t['step']<min_steps:min_step_blocked+=1
                if gate.streak<window:stability_blocked+=1
                if opened:events.append(t['step'])
        te=events[0] if events else end
        assert tc<=te<=end
        result={'model':record['model'],'task':record['task'],'question_id':record['question_id'],
                'threshold':threshold,'window':window,'min_steps':min_steps,
                'uniform_tokens':end,'complete_tokens':tc,'conjunction_tokens':te,
                'completion_opportunities':opportunities,'stable_steps_before_end':stable_count,
                'overlap_opportunities':len(events),'blocked_completion_steps':before_complete,
                'minimum_step_blocks':min_step_blocked,'stability_blocks':stability_blocked,
                'latched_generated_tokens':latch_events[0] if latch_events else end,
                'latched_returned_tokens':tc,
                'complete_replayed_strict_correct':same_answer(trace[tc-1]['prediction'],record['gold'],record['kind']) if tc<end else record['scores']['strict']['correct'],
                'triggered_before_uniform':te<end,'status':'offline-replay-not-measured-latency'}
        if te<end:
            token=trace[te-1]
            result['replayed_strict_correct']=same_answer(token['prediction'],record['gold'],record['kind'])
        else:
            result['replayed_strict_correct']=record['scores']['strict']['correct']
        results.append(result)
    return results


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--runs',type=Path,default=Path('runs'))
    ap.add_argument('--out',type=Path,default=Path('analysis'))
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    report={'errors':[],'warnings':[],'sessions':[]}
    def check(ok,msg):
        if not ok:report['errors'].append(msg)
    all_records=[];replayed=[];plans=set();implementations=set();data_manifests=set()
    for mf in sorted(a.runs.glob('*/meta.json')):
        m=json.loads(mf.read_text())
        if m['status']!='complete':
            report['errors'].append('Incomplete session retained: '+str(mf));continue
        path=mf.parent/'records.jsonl'
        if not path.exists():
            report['errors'].append('Missing records: '+str(path));continue
        check(sha(path)==m['records_sha256'],'Record checksum: '+str(path))
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        check(len(rows)==m['expected_calls'],'Call count: '+str(path))
        identities=[(r['question_id'],r['policy'],r['repeat']) for r in rows]
        expected=[(r['question_id'],r['policy'],r['repeat']) for r in m['job_order']]
        check(identities==expected,'Call grid/order: '+str(path))
        check(all(r['session']==m['session'] and r['run_uuid']==m['run_uuid'] for r in rows),'Session IDs')
        plans.add(m['plan_sha256'])
        implementations.add(json.dumps(m['source_hashes'],sort_keys=True))
        data_manifests.add(m['data_manifest_sha256'])
        stage=m['stage']; report['sessions'].append({'directory':str(mf.parent),'stage':stage,'model':m['model'],
                                                     'session':m['session'],'calls':len(rows)})
        check(all(r['actual_generated_tokens']==len(r['generated_ids']) and r['returned_tokens']==len(r['returned_ids']) for r in rows),'Token lengths')
        spec=m['plan']['stages'][stage]
        warmup_path=mf.parent/'warmups.jsonl'
        warmups=[json.loads(s) for s in warmup_path.read_text().splitlines()] if warmup_path.exists() else []
        check(len(warmups)==2*spec['warmups_per_task_policy']*len(spec['policies']),'Warmup count: '+str(mf))
        for r in rows:
            for contract,stored in r['scores'].items():
                check(stored==score(r['text'],r['kind'],r['gold'],r['choices'],r['returned_eos'],contract),'New score mismatch')
        if stage=='trace':
            for r in rows:
                check(r['diagnostic_only'],'Trace timing not labeled diagnostic')
                replayed.extend(replay_trace(r,m['plan']))
        all_records.extend(rows)
    check(bool(report['sessions']),'No complete sessions discovered')
    check(len(plans)<=1,'Mixed plan hashes; use separate analysis roots')
    check(len(implementations)<=1,'Mixed implementation hashes; do not pool modified source versions')
    check(len(data_manifests)<=1,'Mixed prepared input manifests')
    # Prevent duplicate retries being pooled and changing question/session weighting.
    identity=[(r['stage'],r['model'],r['session'],r['question_id'],r['policy'],r['repeat']) for r in all_records]
    check(len(identity)==len(set(identity)),'Duplicate retry/session records; select one documented run set')
    summaries=[];paired=[];identity_results=[]
    grouped=defaultdict(list)
    for r in all_records:
        if not r['diagnostic_only']:grouped[r['stage'],r['model'],r['session'],r['task'],r['policy']].append(r)
    for (stage,model,session,task,policy),rs in sorted(grouped.items()):
        for contract in rs[0]['scores']:
            summaries.append(dict(stage=stage,model=model,session=session,task=task,policy=policy,
                contract=contract,n_calls=len(rs),n_questions=len({r['question_id'] for r in rs}),
                accuracy=mean(r['scores'][contract]['correct'] for r in rs),
                valid_rate=mean(r['scores'][contract]['valid'] for r in rs),
                mean_generated_tokens=mean(r['actual_generated_tokens'] for r in rs),
                mean_returned_tokens=mean(r['returned_tokens'] for r in rs),
                mean_end_to_end_seconds=mean(r['end_to_end_seconds'] for r in rs),
                end_to_end_p50_seconds=sorted(r['end_to_end_seconds'] for r in rs)[math.ceil(.5*len(rs))-1],
                end_to_end_p95_seconds=sorted(r['end_to_end_seconds'] for r in rs)[math.ceil(.95*len(rs))-1],
                generated_tokens_per_credited_correct=sum(r['actual_generated_tokens'] for r in rs)/sum(r['scores'][contract]['correct'] for r in rs) if any(r['scores'][contract]['correct'] for r in rs) else None))
    contrasts=[('complete','uniform'),('structured_complete','complete'),('entropy_observe','complete'),
               ('boundary_observe','uniform'),('entropy_uniform','boundary_observe')]
    context=sorted({(r['stage'],r['model'],r['session'],r['task']) for r in all_records if not r['diagnostic_only']})
    for stage,model,session,task in context:
        for p,c in contrasts:
            ps,cs=grouped[stage,model,session,task,p],grouped[stage,model,session,task,c]
            if not ps or not cs:continue
            pm={(r['question_id'],r['repeat']):r for r in ps}
            cm={(r['question_id'],r['repeat']):r for r in cs}
            check(pm.keys()==cm.keys(),'Unpaired new policies')
            keys=sorted(pm.keys() & cm.keys())
            output_same=all(pm[k]['generated_ids']==cm[k]['generated_ids'] for k in keys)
            identity_results.append(dict(stage=stage,model=model,session=session,task=task,policy=p,control=c,
                n_pairs=len(keys),generated_ids_equal=output_same))
            if p in {'entropy_observe','boundary_observe','entropy_uniform'}:
                check(output_same,'Monitoring contrast output mismatch: '+str((stage,model,session,task,p,c)))
            if c=='uniform':
                check(all(pm[k]['generated_ids']==cm[k]['generated_ids'][:pm[k]['actual_generated_tokens']] for k in keys),'New stopping policy not Uniform prefix')
            # Average repeat differences within question before resampling.
            d=defaultdict(list)
            for k in keys:d[k[0]].append(pm[k]['end_to_end_seconds']-cm[k]['end_to_end_seconds'])
            ids=sorted(d)
            paired.append(dict(stage=stage,model=model,session=session,task=task,policy=p,control=c,
                metric='end_to_end_seconds',output_matched=output_same,
                descriptive_unadjusted=True,**paired_bootstrap([mean(d[q]) for q in ids])))
            if stage in {'quality','smoke'}:
                for contract in ps[0]['scores']:
                    # Accuracy repeats must be deterministic for binary question analysis.
                    check(all(len({pm[k]['scores'][contract]['correct'] for k in keys if k[0]==q})==1 for q in ids),'Output variation in accuracy repeats')
                    one={q:next(k for k in keys if k[0]==q) for q in ids}
                    paired.append(dict(stage=stage,model=model,session=session,task=task,policy=p,control=c,
                        metric='correct',contract=contract,descriptive_unadjusted=True,
                        **paired_binary([pm[one[q]]['scores'][contract]['correct'] for q in ids],
                                        [cm[one[q]]['scores'][contract]['correct'] for q in ids])))
    # Runtime generalization is reported per session; no pseudo-independent pooling of repetitions.
    timing_sessions=[s for s in report['sessions'] if s['stage']=='timing']
    if timing_sessions:
        for model in ['qwen','mistral']:
            observed={s['session'] for s in timing_sessions if s['model']==model}
            plan=json.loads(next(a.runs.glob('*/meta.json')).read_text())['plan']
            expected=set(range(plan['stages']['timing']['sessions']))
            check(observed==expected,'Incomplete formal timing sessions for '+model)
    csv_dump(a.out/'new_summaries.csv',summaries)
    dump(a.out/'paired_contrasts.json',paired)
    dump(a.out/'output_identity.json',identity_results)
    csv_dump(a.out/'trace_replay.csv',replayed)
    original_match=defaultdict(list)
    for r in all_records:
        if r['policy'] in {'uniform','uniform_trace'}:original_match[r['stage'],r['model']].append(r['original_uniform_ids_equal'])
    report['original_uniform_compatibility']=[dict(stage=k[0],model=k[1],n=len(v),exact_id_matches=sum(v)) for k,v in sorted(original_match.items())]
    if any(not all(v) for v in original_match.values()):
        report['warnings'].append('Some new Uniform trajectories differ from archived Uniform. Treat v8 as a separate implementation/runtime experiment; do not combine policy contrasts across versions.')
    report['warnings'] += ['All follow-up intervals are descriptive and unadjusted.',
       'Trace replay is counterfactual prefix analysis under verified shared-path assumptions, not measured latency.',
       'Per-session timing intervals do not establish a cross-hardware population effect.']
    report['passed']=not report['errors']
    dump(a.out/'analysis_status.json',report)
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
