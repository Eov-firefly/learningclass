"""One entry point for existing-result analysis, validation and a readable report."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_csv(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))

def check_inputs(public,scoring,manifest):
    spec=json.loads(manifest.read_text())
    for key,path in [('public.jsonl',public),('scoring.jsonl',scoring)]:
        if sha(path)!=spec['files'][key]:raise ValueError('input checksum mismatch: '+str(path))
    records=[json.loads(l) for l in public.read_text().splitlines()]
    ids=[r['question_id'] for r in records]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate public question IDs')
    eval_ids={r['question_id'] for r in records if r['split']=='eval'}
    if eval_ids!=set(spec['ids']['eval']):raise ValueError('evaluation manifest differs from public inputs')
    labels=[json.loads(l) for l in scoring.read_text().splitlines()]
    if len(labels)!=len(records) or {r['question_id'] for r in labels}!=set(ids):
        raise ValueError('scoring IDs do not match public records')
    return spec,eval_ids

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True,help='Completed extracted run directory, not a ZIP')
    p.add_argument('--out',type=Path,required=True,help='New empty output directory')
    p.add_argument('--public',type=Path,default=ROOT/'data/public.jsonl')
    p.add_argument('--scoring',type=Path,default=ROOT/'data/scoring.jsonl')
    p.add_argument('--manifest',type=Path,default=ROOT/'data/manifest.json')
    p.add_argument('--model-manifest',type=Path,help='Optional old prepare.py model_manifest.json for local tokenizer paths')
    p.add_argument('--qwen-tokenizer');p.add_argument('--mistral-tokenizer')
    p.add_argument('--require-distances',action='store_true',help='Fail review checks if all Full/Grammar distances cannot be reconstructed')
    a=p.parse_args()
    for name in ['run','out','public','scoring','manifest']:
        setattr(a,name,getattr(a,name).resolve())
    if not a.run.is_dir():p.error('--run must be an existing extracted directory')
    if a.out.exists() and any(a.out.iterdir()):p.error('--out must be empty; keep previous analysis and choose a new directory')
    if a.model_manifest:
        models=json.loads(a.model_manifest.read_text())
        for model in ['qwen','mistral']:
            if not getattr(a,model+'_tokenizer'):setattr(a,model+'_tokenizer',models.get(model,{}).get('local_path'))
    if a.require_distances and not any([a.qwen_tokenizer,a.mistral_tokenizer]):
        p.error('--require-distances needs tokenizer paths or --model-manifest')
    spec,eval_ids=check_inputs(a.public,a.scoring,a.manifest)
    a.out.mkdir(parents=True,exist_ok=True)
    sources={f.name:sha(f) for f in ROOT.glob('*.py')}
    config=dict(started_utc=datetime.now(timezone.utc).isoformat(),run=str(a.run),out=str(a.out),
        source_hashes=sources,inputs={str(f):sha(f) for f in [a.public,a.scoring,a.manifest]},
        tokenizer_paths={m:getattr(a,m+'_tokenizer') for m in ['qwen','mistral']},
        require_distances=a.require_distances,stage='distance' if any([a.qwen_tokenizer,a.mistral_tokenizer]) else 'basic',
        scope='post hoc matched-prefix control analysis; no new model inference; no confirmation claim')
    (a.out/'analysis_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    cmd=[sys.executable,str(ROOT/'analyze_control.py'),'--run',str(a.run),'--public',str(a.public),
         '--scoring',str(a.scoring),'--out',str(a.out)]
    for model in ['qwen','mistral']:
        local=getattr(a,model+'_tokenizer')
        if local:cmd+=['--'+model+'-tokenizer',local]
    env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=''
    subprocess.run(cmd,cwd=ROOT,env=env,check=True)
    summaries=read_csv(a.out/'control_summary.csv');pairs=read_csv(a.out/'trajectory_preservation.csv')
    actual=set();n_rows=0
    for line in (a.out/'control_scored.jsonl').open():
        r=json.loads(line);n_rows+=1
        actual.add((r['model'],r['policy'],r['encoding'],r['cap'],r['question_id']))
    expected={(m,p,e,b,q) for m in ['qwen','mistral'] for p in ['uniform','grammar','full','deterministic','xgrammar']
              for e in ['label','option_text'] for b in [8,24,64] for q in eval_ids}
    expected|={(m,'sequence_score','option_text',24,q) for m in ['qwen','mistral'] for q in eval_ids}
    core={k for k in expected if k[1] in {'full','grammar'}}
    missing_core=core-actual;extra=actual-expected
    core_summary=[r for r in summaries if r['policy'] in {'full','grammar'}]
    exact_checked=sum(int(r['exact_distance_checked']) for r in core_summary)
    exact_required=sum(int(r['n']) for r in core_summary)
    reconstruction_errors=sum(int(r['distance_reconstruction_errors']) for r in core_summary)
    context_unknown=sum(int(r['context_missing']) for r in pairs)
    context_bad=sum(int(r['context_mismatches']) for r in pairs)
    lost_certified=sum(int(r['lost_certified']) for r in pairs)
    lost_correct=sum(int(r['lost_correct'] or 0) for r in pairs)
    missing_token_evidence=sum(int(r['ids_missing']) for r in pairs)
    feasibility_unknown=sum(int(r['n'])-int(r['initial_feasibility_known']) for r in core_summary)
    inference_errors=sum(int(r['inference_errors']) for r in core_summary)
    prefix_escapes=sum(int(r['prefix_language_escapes'] or 0) for r in core_summary)
    checks=dict(stage=config['stage'],expected_matched_records=len(expected),actual_matched_records=n_rows,
      matched_grid_complete=(actual==expected and n_rows==len(expected)),missing_core_count=len(missing_core),
      unexpected_records=len(extra),missing_core_examples=[list(k) for k in sorted(missing_core)[:5]],
      exact_distance_checked=exact_checked,exact_distance_required=exact_required,
      distance_reconstruction_errors=reconstruction_errors,pair_context_unknown=context_unknown,
      pair_context_mismatches=context_bad,missing_success_token_evidence=missing_token_evidence,
      lost_certified=lost_certified,lost_correct=lost_correct,
      initial_feasibility_unknown=feasibility_unknown,inference_errors=inference_errors,
      reconstructed_prefix_language_escapes=prefix_escapes,
      note='A review flag is not permission to delete an unfavorable sample. NA is unavailable evidence, not zero.',
      no_gpu_inference=True)
    review_needed=bool(missing_core or extra or context_unknown or context_bad or missing_token_evidence or reconstruction_errors
                       or feasibility_unknown or inference_errors or prefix_escapes)
    if a.require_distances and exact_checked!=exact_required:review_needed=True
    if lost_certified or lost_correct:review_needed=True
    checks['status']='REVIEW_NEEDED' if review_needed else ('READY_FOR_DISTANCE_RECONSTRUCTION' if exact_checked!=exact_required else 'READY_FOR_INTERPRETATION')
    (a.out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    lines=['# 局部可控性再分析摘要','',f"检查状态：{checks['status']}。本报告不自动判定方法有效或论文可录用。",'',
      '## Full 与 Grammar：全部请求及初始可行子集','',
      '| 模型 | 编码 | cap | 策略 | 请求 | 认证 | 正确 | 可行数 | 可行完成率 | 精确死路/分母 | 失败forward |',
      '| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |']
    show=lambda v: v if v!='' else 'NA'
    for r in core_summary:
        lines.append('| '+' | '.join([r['model'],r['encoding'],r['cap'],r['policy'],r['n'],r['certified'],show(r['correct']),
           r['initially_feasible'] if int(r['initial_feasibility_known']) else 'NA',show(r['feasible_completion_rate']),f"{show(r['dead_entries'])}/{r['dead_entry_denominator']}",show(r['failed_request_forward_calls'])])+' |')
    lines+=['','## 已成功轨迹与新增提交','',
      '| 模型 | 编码 | cap | 配对 | G已认证 | 认证丢失 | token完全保持 | 新增认证 | 新增正确 |',
      '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in pairs:
        lines.append('| '+' | '.join([r['model'],r['encoding'],r['cap'],r['n_pairs'],r['grammar_certified'],r['lost_certified'],
                                     r['same_token_records'],r['new_certified'],show(r['new_correct'])])+' |')
    lines+=['','## 解释边界','',
      '- 基础阶段没有tokenizer时，精确死路为NA；不能当作0。',
      '- `initially_feasible`在基础阶段来自归档元数据，距离阶段才与实际tokenizer重建核对。',
      '- 这里的deadline是token预算，不是硬实时毫秒保证。',
      '- 同时看认证覆盖、全请求正确率和成本；不要把新增错误提交或大量拒绝隐藏掉。',
      '- 只分析matched轨道；不是原6,976条全部轨道的完整复算。',
      '- 新局部目标属于探索性再分析，原24-token主比较不变。',
      '- 若出现保持性违例，检查语言、prefix、模型分数/数值、预算和执行条件，不删除该结果。','']
    (a.out/'执行结果摘要_zh.md').write_text('\n'.join(lines))
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    print('Readable report:',a.out/'执行结果摘要_zh.md')
    if review_needed:raise SystemExit(2)

if __name__=='__main__':main()
