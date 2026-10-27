"""Gold-independent finite token controllers and an actual XGrammar adapter."""
import json
import torch
from transformers import LogitsProcessor,StoppingCriteria
from prototype.controller import RepairTrie,ConstraintFailure


class FiniteController:
    def __init__(self,paths,budget,prefix_ids,tokenizer,accepted,policy='full',audit=False):
        self.paths=paths;self.budget=budget;self.prefix_ids=prefix_ids
        self.tokenizer=tokenizer;self.accepted=accepted;self.policy=policy;self.audit=audit
        self.trie=RepairTrie(paths);self.generated=[];self.events=[]
        self.legal_tokens_removed=0;self.mask_steps=0;self.audit_checks=0
        self.done=False;self.status='ABSTAIN';self.reason='uncertified_end'
        if self.trie.root.distance>budget and policy in {'full','deterministic'}:
            self.done=True;self.reason='infeasible_budget'

    def text(self,generated):
        return self.tokenizer.decode(self.prefix_ids+generated,skip_special_tokens=True,clean_up_tokenization_spaces=False)

    def allowed(self,generated):
        node=self.trie.state(generated);remaining=self.budget-len(generated)
        legal=list(node.children)
        if self.policy=='grammar':return legal
        allowed=[v for v,c in node.children.items() if c.distance<=remaining-1]
        if self.audit:
            # Independent exhaustive token-path oracle, not the trie recurrence.
            oracle={p[len(generated)] for p in self.paths if p[:len(generated)]==generated
                    and len(p)>len(generated) and len(p)-len(generated)<=remaining}
            if oracle!=set(allowed):raise ConstraintFailure('independent viability oracle disagrees')
            self.audit_checks+=1
        self.mask_steps+=1;self.legal_tokens_removed+=len(legal)-len(allowed)
        self.events.append({'step':len(generated),'remaining':remaining,'distance':node.distance,
                            'legal':legal,'allowed':allowed})
        return allowed

    def observe(self,generated):
        self.generated=list(generated)
        if self.trie.state(generated).accepting:
            if self.text(generated).rstrip() not in self.accepted:
                raise ConstraintFailure('final certificate mismatch')
            self.done=True;self.status='COMMIT';self.reason='accepted'
        return self.done


class FiniteMask(LogitsProcessor):
    def __init__(self,c,start):self.c,self.start=c,start
    def __call__(self,ids,scores):
        generated=ids[0,self.start:].tolist();self.c.generated=generated
        allowed=self.c.allowed(generated)
        if not allowed:raise ConstraintFailure('empty legal support')
        values=scores[:,allowed]
        if torch.isnan(values).any() or torch.isposinf(values).any() or not torch.isfinite(values).any():
            raise ConstraintFailure('invalid or zero model support')
        result=torch.full_like(scores,-float('inf'));result[:,allowed]=values
        return result


class FiniteStop(StoppingCriteria):
    def __init__(self,c,start):self.c,self.start=c,start
    def __call__(self,ids,scores,**kwargs):return self.c.observe(ids[0,self.start:].tolist())


class XGrammarRuntime:
    def __init__(self,tokenizer,vocab_size,eos):
        import xgrammar as xgr
        self.xgr=xgr;self.vocab_size=vocab_size
        info=xgr.TokenizerInfo.from_huggingface(tokenizer,vocab_size=vocab_size,stop_token_ids=eos)
        self.compiler=xgr.GrammarCompiler(info,max_threads=2,cache_enabled=False)

    def controller(self,suffixes):
        grammar='root ::= '+' | '.join(json.dumps(s,ensure_ascii=False) for s in suffixes)
        compiled=self.compiler.compile_grammar(grammar)
        return XGrammarController(self.xgr,compiled,self.vocab_size)


class XGrammarController(LogitsProcessor,StoppingCriteria):
    def __init__(self,xgr,compiled,vocab_size):
        self.xgr=xgr;self.matcher=xgr.GrammarMatcher(compiled,terminate_without_stop_token=True)
        self.bits=xgr.allocate_token_bitmask(1,vocab_size)
        self.start=0;self.accepted_count=0;self.generated=[];self.done=False

    def advance(self,ids):
        generated=ids[0,self.start:].tolist();self.generated=generated
        for v in generated[self.accepted_count:]:
            if not self.matcher.accept_token(v):raise ConstraintFailure('XGrammar rejected emitted token')
            self.accepted_count+=1
        self.done=self.matcher.is_terminated()

    def __call__(self,ids,scores):
        self.advance(ids)
        if self.done:return scores
        self.matcher.fill_next_token_bitmask(self.bits)
        self.xgr.apply_token_bitmask_inplace(scores,self.bits.to(scores.device))
        if not torch.isfinite(scores).any():raise ConstraintFailure('XGrammar empty score support')
        return scores


class XGrammarStop(StoppingCriteria):
    def __init__(self,c):self.c=c
    def __call__(self,ids,scores,**kwargs):self.c.advance(ids);return self.c.done
