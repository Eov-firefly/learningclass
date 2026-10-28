"""Arithmetic audit of numbers reported in the manuscript, not a raw-data audit."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
from scipy.stats import beta

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manuscript',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    raw=args.manuscript.read_bytes();text=raw.decode()
    primary=[]
    for model,full,den,pct,grammar,den2,pct2 in re.findall(
        r'^\| (Qwen|Mistral) \| (\d+)/(\d+) \(([\d.]+)%\) \| (\d+)/(\d+) \(([\d.]+)%\)',text,re.M):
        full,den,grammar,den2=map(int,[full,den,grammar,den2])
        assert den==den2==96
        assert abs(full/den*100-float(pct))<.0051
        assert abs(grammar/den*100-float(pct2))<.0051
        bound=float(beta.ppf(1-.025/4,1,den))
        primary.append(dict(model=model,full_correct=full,grammar_correct=grammar,n=den,
            difference_pp=(full-grammar)/den*100,
            zero_discordance_conservative_975_half_width_pp=bound*100))
    assert len(primary)==2
    # Manually transcribed aggregate counts, guarded against changed source text.
    assert '84/96 versus 69/96 for Qwen and 65/96 versus 53/96 for Mistral' in text
    assert '54/96 for both Qwen policies and 41/96 versus 39/96 for Mistral' in text
    tight=[]
    for model,af,ag,qf,qg in [('Qwen',84,69,54,54),('Mistral',65,53,41,39)]:
        tight.append(dict(model=model,n=96,full_certified=af,grammar_certified=ag,
          full_correct=qf,grammar_correct=qg,coverage_difference_pp=(af-ag)/96*100,
          correct_commit_difference_pp=(qf-qg)/96*100,
          full_conditional_accuracy_pct=qf/af*100,grammar_conditional_accuracy_pct=qg/ag*100,
          full_wrong_certified=af-qf,grammar_wrong_certified=ag-qg,
          paired_wins_losses='not recoverable from aggregates',
          caution='conditional rates compare selected sets; not proof of harm on common accepted outputs'))
    timing=[]
    for wave,model,full,grammar,sequence in re.findall(
        r'^\| ([01]) \| (Qwen|Mistral) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|',text,re.M):
        full,grammar,sequence=map(float,[full,grammar,sequence])
        timing.append(dict(wave=int(wave),model=model,full_ms=full,grammar_ms=grammar,
            sequence_ms=sequence,full_minus_grammar_ms=full-grammar,
            full_to_sequence_time_ratio=full/sequence,
            scope='descriptive reported means only; no paired runtime uncertainty available'))
    assert len(timing)==4
    for name,rows in [('primary_arithmetic.csv',primary),('tight_budget_derived.csv',tight),('timing_derived.csv',timing)]:
        with (args.out/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
    report=dict(source_file=str(args.manuscript),source_sha256=hashlib.sha256(raw).hexdigest(),
      review_date='2026-10-28',scope='reported-number arithmetic only, no new inference and no raw statistical reproduction',
      primary=primary,tight_budget=tight,timing=timing,
      missing_evidence=['new raw JSONL archive','actual two-GPU wave runner and version/configuration',
          'all-policy all-budget summaries','paired outcome matrices','latency pairs and environment snapshots'])
    (args.out/'reported_number_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
