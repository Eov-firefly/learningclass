"""One request at a time. No gold labels are accepted by any inference function."""
import time
import torch
from transformers import GenerationConfig,LogitsProcessorList,StoppingCriteria,StoppingCriteriaList
from prototype.controller import RepairTrie,CommitController,ConstraintFailure
from .controllers import FiniteController,FiniteMask,FiniteStop,XGrammarStop
from .spec import compile_case,chat_prompt,artifacts,record_id,digest


def sync(device):
    if str(device).startswith('cuda'):torch.cuda.synchronize(device)

def decode(tok,ids):return tok.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)

class Trace(StoppingCriteria):
    def __init__(self,start):self.start=start;self.ids=[]
    def __call__(self,ids,scores,**kwargs):self.ids=ids[0,self.start:].tolist();return False

def config(model,tok,cap):
    eos=model.generation_config.eos_token_id
    if eos is None:raise ValueError('model must define EOS')
    return GenerationConfig(max_new_tokens=cap,do_sample=False,num_beams=1,use_cache=True,
        repetition_penalty=1.0,eos_token_id=eos,
        pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else (eos[0] if isinstance(eos,list) else eos),
        forced_eos_token_id=None)

def compiled_format(tok,case):
    label=sorted(case['options'])[int(digest(case['question_id'])[:8],16)%len(case['options'])]
    base=artifacts(case,'label')[label][:-2]
    texts=[base+close for close in ['}\n','\n}\n','  }\n']]
    from .spec import lcp
    paths=[tok.encode(t,add_special_tokens=False) for t in texts];prefix_ids=lcp(paths)
    prefix=decode(tok,prefix_ids)
    if any(decode(tok,p)!=t or not t.startswith(prefix) for p,t in zip(paths,texts)):
        raise ValueError('format language round-trip failure')
    return dict(prefix_ids=prefix_ids,prefix=prefix,paths=[p[len(prefix_ids):] for p in paths],
        texts=dict(enumerate(texts)),suffix_strings=[t[len(prefix):] for t in texts],bound_label=label)


@torch.inference_mode()
def run_matched(model,tok,case,job,device,xruntime=None):
    sync(device);started=time.perf_counter();calls=[0];hook=None;c=None;x=None
    generated=[];inserted=[];error=None;status='ABSTAIN';reason='uncertified_end'
    prefix_ids=[];prefix='';cap=job['cap'];compiled_ms=None;events=[]
    result={};trace=None
    try:
        compile_started=time.perf_counter()
        lang=compiled_format(tok,case) if job['track']=='format' else compile_case(tok,case,job['encoding'])
        prefix_ids=lang['prefix_ids'];prefix=lang['prefix'];paths=lang['paths']
        if job['track']=='format':
            minimum=min(map(len,paths));cap=max(0,minimum+{'below':-1,'exact':0,'above':1}[job['condition']])
        accepted={t.rstrip() for t in lang['texts'].values()}
        policy=job['policy']
        if policy in {'full','grammar','deterministic'}:
            c=FiniteController(paths,cap,prefix_ids,tok,accepted,policy,
                audit=(job['track']!='timing' and policy=='full'))
        if policy=='xgrammar':
            if xruntime is None:raise RuntimeError('XGrammar unavailable; required baseline cannot be omitted')
            x=xruntime.controller(lang['suffix_strings'])
        compiled_ms=(time.perf_counter()-compile_started)*1000
        prompt=chat_prompt(tok,case,job['encoding'])
        prompt_ids=tok.encode(prompt,add_special_tokens=False)
        start=len(prompt_ids)+len(prefix_ids)
        result.update(provided_prefix_ids=prefix_ids,provided_prefix_text=prefix,
           prompt_tokens=len(prompt_ids),language_sha256=digest(lang['texts']),
           compiled_minimum_tokens=min(map(len,paths)),candidate_lengths=list(map(len,paths)),
           bound_label=lang.get('bound_label'),cache_regime='cold_per_request',
           tokenizer_path_scope='one canonical path per text; XGrammar can admit alternative tokenizations')
        if c is not None and c.done:status,reason=c.status,c.reason
        elif policy=='deterministic':
            node=c.trie.root
            while not node.accepting:
                v,node=min(node.children.items(),key=lambda item:(item[1].distance,item[0]))
                inserted.append(v)
            c.observe(inserted);status,reason=c.status,'deterministic_shortest'
        elif policy=='sequence_score':
            feasible=[p for p in paths if len(p)<=cap]
            if not feasible:reason='infeasible_budget'
            else:
                base=prompt_ids+prefix_ids;sequences=[base+p for p in feasible]
                pad=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
                length=max(map(len,sequences))
                batch=torch.tensor([s+[pad]*(length-len(s)) for s in sequences],device=device)
                attention=torch.tensor([[1]*len(s)+[0]*(length-len(s)) for s in sequences],device=device)
                result['candidate_score_tokens']=sum(map(len,feasible))
                result['scoring_input_tokens']=sum(map(len,sequences))
                hook=model.register_forward_pre_hook(lambda *args:calls.__setitem__(0,calls[0]+1))
                logits=model(input_ids=batch,attention_mask=attention,use_cache=False).logits
                scores=[]
                for i,path in enumerate(feasible):
                    positions=logits[i,len(base)-1:len(base)+len(path)-1].float()
                    target=torch.tensor(path,device=device)
                    value=positions.log_softmax(-1).gather(1,target[:,None]).sum()
                    if not torch.isfinite(value):raise ConstraintFailure('invalid candidate sequence score')
                    scores.append(float(value))
                inserted=feasible[max(range(len(scores)),key=lambda i:scores[i])]
                result['candidate_scores']=scores
                status,reason='COMMIT','maximum_total_candidate_log_likelihood'
        elif cap==0:reason='zero_budget'
        else:
            inputs=torch.tensor([prompt_ids+prefix_ids],device=device)
            processors=LogitsProcessorList();trace=Trace(start);stoppers=StoppingCriteriaList([trace])
            if c is not None:processors.append(FiniteMask(c,start));stoppers.append(FiniteStop(c,start))
            if x is not None:x.start=start;processors.append(x);stoppers.append(XGrammarStop(x))
            hook=model.register_forward_pre_hook(lambda *args:calls.__setitem__(0,calls[0]+1))
            out=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                generation_config=config(model,tok,cap),logits_processor=processors,stopping_criteria=stoppers)
            generated=out[0,start:].tolist()
            if policy=='uniform':status,reason='SUBMIT','eos_or_cap'
            elif (c is not None and c.status=='COMMIT') or (x is not None and x.done):
                status,reason='COMMIT','accepted'
            else:reason='budget_or_eos_before_acceptance'
        text=decode(tok,prefix_ids+generated+inserted)
        # Independent final text certificate for every declared constrained commit.
        if status=='COMMIT' and text.rstrip() not in accepted:
            status,reason='ABSTAIN','final_certificate_failure'
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}';reason='constraint_failure' if isinstance(exc,ConstraintFailure) else 'runtime_error'
        if trace is not None:generated=trace.ids
        elif c is not None:generated=c.generated
        elif x is not None:generated=x.generated
        status='ABSTAIN'
    finally:
        if hook is not None:hook.remove()
    sync(device)
    text=decode(tok,prefix_ids+generated+inserted)
    result.update(status=status,reason=reason,error=error,generated_ids=generated,inserted_ids=inserted,
        returned_ids=prefix_ids+generated+inserted,returned_text=text,
        generated_tokens=len(generated),inserted_tokens=len(inserted),forward_calls=calls[0],
        effective_cap=cap,compile_ms=compiled_ms,request_ms=(time.perf_counter()-started)*1000,
        events=c.events if c is not None else [],oracle_checks=c.audit_checks if c is not None else 0,
        legal_tokens_removed=c.legal_tokens_removed if c is not None else 0,
        mask_steps=c.mask_steps if c is not None else 0,
        budget_scope='new suffix tokens; supplied prefix excluded, insertion separately counted')
    return result


class WrapperStop(StoppingCriteria):
    def __init__(self,c,start,policy):self.c,self.start,self.policy=c,start,policy
    def __call__(self,ids,scores,**kwargs):
        output=ids[0,self.start:].tolist()
        if self.policy=='early':
            self.c.last_ids=output
            if self.c.validate(self.c.text(output),bool(output and output[-1] in self.c.eos_ids)) is not None:
                self.c.set_mode('COMMIT','same_contract_early_return');return True
            return False
        done=self.c.observe(output)
        return done or (self.policy=='deterministic' and self.c.mode=='REPAIR')


@torch.inference_mode()
def run_wrapper(model,tok,case,job,device):
    from prototype.hf_adapter import ViabilityMask
    sync(device);started=time.perf_counter();calls=[0];hook=None;c=None
    generated=[];inserted=[];error=None;status='ABSTAIN';reason='uncertified_end';trace=None
    try:
        user=('Solve briefly. End with a final line exactly "#### <letter>" using '+''.join(case['options'])+
              '. Put a newline after the final line.\n\n'+case['question'])
        prompt=tok.apply_chat_template([{'role':'user','content':user}],tokenize=False,add_generation_prompt=True)
        inputs=tok(prompt,return_tensors='pt',add_special_tokens=False).to(device);start=inputs.input_ids.shape[1]
        eos=model.generation_config.eos_token_id;eos=eos if isinstance(eos,list) else [eos]
        c=CommitController(tok,'choice',''.join(case['options']),job['cap'],eos,reserve=16)
        processors=LogitsProcessorList();trace=Trace(start);stoppers=StoppingCriteriaList([trace])
        if job['policy']=='full':processors.append(ViabilityMask(c,start))
        if job['policy']!='uniform':stoppers.append(WrapperStop(c,start,job['policy']))
        hook=model.register_forward_pre_hook(lambda *args:calls.__setitem__(0,calls[0]+1))
        out=model.generate(**inputs,generation_config=config(model,tok,job['cap']),
            logits_processor=processors,stopping_criteria=stoppers)
        generated=out[0,start:].tolist()
        if job['policy']=='deterministic' and c.mode=='REPAIR':
            node=c.trie.root
            while not node.accepting:
                v,node=min(node.children.items(),key=lambda item:(item[1].distance,item[0]));inserted.append(v)
            c.observe(generated+inserted)
        if job['policy'] in {'uniform','early'} and c.mode!='COMMIT':status,reason='SUBMIT','eos_or_cap'
        else:status,reason=c.mode,c.reason
        if status not in {'COMMIT','SUBMIT','ABSTAIN'}:status,reason='ABSTAIN','uncertified_end'
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}';status='ABSTAIN';reason='runtime_error'
        if trace is not None:generated=trace.ids
    finally:
        if hook is not None:hook.remove()
    sync(device)
    return dict(status=status,reason=reason,error=error,returned_text=decode(tok,generated+inserted),
        generated_ids=generated,inserted_ids=inserted,returned_ids=generated+inserted,
        generated_tokens=len(generated),inserted_tokens=len(inserted),forward_calls=calls[0],
        effective_cap=job['cap'],compile_ms=None,request_ms=(time.perf_counter()-started)*1000,
        events=c.events if c is not None else [],provided_prefix_ids=[],
        bound_value=c.bound_value if c is not None else None,
        ended_with_eos=bool(generated and c is not None and generated[-1] in c.eos_ids),
        budget_scope='generated plus deterministic inserted output tokens, no free prefix')
