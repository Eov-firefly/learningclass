# 论文评审、修改稿与补充实验

本目录收录本次论文工作生成的可审阅输出。原始论文及实验数据 ZIP 保留在仓库根目录，没有覆盖。

## 阅读入口

| 内容 | 文件 |
|---|---|
| 严格投稿前评审 | [SCI_review_zh.md](review/SCI_review_zh.md) |
| v7 英文修改稿 | [PDF](manuscript_v7/main.pdf) · [LaTeX](manuscript_v7/main.tex) · [Markdown](manuscript_v7/manuscript.md) |
| v7 修改说明 | [REVISION_NOTES_zh.md](manuscript_v7/REVISION_NOTES_zh.md) |
| v7 待补验证计划 | [VALIDATION_PLAN_zh.md](manuscript_v7/VALIDATION_PLAN_zh.md) |
| 新上传实验数据的独立审计与实验建议 | [AUDIT_AND_EXPERIMENTS_zh.md](experiments_v8/AUDIT_AND_EXPERIMENTS_zh.md) |
| GPU 服务器执行说明 | [README_zh.md](experiments_v8/README_zh.md) |
| 补充实验配置 | [plan.json](experiments_v8/plan.json) |
| 独立数据审计结果 | [audit_report.json](experiments_v8/audit/audit_report.json) |
| 全部114个主实验不一致案例 | [discordant_pairs.json](experiments_v8/audit/discordant_pairs.json) |
| 新增回顾性合同敏感性结果 | [contract_sensitivity.csv](experiments_v8/audit/contract_sensitivity.csv) |
| 程序测试范围与结果 | [TEST_REPORT.json](experiments_v8/TEST_REPORT.json) |

## 下载完整包

- [v7 稿件修改包](packages/JANUS_v7_structural_revision.zip)
- [v8 补充实验代码与恢复输入](packages/JANUS_v8_supplement_experiments.zip)

两个 ZIP 与本次交付版本一致。解压版便于 GitHub 浏览、代码审查和后续修改。

## 当前状态

v7 是结构和理论修订稿：保留既有实验方法、五张表和结果章节，新增分析不冒充预设实验或已完成新结果。它形成于新实验输出包上传之前，其数据可用性和后续证据状态应以 v8 审计报告为补充，下一轮稿件再统一更新。

v8 指补充实验工具版本，不表示已经完成 v8 科学实验。现有25,200条记录的内部一致性独立核验通过；新增合同分析属于回顾性诊断。代码通过12项本地测试，包括小型随机模型的真实 Transformers generate CPU 集成测试；尚未运行实际 Qwen/Mistral CUDA 实验。

旧 v5 完整 runner/parser 源码仍未包含在原实验资料包中，因此 v8 是独立参考实现，不是旧 Legacy 的精确源码补丁。人工语义评估仍待完成。不要将文件哈希、排版检查或代码测试理解为 SCI 录用保证。

## 在 GPU 服务器运行

推荐下载上方实验 ZIP 后按其说明操作。也可使用此仓库中的目录：

```bash
cd research_outputs/experiments_v8
bash setup_gpu.sh
bash run_stage.sh smoke
.venv/bin/python -m janus_v8.analyze --runs runs --out analysis-smoke
```

先检查 Smoke，再按说明运行 Trace、Quality、Timing pilot 和正式 Timing。已有恢复输入，不需重新下载 GSM8K/ARC；模型权重需要另行下载或提供可追溯本地快照。

本目录没有纳入虚拟环境、模型权重、依赖缓存、临时编译文件或 GPU 实验结果。未来产生的新结果请保留完整配置、来源及失败/重试记录。
