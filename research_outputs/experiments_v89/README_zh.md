# JANUS 最小验证实验包 v8.9.1：4 × A100

2026-10-27启动前复核补丁：ETA读取活动JSONL时只统计已换行结束的完整记录，避免worker正在写下一行时误报JSON错误。原始日志不改写、不丢弃；已完成记录中的损坏JSON仍会报错。已通过41项CPU检查。数据、模型和6,976条正式实验网格不变。请优先使用v8.9.1代码/压缩包；已经按旧代码生成数据时使用新输出目录，不能混写不同代码哈希。

本包将v8.8的E1–E6合并为小规模可执行验证。**数据和抽样已冻结，代码附带真实XGrammar接口及CPU集成检查；本机没有跑过A100或两个7B模型，GPU效果/耗时不是实测。**

## 数据确定为一个集合

ARC-Challenge，96道正式题+16道开发题，数据已打包。来自此前已核查的归档题目，按question_id的固定哈希排序抽样，不根据旧输出或正确率选择。主样本来自旧main队列，开发来自旧dev队列；是**已知队列复评**，不是新holdout。

data/public.jsonl只有题目、全部公开选项、题号与split；data/scoring.jsonl的gold只由独立分析进程读取。推理程序不接收gold。data/manifest.json记录来源、dataset revision、样本ID及哈希。无需重新下载数据集。

同一批题采用label、option_text两种表示：前者是短标签负对照，后者生成选项全文，允许长短接受路径不同。它们不是两份独立数据集，也不能单独支持跨任务泛化。96题只适合机制/大效果的低成本验证，不能宣称已具足够功效检测小幅收益；零差异也不能证明等价或无损。

## 环境与运行

建议Linux、Python3.10–3.12、4张A100 40GB或80GB、至少64GB主机RAM（推荐96–128GB）、16个CPU线程及100GB可用磁盘。每张卡独立放一个BF16 7B模型，不用DDP或tensor parallel。已有可用torch2.6 CUDA12.4环境可直接安装requirements.txt；新环境：

```bash
cd JANUS_minimal_v8_9
export HF_HOME="$PWD/.hf_cache"
bash scripts/setup_cuda.sh

# 只做一次，下载固定revision的两个模型；建议同时保存权重哈希。
.venv/bin/python -m janus_min.prepare --download --hash-weights --output model_manifest.json

# 打印固定工作量，不需要GPU，也不加载权重。
.venv/bin/python -m janus_min.launch --plan

# 一次启动，含短校准、质量/机制实验、同步后的独立计时和分析。
bash scripts/run_4a100.sh runs/minimal 0,1,2,3
```

如权重已在云端服务器本地：

```bash
.venv/bin/python -m janus_min.prepare \
  --qwen-path /models/Qwen2.5-7B-Instruct-1M \
  --mistral-path /models/Mistral-7B-Instruct-v0.3 \
  --hash-weights --output model_manifest.json

.venv/bin/python -m janus_min.launch --output runs/minimal \
  --devices 0,1,2,3 --local-files-only \
  --qwen-path /models/Qwen2.5-7B-Instruct-1M \
  --mistral-path /models/Mistral-7B-Instruct-v0.3
```

固定模型是此前的Qwen2.5-7B-Instruct-1M与Mistral-7B-Instruct-v0.3，revision写在spec.py。不要无记录换成普通Qwen2.5-7B或量化版。没有缓存时先prefetch；正式launcher默认local-files-only，避免4进程同时下载。可读的本地权重是另一路径，来源与hash由prepare保留。

## 先看预计时间

直接正式运行也会先自动校准。若只想先测服务器速度：

```bash
.venv/bin/python -m janus_min.launch --output runs/calibration \
  --devices 0,1,2,3 --local-files-only --calibrate-only
```

每worker：2次warmup+12条校准记录（每种表示各含5种模型策略+1个确定性CPU基线）。默认每模型用开发集前4道对应分片题，16道开发池并非全部用完。约40次实际模型校准请求+8次warmup。会输出calibrated_eta.json；该文件是依据本机校准及输出cap的保守工作量估算，范围不是统计置信区间，首次JIT/加载、网络和异常重试另计。

**规划预算：纯正式实验先预留45–120分钟；环境安装与约30GB模型准备另计20–60分钟或更久，建议首次租机预留约3小时。** 这不是A100实测承诺。GPU型号/功耗、磁盘、CPU和grammar编译会影响耗时；校准结果优先于这个初步范围。

## 请求量及E1–E6映射

| 轨道 | 设置 | 两模型总记录数 | 作用 |
| --- | --- | ---: | --- |
| matched | 96题×(2表示×3剩余预算×5策略+主设置候选评分) | 5,952 | E1、E3；同prefix、同有限文本语言；full/grammar严格同token路径 |
| format | 16题×d-1/d/d+1×3策略 | 288 | E2确定性退化，兼看已绑定答案错误仍会合法提交 |
| wrapper_e2e | 32题×4策略×cap128 | 256 | E5追加式候选绑定/起草失败和完整成本；并非未绑定字段端到端主结果 |
| timing | 16题×5模型策略×3重复×剩余预算24 | 480 | E6独立GPU阶段、问题级配对，不把48次重复当48独立题 |
| 合计 | 不含校准/warmup | **6,976** | 其中1,248条为共享prefix的确定性CPU基线；其余最多5,728次模型请求，部分不可行请求会提前拒绝 |

主对比预先固定：matched / option_text / remaining budget24 / full−grammar，两个模型分别报告；每个97.5%保守配对区间，形成至少95%的两比较family覆盖。其余预算8/64、label及其他对比为描述性诊断。不要看完结果再改“主要预算”。

## 并行与提速安排

GPU0/1：Qwen，各48道正式题分片；GPU2/3：Mistral，各48题。每卡一个模型实例+一个batch1 worker，不共卡并行，OOM风险低，样本分片相互无依赖。CPU线程每worker2个，grammar编译最多2线程，避免过度争抢主机。

质量/format/wrapper可在四卡并行。所有worker完成这些请求后通过barrier，再同时进入独立计时；模型一直留在显存中。每卡顺序执行计时请求，不与同卡质量任务混跑；主机仍共享，环境与device记录保留，不能宣称整机独占服务吞吐。

提速：预下载一次；BF16+SDPA+KV cache；只生成必要JSON后缀；相同案例承载多项诊断；确定性最短完成零新增模型调用；full的等价性由独立CPU路径枚举在线核对，无需再跑一份GPU重复算法。计时阶段关闭该审计，保留实际mask/编译/验证成本。未使用跨策略KV或输出复用，所有标为模型请求的记录都实际推理。

## 对照和计分

matched基础策略：uniform、grammar、full、deterministic、xgrammar；另在主设置增加sequence_score。grammar和full使用相同canonical token trie，区别为是否按距离剪枝；xgrammar0.1.21是真实引擎，接受相同有限文本后缀，可有其他token化路径。其差异需单列，不能全部归因于mask。编译缓存明确关闭，报告每request冷编译成本；本包不声称使用最新XGrammar-2或已比较所有先进系统。

主指标是所有冻结请求中正确、通过合同和绑定验证的提交比例，同时报告覆盖率、条件准确率、无效提交、错误/拒绝、token、forward和成本。无通过输出时条件准确率为空/NA。输出cap之外的prefix在matched轨道由调用方提供，明确不计其生成时间；不能把suffix耗时当端到端性能。

预算不可行而提前拒绝可能几乎不调用模型；平均延迟因此下降并不自动是有效加速。质量、覆盖与成本必须一起看，不能把低覆盖的快拒绝当作同质量收益，也不能仅保留成功样本计算主成本。

format绑定的答案由公开题号哈希选定，可能正确也可能错误；gold不参与构造。端到端wrapper用有限closure_balanced参考规则，保留所有no_candidate等失败。E5在此最小包是绑定/失败诊断，**未提供“任意字段编辑/完整答案绑定对结构绑定”的严格端到端消融**。若论文保留这类更广主张，需再加实验或收窄结论。

## 断点续跑和失败

同命令、同代码、同数据、同输出目录可重启；已经落盘的request_id跳过，包括失败记录，不会静默重跑并替换失败。模型与输入配置改变时拒绝混写，使用新目录。进程崩溃时会留下log；若launch被强杀，确认旧worker均退出后才移除launch.lock。原始JSONL若最后一行不完整，先备份文件并修复该未完成行，程序不会自动丢弃原始日志。

XGrammar默认必需；初始化/校准失败会在正式GPU长跑前停下。--skip-xgrammar只用于排错，会保留缺基线错误并使正式检查不通过，不能作为完整实验报告。逐请求算法/运行错误都记录，分析发现缺格、重复、错误或非法提交会REQUIRES_REVIEW并非零退出，避免“跑完”等于“实验有效”。

## 跑完给我什么

压缩整个runs/minimal目录以及model_manifest.json，尤其保留四份raw.jsonl、环境/配置、calibration、analysis目录和日志，不要只传CSV截图。analysis包含summary、paired_contrasts、failure_breakdown、offline_reference_reachability、逐请求评分和checks。

```bash
.venv/bin/python -m janus_min.collect --run runs/minimal \
  --model-manifest model_manifest.json --output JANUS_results.zip
```

上传JANUS_results.zip即可；不会包含模型权重/HF缓存。若运行中途失败，也可打包现有日志，manifest会标为PARTIAL或REQUIRES_REVIEW，不伪装成功。

sequence_score将所有预算可行候选并成一个teacher-forcing batch，用候选完整后缀的总log likelihood选择，不用gold、不做事后长度调参。只在option_text/24主设置增加192条主记录和96条计时记录，成本较低。它确实调用GPU，记录forward、scoring_input_tokens和candidate_score_tokens；被选后序列化的后缀记为inserted，不冒充零成本确定性修复或自回归生成。

原始记录不含gold；分析后的scored.jsonl包含评分，回传时保留。offline参考路径诊断只在评分端做，是canonical路径是否够预算，不冒充XGrammar全部路径的最短距离。

本最小包可以检验实现、明显预算效应及成本，并据实决定是否扩展。它不能保证SCI录用、算法优先权、2个百分点等小效果的统计功效或跨任务普适性。若主结果不支持方法，就按实际结果收窄/修改，不能增加只对新方法有利的过滤。
