import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
MODEL_SPECS={
 'qwen':{'id':'Qwen/Qwen2.5-7B-Instruct-1M','revision':'e28526f7bb80e2a9c8af03b831a9af3812f18fba'},
 'mistral':{'id':'mistralai/Mistral-7B-Instruct-v0.3','revision':'c170c708c41dac9275d15a8fff4eca08d52bab71'},
}
POLICIES=['uniform','grammar','full','deterministic','xgrammar']
BUDGETS=[8,24,64]

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def load_public(split='eval'):
    manifest=json.loads((ROOT/'data/manifest.json').read_text())
    for name,h in manifest['files'].items():
        # Workers do not read the scoring file, including for checksum verification.
        if name=='public.jsonl':
            assert hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()==h
    rows=[json.loads(l) for l in (ROOT/'data/public.jsonl').read_text().splitlines()]
    assert all(set(r)=={'question_id','split','question','options'} for r in rows)
    return [r for r in rows if r['split']==split]

def record_id(case):return case['question_id'].split(':')[-1][:8]

def artifacts(case,encoding):
    return {label:json.dumps({'id':record_id(case),'answer':label if encoding=='label' else text},
             separators=(',',':'),ensure_ascii=False)+'\n' for label,text in case['options'].items()}

def lcp(paths):
    n=min(map(len,paths),default=0);i=0
    while i<n and len({p[i] for p in paths})==1:i+=1
    return paths[0][:i] if paths else []

def compile_case(tokenizer,case,encoding):
    texts=artifacts(case,encoding)
    paths=[tokenizer.encode(t,add_special_tokens=False) for t in texts.values()]
    decode=lambda ids:tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)
    if any(decode(p)!=t for p,t in zip(paths,texts.values())):
        raise ValueError('full artifact tokenizer round-trip failed')
    common=lcp(paths);prefix=decode(common)
    if not common or any(len(p)==len(common) for p in paths):raise ValueError('no nonempty unbound-field completion')
    suffixes=[p[len(common):] for p in paths]
    if any(not t.startswith(prefix) for t in texts.values()):raise ValueError('decoded common prefix is incompatible')
    return dict(prefix_ids=common,prefix=prefix,paths=suffixes,texts=texts,
                suffix_strings=[t[len(prefix):] for t in texts.values()])

def instruction(case,encoding):
    if encoding=='label':answer='the single option letter'
    else:answer='the exact full text of the selected option, copied without changes'
    return (f'Answer the science question. Return ONLY a minified JSON object in key order id,answer. '
       f'The id must be "{record_id(case)}" and answer must be {answer}. '
       'Do not explain. Finish the object and add a newline.\n\n'+case['question'])

def chat_prompt(tokenizer,case,encoding):
    return tokenizer.apply_chat_template([{'role':'user','content':instruction(case,encoding)}],
              tokenize=False,add_generation_prompt=True)

def validate_artifact(text,case,encoding):
    # Exact finite textual contract, allowing trailing whitespace only.
    return next((label for label,t in artifacts(case,encoding).items() if text.rstrip()==t.rstrip()),None)

def jobs(model,shard=0,shards=1,split='eval',suite='all'):
    rows=load_public(split);result=[]
    def add(case,track,policy,encoding,cap,repeat=0,condition='ordinary'):
        job=dict(question_id=case['question_id'],model=model,split=split,track=track,
          policy=policy,encoding=encoding,cap=cap,repeat=repeat,condition=condition)
        job['request_id']=digest(job)[:24];result.append(job)
    for index,case in enumerate(rows):
        if index%shards!=shard:continue
        if suite in {'all','main'}:
            for encoding in ['label','option_text']:
                for cap in BUDGETS:
                    for policy in POLICIES:add(case,'matched',policy,encoding,cap)
            # Strong finite-choice baseline at the fixed primary setting only.
            add(case,'matched','sequence_score','option_text',24)
        if suite in {'all','e2e'} and index<32:
            for policy in ['uniform','early','full','deterministic']:add(case,'wrapper_e2e',policy,'label',128)
        if suite in {'all','timing'} and index<16:
            for repeat in range(3):
                for policy in ['uniform','grammar','full','xgrammar','sequence_score']:
                    add(case,'timing',policy,'option_text',24,repeat)
        if suite in {'all','format'} and index<16:
            for condition in ['below','exact','above']:
                for policy in ['grammar','full','deterministic']:
                    add(case,'format',policy,'label',0,condition=condition)
    # Deterministic shuffled job order, interleaving policies/budgets.
    result.sort(key=lambda j:digest({'order_seed':20261027,'job':j}))
    return result
