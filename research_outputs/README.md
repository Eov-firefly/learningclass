# JANUS 论文修订、严格评审与实验交付

最新整理：2026-10-27。当前入口为**v8.8论文修订母版**与**v8.9.1四卡A100最小实验包**。新方法的真实7B/A100实验尚未执行；文件整理、PDF编译和CPU软件检查不代表已经达到投稿标准。

## 最新阅读入口

| 内容 | 入口 |
| --- | --- |
| 修正后的核心创新点 | [CORE_INNOVATION_zh.md](review/CORE_INNOVATION_zh.md) |
| v8.8论文 | [PDF](manuscript_v88/main.pdf) · [LaTeX](manuscript_v88/main.tex) · [Markdown](manuscript_v88/manuscript.md) |
| 严格审稿与本轮处理 | [审稿意见](manuscript_v88/严格审稿意见与处理结果_zh.md) |
| 必须补充的实验 | [E1–E6与结果回填](manuscript_v88/必须补充的实验与结果回填_zh.md) |
| 投稿前放行条件 | [最终核对表](manuscript_v88/投稿前最终核对表_zh.md) |
| 旧十张表和完整历史协议 | [历史补充PDF](manuscript_v88/historical_supplement.pdf) · [Markdown](manuscript_v88/historical_supplement.md) |
| v8.9.1最小实验运行说明 | [README_zh.md](experiments_v89/README_zh.md) |
| 冻结工作量和模型版本 | [RUN_PLAN.json](experiments_v89/RUN_PLAN.json) |
| 数据及抽样来源 | [manifest.json](experiments_v89/data/manifest.json) |
| 最小实验对论文结论的限制 | [论文回填范围](experiments_v89/论文回填范围_zh.md) |
| 41项CPU检查范围 | [TEST_REPORT.json](experiments_v89/TEST_REPORT.json) |

## 直接下载

- **最新论文包**：[JANUS_v8_8_strict_review_final_revision_20261027.zip](packages/JANUS_v8_8_strict_review_final_revision_20261027.zip)
- **最新GPU实验包**：[JANUS_v8_9_1_minimal_ARC_4xA100_experiments.zip](packages/JANUS_v8_9_1_minimal_ARC_4xA100_experiments.zip)

两个解压目录与对应最新交付ZIP一致，保留各自SHA256SUMS。v8.9原始包保留在packages作为历史版本；v8.9.1修复了ETA并发读取日志的问题。没有纳入模型权重、虚拟环境、下载缓存或伪造的GPU结果。

## 四卡A100运行

数据已确定为一个ARC-Challenge已知队列子集：96题正式评估、16题开发。两种输出编码不算两个独立数据集。两个固定revision的7B模型分别分配两张GPU，每卡独立batch1推理；正式计划6,976条记录，其中1,248条为无需新增模型调用的确定性完成。

```bash
cd research_outputs/experiments_v89
export HF_HOME="$PWD/.hf_cache"
bash scripts/setup_cuda.sh
.venv/bin/python -m janus_min.prepare --download --hash-weights
bash scripts/run_4a100.sh runs/minimal 0,1,2,3
```

已有权重时使用运行说明中的本地路径参数。启动短校准会生成ETA；初步规划正式实验45–120分钟，安装/下载另计，未在A100实测。质量阶段后同步进入独立计时，不将共享prefix的后缀时间当作端到端速度。

```bash
.venv/bin/python -m janus_min.collect --run runs/minimal \
  --model-manifest model_manifest.json --output JANUS_results.zip
```

回传完整结果ZIP，包括raw、配置、环境、失败、评分与分析。有限数据仅适合机制/较大效果检查，不保证小幅收益功效、算法新颖性或SCI录用。当前不设人工评分工作流。

## 历史版本与证据

| 版本 | 交付档案 |
| --- | --- |
| v8.3独立复审 | [SCI_readiness_review_v83_zh.md](review/SCI_readiness_review_v83_zh.md) |
| v8.4终止约束视角 | [完整包](packages/JANUS_v8_4_termination_constraints_revision.zip) |
| v8.5历史证据增强 | [完整包](packages/JANUS_v8_5_evidence_strengthened_revision.zip) |
| v8.6候选机制及原型 | [完整包](packages/JANUS_v8_6_budget_viable_commitment_research.zip) |
| v8.7主线与实验重排 | [完整包](packages/JANUS_v8_7_logic_and_experiment_audit_20261027.zip) |
| v7结构修订 | [PDF](manuscript_v7/main.pdf) · [完整包](packages/JANUS_v7_structural_revision.zip) |
| 旧v8审计与工具 | [审计报告](experiments_v8/AUDIT_AND_EXPERIMENTS_zh.md) · [完整包](packages/JANUS_v8_supplement_experiments.zip) |

历史材料描述其当时状态；其中人工评估计划已被后续用户指示取消，不是当前待办。旧早停/监控数据不冒充新约束完成方法的结果。原始论文及上传档案仍保留在仓库原处。
