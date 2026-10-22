"""Independent, read-only audit of the supplied output archive."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from .contracts import allowed_choices, score, wrapper_balanced
from .stats import paired_binary, paired_bootstrap

POLICIES = {'uniform', 'marker', 'legacy_entropy', 'complete', 'entropy_observe', 'entropy_complete'}


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def csv_dump(path, rows):
    if not rows:
        Path(path).write_text('')
        return
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--export-cases', type=Path)
    ap.add_argument('--source-commit', help='Optional verified repository commit for provenance; never inferred from directory names')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    root = a.archive_root.resolve()
    report = {'scope': 'Independent file, record, parser, aggregate and paired-output checks; no GPU rerun',
              'errors': [], 'warnings': []}
    def check(condition, message):
        if not condition:
            report['errors'].append(message)
    count = 0
    for line in (root/'SHA256SUMS').read_text().splitlines():
        digest, rel = line.split('  ', 1)
        f = (root/rel).resolve()
        if not f.is_relative_to(root):
            raise ValueError('Checksum path escapes archive')
        check(f.exists() and hashlib.sha256(f.read_bytes()).hexdigest() == digest, 'checksum: '+rel)
        count += 1
    report['checksum_entries'] = count
    files = sorted((root/'results/revision_v5_1').glob('*.jsonl'))
    protocol=json.loads((root/'protocol/protocol.json').read_text())
    input_manifest=json.loads((root/'protocol/input_manifest.json').read_text())
    check(len(files) == 8, 'Expected exactly 8 scored JSONL files')
    records, groups, unique, jobs = [], defaultdict(list), set(), set()
    parser_mismatches = []
    expected = {'pilot': 480, 'dev': 6000, 'main': 14400, 'timing': 4320}
    for f in files:
        metadata = json.loads(f.with_suffix('.meta.json').read_text())
        check(metadata['spec']==protocol,'Metadata protocol differs: '+f.name)
        # Stored fingerprint hashes canonical sorted JSON, not the pretty-printed file bytes.
        canonical_manifest=json.dumps(input_manifest,sort_keys=True,ensure_ascii=False)
        check(metadata['input_manifest_hash']==hashlib.sha256(canonical_manifest.encode()).hexdigest(),'Canonical input manifest fingerprint: '+f.name)
        file_rows = 0
        with f.open() as h:
            for line in h:
                r = json.loads(line)
                file_rows += 1
                check(r['fingerprint'] == metadata['fingerprint'], 'fingerprint: '+r['job_id'])
                check(r['stage']==metadata['stage'] and r['model']==metadata['model'],'Wrong stage/model: '+r['job_id'])
                check(r['environment_fingerprint'] == metadata['environment_fingerprint'], 'environment: '+r['job_id'])
                key = (r['model'], r['stage'], r['task'], r['question_id'], r['policy'], r['threshold'], r['repeat'])
                check(key not in unique, 'duplicate call: '+str(key))
                unique.add(key)
                check(r['job_id'] not in jobs, 'duplicate job: '+r['job_id'])
                jobs.add(r['job_id'])
                check(len(r['output_ids']) == r['tokens'] <= r['effective_cap'] == 512, 'token count/cap: '+r['job_id'])
                check(all(isinstance(x, int) and x >= 0 for x in r['output_ids']), 'invalid token IDs')
                check(r['stop_reason'] in {'eos', 'cap', 'policy'}, 'unknown stop reason')
                check(all(math.isfinite(r[k]) and r[k] >= 0 for k in ['generation_seconds','end_to_end_seconds']), 'invalid time')
                check(r['end_to_end_seconds'] >= r['generation_seconds'], 'end-to-end below generation')
                choices = allowed_choices(r['prompt']) if r['kind'] == 'choice' else ''
                s = score(r['text'], r['kind'], r['gold'], choices, r['stop_reason']=='eos')
                if (s['valid'], s['correct']) != (r['valid'], r['correct']):
                    parser_mismatches.append({'job_id':r['job_id'], 'stored': [r['valid'],r['correct']], 'recomputed':s})
                r['_choices'] = choices
                records.append(r)
                groups[(r['stage'],r['model'],r['task'],r['question_id'])].append(r)
        check(file_rows == metadata['expected_shard_jobs'], 'file count: '+f.name)
    report['stage_counts'] = dict(Counter(r['stage'] for r in records))
    check(report['stage_counts'] == expected, 'stage counts differ')
    report['strict_parser_mismatch_count'] = len(parser_mismatches)
    check(not parser_mismatches, 'Independent strict parser differs from stored scores; inspect parser_mismatches.json')
    dump(a.out/'parser_mismatches.json', parser_mismatches)
    sets = defaultdict(set)
    for (stage, model, task, qid), rows in groups.items():
        sets[stage,model,task].add(qid)
        check(len({r['prompt'] for r in rows}) == 1 and len({r['gold'] for r in rows}) == 1, 'unmatched prompt/gold: '+qid)
        if stage == 'dev':
            counts = Counter(r['policy'] for r in rows)
            check(counts == {'uniform':1,'complete':1,'entropy_complete':3}, 'incomplete dev grid: '+qid)
            check({r['threshold'] for r in rows if r['policy']=='entropy_complete'} == {0.005,0.01,0.05}, 'dev thresholds')
        else:
            check(set(r['policy'] for r in rows) == POLICIES, 'policy grid: '+qid)
            repeats = 3 if stage == 'timing' else 1
            check(Counter(r['policy'] for r in rows) == {p:repeats for p in POLICIES}, 'repeat grid: '+qid)
            for policy in POLICIES:
                check({r['repeat'] for r in rows if r['policy']==policy} == set(range(repeats)), 'repeat IDs: '+qid)
    for model in ['qwen','mistral']:
        for task in ['gsm8k','arc']:
            for stage,n in [('dev',300),('pilot',20),('main',600),('timing',60)]:
                check(len(sets[stage,model,task]) == n, 'question count: '+str((stage,model,task)))
            check(not sets['dev',model,task] & sets['main',model,task], 'dev/test overlap')
            check(sets['pilot',model,task] <= sets['dev',model,task], 'pilot not nested')
            check(sets['timing',model,task] <= sets['main',model,task], 'timing not nested')
            check(sets['main',model,task] == sets['main','qwen',task], 'model cohort mismatch')
    report['question_grids_verified'] = len(groups)
    for model in ['qwen','mistral']:
        excluded=set(input_manifest['historical_exposure']['gsm8k']['excluded_test_ids'])
        check(not sets['main',model,'gsm8k'] & excluded,'Historical exposure manifest/main overlap')
    exitcodes=list((root/'operations').glob('*.exitcode'))
    check(all(f.read_text().strip()=='0' for f in exitcodes),'Nonzero or malformed archived operation exit code')
    report['archived_exitcode_files']=len(exitcodes)
    question_identity={}
    question_texts=defaultdict(set)
    for r in records:
        identity=(r['question'].strip(),r['gold'],r['kind'])
        previous=question_identity.setdefault(r['question_id'],identity)
        check(previous==identity,'Question/gold identity mismatch across stages/models')
        question_texts[r['stage'],r['model'],r['task']].add(r['question'].strip())
    for model in ['qwen','mistral']:
        for task in ['gsm8k','arc']:
            check(not question_texts['main',model,task] & question_texts['dev',model,task], 'Text-level dev/main overlap')
            check(len(question_texts['main',model,task])==600,'Duplicate main question text')
    mechanisms = Counter()
    pairs, changed, sensitivity = [], [], []
    main_rows = [r for r in records if r['stage']=='main']
    for key, rows in groups.items():
        if key[0] not in {'main','timing','pilot'}:
            continue
        for rep in range(3 if key[0]=='timing' else 1):
            by = {r['policy']:r for r in rows if r['repeat']==rep}
            u,c,s,e = [by[x] for x in ['uniform','complete','entropy_observe','entropy_complete']]
            for p,r in by.items():
                check(r['output_ids'] == u['output_ids'][:r['tokens']], 'not Uniform prefix: '+r['job_id'])
            check(c['output_ids'] == s['output_ids'], 'Shadow identity: '+c['job_id'])
            check(c['tokens'] <= e['tokens'], 'Conjunction ordering')
            mechanisms[key[0]+'_pairs'] += 1
            mechanisms[key[0]+'_E_equals_U'] += e['output_ids'] == u['output_ids']
            if key[0]=='main' and c['correct'] != u['correct']:
                suffix = u['text'][len(c['text']):] if u['text'].startswith(c['text']) else None
                changed.append({'model':c['model'],'task':c['task'],'question_id':c['question_id'],
                    'win':c['correct'],'gold':c['gold'],'uniform_prediction':u['prediction'],
                    'complete_prediction':c['prediction'],'uniform_valid':u['valid'],
                    'complete_wrapper_balanced':wrapper_balanced(c['text']),
                    'text_prefix':suffix is not None, 'continuation':suffix,
                    'complete_text':c['text'],'uniform_text':u['text'],
                    'classification':'machine-extracted pair; human categorization pending'})
    report['mechanisms'] = dict(mechanisms)
    report['main_discordant_pairs'] = len(changed)
    dump(a.out/'discordant_pairs.json', changed)
    # Reconstruct aggregate means against supplied summaries without trusting stored scores blindly.
    aggregate_checks = 0
    by_group = defaultdict(list)
    for r in records:
        by_group[r['stage'],r['model'],r['task'],r['policy']].append(r)
    for stage in ['main','timing']:
        saved = json.loads((root/f'results/revision_v5_1/{stage}-analysis.json').read_text())
        for row in saved['summary']:
            rs = by_group[stage,row['model'],row['task'],row['policy']]
            for k,field in [('accuracy','correct'),('valid_rate','valid'),('legacy_accuracy','legacy_correct'),
                            ('mean_tokens','tokens'),('end_to_end_mean_s','end_to_end_seconds')]:
                check(math.isclose(mean(r[field] for r in rs),row[k],rel_tol=1e-12,abs_tol=1e-12), 'summary mismatch '+stage+':'+k)
                aggregate_checks += 1
        for row in saved['paired']:
            model,task,p,control,metric = [row[k] for k in ['model','task','policy','control','metric']]
            pmap,cmap = defaultdict(list),defaultdict(list)
            for r in by_group[stage,model,task,p]:pmap[r['question_id']].append(r[metric])
            for r in by_group[stage,model,task,control]:cmap[r['question_id']].append(r[metric])
            ids = sorted(pmap)
            check(set(ids)==set(cmap),'paired identity mismatch')
            d = [mean(pmap[q])-mean(cmap[q]) for q in ids]
            check(math.isclose(mean(d),row['mean'],rel_tol=1e-12,abs_tol=1e-12), 'paired mean mismatch '+str((stage,model,task,p,metric)))
    report['aggregate_scalar_checks'] = aggregate_checks
    contracts = ['strict','closure_tolerant','closure_balanced','wrapper_balanced_strict','last_marked']
    for model in ['qwen','mistral']:
        for task in ['gsm8k','arc']:
            for contract in contracts:
                computed = {}
                for policy in sorted(POLICIES):
                    rs = sorted(by_group['main',model,task,policy],key=lambda r:r['question_id'])
                    sc = [score(r['text'],r['kind'],r['gold'],r['_choices'],r['stop_reason']=='eos',contract) for r in rs]
                    computed[policy] = sc
                    sensitivity.append(dict(model=model,task=task,policy=policy,contract=contract,n=len(rs),
                        accuracy=mean(s['correct'] for s in sc),valid_rate=mean(s['valid'] for s in sc)))
                ci=paired_binary([s['correct'] for s in computed['complete']], [s['correct'] for s in computed['uniform']],
                                  alpha=0.0125 if contract=='strict' else 0.05)
                pairs.append(dict(model=model,task=task,contract=contract,**ci,
                                  status='original-primary-family' if contract=='strict' else 'retrospective-unadjusted'))
    csv_dump(a.out/'contract_sensitivity.csv',sensitivity)
    dump(a.out/'contract_paired.json',pairs)
    timing=[]
    for model in ['qwen','mistral']:
        for task in ['gsm8k','arc']:
            for p,control in [('entropy_observe','complete'),('complete','uniform'),('legacy_entropy','uniform')]:
                qm={}
                for policy in [p,control]:
                    qr=defaultdict(list)
                    for r in by_group['timing',model,task,policy]:qr[r['question_id']].append(r['end_to_end_seconds'])
                    qm[policy]={q:mean(v) for q,v in qr.items()}
                ids=sorted(qm[p]); d=[qm[p][q]-qm[control][q] for q in ids]
                timing.append(dict(model=model,task=task,policy=p,control=control,
                    reference_mean_seconds=mean(qm[control].values()),**paired_bootstrap(d)))
    dump(a.out/'timing_question_bootstrap.json',timing)
    if a.export_cases:
        a.export_cases.mkdir(parents=True,exist_ok=True)
        for model in ['qwen','mistral']:
            cases=[]
            for r in sorted(records,key=lambda r:(r['stage'],r['task'],r['question_id'])):
                if r['model']!=model or r['policy']!='uniform' or r['stage'] not in {'main','dev'}:
                    continue
                cases.append({k:r[k] for k in ['model','task','kind','question_id','question','prompt','gold','prompt_tokens','stage']} |
                    {'choices':r['_choices'],'original_output_ids':r['output_ids'],
                     'original_text':r['text'],'original_correct':r['correct'],
                     'timing_member':r['question_id'] in sets['timing',model,r['task']]})
            with (a.export_cases/f'{model}.jsonl').open('w') as h:
                for case in cases:h.write(json.dumps(case,ensure_ascii=False)+'\n')
        (a.export_cases/'protocol.json').write_bytes((root/'protocol/protocol.json').read_bytes())
        dump(a.export_cases/'manifest.json',{'source_commit':a.source_commit,'source':'JANUS_experiment_outputs_20261022.zip',
             'source_checksums_sha256':hashlib.sha256((root/'SHA256SUMS').read_bytes()).hexdigest(),
             'scope':'Reconstructed serialized prompts and baseline records, NOT original input manifests',
             'files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.export_cases.glob('*')) if f.name!='manifest.json'}})
    report['warnings'] += ['Original runnable sources and original prepared input files absent.',
        'No token-level entropy traces; exact historical entropy implementation cannot be certified.',
        'New alternate contracts are retrospective diagnostics; wrapper checks are limited heuristics, not semantic validation.',
        'Continuous bootstrap uses declared ordering/RNG; finite-Monte-Carlo endpoints are independent estimates, not claimed byte-identical to archived endpoints.']
    report['passed'] = not report['errors']
    dump(a.out/'audit_report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__ == '__main__':main()
