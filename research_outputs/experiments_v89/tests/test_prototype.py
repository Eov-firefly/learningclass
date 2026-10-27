import unittest
import torch
from tokenizers import Tokenizer,models,pre_tokenizers,decoders
from transformers import GPT2Config,GPT2LMHeadModel,PreTrainedTokenizerFast
from prototype.controller import RepairTrie,CommitController,ConstraintFailure,shortest_verified_repair
from prototype.hf_adapter import run_one,ViabilityMask


class TrieTests(unittest.TestCase):
    def test_empty_path_accepts_without_a_token(self):
        self.assertTrue(RepairTrie([[]]).root.accepting)
        self.assertEqual(RepairTrie([[]]).root.distance,0)
        self.assertEqual(RepairTrie([]).root.distance,float('inf'))
    def test_distance_and_deadline_pruning(self):
        trie=RepairTrie([[1,2],[1,3,4]])
        self.assertEqual(trie.root.distance,2)
        self.assertEqual(trie.allowed([],2),[1])
        self.assertEqual(trie.allowed([1],1),[2])
        self.assertEqual(set(trie.allowed([1],2)),{2,3})
        self.assertTrue(trie.state([1,3,4]).accepting)
        self.assertEqual(trie.allowed([],1),[])

    def test_all_feasible_paths_preserve_invariant(self):
        trie=RepairTrie([[1,2],[1,3,4],[5,6,7,8]])
        visits=[([],r) for r in [2,3,4]]
        while visits:
            path,r=visits.pop();node=trie.state(path)
            self.assertLessEqual(node.distance,r)
            if node.accepting:continue
            allowed=trie.allowed(path,r);self.assertTrue(allowed)
            visits.extend((path+[v],r-1) for v in allowed)


class GenerateTests(unittest.TestCase):
    def tearDown(self):
        self.model.forward=self.original

    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        vocab={'<unk>':0,'<eos>':1,'<bos>':2}
        for ch in 'Q# 0123456789\ncorrection.\\[]()`text~{}begin"id:7,labelAB':
            if ch not in vocab:vocab[ch]=len(vocab)
        raw=Tokenizer(models.BPE(vocab=vocab,merges=[],unk_token='<unk>'))
        raw.pre_tokenizer=pre_tokenizers.Split('',behavior='isolated');raw.decoder=decoders.Fuse()
        cls.tok=PreTrainedTokenizerFast(tokenizer_object=raw,unk_token='<unk>',eos_token='<eos>',bos_token='<bos>')
        cls.model=GPT2LMHeadModel(GPT2Config(vocab_size=len(vocab),n_positions=160,n_embd=16,n_layer=1,n_head=2,
            bos_token_id=2,eos_token_id=1,pad_token_id=1)).eval()
        cls.original=cls.model.forward

    def generate(self,script,cap=80,reserve=8):
        ids=self.tok.encode(script,add_special_tokens=False)+[1];step=[0];original=self.original
        def forward(input_ids=None,attention_mask=None,token_type_ids=None,**kwargs):
            out=original(input_ids=input_ids,attention_mask=attention_mask,token_type_ids=token_type_ids,**kwargs)
            out.logits[:,-1,:]=-10000
            out.logits[:,-1,ids[min(step[0],len(ids)-1)]]=0
            step[0]+=1;return out
        self.model.forward=forward
        return run_one(self.model,self.tok,'Q','numeric',cap=cap,reserve=reserve)

    def test_repair_changes_trajectory_and_preserves_value(self):
        r=self.generate('\\[\n#### 42\ncorrection...')
        self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(r['bound_value'],'42')
        self.assertIn('\\]',r['committed_text'])
        self.assertNotIn('correction',r['committed_text'])
        self.assertGreater(r['repair_tokens'],0)
        self.assertTrue(any(e['mode']=='REPAIR' for e in r['events']))
        self.assertEqual(r['forward_calls'],r['actual_generated_tokens'])

    def test_fence_repair(self):
        r=self.generate('```text\n#### 42\ncorrection...')
        self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(r['committed_text'].count('```'),2)

    def test_no_semantic_guarantee(self):
        r=self.generate('#### 41\ncorrection...\n#### 42\n')
        self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(r['bound_value'],'41')

    def test_invalid_eos_is_explicit_abstention(self):
        r=self.generate('correction')
        self.assertEqual(r['status'],'ABSTAIN');self.assertIsNone(r['committed_text'])
        self.assertGreater(r['actual_generated_tokens'],0)
        self.assertGreater(r['end_to_end_seconds'],0)

    def test_infeasible_repair_abstains(self):
        prefix='\\[\n#### 42\n'
        r=self.generate(prefix+'correction',cap=len(prefix)+1,reserve=0)
        self.assertEqual(r['status'],'ABSTAIN')
        self.assertEqual(r['reason'],'repair_not_budget_viable')

    def test_unsupported_wrapper_abstains(self):
        r=self.generate('\\begin{x}\n#### 42\ncorrection')
        self.assertEqual(r['status'],'ABSTAIN')

    def test_deadline_is_not_success(self):
        r=self.generate('correction...correction...',cap=12,reserve=3)
        self.assertEqual(r['status'],'ABSTAIN')
        self.assertEqual(r['actual_generated_tokens'],9)
        self.assertEqual(r['reason'],'no_candidate_at_draft_deadline')

    def test_context_roundtrip_failure_is_not_accepted(self):
        c=CommitController(self.tok,'numeric','',80,[1],8)
        prefix=self.tok.encode('\\[\n#### 42\n',add_special_tokens=False)
        original=self.tok.encode
        try:
            self.tok.encode=lambda *a,**k:[self.tok.unk_token_id]
            self.assertTrue(c.observe(prefix))
            self.assertEqual(c.mode,'ABSTAIN')
        finally:self.tok.encode=original

    def test_mask_prunes_infeasible_branch_and_eos(self):
        c=CommitController(self.tok,'numeric','',20,[1],0)
        c.mode='REPAIR';c.checkpoint=1;c.trie=RepairTrie([[3,4],[3,5,6]])
        c.cap=3
        proc=ViabilityMask(c,1)
        scores=torch.zeros(1,len(self.tok))
        masked=proc(torch.tensor([[2,9,3]]),scores)
        self.assertEqual(torch.isfinite(masked).nonzero()[:,1].tolist(),[4])
        self.assertFalse(torch.isfinite(masked[0,1]))

    def test_deterministic_baseline_is_required_and_equivalent_in_format_only_case(self):
        prefix='\\[\n#### 42\n'
        d=shortest_verified_repair(self.tok,self.tok.encode(prefix,add_special_tokens=False),'numeric','',80)
        m=self.generate(prefix+'correction...')
        self.assertEqual(d['status'],m['status'])
        self.assertEqual(d['bound_value'],m['bound_value'])
        self.assertEqual(d['new_model_calls'],0)
        self.assertLessEqual(d['inserted_tokens'],m['repair_tokens'])

    def test_unbound_record_field_is_model_selected_while_id_is_preserved(self):
        import json
        from prototype.finite_record import complete_finite_record
        target='"B"}\n';ids=self.tok.encode(target,add_special_tokens=False);step=[0];original=self.original
        def forward(input_ids=None,attention_mask=None,**kwargs):
            out=original(input_ids=input_ids,attention_mask=attention_mask,**kwargs)
            out.logits[:,-1,:]=-10000;out.logits[:,-1,ids[min(step[0],len(ids)-1)]]=0
            step[0]+=1;return out
        self.model.forward=forward
        def accepted(s):
            try:return json.loads(s)['label'] in ['A','B']
            except (ValueError,KeyError):return False
        def preserved(s):
            try:return json.loads(s)['id']==7
            except (ValueError,KeyError):return False
        r=complete_finite_record(self.model,self.tok,'Q','{"id":7,"label":',
            ['"A"}\n','"B"}\n'],8,accepted,preserved)
        self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(json.loads(r['committed_text']),{'id':7,'label':'B'})

    def test_compiler_rejects_candidate_that_changes_bound_record_field(self):
        import json
        from prototype.finite_record import FiniteRecordController
        prefix=self.tok.encode('{"id":',add_special_tokens=False)
        accept=lambda s:isinstance(json.loads(s)['id'],int)
        preserve=lambda s:json.loads(s)['id']==7
        c=FiniteRecordController(self.tok,prefix,['7}','8}'],4,[1],accept,preserve)
        # The root can only select the representation of the preserved value.
        self.assertEqual(c.allowed_tokens(prefix),self.tok.encode('7',add_special_tokens=False))

    def test_already_accepted_record_needs_no_generation_or_budget(self):
        from prototype.finite_record import complete_finite_record
        r=complete_finite_record(self.model,self.tok,'Q','{"id":7}',[],0,
            lambda s:s=='{"id":7}',lambda s:s=='{"id":7}')
        self.assertEqual(r['status'],'COMMIT')
        self.assertEqual(r['actual_generated_tokens'],0)
        self.assertEqual(r['forward_calls'],0)
        self.assertEqual(r['reason'],'already_accepted')

    def test_zero_budget_unaccepted_record_abstains_without_generation(self):
        from prototype.finite_record import complete_finite_record
        r=complete_finite_record(self.model,self.tok,'Q','{"id":',['7}'],0,
            lambda s:s=='{"id":7}',lambda s:True)
        self.assertEqual(r['status'],'ABSTAIN')
        self.assertEqual(r['forward_calls'],0)
        self.assertEqual(r['actual_generated_tokens'],0)
        self.assertEqual(r['reason'],'completion_not_budget_viable')

    def test_zero_probability_allowed_token_does_not_block_positive_support(self):
        class C:
            def allowed_tokens(self,ids):return [3,4]
        scores=torch.zeros(1,len(self.tok));scores[0,3]=-float('inf')
        masked=ViabilityMask(C(),0)(torch.tensor([[2]]),scores)
        self.assertEqual(torch.isfinite(masked).nonzero()[:,1].tolist(),[4])

    def test_empty_probability_support_is_rejected(self):
        class C:
            def allowed_tokens(self,ids):return [3,4]
        with self.assertRaises(ConstraintFailure):
            ViabilityMask(C(),0)(torch.tensor([[2]]),torch.full((1,len(self.tok)),-float('inf')))

    def test_nan_or_positive_infinity_on_allowed_support_is_rejected(self):
        class C:
            def allowed_tokens(self,ids):return [3,4]
        for value in [float('nan'),float('inf')]:
            scores=torch.zeros(1,len(self.tok));scores[0,3]=value
            with self.assertRaises(ConstraintFailure):
                ViabilityMask(C(),0)(torch.tensor([[2]]),scores)

    def test_record_final_certificate_failure_keeps_trace_and_cost(self):
        from prototype.finite_record import complete_finite_record
        checks=[0]
        def accepted(s):
            if s=='{"id":7}':
                checks[0]+=1
                return checks[0]==1  # compile accepts, final independent check rejects
            return False
        r=complete_finite_record(self.model,self.tok,'Q','{"id":',['7}'],4,accepted,lambda s:True)
        self.assertEqual(r['status'],'ABSTAIN')
        self.assertEqual(r['reason'],'constraint_failure')
        self.assertIsNone(r['committed_text'])
        self.assertGreater(r['actual_generated_tokens'],0)
        self.assertGreater(r['forward_calls'],0)
        self.assertGreater(r['end_to_end_seconds'],0)
        self.assertEqual(len(r['generated_ids']),r['actual_generated_tokens'])

    def test_record_runtime_error_is_explicit_and_forward_hook_removed(self):
        from prototype.finite_record import complete_finite_record
        hooks=len(self.model._forward_pre_hooks)
        def fail(*args,**kwargs):raise RuntimeError('injected model failure')
        self.model.forward=fail
        r=complete_finite_record(self.model,self.tok,'Q','{"id":',['7}'],4,
            lambda s:s=='{"id":7}',lambda s:True)
        self.assertEqual(r['status'],'ABSTAIN')
        self.assertEqual(r['reason'],'runtime_error')
        self.assertIn('injected model failure',r['error'])
        self.assertEqual(len(self.model._forward_pre_hooks),hooks)
        self.assertEqual(r['forward_calls'],1)
        self.assertGreater(r['end_to_end_seconds'],0)


if __name__=='__main__':unittest.main()
