"""CPU-only scoring against the pre-inference frozen token language."""
import argparse
import json
from pathlib import Path
import sys
from collections import defaultdict
from common import ROOT, MODEL_SPECS, POLICIES, CONDITIONS, digest, sha, read_jsonl, atomic, load_protocol, jobs
sys.path.insert(0, str(ROOT.parent / 'controllability_v1'))
from analyze_control import score, path_diagnostics, pair_summary, paired_bounds, write_csv


def evaluate(raw, expected, public, languages, gold, protocol_hash):
    expected = {r['request_id']: r for r in expected}
    cases = {r['question_id']: r for r in public}
    seen, rows = set(), []
    issues = defaultdict(int)
    for r in raw:
        rid = r['request_id']
        if rid in seen:
            raise ValueError('duplicate request_id: ' + rid)
        seen.add(rid)
        if rid not in expected or any(r.get(k) != v for k, v in expected[rid].items()):
            raise ValueError('unexpected or modified job: ' + rid)
        if r.get('protocol_sha256') != protocol_hash:
            raise ValueError('protocol hash mismatch')
        r = dict(r)
        case = cases[r['question_id']]
        lang = languages[r['model']][r['question_id']]
        context_ok = (r.get('provided_prefix_ids') == lang['prefix_ids'] and
            r.get('language_sha256') == digest(lang['texts']) and
            r.get('effective_cap') == r['cap'] and
            r.get('compiled_minimum_tokens') == min(map(len, lang['paths'])))
        issues['context_mismatches'] += int(not context_ok)
        r.update(score(r, case, gold[r['question_id']]))
        r['initially_feasible'] = int(min(map(len, lang['paths'])) <= r['cap'])
        generated = r.get('generated_ids'); inserted = r.get('inserted_ids')
        complete_ids = (isinstance(generated, list) and isinstance(inserted, list) and
            r.get('returned_ids') == lang['prefix_ids'] + generated + inserted and
            r.get('generated_tokens') == len(generated) and r.get('inserted_tokens') == len(inserted))
        issues['token_record_mismatches'] += int(not complete_ids)
        if complete_ids and r['policy'] != 'xgrammar' and r.get('status') == 'COMMIT':
            suffix = generated + inserted
            canonical = next((text for text, path in zip(lang['texts'].values(), lang['paths'])
                              if suffix == path), None)
            issues['canonical_artifact_mismatches'] += int(
                canonical is None or canonical.rstrip() != r.get('returned_text', '').rstrip())
        issues['inference_errors'] += int(bool(r.get('error')))
        issues['invalid_submissions'] += r['invalid_submission']
        issues['budget_overruns'] += int(complete_ids and len(generated) + len(inserted) > r['cap'])
        r['entered_dead_after_feasible'] = None; r['calls_after_dead'] = None
        r['first_language_escape_step'] = None
        if r['policy'] in {'grammar', 'full'} and complete_ids and context_ok:
            r.update(path_diagnostics(lang['paths'], generated, r['cap'], r.get('forward_calls')))
            issues['core_prefix_escapes'] += int(r['first_language_escape_step'] is not None)
            if r['policy'] == 'full':
                issues['full_dead_entries'] += r['entered_dead_after_feasible']
        rows.append(r)
    issues['missing_records'] = len(set(expected) - seen)
    return rows, dict(issues)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--protocol', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists() and any(a.out.iterdir()):
        raise ValueError('use a new empty analysis directory')
    plan, public, languages, _ = load_protocol(a.protocol, check_source=False)
    if sha(a.protocol / 'scoring.jsonl') != plan['files']['scoring.jsonl']:
        raise ValueError('gold file changed after freeze')
    gold = {r['question_id']: r['gold'] for r in read_jsonl(a.protocol / 'scoring.jsonl')}
    expected = [j for model in MODEL_SPECS for j in jobs(public, languages, model)]
    sources, raw = {}, []
    for f in sorted(a.run.rglob('*.raw.jsonl')):
        sources[str(f)] = sha(f); raw.extend(read_jsonl(f))
    if not raw:
        raise ValueError('no completed raw records')
    rows, checks = evaluate(raw, expected, public, languages, gold, sha(a.protocol / 'protocol.json'))
    groups = defaultdict(list)
    for r in rows:
        groups[(r['model'], r['condition'], r['policy'])].append(r)
    summaries, pairs = [], []
    for (model, condition, policy), rs in sorted(groups.items()):
        feasible = [r for r in rs if r['initially_feasible']]
        failed = [r for r in rs if not r['certified']]
        core = policy in {'grammar', 'full'}
        summaries.append(dict(model=model, condition=condition, policy=policy, n=len(rs),
            certified=sum(r['certified'] for r in rs), correct=sum(r['correct'] for r in rs),
            wrong_certified=sum(r['certified']-r['correct'] for r in rs),
            initially_feasible=len(feasible), feasible_certified=sum(r['certified'] for r in feasible),
            feasible_completion_rate=sum(r['certified'] for r in feasible)/len(feasible) if feasible else None,
            dead_entry_denominator=sum(r['entered_dead_after_feasible'] is not None for r in feasible) if core else None,
            dead_entries=sum(r['entered_dead_after_feasible'] or 0 for r in feasible) if core else None,
            post_dead_calls=sum(r['calls_after_dead'] or 0 for r in rs) if core and all(r['calls_after_dead'] is not None for r in rs) else None,
            failed_forward_calls=sum(r['forward_calls'] for r in failed) if all(r.get('forward_calls') is not None for r in failed) else None,
            failed_request_ms=sum(r['request_ms'] for r in failed),
            total_request_ms=sum(r['request_ms'] for r in rs),
            total_forward_calls=sum(r['forward_calls'] for r in rs) if all(r.get('forward_calls') is not None for r in rs) else None,
            total_generated_tokens=sum(r['generated_tokens'] for r in rs),
            total_inserted_tokens=sum(r['inserted_tokens'] for r in rs),
            candidate_score_tokens=sum(r.get('candidate_score_tokens', 0) for r in rs),
            scoring_input_tokens=sum(r.get('scoring_input_tokens', 0) for r in rs),
            total_compile_ms=sum(r.get('compile_ms') or 0 for r in rs),
            max_peak_allocated_bytes=max((r.get('peak_allocated_bytes', 0) for r in rs), default=0)))
    for model in MODEL_SPECS:
        for condition in CONDITIONS:
            f = {r['question_id']: r for r in groups[(model, condition, 'full')]}
            g = {r['question_id']: r for r in groups[(model, condition, 'grammar')]}
            paired = pair_summary(f, g)
            eligible = [q for q in f.keys() & g.keys() if f[q]['initially_feasible'] and g[q]['initially_feasible']]
            wins = sum(f[q]['certified'] and not g[q]['certified'] for q in eligible)
            losses = sum(g[q]['certified'] and not f[q]['certified'] for q in eligible)
            lo, hi = paired_bounds(wins, losses, len(eligible), alpha=.025 if condition == 'fixed8' else .05)
            paired.update(primary_feasible_ci_low=lo, primary_feasible_ci_high=hi,
                primary_ci_scope='97.5% paired per model, two primary cells' if condition == 'fixed8' else '95% descriptive control',
                model=model, condition=condition)
            pairs.append(paired)
    checks['lost_certified'] = sum(p['lost_certified'] for p in pairs)
    checks['lost_correct'] = sum(p['lost_correct'] or 0 for p in pairs)
    checks['preserved_success_token_mismatches'] = sum(p['grammar_certified'] - p['same_token_records'] for p in pairs)
    checks['core_distance_missing'] = sum(r['entered_dead_after_feasible'] is None for r in rows if r['policy'] in {'full', 'grammar'})
    checks['primary_feasible_empty_cells'] = sum(p['feasible_n_pairs'] == 0 for p in pairs if p['condition'] == 'fixed8')
    checks['source_hash_mismatches'] = sum(r.get('code_sha256') != plan['source_sha256'] for r in rows)
    # Unknown telemetry never becomes measured zero.
    checks['missing_cost_records'] = sum(any(r.get(k) is None for k in ['forward_calls', 'request_ms', 'compile_ms']) for r in rows)
    checks['status'] = 'REVIEW_NEEDED' if any(v for v in checks.values()) else 'READY_FOR_INTERPRETATION'
    a.out.mkdir(parents=True, exist_ok=True)
    write_csv(a.out / 'control_summary.csv', summaries)
    write_csv(a.out / 'trajectory_preservation.csv', pairs)
    (a.out / 'control_scored.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    atomic(a.out / 'checks.json', checks)
    atomic(a.out / 'analysis_scope.json', dict(evidence_label=plan['evidence_label'],
        protocol_sha256=sha(a.protocol / 'protocol.json'), raw_sources=sources,
        baseline_warning='XGrammar may admit alternative tokenizations; canonical dead-end checks restricted to Full/grammar.',
        costs='instrumented correctness run, not isolated latency benchmark',
        prior_primary='Original 24-token comparison remains unchanged; do not pool models or boundary controls as independent samples.'))
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if checks['status'] == 'REVIEW_NEEDED':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
