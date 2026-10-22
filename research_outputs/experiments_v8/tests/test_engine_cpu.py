"""Offline integration tests: tiny random GPT2 plus scripted logits, no Hub calls."""
import tempfile
import unittest
import json
import sys
from unittest.mock import patch
from pathlib import Path

import torch
from tokenizers import Tokenizer, models, pre_tokenizers, decoders
from transformers import GPT2Config,GPT2LMHeadModel,PreTrainedTokenizerFast
from janus_v8.engine import generate_one
from janus_v8.analyze import replay_trace


class EngineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        vocab={'<unk>':0,'<eos>':1,'<bos>':2}
        for ch in 'Q# 0123456789\ncorrection.\\[]`text':
            if ch not in vocab:vocab[ch]=len(vocab)
        raw=Tokenizer(models.BPE(vocab=vocab,merges=[],unk_token='<unk>'))
        raw.pre_tokenizer=pre_tokenizers.Split('',behavior='isolated')
        raw.decoder=decoders.Fuse()
        cls.tok=PreTrainedTokenizerFast(tokenizer_object=raw,unk_token='<unk>',eos_token='<eos>',bos_token='<bos>')
        config=GPT2Config(vocab_size=len(vocab),n_positions=128,n_embd=16,n_layer=1,n_head=2,
                          bos_token_id=2,eos_token_id=1,pad_token_id=1)
        cls.model=GPT2LMHeadModel(config).eval()
        cls.original_forward=cls.model.forward

    def run_policy(self,policy,script='#### 41\ncorrection...\n#### 42\n',cap=80):
        ids=self.tok.encode(script,add_special_tokens=False)+[self.tok.eos_token_id]
        count=[0]
        original=self.original_forward
        def forward(input_ids=None,attention_mask=None,token_type_ids=None,**kwargs):
            out=original(input_ids=input_ids,attention_mask=attention_mask,token_type_ids=token_type_ids,**kwargs)
            out.logits[:,-1,:]=-10000
            out.logits[:,-1,ids[min(count[0],len(ids)-1)]]=0
            count[0]+=1
            return out
        self.model.forward=forward
        case=dict(prompt='Q',prompt_tokens=1,question_id='fixture',kind='numeric',gold='42',choices='',original_output_ids=ids)
        return generate_one(self.model,self.tok,case,policy,cap,
                            dict(threshold=.01,window=5,min_steps=21,alpha=2/11),'cpu')

    def test_output_identity_and_early_wrong_answer(self):
        u=self.run_policy('uniform');c=self.run_policy('complete');s=self.run_policy('entropy_observe')
        self.assertTrue(u['scores']['strict']['correct'])
        self.assertFalse(c['scores']['strict']['correct'])
        self.assertEqual(c['generated_ids'],s['generated_ids'])
        self.assertEqual(c['generated_ids'],u['generated_ids'][:len(c['generated_ids'])])
        self.assertTrue(u['original_uniform_ids_equal'])
        for p in ['boundary_observe','entropy_uniform']:
            self.assertEqual(self.run_policy(p)['generated_ids'],u['generated_ids'])

    def test_latch_counts_all_generated_tokens(self):
        c=self.run_policy('complete');l=self.run_policy('latched_buffer')
        self.assertEqual(l['returned_ids'],c['returned_ids'])
        self.assertGreater(l['actual_generated_tokens'],l['returned_tokens'])
        self.assertFalse(l['returned_eos'])

    def test_structure_and_cap(self):
        script='\\[\n#### 42\n\\]\n'
        c=self.run_policy('complete',script);s=self.run_policy('structured_complete',script)
        self.assertFalse(c['scores']['closure_balanced']['valid'])
        self.assertTrue(s['scores']['closure_balanced']['valid'])
        r=self.run_policy('uniform','#### 42',cap=6)
        self.assertEqual(r['stop_reason'],'cap')
        self.assertFalse(r['scores']['strict']['valid'])

    def test_trace_replay_matches_live_conjunction(self):
        r=self.run_policy('uniform_trace');e=self.run_policy('conjunction')
        r.update(model='fixture',task='gsm8k',question_id='fixture',gold='42',kind='numeric')
        plan={'trace_replay_grid':{'thresholds':[.01],'windows':[5],'min_steps':[21]},'entropy':{'alpha':2/11}}
        replay=replay_trace(r,plan)[0]
        self.assertEqual(replay['conjunction_tokens'],e['actual_generated_tokens'])
        self.assertTrue(r['diagnostic_only'])
        self.assertEqual(len(r['trace']),len(r['generated_ids']))

    def test_saved_run_analysis_and_duplicate_rejection(self):
        from janus_v8.analyze import main as analyze_main
        from janus_v8.run import sha
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'runs'/'fixture';run.mkdir(parents=True)
            policies=['uniform','complete','entropy_observe','structured_complete','boundary_observe','entropy_uniform']
            records=[]
            for qid in ['a','b']:
                for p in policies:
                    r=self.run_policy(p)
                    records.append(dict(question_id=qid,model='qwen',task='gsm8k',kind='numeric',gold='42',choices='',
                        session=0,run_uuid='fixture',repeat=0,stage='smoke',**r))
            (run/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            (run/'warmups.jsonl').write_text('')
            meta=dict(status='complete',records_sha256=sha(run/'records.jsonl'),stage='smoke',model='qwen',session=0,
                      expected_calls=len(records),run_uuid='fixture',plan_sha256='fixture',source_hashes={'fixture':'fixture'},
                      data_manifest_sha256='fixture',job_order=[{k:r[k] for k in ['question_id','policy','repeat']} for r in records],
                      plan={'stages':{'smoke':{'warmups_per_task_policy':0,'policies':policies}}})
            (run/'meta.json').write_text(json.dumps(meta))
            args=['analyze','--runs',str(root/'runs'),'--out',str(root/'analysis')]
            with patch.object(sys,'argv',args):analyze_main()
            self.assertTrue(json.loads((root/'analysis'/'analysis_status.json').read_text())['passed'])
            import shutil
            shutil.copytree(run,root/'runs'/'duplicate')
            with patch.object(sys,'argv',args),self.assertRaises(SystemExit):analyze_main()
            self.assertFalse(json.loads((root/'analysis'/'analysis_status.json').read_text())['passed'])


if __name__=='__main__':unittest.main()
