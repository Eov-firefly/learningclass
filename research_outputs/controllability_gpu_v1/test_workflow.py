"""CPU software checks with synthetic fixtures, never reported as model results."""
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch
from types import SimpleNamespace
from common import (MODEL_SPECS, compile_case, digest, validate_public, jobs,
                    assignment, read_jsonl, load_protocol, atomic, sha, source_hash)
from run import resume_records
from analyze import evaluate


class ByteTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(text.encode())

    def decode(self, ids, **kwargs):
        return bytes(ids).decode()


def fixture(n=1):
    public = [dict(question_id=f'new:{i:08d}', split='eval', question=f'Question {i}? A. cat B. caterpillar',
                   options={'A': 'cat', 'B': 'caterpillar'}) for i in range(n)]
    langs = {}
    for model in MODEL_SPECS:
        langs[model] = {}
        for case in public:
            lang = compile_case(ByteTokenizer(), case, 'option_text')
            lang['budgets'] = dict(fixed8=8, exact_min=min(map(len, lang['paths'])), wide=max(map(len, lang['paths'])))
            langs[model][case['question_id']] = lang
    expected = [j for model in MODEL_SPECS for j in jobs(public, langs, model)]
    return public, langs, expected


def records(public, langs, expected):
    result = []
    for j in expected:
        lang = langs[j['model']][j['question_id']]
        path = lang['paths'][0]
        inserted = path if j['policy'] in {'deterministic', 'sequence_score'} else []
        generated = [] if inserted else path
        result.append(dict(**j, protocol_sha256='test-protocol', code_sha256='test-code',
            provided_prefix_ids=lang['prefix_ids'], compiled_minimum_tokens=min(map(len, lang['paths'])),
            language_sha256=digest(lang['texts']), effective_cap=j['cap'],
            generated_ids=generated, inserted_ids=inserted, returned_ids=lang['prefix_ids']+path,
            generated_tokens=len(generated), inserted_tokens=len(inserted),
            returned_text=lang['texts']['A'], status='COMMIT', error=None, request_ms=1., compile_ms=.1,
            forward_calls=len(generated) if generated else int(j['policy']=='sequence_score')))
    return result


class WorkflowTests(unittest.TestCase):
    def test_freeze_cli_uses_structure_and_retains_external_exposure_warning(self):
        import freeze
        public, _, _ = fixture(2)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base/'public.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in public))
            (base/'scoring.jsonl').write_text(''.join(json.dumps(dict(question_id=r['question_id'], gold='A'))+'\n' for r in public))
            atomic(base/'models.json', {m:dict(spec=s, local_path=str(base), files={}) for m,s in MODEL_SPECS.items()})
            fake = SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**k:ByteTokenizer()))
            argv = ['freeze.py','--public',str(base/'public.jsonl'),'--scoring',str(base/'scoring.jsonl'),
                    '--model-manifest',str(base/'models.json'),'--source-description','synthetic CPU fixture',
                    '--n','2','--out',str(base/'frozen')]
            with patch.dict(sys.modules, {'transformers':fake}), patch.object(sys, 'argv', argv):
                freeze.main()
            plan, selected, langs, _ = load_protocol(base/'frozen')
            self.assertEqual(plan['total_records'], 60)
            self.assertEqual(plan['overlap_with_known_112'], 0)
            self.assertEqual(plan['evidence_label'], 'prospective_external_cohort_unverified_prior_exposure')
            self.assertIn('NOT proof', plan['exposure_warning'])

    def test_counts_and_sharding(self):
        public, langs, expected = fixture(64)
        self.assertEqual(len(expected), 1920)
        self.assertEqual(sum(j['policy'] != 'deterministic' for j in expected), 1536)
        full = {j['request_id'] for j in jobs(public, langs, 'qwen')}
        s0 = {j['request_id'] for j in jobs(public, langs, 'qwen', 0, 2)}
        s1 = {j['request_id'] for j in jobs(public, langs, 'qwen', 1, 2)}
        self.assertFalse(s0 & s1); self.assertEqual(s0 | s1, full)

    def test_assignments(self):
        self.assertEqual(assignment(['0','1']), [('qwen',0,1,'0'), ('mistral',0,1,'1')])
        self.assertEqual(len(assignment(['0','1','2','3'])), 4)
        for bad in [['0'], ['0','0'], ['0','1','2']]:
            with self.assertRaises(ValueError): assignment(bad)

    def test_public_rejects_gold_duplicates_and_collision(self):
        public, _, _ = fixture(2)
        validate_public(public)
        with self.assertRaises(ValueError): validate_public([dict(public[0], gold='A')])
        with self.assertRaises(ValueError): validate_public([public[0], public[0]])
        public[1]['question_id'] = public[0]['question_id']+'extra'
        with self.assertRaises(ValueError): validate_public(public)

    def test_complete_evaluation_and_preservation(self):
        public, langs, expected = fixture()
        rows, issues = evaluate(records(public, langs, expected), expected, public, langs,
                                {public[0]['question_id']:'A'}, 'test-protocol')
        self.assertEqual(len(rows), 30)
        self.assertFalse(any(issues.values()))
        self.assertTrue(all(r['correct']==1 for r in rows))

    def test_missing_grid_is_reported(self):
        public, langs, expected = fixture()
        _, issues = evaluate(records(public, langs, expected)[:-1], expected, public, langs,
                              {public[0]['question_id']:'A'}, 'test-protocol')
        self.assertEqual(issues['missing_records'], 1)

    def test_duplicate_and_modified_jobs_rejected(self):
        public, langs, expected = fixture()
        rows = records(public, langs, expected)
        for bad in [rows+[rows[0]], [dict(rows[0], cap=999)]]:
            with self.assertRaises(ValueError):
                evaluate(bad, expected, public, langs, {public[0]['question_id']:'A'}, 'test-protocol')

    def test_dead_end_reconstruction_and_initial_infeasible(self):
        from analyze_control import path_diagnostics
        d = path_diagnostics([[1,2], [1,3,4,5]], [1,3,4], 3, 3)
        self.assertEqual(d['first_dead_step'], 2)
        self.assertEqual(d['calls_after_dead'], 1)
        self.assertEqual(d['entered_dead_after_feasible'], 1)
        d = path_diagnostics([[1,2]], [1], 1, 1)
        self.assertEqual(d['first_dead_step'], 0)
        self.assertEqual(d['entered_dead_after_feasible'], 0)

    def test_context_and_token_mismatch_not_silenced(self):
        public, langs, expected = fixture()
        rows = records(public, langs, expected)
        rows[0]['provided_prefix_ids'] = []
        _, issues = evaluate(rows, expected, public, langs, {public[0]['question_id']:'A'}, 'test-protocol')
        self.assertEqual(issues['context_mismatches'], 1)
        rows[0]['generated_tokens'] = 999
        _, issues = evaluate(rows, expected, public, langs, {public[0]['question_id']:'A'}, 'test-protocol')
        self.assertEqual(issues['token_record_mismatches'], 1)

    def test_valid_text_must_match_its_canonical_token_path(self):
        public, langs, expected = fixture()
        rows = records(public, langs, expected)
        r = next(r for r in rows if r['policy']=='full')
        r['returned_text'] = langs[r['model']][r['question_id']]['texts']['B']
        _, issues = evaluate(rows, expected, public, langs, {public[0]['question_id']:'A'}, 'test-protocol')
        self.assertEqual(issues['canonical_artifact_mismatches'], 1)

    def test_partial_jsonl_and_failed_resume_rejected(self):
        public, langs, expected = fixture()
        rows = records(public, langs, expected)
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'q.raw.jsonl'
            p.write_text(json.dumps(rows[0]))
            with self.assertRaises(ValueError): read_jsonl(p)
            p.write_text(json.dumps(rows[0])+'\n')
            self.assertEqual(len(resume_records(p, expected, 'test-protocol')), 1)
            rows[0]['error'] = 'OOM'
            p.write_text(json.dumps(rows[0])+'\n')
            with self.assertRaises(ValueError): resume_records(p, expected, 'test-protocol')

    def test_frozen_hash_and_worker_does_not_read_gold(self):
        public, langs, _ = fixture()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out/'public.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in public))
            atomic(out/'languages.json', langs); atomic(out/'models.json', {})
            plan = dict(source_sha256=source_hash(), files={n:sha(out/n) for n in ['public.jsonl','languages.json','models.json']})
            atomic(out/'protocol.json', plan)
            self.assertEqual(len(load_protocol(out)[1]), 1)  # No gold file exists.
            (out/'public.jsonl').write_text('changed\n')
            with self.assertRaises(ValueError): load_protocol(out)

    def test_cli_plan_and_full_analysis_without_gpu(self):
        public, langs, expected = fixture(2)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); frozen = base/'protocol'; frozen.mkdir(); run = base/'run'; run.mkdir()
            (frozen/'public.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in public))
            (frozen/'scoring.jsonl').write_text(''.join(json.dumps(dict(question_id=r['question_id'], gold='A'))+'\n' for r in public))
            atomic(frozen/'languages.json', langs); atomic(frozen/'models.json', {})
            code = source_hash()
            plan = dict(source_sha256=code, total_records=len(expected), neural_request_upper_bound=48,
                        evidence_label='synthetic_software_test_only',
                        files={n:sha(frozen/n) for n in ['public.jsonl','scoring.jsonl','languages.json','models.json']})
            atomic(frozen/'protocol.json', plan)
            for devices in ['0,1', '0,1,2,3']:
                proc = subprocess.run([sys.executable, 'run.py', '--protocol', str(frozen), '--output', str(run),
                                       '--devices', devices, '--plan'], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            raw = records(public, langs, expected)
            for r in raw:
                r['protocol_sha256'] = sha(frozen/'protocol.json'); r['code_sha256'] = code
            (run/'test.raw.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in raw))
            proc = subprocess.run([sys.executable, 'analyze.py', '--protocol', str(frozen), '--run', str(run),
                                   '--out', str(base/'analysis')], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr+proc.stdout)
            self.assertEqual(json.loads((base/'analysis/checks.json').read_text())['status'], 'READY_FOR_INTERPRETATION')
            raw.pop()
            (run/'test.raw.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in raw))
            proc = subprocess.run([sys.executable, 'analyze.py', '--protocol', str(frozen), '--run', str(run),
                                   '--out', str(base/'partial')], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2, proc.stderr+proc.stdout)
            self.assertEqual(json.loads((base/'partial/checks.json').read_text())['status'], 'REVIEW_NEEDED')


if __name__ == '__main__':
    unittest.main()
