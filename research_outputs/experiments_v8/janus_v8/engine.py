"""HF generate callbacks, with timing and trace modes intentionally separated."""
import time
import torch
from transformers import LogitsProcessor, LogitsProcessorList, StoppingCriteria, StoppingCriteriaList, GenerationConfig
from .contracts import parse, wrapper_balanced, EntropyGate, score

POLICIES = {'uniform','boundary_observe','complete','entropy_observe','structured_complete',
            'conjunction','latched_buffer','entropy_uniform','uniform_trace'}


class Monitor(LogitsProcessor):
    def __init__(self, gate, trace=False):
        self.gate, self.trace = gate, trace
        self.step = 0
        self.current_entropy = None
        self.gate_open = False

    def __call__(self, input_ids, scores):
        self.step += 1
        p = torch.softmax(scores.float(), dim=-1)
        h = -(p * torch.log(p + 1e-12)).sum(dim=-1)
        self.current_entropy = float(h.item())  # Explicit synchronization is part of this implementation.
        self.gate_open = self.gate.update(self.step, self.current_entropy)
        return scores  # Never modifies logits.


class Boundary(StoppingCriteria):
    def __init__(self, tokenizer, prompt_length, kind, choices, policy, eos_ids, monitor=None):
        self.tokenizer, self.prompt_length = tokenizer, prompt_length
        self.kind, self.choices, self.policy = kind, choices, policy
        self.eos_ids, self.monitor = set(eos_ids), monitor
        self.trace = []
        self.buffer_length = None
        self.triggered = False

    def __call__(self, input_ids, scores, **kwargs):
        ids = input_ids[0,self.prompt_length:].tolist()
        step = len(ids)
        eos = bool(ids and ids[-1] in self.eos_ids)
        text = self.tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        pred = parse(text,self.kind,self.choices,eos=False)
        complete = pred is not None
        if complete and not eos and self.buffer_length is None:
            self.buffer_length = step
        gate_open = bool(self.monitor and self.monitor.gate_open)
        if self.policy == 'uniform_trace':
            assert self.monitor is not None and self.monitor.step == step
            self.trace.append({'step':step,'entropy':self.monitor.current_entropy,'completion':complete,
                               'prediction':pred,'wrapper_balanced':wrapper_balanced(text),'eos':eos})
        if eos:
            return False  # Natural EOS takes priority over a policy event.
        decision = False
        if self.policy in {'complete','entropy_observe'}:
            decision = complete
        elif self.policy == 'structured_complete':
            decision = parse(text,self.kind,self.choices,eos=False,contract='closure_balanced') is not None
        elif self.policy == 'conjunction':
            decision = complete and gate_open
        elif self.policy == 'latched_buffer':
            decision = self.buffer_length is not None and gate_open
        self.triggered = self.triggered or decision
        return bool(decision)


def sync(device):
    if str(device).startswith('cuda'):
        torch.cuda.synchronize(device)


@torch.inference_mode()
def generate_one(model, tokenizer, case, policy, cap, entropy, device):
    if policy not in POLICIES:
        raise ValueError(policy)
    eos_ids = model.generation_config.eos_token_id
    eos_ids = [eos_ids] if isinstance(eos_ids,int) else list(eos_ids or [])
    if not eos_ids:
        raise ValueError('Explicit model EOS IDs required')
    sync(device)
    start = time.perf_counter()
    inputs = tokenizer(case['prompt'],return_tensors='pt',add_special_tokens=False).to(device)
    prompt_length = inputs.input_ids.shape[1]
    if prompt_length != case['prompt_tokens']:
        raise ValueError(f"Prompt token mismatch for {case['question_id']}: {prompt_length} != {case['prompt_tokens']}")
    needs_entropy = policy in {'entropy_observe','conjunction','latched_buffer','entropy_uniform','uniform_trace'}
    monitor = Monitor(EntropyGate(**entropy),trace=policy=='uniform_trace') if needs_entropy else None
    boundary = Boundary(tokenizer,prompt_length,case['kind'],case['choices'],policy,eos_ids,monitor) if policy != 'uniform' else None
    processors = LogitsProcessorList([monitor] if monitor else [])
    criteria = StoppingCriteriaList([boundary] if boundary else [])
    config = GenerationConfig(
        max_new_tokens=cap, min_new_tokens=0, do_sample=False, num_beams=1,
        use_cache=True, repetition_penalty=1.0, eos_token_id=eos_ids,
        bos_token_id=tokenizer.bos_token_id,
        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else eos_ids[0],
        forced_eos_token_id=None, return_dict_in_generate=False,
    )
    sync(device)
    gen_start = time.perf_counter()
    output = model.generate(**inputs,generation_config=config,logits_processor=processors,stopping_criteria=criteria)
    sync(device)
    gen_end = time.perf_counter()
    generated = output[0,prompt_length:].tolist()
    eos = bool(generated and generated[-1] in eos_ids)
    reason = 'eos' if eos else 'policy' if boundary and boundary.triggered else 'cap'
    # A buffered policy returns its earliest completed prefix even if fallback EOS/cap was needed.
    returned = generated[:boundary.buffer_length] if policy=='latched_buffer' and boundary.buffer_length else generated
    text = tokenizer.decode(returned,skip_special_tokens=True,clean_up_tokenization_spaces=False)
    end = time.perf_counter()
    returned_eos = bool(returned and returned[-1] in eos_ids)
    result = dict(policy=policy,generated_ids=generated,returned_ids=returned,text=text,
                  actual_generated_tokens=len(generated),returned_tokens=len(returned),
                  prompt_tokens=prompt_length,stop_reason=reason,returned_eos=returned_eos,
                  generation_seconds=gen_end-gen_start,end_to_end_seconds=end-start,
                  diagnostic_only=policy=='uniform_trace',
                  original_uniform_ids_equal=generated==case.get('original_output_ids'),
                  scores={c:score(text,case['kind'],case['gold'],case['choices'],returned_eos,c)
                          for c in ['strict','closure_tolerant','closure_balanced','wrapper_balanced_strict','last_marked']})
    if boundary and policy=='uniform_trace':
        result['trace'] = boundary.trace
    if policy=='latched_buffer':
        result['buffer_length'] = boundary.buffer_length
    return result
