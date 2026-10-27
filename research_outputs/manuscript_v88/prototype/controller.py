"""Finite token-language prototype for budget-viable commitment.

Uses the explicitly named v8 reference wrapper heuristic, not a complete document
grammar. Gold answers are never inputs to the controller.
"""
from dataclasses import dataclass, field
import re
from .reference_contracts import parse, same_answer


class ConstraintFailure(RuntimeError):
    pass


@dataclass
class Node:
    children: dict = field(default_factory=dict)
    accepting: bool = False
    distance: float = float('inf')


class RepairTrie:
    def __init__(self, paths):
        self.root=Node()
        for path in paths:
            node=self.root
            for token in path:node=node.children.setdefault(int(token),Node())
            node.accepting=True
        def distances(n):
            child=[distances(c)+1 for c in n.children.values()]
            n.distance=min(([0] if n.accepting else [])+child,default=float('inf'))
            return n.distance
        distances(self.root)

    def state(self, emitted):
        node=self.root
        for v in emitted:
            if v not in node.children:raise ConstraintFailure('repair escaped its compiled token language')
            node=node.children[v]
        return node

    def allowed(self, emitted, remaining):
        n=self.state(emitted)
        return [v for v,c in n.children.items() if c.distance<=remaining-1]


def candidate_suffixes(text):
    """Conservative proposal builder for a few common wrappers.

    The external acceptance check filters every candidate. Unsupported or
    mismatched wrappers yield no path, never an invented answer.
    """
    if re.search(r'\\(?:begin|end)\{',text):return []
    stack=[]
    for m in re.finditer(r'\\\[|\\\]|\\\(|\\\)|(?<!\\)\$\$',text):
        s=m.group()
        if s in [r'\[',r'\(']:stack.append(s)
        elif s=='$$':
            if stack and stack[-1]=='$$':stack.pop()
            else:stack.append(s)
        else:
            expected=r'\[' if s==r'\]' else r'\('
            if not stack or stack.pop()!=expected:return []
    fence=None
    for line in text.splitlines():
        m=re.match(r'^\s*(`{3,}|~{3,})(.*)$',line)
        if not m:continue
        token,rest=m.groups()
        if fence:
            if token[0]==fence[0] and len(token)>=len(fence) and not rest.strip():fence=None
        else:fence=token
    close={r'\[':r'\]',r'\(':r'\)','$$':'$$'}
    closers=[close[s] for s in reversed(stack)]
    if fence:closers.append(fence)
    if not closers:return []
    a='\n'.join(closers)+'\n'
    variants=[a,'\n'+a]
    # This is a finite proposal set, not a complete grammar compiler.
    if fence and len(closers)>1:variants.append('\n'.join([fence]+closers[:-1])+'\n')
    return list(dict.fromkeys(variants))


class CommitController:
    def __init__(self,tokenizer,kind,choices,cap,eos_ids,reserve=16):
        if cap<1 or reserve<0 or reserve>=cap:raise ValueError('Require 0 <= reserve < cap')
        self.tokenizer,self.kind,self.choices=tokenizer,kind,choices
        self.cap,self.reserve,self.eos_ids=cap,reserve,set(eos_ids)
        self.mode='DRAFT';self.reason=None;self.last_ids=[]
        self.bound_value=None;self.checkpoint=None;self.trie=None
        self.events=[]

    def text(self,ids):
        return self.tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)

    def set_mode(self,mode,reason):
        self.mode,self.reason=mode,reason
        self.events.append(dict(step=len(self.last_ids),mode=mode,reason=reason))

    def validate(self,text,eos=False):
        value=parse(text,self.kind,self.choices,eos=eos,contract='closure_balanced')
        return value

    def observe(self,ids):
        self.last_ids=list(ids)
        if self.mode in {'COMMIT','ABSTAIN'}:return True
        text=self.text(ids);eos=bool(ids and ids[-1] in self.eos_ids)
        value=self.validate(text,eos)
        if self.mode=='REPAIR':
            node=self.trie.state(ids[self.checkpoint:])
            if eos:raise ConstraintFailure('EOS was emitted inside an unfinished repair')
            if node.accepting:
                if value is None or not same_answer(value,self.bound_value,self.kind):
                    raise ConstraintFailure('compiled repair failed the independent final certificate')
                self.set_mode('COMMIT','repair_and_certificate_complete');return True
            if len(ids)>=self.cap:
                self.set_mode('ABSTAIN','repair_budget_exhausted');return True
            return False
        if value is not None:
            self.bound_value=value;self.set_mode('COMMIT','already_accepted');return True
        if eos:
            self.set_mode('ABSTAIN','invalid_natural_eos');return True
        # A candidate is locally complete under the strict marker rule, but not
        # globally accepted under the closure-balanced reference contract.
        candidate=parse(text,self.kind,self.choices,eos=False,contract='strict')
        if candidate is not None:
            self.bound_value=candidate;self.checkpoint=len(ids)
            paths=[]
            for suffix in candidate_suffixes(text):
                extra=self.tokenizer.encode(suffix,add_special_tokens=False)
                if not extra or any(v in self.eos_ids for v in extra):continue
                decoded=self.text(ids+extra)
                # Context round trip is verified, never assumed from standalone tokens.
                if decoded!=text+suffix:continue
                end=self.validate(decoded,False)
                if end is not None and same_answer(end,candidate,self.kind):paths.append(extra)
            if not paths:
                self.set_mode('ABSTAIN','no_verified_repair_language');return True
            self.trie=RepairTrie(paths)
            if self.trie.root.distance>self.cap-len(ids):
                self.set_mode('ABSTAIN','repair_not_budget_viable');return True
            self.set_mode('REPAIR','candidate_bound_with_verified_paths');return False
        if len(ids)>=self.cap-self.reserve:
            self.set_mode('ABSTAIN','no_candidate_at_draft_deadline');return True
        return False

    def allowed_tokens(self,ids):
        self.last_ids=list(ids)
        if self.mode!='REPAIR':return None
        allowed=self.trie.allowed(ids[self.checkpoint:],self.cap-len(ids))
        if not allowed:raise ConstraintFailure('empty budget-viable token support')
        return allowed


def shortest_verified_repair(tokenizer,ids,kind,choices,cap):
    """Required no-new-model-call baseline, using exactly the same compiler.

    For the format-only special case this preserves the same candidate value
    and chooses the shortest compiled suffix. Inserted tokens are not GPU-
    generated tokens and must be reported separately.
    """
    c=CommitController(tokenizer,kind,choices,cap,[tokenizer.eos_token_id],reserve=0)
    c.observe(ids)
    added=[]
    if c.mode=='REPAIR':
        node=c.trie.root
        while not node.accepting:
            token,child=min(node.children.items(),key=lambda kv:(kv[1].distance,kv[0]))
            added.append(token);node=child
        c.observe(list(ids)+added)
    return dict(status=c.mode,reason=c.reason,bound_value=c.bound_value,
        committed_text=c.text(c.last_ids) if c.mode=='COMMIT' else None,
        inserted_ids=added,inserted_tokens=len(added),new_model_calls=0)
