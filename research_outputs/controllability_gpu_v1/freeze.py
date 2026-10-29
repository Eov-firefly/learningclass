"""Freeze examples, tokenizer paths and budgets BEFORE any formal model outputs."""
import argparse
import json
from pathlib import Path
from common import (ROOT, ENGINE, MODEL_SPECS, compile_case, digest, sha, read_jsonl,
                    atomic, validate_public, fingerprint, source_hash, jobs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--public', type=Path, default=ENGINE / 'data/public.jsonl')
    p.add_argument('--scoring', type=Path, default=ENGINE / 'data/scoring.jsonl')
    p.add_argument('--model-manifest', type=Path, required=True)
    p.add_argument('--exclude-public', type=Path, action='append', default=[])
    p.add_argument('--source-description', required=True)
    p.add_argument('--n', type=int, default=64)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.n <= 0:
        raise ValueError('n must be positive')
    if a.out.exists() and any(a.out.iterdir()):
        raise ValueError('use a new empty protocol directory')
    rows = read_jsonl(a.public); validate_public(rows)
    exclusions = [r for f in a.exclude_public for r in read_jsonl(f)]
    excluded_ids = {r['question_id'] for r in exclusions}
    excluded_text = {fingerprint(r) for r in exclusions}
    eligible = [r for r in rows if r['split'] == 'eval' and
                r['question_id'] not in excluded_ids and fingerprint(r) not in excluded_text]
    eligible.sort(key=lambda r: digest({'seed': 'janus-control-20261029', 'qid': r['question_id']}))
    if len(eligible) < a.n:
        raise ValueError('not enough eligible examples after exclusions')
    selected = eligible[:a.n]
    gold_rows = read_jsonl(a.scoring)
    if len({r['question_id'] for r in gold_rows}) != len(gold_rows):
        raise ValueError('duplicate scoring IDs')
    gold = {r['question_id']: r['gold'] for r in gold_rows}
    if any(gold.get(r['question_id']) not in r['options'] for r in selected):
        raise ValueError('missing or invalid gold labels (only used offline)')
    known = read_jsonl(ENGINE / 'data/public.jsonl')
    known_ids = {r['question_id'] for r in known}; known_text = {fingerprint(r) for r in known}
    overlap = sum(r['question_id'] in known_ids or fingerprint(r) in known_text for r in selected)
    model_manifest = json.loads(a.model_manifest.read_text())
    from transformers import AutoTokenizer
    languages, models = {}, {}
    for model, spec in MODEL_SPECS.items():
        item = model_manifest[model]
        if item['spec'] != spec:
            raise ValueError('model manifest differs from pinned model specification')
        location = Path(item['local_path']).resolve()
        tokenizer = AutoTokenizer.from_pretrained(location, local_files_only=True, trust_remote_code=False)
        languages[model] = {}
        for case in selected:
            lang = compile_case(tokenizer, case, 'option_text')
            minimum, maximum = min(map(len, lang['paths'])), max(map(len, lang['paths']))
            languages[model][case['question_id']] = dict(
                **lang, budgets={'fixed8': 8, 'exact_min': minimum, 'wide': maximum})
        models[model] = dict(spec=spec, local_path=str(location),
                             manifest=item, provenance='manifest claimed revision; verify weight hashes separately')
    a.out.mkdir(parents=True, exist_ok=True)
    for name, data in [('public.jsonl', selected), ('scoring.jsonl',
            [dict(question_id=r['question_id'], gold=gold[r['question_id']]) for r in selected])]:
        (a.out / name).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in data))
    atomic(a.out / 'languages.json', languages); atomic(a.out / 'models.json', models)
    count = sum(len(jobs(selected, languages, model)) for model in MODEL_SPECS)
    plan = dict(version='control-gpu-1', date='2026-10-29', n=a.n, source_description=a.source_description,
        source_inputs={str(a.public.resolve()): sha(a.public), str(a.scoring.resolve()): sha(a.scoring),
                       str(a.model_manifest.resolve()): sha(a.model_manifest)},
        exclusions={str(f.resolve()): sha(f) for f in a.exclude_public},
        overlap_with_known_112=overlap,
        evidence_label='exploratory_known_cohort' if overlap else 'prospective_external_cohort_unverified_prior_exposure',
        exposure_warning='Zero overlap with these 112 is NOT proof of no overlap with all historical data or model training.',
        sampling='smallest SHA256(seed,qid); eval split only; gold does not affect selection/budgets',
        primary='Full minus grammar certified completion on initially feasible fixed8 requests, separately by model',
        secondary='all-request correct/certified/wrong; dead-end entry; failed computation; conditional trajectory preservation',
        intervals='conservative paired 97.5% per model primary cell (Bonferroni for two cells); other intervals descriptive',
        budget_scope='new suffix tokens, supplied prefix excluded, deterministic insertion counted separately',
        conditions={'fixed8': 'global cap8; selected using previous pilot, not a new discovery',
                    'exact_min': 'per-case/model minimum canonical suffix length',
                    'wide': 'per-case/model maximum canonical suffix length'},
        controls='exact_min/wide are mechanism stress controls, not deployment budget distributions',
        total_records=count, neural_request_upper_bound=count * 4 // 5,
        deterministic_records=count // 5,
        sample_size_warning='64 is a cost plan, not proof of power or noninferiority; publish uncertainty and failures',
        source_sha256=source_hash(),
        files={n: sha(a.out / n) for n in ['public.jsonl', 'scoring.jsonl', 'languages.json', 'models.json']})
    atomic(a.out / 'protocol.json', plan)
    print(json.dumps({k: plan[k] for k in ['n', 'evidence_label', 'overlap_with_known_112',
                                         'total_records', 'neural_request_upper_bound']}, indent=2))


if __name__ == '__main__':
    main()
