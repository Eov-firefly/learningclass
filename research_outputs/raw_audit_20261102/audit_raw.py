"""Offline audit of the supplied raw bundle. Never loads weights or executes launchers."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments_v89'))
sys.path.insert(0, str(ROOT / 'controllability_v1'))
from janus_min.spec import jobs, load_public, digest
from janus_min.analyze import score as score_original
from historical_contracts_frozen import score as historical_score, allowed_choices
from analyze_control import score, paired_bounds, pair_summary


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path):
    data = path.read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('unfinished JSONL: ' + str(path))
    return [json.loads(line) for line in data.splitlines()]


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def csv_out(path, rows):
    if not rows:
        path.write_text(''); return
    with path.open('w', newline='') as stream:
        w = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        w.writeheader(); w.writerows(rows)


def distance_trace(paths, emitted, cap, forwards):
    """Independent path enumeration, not controller event/distance telemetry."""
    initial = min(map(len, paths)) <= cap
    first_dead = 0 if not initial else None
    escape = None
    for step in range(len(emitted) + 1):
        tails = [p[step:] for p in paths if len(p) >= step and p[:step] == emitted[:step]]
        if not tails:
            escape = step; break
        if min(map(len, tails)) > cap-step and first_dead is None:
            first_dead = step
    return dict(initially_feasible=int(initial), first_dead_step=first_dead,
        first_language_escape_step=escape, entered_dead_after_feasible=int(initial and first_dead is not None),
        calls_after_dead=max(0, forwards-first_dead) if first_dead is not None else 0)


def summarize(rows, keyfields):
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keyfields)].append(r)
    out = []
    for key, rs in sorted(groups.items()):
        feasible = [r for r in rs if r.get('initially_feasible') == 1]
        failed = [r for r in rs if not r['certified']]
        checked = [r for r in feasible if r.get('entered_dead_after_feasible') is not None]
        out.append(dict(**dict(zip(keyfields, key)), n=len(rs), certified=sum(r['certified'] for r in rs),
            correct=sum(r['correct'] for r in rs), wrong=sum(r['certified']-r['correct'] for r in rs),
            abstained=sum(r['status']=='ABSTAIN' for r in rs), initially_feasible=len(feasible),
            distance_checked_feasible=len(checked), dead_entries=sum(r['entered_dead_after_feasible'] for r in checked) if checked else None,
            post_dead_calls_feasible=sum(r['calls_after_dead'] for r in checked) if checked else None,
            initial_infeasible_forward_calls=sum(r['forward_calls'] for r in rs if r.get('initially_feasible')==0),
            failed_forward_calls=sum(r['forward_calls'] for r in failed),
            total_forward_calls=sum(r['forward_calls'] for r in rs),
            generated_tokens=sum(r['generated_tokens'] for r in rs), inserted_tokens=sum(r['inserted_tokens'] for r in rs),
            candidate_score_tokens=sum(r.get('candidate_score_tokens', 0) for r in rs),
            scoring_input_tokens=sum(r.get('scoring_input_tokens', 0) for r in rs),
            total_compile_ms=sum(r.get('compile_ms') or 0 for r in rs),
            mean_request_ms=sum(r['request_ms'] for r in rs)/len(rs),
            total_failed_ms=sum(r['request_ms'] for r in failed)))
    return out


def audit_single(base, out):
    plan = json.loads((base/'protocol/protocol.json').read_text())
    for name, expected in plan['files'].items():
        assert sha(base/'protocol'/name) == expected, ('frozen input', name)
    cases = {r['question_id']: r for r in read_rows(base/'protocol/public.jsonl')}
    gold = {r['question_id']: r['gold'] for r in read_rows(base/'protocol/scoring.jsonl')}
    languages = json.loads((base/'protocol/languages.json').read_text())
    expected = {}
    for model in ['qwen', 'mistral']:
        for case in cases.values():
            q = case['question_id']
            for condition, cap in languages[model][q]['budgets'].items():
                for policy in ['grammar','full','xgrammar','sequence_score','deterministic']:
                    j = dict(question_id=q, model=model, track='matched', encoding='option_text',
                        condition=condition, cap=cap, policy=policy, repeat=0, split='eval')
                    expected[digest(j)[:24]] = j
    rows, seen = [], set()
    checks = Counter()
    for file in sorted((base/'run/execute').glob('*.raw.jsonl')):
        for raw in read_rows(file):
            r = dict(raw); rid = r['request_id']
            assert rid in expected and rid not in seen, ('request identity', rid)
            seen.add(rid)
            assert all(r[k] == v for k,v in expected[rid].items())
            assert r['protocol_sha256'] == sha(base/'protocol/protocol.json')
            assert r['code_sha256'] == plan['source_sha256']
            case=cases[r['question_id']]; lang=languages[r['model']][r['question_id']]
            assert r['provided_prefix_ids']==lang['prefix_ids'] and r['language_sha256']==digest(lang['texts'])
            assert r['effective_cap']==r['cap'] and r['compiled_minimum_tokens']==min(map(len,lang['paths']))
            assert r['returned_ids']==lang['prefix_ids']+r['generated_ids']+r['inserted_ids']
            assert r['generated_tokens']==len(r['generated_ids']) and r['inserted_tokens']==len(r['inserted_ids'])
            checks['errors']+=bool(r.get('error'))
            checks['overruns']+=r['generated_tokens']+r['inserted_tokens']>r['cap']
            r.update(score(r,case,gold[r['question_id']]))
            checks['invalid_submissions']+=r['invalid_submission']
            # Candidate order is verified against the canonical artifacts, not assumed from gold.
            from janus_min.spec import artifacts
            assert artifacts(case,'option_text')==lang['texts']
            text_label=next((label for label,value in lang['texts'].items()
                             if value.rstrip()==r['returned_text'].rstrip()),None)
            r['consumer_text_valid']=int(text_label is not None)
            r['consumer_text_correct']=int(text_label is not None and text_label==gold[r['question_id']])
            r['exact_literal_valid']=int(r['returned_text'] in lang['texts'].values())
            ref_index=list(case['options']).index(gold[r['question_id']])
            r['gold_suffix_tokens']=len(lang['paths'][ref_index])
            r['gold_reachable']=int(r['gold_suffix_tokens']<=r['cap'])
            r['initially_feasible']=int(min(map(len,lang['paths']))<=r['cap'])
            if r['policy']!='xgrammar' and r['certified']:
                suffix=r['generated_ids']+r['inserted_ids']
                matches=[text for text,path in zip(lang['texts'].values(),lang['paths']) if path==suffix]
                assert r['returned_text'] in matches
            if r['policy'] in {'full','grammar'}:
                r.update(distance_trace(lang['paths'],r['generated_ids'],r['cap'],r['forward_calls']))
                checks['prefix_escapes']+=r['first_language_escape_step'] is not None
                if r['policy']=='full':checks['full_dead_entries']+=r['entered_dead_after_feasible']
            rows.append(r)
    assert seen==set(expected)
    checks['expected_records']=len(expected);checks['actual_records']=len(rows)
    csv_out(out/'single_all_baselines.csv',summarize(rows,['model','condition','policy']))
    csv_out(out/'reference_reachability.csv',summarize(rows,['model','condition','policy','gold_reachable']))
    pairs=[];rescues=[];contrasts=[]
    for model in ['qwen','mistral']:
        for condition in ['fixed8','exact_min','wide']:
            cell=[r for r in rows if r['model']==model and r['condition']==condition]
            f={r['question_id']:r for r in cell if r['policy']=='full'}
            g={r['question_id']:r for r in cell if r['policy']=='grammar'}
            pair=pair_summary(f,g)
            feasible=[q for q in f if f[q]['initially_feasible']]
            wins=sum(f[q]['certified'] and not g[q]['certified'] for q in feasible)
            losses=sum(g[q]['certified'] and not f[q]['certified'] for q in feasible)
            lo,hi=paired_bounds(wins,losses,len(feasible),.025 if condition=='fixed8' else .05)
            pair.update(model=model,condition=condition,feasible_adjusted_ci_low=lo,feasible_adjusted_ci_high=hi)
            pairs.append(pair)
            assert pair['lost_certified']==pair['lost_correct']==0
            assert pair['same_token_records']==pair['grammar_certified']
            for q in f:
                if f[q]['certified'] and not g[q]['certified']:
                    rescues.append(dict(model=model,condition=condition,question_id=q,
                        gold=gold[q],gold_tokens=f[q]['gold_suffix_tokens'],cap=f[q]['cap'],gold_reachable=f[q]['gold_reachable'],
                        newly_correct=f[q]['correct'],grammar_first_dead=g[q]['first_dead_step'],
                        grammar_calls_after_dead=g[q]['calls_after_dead'],full_request_id=f[q]['request_id'],
                        grammar_request_id=g[q]['request_id'],full_text=f[q]['returned_text'].strip()))
            for policy in ['grammar','sequence_score','deterministic','xgrammar']:
                b={r['question_id']:r for r in cell if r['policy']==policy}
                w=sum(f[q]['correct']>b[q]['correct'] for q in f);l=sum(f[q]['correct']<b[q]['correct'] for q in f)
                ci=paired_bounds(w,l,len(f))
                contrasts.append(dict(model=model,condition=condition,baseline=policy,n=len(f),correct_wins=w,
                    correct_losses=l,difference=(w-l)/len(f),descriptive_95_low=ci[0],descriptive_95_high=ci[1]))
    csv_out(out/'trajectory_transitions.csv',pairs);csv_out(out/'rescued_cases.csv',rescues)
    csv_out(out/'paired_correctness.csv',contrasts)
    terminal=[]
    for model in ['qwen','mistral']:
        for condition in ['fixed8','exact_min','wide']:
            for policy in ['full','grammar','xgrammar','sequence_score','deterministic']:
                rs=[r for r in rows if r['model']==model and r['condition']==condition and r['policy']==policy]
                terminal.append(dict(model=model,condition=condition,policy=policy,n=len(rs),
                    controller_certified=sum(r['certified'] for r in rs),controller_correct=sum(r['correct'] for r in rs),
                    consumer_text_valid=sum(r['consumer_text_valid'] for r in rs),
                    consumer_text_correct=sum(r['consumer_text_correct'] for r in rs),
                    exact_literal_valid=sum(r['exact_literal_valid'] for r in rs),
                    valid_but_uncommitted=sum(r['consumer_text_valid'] and not r['certified'] for r in rs),
                    note='Offline endpoint sensitivity only; original statuses and primary results are unchanged.'))
    csv_out(out/'terminal_policy_sensitivity.csv',terminal)
    with (out/'single_scored.jsonl').open('w') as stream:
        for r in rows:stream.write(json.dumps(r,ensure_ascii=False)+'\n')
    dump(out/'single_checks.json',dict(checks))
    return rows


def audit_double(base,out,single):
    cases={r['question_id']:r for r in load_public('eval')}
    gold={r['question_id']:r['gold'] for r in read_rows(ROOT/'experiments_v89/data/scoring.jsonl')}
    expected={j['request_id']:j for m in ['qwen','mistral'] for j in jobs(m)}
    rows=[];seen=set();checks=Counter()
    for file in sorted((base/'run/aggregate').glob('*.raw.jsonl')):
        for r in read_rows(file):
            rid=r['request_id'];assert rid in expected and rid not in seen
            assert all(r[k]==v for k,v in expected[rid].items());seen.add(rid)
            r.update(score_original(r,cases[r['question_id']],gold[r['question_id']]))
            checks['errors']+=bool(r.get('error'));checks['overruns']+=r['budget_overrun']
            checks['invalid_constrained_commits']+=r['status']=='COMMIT' and not r['certified']
            r['initially_feasible']=int(r.get('compiled_minimum_tokens',10**9)<=r['effective_cap'])
            rows.append(r)
    assert seen==set(expected)
    checks['actual_records']=len(rows);checks['expected_records']=len(expected)
    matched=[r for r in rows if r['track']=='matched']
    csv_out(out/'double_matched_baselines.csv',summarize(matched,['model','encoding','cap','policy']))
    pairs=[]
    for model in ['qwen','mistral']:
        for encoding in ['label','option_text']:
            for cap in [8,24,64]:
                cell=[r for r in matched if r['model']==model and r['encoding']==encoding and r['cap']==cap]
                f={r['question_id']:r for r in cell if r['policy']=='full'}
                g={r['question_id']:r for r in cell if r['policy']=='grammar'}
                pair=pair_summary(f,g);pair.update(model=model,encoding=encoding,cap=cap);pairs.append(pair)
                assert pair['lost_certified']==pair['lost_correct']==0
                assert pair['same_token_records']==pair['grammar_certified']
    csv_out(out/'double_trajectory_transitions.csv',pairs)
    old={(r['model'],r['question_id'],r['policy']):r for r in matched if r['encoding']=='option_text' and r['cap']==8}
    comparison=[]
    for model in ['qwen','mistral']:
        for policy in ['full','grammar','deterministic','xgrammar']:
            new=[r for r in single if r['model']==model and r['policy']==policy and r['condition']=='fixed8']
            comparison.append(dict(model=model,policy=policy,n=len(new),
                same_returned_ids=sum(r['returned_ids']==old[model,r['question_id'],policy]['returned_ids'] for r in new),
                same_correct=sum(r['correct']==old[model,r['question_id'],policy]['correct'] for r in new)))
    csv_out(out/'known_cohort_run_overlap.csv',comparison)
    dump(out/'double_checks.json',dict(checks))
    return rows


def audit_provenance(bundle, out):
    single=bundle/'01_单卡补充实验_20261030/已核验完整内容'
    double_zip=bundle/'02_双卡实验_v8.9.1_20261028/原始完整备份.zip'
    with zipfile.ZipFile(double_zip) as z:
        double_manifest=json.loads(z.read('model_manifest.json'))
        single_models=json.loads((single/'protocol/models.json').read_text())
        model_checks={}
        for model in ['qwen','mistral']:
            one=single_models[model]['manifest'];two=double_manifest[model]
            assert one['spec']==two['spec'] and one['files']==two['files']
            model_checks[model]=dict(spec=one['spec'],matching_file_entries=len(one['files']),
                weight_entries_with_sha256=sum(n.endswith('.safetensors') and 'sha256' in v for n,v in one['files'].items()))
        sources={}
        for name in z.namelist():
            if name.startswith('frozen/') and name.endswith('.py') and not Path(name).name.startswith('._'):
                relative=Path(name).relative_to('frozen')
                assert z.read(name)==(ROOT/'experiments_v89'/relative).read_bytes()
                sources[str(relative)]=hashlib.sha256(z.read(name)).hexdigest()
        for f in (bundle/'02_双卡实验_v8.9.1_20261028/直接读取/run/aggregate').glob('*.raw.jsonl'):
            assert f.read_bytes()==z.read('run/aggregate/'+f.name)
            shard=f.stem.split('.')[1]
            assert f.read_bytes()==z.read(f'run/waves/wave{shard[-1]}/'+f.name)
        timing=defaultdict(list)
        for f in (bundle/'02_双卡实验_v8.9.1_20261028/直接读取/run/aggregate').glob('*.raw.jsonl'):
            for r in read_rows(f):
                if r['track']=='timing':timing[(r['shard'],r['model'],r['policy'])].append(r)
        csv_out(out/'two_wave_timing.csv',[dict(wave=w,model=m,policy=p,n=len(rs),
            n_questions=len({r['question_id'] for r in rs}),mean_request_ms=sum(r['request_ms'] for r in rs)/len(rs))
            for (w,m,p),rs in sorted(timing.items())])
    with zipfile.ZipFile(bundle/'01_单卡补充实验_20261030/archive.zip') as z:
        for f in (single/'run/execute').glob('*.raw.jsonl'):
            assert f.read_bytes()==z.read('run/execute/'+f.name)
    dump(out/'provenance_checks.json',dict(recorded_model_manifest_matches=model_checks,
        original_source_python_files_matched=len(sources),aggregate_wave_raw_byte_equality=True,
        single_raw_archive_byte_equality=True,
        note='Recorded hashes are compared; absent weights are not reread. No infrastructure/closeout script is executed.'))


def audit_history(bundle,out):
    historical_archive=bundle/'03_三卡计时_v8.3_20261023/原始完整备份.tar.gz'
    provenance=json.loads((Path(__file__).parent/'historical_contract_source.json').read_text())
    with tarfile.open(historical_archive) as archive:
        archived=archive.extractfile(provenance['archive_member']).read()
    assert hashlib.sha256(archived).hexdigest()==provenance['original_sha256']
    assert archived.split(b'\n\nclass EntropyGate:')[0].rstrip()+b'\n'==(Path(__file__).parent/'historical_contracts_frozen.py').read_bytes()
    timing=bundle/'03_三卡计时_v8.3_20261023/直接读取/runs'
    counts=Counter();mismatch=Counter();summary=defaultdict(list);identity=defaultdict(dict)
    for file in sorted(timing.rglob('*.jsonl')):
        for r in read_rows(file):
            warm=file.name=='warmups.jsonl';counts['warmups' if warm else r['stage']]+=1
            if warm:continue
            for contract,stored in r['scores'].items():
                actual=historical_score(r['text'],r['kind'],r['gold'],r['choices'],r['returned_eos'],contract)
                mismatch[contract]+=actual!=stored
            key=(r['stage'],r['model'],r['task'],r['session'],r['policy'])
            summary[key].append(r)
            pair=(r['stage'],r['model'],r['question_id'],r['session'],r['repeat'])
            assert r['policy'] not in identity[pair]
            identity[pair][r['policy']]=r
    reports=[]
    for key,rs in sorted(summary.items()):
        reports.append(dict(zip(['stage','model','task','session','policy'],key),n=len(rs),
            n_questions=len({r['question_id'] for r in rs}),correct=sum(r['scores']['strict']['correct'] for r in rs),
            valid=sum(r['scores']['strict']['valid'] for r in rs),
            mean_end_to_end_seconds=sum(r['end_to_end_seconds'] for r in rs)/len(rs)))
    csv_out(out/'historical_three_gpu_summary.csv',reports)
    main=bundle/'04_原始主实验_v5.1_20261021/直接读取/revision_v5_1'
    old_counts=Counter();old_mismatch=0;cells=defaultdict(dict)
    for file in sorted(main.glob('*.jsonl')):
        for r in read_rows(file):
            old_counts[r['stage']]+=1
            if r['stage']!='main':continue
            choices=allowed_choices(r['prompt']) if r['kind']=='choice' else 'ABCDE'
            actual=historical_score(r['text'],r['kind'],r['gold'],choices,r['stop_reason']=='eos','strict')
            old_mismatch+=bool(actual['valid'])!=bool(r['valid']) or bool(actual['correct'])!=bool(r['correct'])
            key=(r['model'],r['task'],r['question_id'])
            cells[key][r['policy']]=dict(r,**actual)
    historical=defaultdict(Counter)
    for (model,task,q),pair in cells.items():
        u,c=pair['uniform'],pair['complete'];entry=historical[(model,task)]
        entry['n']+=1;entry['repairs']+=not u['valid'] and c['valid']
        entry['correct_repairs']+=not u['valid'] and c['valid'] and c['correct']
        entry['wrong_repairs']+=not u['valid'] and c['valid'] and not c['correct']
        entry['validity_losses']+=u['valid'] and not c['valid']
    csv_out(out/'historical_main_repairs.csv',[dict(model=m,task=t,**c) for (m,t),c in sorted(historical.items())])
    dump(out/'historical_checks.json',dict(three_gpu_counts=dict(counts),three_gpu_score_mismatches=dict(mismatch),
        old_counts=dict(old_counts),old_main_score_mismatches=old_mismatch,
        note='Historical scoring/counts recomputed. Timing means kept per session; no cross-hardware pooling or new timing-interval claim.'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();bundle=a.bundle.resolve();a.out=a.out.resolve()
    if a.out.exists() and any(a.out.iterdir()):raise ValueError('use a new empty output directory')
    a.out.mkdir(parents=True,exist_ok=True)
    verified=0
    for line in (bundle/'SHA256SUMS.txt').read_text().splitlines():
        expected,name=line.split('  ',1);path=(bundle/name).resolve()
        assert path.is_relative_to(bundle) and sha(path)==expected, ('bundle hash',name)
        verified+=1
    single=bundle/'01_单卡补充实验_20261030/已核验完整内容'
    source_differences=[]
    for file in (single/'source').rglob('*.py'):
        local=ROOT/file.relative_to(single/'source')
        if not local.exists() or sha(local)!=sha(file):source_differences.append(str(file.relative_to(single/'source')))
    assert not source_differences
    # The direct-read tree is intentionally used once, not aggregate plus per-wave copies.
    double=bundle/'02_双卡实验_v8.9.1_20261028/直接读取'
    one=audit_single(single,a.out);two=audit_double(double,a.out,one);audit_history(bundle,a.out);audit_provenance(bundle,a.out)
    archive_hashes={name:sha(bundle/name) for name in [
        '01_单卡补充实验_20261030/archive.zip','02_双卡实验_v8.9.1_20261028/原始完整备份.zip']}
    report=dict(bundle_files_hash_verified=verified,archive_hashes=archive_hashes,source_py_differences=source_differences,
        single_records=len(one),double_records=len(two),new_gpu_inference=False,
        consumer_valid_but_uncommitted_records=sum(r['consumer_text_valid'] and not r['certified'] for r in one),
        substantive_cautions=['terminal-policy sensitivity','most fixed8 rescues have over-budget canonical reference paths',
            'known-cohort reuse','no demonstrated quality advantage over candidate scoring','priority comparison incomplete'],
        distance_scope='Exact enumeration of frozen single-study canonical paths, not a newly loaded tokenizer or all XGrammar tokenizations.',
        provenance_scope='Archive/file hashes and recorded model manifests checked; model weights absent, no independent bitwise weight reread.',
        inference_scope='Known cohort; no independent new evaluation, no priority claim.')
    dump(a.out/'audit_scope.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
