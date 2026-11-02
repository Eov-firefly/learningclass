"""Answer retention against already-certified Grammar outputs; offline only."""
import argparse,csv,hashlib,json
from pathlib import Path


def read(path):
    data=path.read_bytes()
    if data and not data.endswith(b'\n'):raise ValueError('unfinished JSONL')
    return [json.loads(l) for l in data.splitlines()]


def main():
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();protocol=json.loads((a.study/'protocol/protocol.json').read_text())
    for name,expected in protocol['files'].items():
        assert hashlib.sha256((a.study/'protocol'/name).read_bytes()).hexdigest()==expected
    public={r['question_id']:r for r in read(a.study/'protocol/public.jsonl')}
    gold={r['question_id']:r['gold'] for r in read(a.study/'protocol/scoring.jsonl')}
    def prediction(r):
        c=public[r['question_id']];ident=c['question_id'].split(':')[-1][:8]
        for label,text in c['options'].items():
            artifact=json.dumps({'id':ident,'answer':text},separators=(',',':'),ensure_ascii=False)+'\n'
            if r['status'] in {'COMMIT','SUBMIT'} and r['returned_text'].rstrip()==artifact.rstrip():return label
        return None
    data=[];seen=set()
    for file in sorted((a.study/'run/execute').glob('*.raw.jsonl')):
        for raw in read(file):
            assert raw['request_id'] not in seen;seen.add(raw['request_id'])
            raw['pred']=prediction(raw);raw['correct']=raw['pred']==gold[raw['question_id']]
            data.append(raw)
    assert len(data)==1920
    result=[]
    for model in ['qwen','mistral']:
        for condition in ['fixed8','exact_min','wide']:
            cell=[r for r in data if r['model']==model and r['condition']==condition]
            ref={r['question_id']:r for r in cell if r['policy']=='grammar' and r['pred'] is not None}
            for policy in ['full','sequence_score','deterministic','xgrammar']:
                alt={r['question_id']:r for r in cell if r['policy']==policy};assert len(alt)==64
                retained=sum(alt[q]['pred']==g['pred'] for q,g in ref.items())
                lost=sum(g['correct'] and not alt[q]['correct'] for q,g in ref.items())
                gained=sum(not g['correct'] and alt[q]['correct'] for q,g in ref.items())
                row=dict(model=model,condition=condition,policy=policy,n_grammar_certified=len(ref),
                    n_grammar_correct=sum(r['correct'] for r in ref.values()),
                    n_alternative_certified=sum(alt[q]['pred'] is not None for q in ref),
                    n_same_certified_answer=retained,n_previous_correct_lost=lost,n_grammar_wrong_corrected=gained)
                if policy=='full':assert retained==len(ref) and lost==0
                result.append(row)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('w',newline='') as f:
        w=csv.DictWriter(f,list(result[0]),lineterminator='\n');w.writeheader();w.writerows(result)
    print('Retained certified Grammar answers over all repeated model/condition cells:')
    for policy in ['full','sequence_score']:
        rs=[r for r in result if r['policy']==policy]
        print(policy,sum(r['n_same_certified_answer'] for r in rs),'/',sum(r['n_grammar_certified'] for r in rs),
              'previous correct lost:',sum(r['n_previous_correct_lost'] for r in rs),
              'Grammar-wrong corrected:',sum(r['n_grammar_wrong_corrected'] for r in rs))


if __name__=='__main__':main()
