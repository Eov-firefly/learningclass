# JANUS v8.8 严格终审修订母版

2026-10-27。本轮能完成的文字、形式化与软件修订已完成；新方法真实模型主实验、近邻文献/实现对照及作者声明仍未闭环。因此这是**待补实证的最终修订母版**，不是已经可直接投稿的终稿。

## 阅读入口

1. manuscript.md / main.tex / main.pdf：主稿；Markdown为可编辑源。题目收窄为有限语言完成，不宣称新范式优先权。
2. 严格审稿意见与处理结果_zh.md：12项问题、处理结果和剩余缺口。
3. 必须补充的实验与结果回填_zh.md：E1–E6、对比/指标/原始记录与结果位置。
4. 投稿前最终核对表_zh.md：实验、文献、作者及期刊条件；总状态HOLD。
5. historical_supplement.md / .tex / .pdf：旧完整协议及S1–S10，表体数据保持不变。
6. result_templates/：空表头及机器可读缺口清单，无虚构结果。

## 软件与证据

prototype/沿用v8.6/v8.7有限语言方案并修复边界与失败记录。22项受控CPU测试通过，不下载预训练权重，不提供GPU速度或真实任务准确率。test-log.txt与TEST_REPORT.json记录本次验证。

finite_record增加已合法prefix零预算提交、明确失败状态、轨迹/耗时/forward记录；mask允许负无穷零支持token与其他有效token并存，拒绝空概率支持/NaN/正无穷。forward pre-hook计数包括进入后报错的调用。接口外的配置、分词、谓词、设备异常仍需统一runner捕获，原型不是完整benchmark。

source_checks/保存本轮核实的官方版本文档、URL/hash；不等于已完整评阅相关研究论文。historical_evidence/保留旧分析和摘要。旧raw JSONL及未提供的后续raw timing不在此包；没有虚构独立复现。

实验验证方案_zh.md为较详细执行设计，与新的E1–E6清单配合阅读。不新增人工评分要求。

## 构建

Pandoc+pdfLaTeX环境运行`python build.py`生成主稿与补充PDF。原型依赖见requirements-prototype.txt；另按CPU/CUDA环境安装torch2.6。运行`python -m unittest discover -s tests -v`执行CPU软件检查。

最终状态与文件哈希见revision_checks.json、SHA256SUMS。旧版本保持不变；本包未自动上传GitHub或向期刊投稿。
