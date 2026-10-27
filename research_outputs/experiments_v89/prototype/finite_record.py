"""Fixed-prefix structured completion with immutable selected fields.

The caller supplies a finite completion language and independent acceptance and
binding checks. This is not a schema-to-grammar compiler. The prefix is supplied,
so no cost or quality claim about generating that prefix follows from this API.
"""
import time
import torch
from transformers import GenerationConfig,LogitsProcessorList,StoppingCriteriaList
from .controller import RepairTrie,ConstraintFailure
from .hf_adapter import ViabilityMask,CommitStop,sync


class FiniteRecordController:
    def __init__(self,tokenizer,prefix_ids,suffixes,budget,eos_ids,accept,preserve):
        if budget<0:raise ValueError('Nonnegative completion budget required')
        self.tokenizer,self.prefix_ids=tokenizer,list(prefix_ids)
        self.checkpoint=len(prefix_ids);self.cap=self.checkpoint+budget
        self.accept,self.preserve=accept,preserve
        self.mode='REPAIR';self.last_ids=list(prefix_ids);self.events=[]
        self.reason='compiled_completion';self.bound_value=None
        prefix=self.text(prefix_ids);paths=[]
        if self.predicates_pass(prefix):
            self.trie=RepairTrie([[]]);self.set_mode('COMMIT','already_accepted');return
        for suffix in suffixes:
            ids=tokenizer.encode(suffix,add_special_tokens=False)
            text=self.text(prefix_ids+ids)
            if ids and not set(ids)&set(eos_ids) and text==prefix+suffix and self.predicates_pass(text):paths.append(ids)
        self.trie=RepairTrie(paths)
        if self.trie.root.distance>budget:
            self.set_mode('ABSTAIN','no_verified_paths' if not paths else 'completion_not_budget_viable')
        else:self.set_mode('REPAIR','compiled_viable_completion')

    def set_mode(self,mode,reason):
        self.mode,self.reason=mode,reason
        self.events.append(dict(step=len(self.last_ids)-self.checkpoint,mode=mode,reason=reason))

    def text(self,ids):return self.tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)

    def predicates_pass(self,text):
        try:return bool(self.accept(text)) and bool(self.preserve(text))
        except (ValueError,KeyError):return False

    def allowed_tokens(self,ids):
        self.last_ids=list(ids)
        if ids[:self.checkpoint]!=self.prefix_ids:raise ConstraintFailure('bound prefix changed')
        allowed=self.trie.allowed(ids[self.checkpoint:],self.cap-len(ids))
        if not allowed:raise ConstraintFailure('no budget-viable completion')
        return allowed

    def observe(self,ids):
        self.last_ids=list(ids)
        if self.mode in {'COMMIT','ABSTAIN'}:return True
        if ids[:self.checkpoint]!=self.prefix_ids:raise ConstraintFailure('bound prefix changed')
        if len(ids)>self.cap:raise ConstraintFailure('completion budget exceeded')
        if self.trie.state(ids[self.checkpoint:]).accepting:
            text=self.text(ids)
            if not self.predicates_pass(text):raise ConstraintFailure('final record certificate failed')
            self.set_mode('COMMIT','completion_and_certificate_complete');return True
        return False


@torch.inference_mode()
def complete_finite_record(model,tokenizer,prompt,prefix,suffixes,budget,accept,preserve,device='cpu'):
    sync(device);start=time.perf_counter()
    prompt_ids=tokenizer.encode(prompt,add_special_tokens=False)
    prefix_ids=tokenizer.encode(prefix,add_special_tokens=False)
    if tokenizer.decode(prompt_ids+prefix_ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)!=prompt+prefix:
        raise ConstraintFailure('prompt-prefix tokenizer context mismatch')
    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else list(eos or [])
    if not eos:raise ValueError('Model EOS IDs required')
    compile_start=time.perf_counter()
    c=FiniteRecordController(tokenizer,prefix_ids,suffixes,budget,eos,accept,preserve)
    compile_seconds=time.perf_counter()-compile_start
    calls=[0];error=None;generated=[]
    if c.mode=='REPAIR':
        hook=model.register_forward_pre_hook(lambda *unused:calls.__setitem__(0,calls[0]+1))
        try:
            inputs=torch.tensor([prompt_ids+prefix_ids],device=device)
            out=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                generation_config=GenerationConfig(max_new_tokens=budget,do_sample=False,num_beams=1,use_cache=True,
                    eos_token_id=eos,pad_token_id=eos[0],forced_eos_token_id=None),
                logits_processor=LogitsProcessorList([ViabilityMask(c,len(prompt_ids))]),
                stopping_criteria=StoppingCriteriaList([CommitStop(c,len(prompt_ids))]))
            generated=out[0,len(prompt_ids)+len(prefix_ids):].tolist()
            if c.mode not in {'COMMIT','ABSTAIN'}:
                c.last_ids=prefix_ids+generated;c.set_mode('ABSTAIN','uncertified_generation_end')
        except ConstraintFailure as exc:
            error=str(exc);generated=c.last_ids[c.checkpoint:]
            c.set_mode('ABSTAIN','constraint_failure')
        except RuntimeError as exc:
            error=f'{type(exc).__name__}: {exc}';generated=c.last_ids[c.checkpoint:]
            c.set_mode('ABSTAIN','runtime_error')
        finally:hook.remove()
    sync(device);elapsed=time.perf_counter()-start
    return dict(status=c.mode,reason=c.reason,
        committed_text=c.text(prefix_ids+generated) if c.mode=='COMMIT' else None,
        generated_text=c.text(generated),generated_ids=generated,provided_prefix_text=prefix,
        actual_generated_tokens=len(generated),provided_prefix_tokens=len(prefix_ids),
        forward_calls=calls[0],compile_seconds=compile_seconds,end_to_end_seconds=elapsed,
        events=c.events,error=error,prototype=True)
