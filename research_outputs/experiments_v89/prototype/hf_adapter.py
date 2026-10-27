"""Real Transformers generate integration. Prototype, no speed claims."""
import time
import torch
from transformers import GenerationConfig,LogitsProcessor,LogitsProcessorList,StoppingCriteria,StoppingCriteriaList
from .controller import CommitController,ConstraintFailure


class ViabilityMask(LogitsProcessor):
    def __init__(self,controller,prompt_len):self.controller,self.prompt_len=controller,prompt_len
    def __call__(self,input_ids,scores):
        if scores.shape[0]!=1:raise ValueError('Prototype supports batch size one only')
        allowed=self.controller.allowed_tokens(input_ids[0,self.prompt_len:].tolist())
        if allowed is None:return scores
        values=scores[:,allowed]
        if torch.isnan(values).any() or torch.isposinf(values).any():
            raise ConstraintFailure('invalid scores on the viable support')
        if not torch.isfinite(values).any():
            raise ConstraintFailure('no positive model support on viable tokens')
        masked=torch.full_like(scores,-float('inf'))
        masked[:,allowed]=values
        return masked


class CommitStop(StoppingCriteria):
    def __init__(self,controller,prompt_len):self.controller,self.prompt_len=controller,prompt_len
    def __call__(self,input_ids,scores,**kwargs):
        return self.controller.observe(input_ids[0,self.prompt_len:].tolist())


def sync(device):
    if str(device).startswith('cuda'):torch.cuda.synchronize(device)


@torch.inference_mode()
def run_one(model,tokenizer,prompt,kind,choices='',cap=512,reserve=16,device='cpu'):
    eos=model.generation_config.eos_token_id
    eos=[eos] if isinstance(eos,int) else list(eos or [])
    if not eos:raise ValueError('Model EOS IDs required')
    c=CommitController(tokenizer,kind,choices,cap,eos,reserve)
    sync(device);start=time.perf_counter()
    inputs=tokenizer(prompt,return_tensors='pt',add_special_tokens=False).to(device)
    plen=inputs.input_ids.shape[1];calls=[0]
    hook=model.register_forward_pre_hook(lambda *unused:calls.__setitem__(0,calls[0]+1))
    error=None
    try:
        output=model.generate(**inputs,generation_config=GenerationConfig(max_new_tokens=cap,do_sample=False,
            num_beams=1,use_cache=True,repetition_penalty=1.0,eos_token_id=eos,
            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else eos[0],
            forced_eos_token_id=None),
            logits_processor=LogitsProcessorList([ViabilityMask(c,plen)]),
            stopping_criteria=StoppingCriteriaList([CommitStop(c,plen)]))
        ids=output[0,plen:].tolist()
        if c.mode not in {'COMMIT','ABSTAIN'}:
            c.last_ids=ids;c.set_mode('ABSTAIN','uncertified_generation_end')
    except ConstraintFailure as exc:
        error=str(exc);ids=c.last_ids
        c.set_mode('ABSTAIN','constraint_failure')
    except RuntimeError as exc:
        error=f'{type(exc).__name__}: {exc}';ids=c.last_ids
        c.set_mode('ABSTAIN','runtime_error')
    finally:hook.remove()
    sync(device);elapsed=time.perf_counter()-start
    raw_text=c.text(ids)
    return dict(status=c.mode,reason=c.reason,committed_text=raw_text if c.mode=='COMMIT' else None,
        generated_text=raw_text,generated_ids=ids,actual_generated_tokens=len(ids),
        bound_value=c.bound_value,repair_tokens=len(ids)-c.checkpoint if c.checkpoint is not None else 0,
        forward_calls=calls[0],end_to_end_seconds=elapsed,events=c.events,error=error,
        contract='closure_balanced_v8_reference',prototype=True)
