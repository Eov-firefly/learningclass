import unittest
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from analyze_control import path_diagnostics,pair_summary

class ControlTests(unittest.TestCase):
    def test_bundled_data_manifest_is_complete_and_blinded(self):
        from run_control import ROOT,check_inputs
        manifest,ids=check_inputs(ROOT/'data/public.jsonl',ROOT/'data/scoring.jsonl',ROOT/'data/manifest.json')
        self.assertEqual(len(ids),96);self.assertEqual(manifest['dev'],16)
        public=[json.loads(l) for l in (ROOT/'data/public.jsonl').read_text().splitlines()]
        self.assertTrue(all('gold' not in r for r in public))

    def test_input_corruption_is_not_silently_accepted(self):
        from run_control import ROOT,check_inputs
        with tempfile.TemporaryDirectory() as temp:
            bad=Path(temp)/'public.jsonl'
            bad.write_text((ROOT/'data/public.jsonl').read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                check_inputs(bad,ROOT/'data/scoring.jsonl',ROOT/'data/manifest.json')

    def test_pair_context_mismatch_is_reported(self):
        r=dict(certified=1,correct=1,provided_prefix_ids=[1],generated_ids=[2],returned_ids=[1,2],
               language_sha256='one',effective_cap=8,code_sha256='same',compiled_minimum_tokens=2)
        other=dict(r,language_sha256='two')
        result=pair_summary({'a':r},{'a':other})
        self.assertEqual(result['context_mismatches'],1);self.assertEqual(result['context_missing'],0)

    def test_zero_discordance_interval_does_not_prove_equivalence(self):
        from analyze_control import paired_bounds
        lo,hi=paired_bounds(0,0,96,alpha=.025)
        self.assertAlmostEqual(hi,1-(.025/4)**(1/96),places=12)
        self.assertAlmostEqual(lo,-hi,places=12)

    def test_paired_interval_handles_direction_and_no_samples(self):
        from analyze_control import paired_bounds
        lo,hi=paired_bounds(16,0,64)
        self.assertLess(lo,16/64);self.assertGreater(hi,16/64)
        self.assertGreater(lo,0)
        self.assertEqual(paired_bounds(0,0,0),(None,None))

    def test_runner_partial_grid_and_collection_remain_review_needed(self):
        from run_control import ROOT
        from analyze_control import artifacts
        case=next(r for r in map(json.loads,(ROOT/'data/public.jsonl').read_text().splitlines()) if r['split']=='eval')
        text=next(iter(artifacts(case,'label').values()))
        common=dict(model='qwen',question_id=case['question_id'],track='matched',encoding='label',cap=8,
            effective_cap=8,compiled_minimum_tokens=2,provided_prefix_ids=[1],generated_ids=[2,3],returned_ids=[1,2,3],
            forward_calls=2,request_ms=10,language_sha256='test',code_sha256='test')
        full=dict(**common,request_id='full',policy='full',status='COMMIT',returned_text=text)
        grammar=dict(**common,request_id='grammar',policy='grammar',status='ABSTAIN',returned_text='incomplete')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';run.mkdir()
            (run/'test.raw.jsonl').write_text(json.dumps(full)+'\n'+json.dumps(grammar)+'\n')
            result=subprocess.run([sys.executable,str(ROOT/'run_control.py'),'--run',str(run),'--out',str(root/'out')],
                capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            checks=json.loads((root/'out/checks.json').read_text())
            self.assertEqual(checks['status'],'REVIEW_NEEDED')
            self.assertEqual(checks['expected_matched_records'],5952)
            self.assertGreater(checks['missing_core_count'],0)
            self.assertTrue((root/'out/执行结果摘要_zh.md').exists())
            packed=subprocess.run([sys.executable,str(ROOT/'package_results.py'),'--analysis',str(root/'out'),
                   '--out',str(root/'result.zip')],capture_output=True,text=True)
            self.assertEqual(packed.returncode,0,packed.stderr)
            import zipfile
            with zipfile.ZipFile(root/'result.zip') as archive:
                self.assertEqual(json.loads(archive.read('RESULT_MANIFEST.json'))['status'],'REVIEW_NEEDED')

    def test_cli_reanalysis_scores_transfer_but_leaves_unknown_distance_empty(self):
        case=dict(question_id='arc:abc',options={'A':'x','B':'y'})
        common=dict(model='qwen',question_id='arc:abc',track='matched',encoding='label',cap=3,
            effective_cap=3,compiled_minimum_tokens=2,generated_ids=[1,2],forward_calls=2,request_ms=10)
        full=dict(**common,request_id='full',policy='full',status='COMMIT',returned_text='{"id":"abc","answer":"A"}\n')
        grammar=dict(**common,request_id='grammar',policy='grammar',status='ABSTAIN',returned_text='incomplete')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';run.mkdir()
            (run/'qwen.raw.jsonl').write_text(json.dumps(full)+'\n'+json.dumps(grammar)+'\n')
            (root/'public.jsonl').write_text(json.dumps(case)+'\n')
            (root/'gold.jsonl').write_text(json.dumps(dict(question_id='arc:abc',gold='A'))+'\n')
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('analyze_control.py')),
               '--run',str(run),'--public',str(root/'public.jsonl'),'--scoring',str(root/'gold.jsonl'),
               '--out',str(root/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            pairs=list(csv.DictReader((root/'out/trajectory_preservation.csv').read_text().splitlines()))
            self.assertEqual(pairs[0]['new_certified'],'1');self.assertEqual(pairs[0]['new_correct'],'1')
            summaries=list(csv.DictReader((root/'out/control_summary.csv').read_text().splitlines()))
            self.assertTrue(all(r['dead_entries']=='' and r['exact_distance_checked']=='0' for r in summaries))

    def test_legal_long_branch_becomes_dead_before_cap(self):
        r=path_diagnostics([[1,2],[3,4,5,6]],[3,4,5],3,3)
        self.assertEqual(r['initially_feasible'],1)
        self.assertEqual(r['first_dead_step'],1)
        self.assertEqual(r['calls_after_dead'],2)
        self.assertEqual(r['entered_dead_after_feasible'],1)

    def test_feasible_success_has_no_dead_entry(self):
        r=path_diagnostics([[1,2],[3,4,5,6]],[1,2],3,2)
        self.assertIsNone(r['first_dead_step']);self.assertEqual(r['calls_after_dead'],0)

    def test_initial_infeasibility_is_not_a_new_dead_entry(self):
        r=path_diagnostics([[1,2,3]],[1],2,1)
        self.assertEqual(r['first_dead_step'],0);self.assertEqual(r['entered_dead_after_feasible'],0)

    def test_illegal_prefix_distinguished_from_legal_budget_dead_end(self):
        r=path_diagnostics([[1,2]],[9],2,1)
        self.assertEqual(r['first_language_escape_step'],1)
        self.assertIsNone(r['first_dead_step'])

    def test_success_preservation_and_new_commit_are_separate(self):
        good=dict(certified=1,correct=1,provided_prefix_ids=[8],generated_ids=[1,2],returned_ids=[8,1,2])
        bad=dict(certified=0,correct=0,provided_prefix_ids=[8],generated_ids=[3],returned_ids=[8,3])
        wrong=dict(certified=1,correct=0,provided_prefix_ids=[8],generated_ids=[4],returned_ids=[8,4])
        r=pair_summary({'a':good,'b':wrong},{'a':good,'b':bad})
        self.assertEqual(r['lost_certified'],0);self.assertEqual(r['same_token_records'],1)
        self.assertEqual(r['new_certified'],1);self.assertEqual(r['new_correct'],0)

    def test_missing_token_evidence_is_not_identical_trajectory(self):
        record=dict(certified=1,correct=None)
        r=pair_summary({'a':record},{'a':record})
        self.assertEqual(r['same_token_records'],0);self.assertEqual(r['ids_missing'],1)

if __name__=='__main__':unittest.main()
