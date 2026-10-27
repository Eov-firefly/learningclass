import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import torch
from tokenizers import Tokenizer,models,pre_tokenizers,decoders
from transformers import GPT2Config,GPT2LMHeadModel,PreTrainedTokenizerFast
from janus_min.spec import load_public,jobs,compile_case,validate_artifact,artifacts
from janus_min.engine import run_matched,run_wrapper
from janus_min.controllers import XGrammarRuntime


class DataTests(unittest.TestCase):
    def test_eta_ignores_only_inflight_partial_record_and_preserves_raw(self):
        from janus_min.launch import complete_records,estimate,assignment
        from janus_min.spec import POLICIES
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            assign=assignment(['0','1','2','3'])
            for model,shard,_ in assign:
                sample=[dict(policy=p,encoding=e,request_ms=10,generated_tokens=4,inserted_tokens=0)
                        for p in POLICIES+['sequence_score'] for e in ['label','option_text']]
                (root/f'{model}.s{shard}.calibration.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in sample))
                job=jobs(model,shard,2)[0]
                raw=root/f'{model}.s{shard}.raw.jsonl'
                contents=json.dumps({'request_id':job['request_id']})+'\n'+ '{"request_id":"unfinished'
                raw.write_text(contents)
                self.assertEqual(complete_records(raw),[{'request_id':job['request_id']}])
            result=estimate(root,assign)
            self.assertGreater(result['remaining_point_minutes'],0)
            self.assertTrue(raw.read_text().endswith('{"request_id":"unfinished'))
            raw.write_text('{broken}\n')
            with self.assertRaises(json.JSONDecodeError):complete_records(raw)

    def test_analyzer_keeps_missing_grid_and_invalid_outputs_visible(self):
        from janus_min.spec import ROOT
        case=load_public('eval')[0]
        j=next(j for j in jobs('qwen') if j['question_id']==case['question_id'] and j['track']=='matched' and j['policy']=='uniform')
        row=dict(**j,status='SUBMIT',reason='eos_or_cap',error=None,returned_text='A',generated_tokens=1,
            inserted_tokens=0,forward_calls=1,request_ms=1,effective_cap=j['cap'])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'qwen.s0.raw.jsonl').write_text(json.dumps(row)+'\n')
            result=subprocess.run([sys.executable,'-m','janus_min.analyze','--run',str(root),'--allow-incomplete'],
                cwd=ROOT,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            checks=json.loads((root/'analysis/checks.json').read_text())
            self.assertEqual(checks['status'],'REQUIRES_REVIEW');self.assertEqual(len(checks['missing']),6975)
            scored=json.loads((root/'analysis/scored.jsonl').read_text())
            self.assertEqual(scored['correct'],0);self.assertEqual(scored['invalid_submission'],1)
    def test_public_data_is_small_and_blinded(self):
        self.assertEqual(len(load_public('eval')),96);self.assertEqual(len(load_public('dev')),16)
        self.assertFalse(set(r['question_id'] for r in load_public('eval'))&set(r['question_id'] for r in load_public('dev')))
        self.assertTrue(all('gold' not in r and 'original_text' not in r for r in load_public('eval')))

    def test_shards_cover_frozen_grid_without_overlap(self):
        for model in ['qwen','mistral']:
            all_ids={j['request_id'] for j in jobs(model)}
            first={j['request_id'] for j in jobs(model,0,2)};second={j['request_id'] for j in jobs(model,1,2)}
            self.assertFalse(first&second);self.assertEqual(first|second,all_ids)
        self.assertEqual(sum(len(jobs(m)) for m in ['qwen','mistral']),6976)

    def test_conservative_binary_interval_does_not_claim_zero_loss_from_zero_events(self):
        from janus_min.analyze import paired_binary
        r=paired_binary([0]*96,[0]*96)
        self.assertLess(r['ci_low'],0);self.assertGreater(r['ci_high'],0)


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        vocab={'<unk>':0,'<eos>':1}
        for ch in sorted(pre_tokenizers.ByteLevel.alphabet()):vocab[ch]=len(vocab)
        raw=Tokenizer(models.BPE(vocab=vocab,merges=[],unk_token='<unk>'))
        raw.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False)
        raw.decoder=decoders.ByteLevel()
        cls.tok=PreTrainedTokenizerFast(tokenizer_object=raw,unk_token='<unk>',eos_token='<eos>')
        cls.tok.chat_template="{{ messages[0]['content'] }}\nASSISTANT\n"
        cls.model=GPT2LMHeadModel(GPT2Config(vocab_size=len(vocab),n_positions=4096,n_embd=16,n_layer=1,n_head=2,eos_token_id=1,pad_token_id=1)).eval()
        cls.original=cls.model.forward
        cls.case=dict(question_id='arc:1234567890',split='eval',question='Pick A.\nA. x\nB. a much longer option',options={'A':'x','B':'a much longer option'})
        cls.xr=XGrammarRuntime(cls.tok,len(vocab),[1])

    def tearDown(self):self.model.forward=self.original

    def script(self,ids,fail_at=None):
        step=[0];original=self.original
        def forward(input_ids=None,attention_mask=None,token_type_ids=None,**kwargs):
            if fail_at is not None and step[0]==fail_at:raise RuntimeError('injected model error')
            result=original(input_ids=input_ids,attention_mask=attention_mask,token_type_ids=token_type_ids,**kwargs)
            result.logits[:,-1,:]=-10000;result.logits[:,-1,ids[min(step[0],len(ids)-1)]]=0
            step[0]+=1;return result
        self.model.forward=forward

    def job(self,policy,encoding='label',cap=16,track='matched',condition='ordinary'):
        return dict(policy=policy,encoding=encoding,cap=cap,track=track,condition=condition)

    def test_compiler_canonical_roundtrip_and_unbound_choices(self):
        c=compile_case(self.tok,self.case,'option_text')
        self.assertEqual(len(c['paths']),2)
        for p,t in zip(c['paths'],c['texts'].values()):
            self.assertEqual(self.tok.decode(c['prefix_ids']+p),t)

    def test_full_prunes_long_branch_and_preserves_public_id(self):
        c=compile_case(self.tok,self.case,'option_text');self.script(c['paths'][1]+[1])
        r=run_matched(self.model,self.tok,self.case,self.job('full','option_text',8),'cpu',self.xr)
        self.assertEqual(r['status'],'COMMIT');self.assertEqual(validate_artifact(r['returned_text'],self.case,'option_text'),'A')
        self.assertGreater(r['legal_tokens_removed'],0);self.assertGreater(r['oracle_checks'],0)
        self.assertEqual(r['forward_calls'],r['generated_tokens'])

    def test_grammar_only_can_exhaust_budget_on_long_valid_branch(self):
        c=compile_case(self.tok,self.case,'option_text');self.script(c['paths'][1]+[1])
        r=run_matched(self.model,self.tok,self.case,self.job('grammar','option_text',8),'cpu',self.xr)
        self.assertEqual(r['status'],'ABSTAIN');self.assertEqual(r['generated_tokens'],8)

    def test_real_xgrammar_adapter_generates_accepted_alternative(self):
        c=compile_case(self.tok,self.case,'label');self.script(c['paths'][1]+[1])
        r=run_matched(self.model,self.tok,self.case,self.job('xgrammar'),'cpu',self.xr)
        self.assertIsNone(r['error']);self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(validate_artifact(r['returned_text'],self.case,'label'),'B')

    def test_deterministic_baseline_has_no_model_forward(self):
        r=run_matched(self.model,self.tok,self.case,self.job('deterministic'),'cpu',self.xr)
        self.assertEqual(r['status'],'COMMIT');self.assertEqual(r['forward_calls'],0)
        self.assertEqual(r['generated_tokens'],0);self.assertGreater(r['inserted_tokens'],0)

    def test_candidate_sequence_scoring_is_one_batched_forward_not_free_generation(self):
        r=run_matched(self.model,self.tok,self.case,self.job('sequence_score','option_text',32),'cpu',self.xr)
        self.assertIsNone(r['error']);self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(r['forward_calls'],1);self.assertEqual(r['generated_tokens'],0)
        self.assertGreater(r['candidate_score_tokens'],0);self.assertGreater(r['scoring_input_tokens'],r['candidate_score_tokens'])
        self.assertIn(validate_artifact(r['returned_text'],self.case,'option_text'),['A','B'])

    def test_budget_below_minimum_does_no_model_work(self):
        r=run_matched(self.model,self.tok,self.case,self.job('full',cap=0),'cpu',self.xr)
        self.assertEqual(r['status'],'ABSTAIN');self.assertEqual(r['forward_calls'],0)

    def test_runtime_failure_retains_previous_tokens_and_cost(self):
        c=compile_case(self.tok,self.case,'label');self.script(c['paths'][1]+[1],fail_at=2)
        count=len(self.model._forward_pre_hooks)
        r=run_matched(self.model,self.tok,self.case,self.job('full'),'cpu',self.xr)
        self.assertEqual(r['status'],'ABSTAIN');self.assertEqual(r['generated_tokens'],2)
        self.assertEqual(r['forward_calls'],3);self.assertGreater(r['request_ms'],0)
        self.assertEqual(len(self.model._forward_pre_hooks),count)

    def test_missing_required_engine_is_a_visible_failure(self):
        r=run_matched(self.model,self.tok,self.case,self.job('xgrammar'),'cpu',None)
        self.assertEqual(r['status'],'ABSTAIN');self.assertIn('XGrammar unavailable',r['error'])

    def test_timing_disables_online_oracle(self):
        r=run_matched(self.model,self.tok,self.case,self.job('full',track='timing'),'cpu',self.xr)
        self.assertEqual(r['status'],'COMMIT');self.assertEqual(r['oracle_checks'],0)

    def test_format_only_full_and_deterministic_preserve_same_answer(self):
        full=run_matched(self.model,self.tok,self.case,self.job('full',track='format',condition='exact'),'cpu',self.xr)
        det=run_matched(self.model,self.tok,self.case,self.job('deterministic',track='format',condition='exact'),'cpu',self.xr)
        self.assertEqual(full['status'],'COMMIT');self.assertEqual(det['status'],'COMMIT')
        self.assertEqual(json.loads(full['returned_text']),json.loads(det['returned_text']))
        self.assertEqual(det['forward_calls'],0)

    def test_wrapper_eos_certificate_is_recorded(self):
        self.script(self.tok.encode('#### A',add_special_tokens=False)+[1])
        r=run_wrapper(self.model,self.tok,self.case,self.job('uniform',cap=32),'cpu')
        self.assertTrue(r['ended_with_eos']);self.assertEqual(r['status'],'SUBMIT')
        from janus_min.analyze import score
        self.assertEqual(score(dict(track='wrapper_e2e',cap=32,**r),self.case,'A')['correct'],1)

    def test_invalid_fragment_never_receives_correct_credit(self):
        from janus_min.analyze import score
        row=dict(track='matched',encoding='label',status='SUBMIT',returned_text='A',cap=8,generated_tokens=1,inserted_tokens=0)
        self.assertEqual(score(row,self.case,'A')['correct'],0)

    def test_worker_model_load_calibration_and_progress_on_cpu(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);weights=root/'weights';self.model.save_pretrained(weights);self.tok.save_pretrained(weights)
            result=subprocess.run([sys.executable,'-m','janus_min.worker','--model','qwen','--model-path',str(weights),
                '--shard','0','--output',str(root/'run'),'--device','cpu','--allow-cpu','--calibrate-only'],
                capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[-3000:])
            self.assertEqual(json.loads((root/'run/qwen.s0.progress.json').read_text())['phase'],'calibrated')
            self.assertEqual(len((root/'run/qwen.s0.calibration.jsonl').read_text().splitlines()),12)

if __name__=='__main__':unittest.main()
