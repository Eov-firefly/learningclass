"""Reported-number arithmetic only; does not verify raw outputs or archive hashes."""
from pathlib import Path
import argparse, hashlib, json, re, sys

def main():
 p=argparse.ArgumentParser();p.add_argument('--tex',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--analysis-code',type=Path,required=True);a=p.parse_args()
 sys.path.insert(0,str(a.analysis_code));from analyze_control import paired_bounds
 text=a.tex.read_text();section=text.split('\\subsection{6.4. Single-GPU exploratory controllability study}')[1].split('\\subsection{6.5.')[0]
 found=re.findall(r'^(Qwen|Mistral) & (\d+)/64 & (\d+)/(\d+) & (\d+)/(\d+) & (\d+)/64 & (\d+)/64',section,re.M)
 assert len(found)==2
 intervals=[(2.16,39.39),(-4.42,36.02)];result=[]
 for index,(model,feas,full,fd,gram,gd,fc,gc) in enumerate(found):
  feas,full,fd,gram,gd,fc,gc=map(int,[feas,full,fd,gram,gd,fc,gc]);assert feas==fd==gd and full==feas
  low,high=paired_bounds(full-gram,0,feas,alpha=.025)
  assert abs(low*100-intervals[index][0])<.0051 and abs(high*100-intervals[index][1])<.0051
  result.append(dict(model=model,all_requests=64,initially_feasible=feas,initially_infeasible=64-feas,
   full_certified=full,grammar_certified=gram,feasible_difference_pp=100*(full-gram)/feas,
   conservative_paired_975_ci_pp=[100*low,100*high],full_correct=fc,grammar_correct=gc,
   full_wrong_certified=full-fc,grammar_wrong_certified=gram-gc,
   full_conditional_accuracy=fc/full,grammar_conditional_accuracy=gc/gram,
   extra_correct_if_reported_preservation_holds=fc-gc,extra_wrong_if_reported_preservation_holds=full-fc-gram+gc))
 abstract=text.split('\\section{Abstract}')[1].split('Keywords:')[0]
 abstract=re.sub(r'\\label\{[^}]*\}', '',abstract)
 report=dict(date='2026-10-31',source=str(a.tex),source_sha256=hashlib.sha256(a.tex.read_bytes()).hexdigest(),
  scope='source-number arithmetic; no raw traces, archive checksum verification or GPU replication',
  paired_intervals_assume='reported subset preservation and zero paired certification losses are correct',
  abstract_whitespace_word_count=len(abstract.split()),single_gpu=result)
 a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
