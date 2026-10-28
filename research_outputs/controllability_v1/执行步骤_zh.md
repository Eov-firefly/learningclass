# 可直接执行的步骤：先复用现有实验，不新增GPU

日期：2026-10-28。当前可运行的是阶段A/B“既有结果再分析”，不是新增确认实验。局部突破实验方案_zh.md中的64题、最多1,536条模型请求属于下一轮待冻结方案；本目录没有把它伪装成已实现、已运行的GPU实验。

目标：先验证预算内完成、预算死路/失败计算、原本成功的匹配grammar轨迹保持。保留24-token原主比较，所有新指标标为探索性再分析。

## 1. 在有原始结果的机器上取得代码

不需要租GPU。原来的GPU服务器也可以，但程序不会调用GPU。建议另开克隆目录，保留原实验目录、两卡启动补丁及日志。

```bash
git clone --depth 1 https://github.com/Eov-firefly/learningclass.git learningclass-control
cd learningclass-control/research_outputs/controllability_v1
python3 -m venv .venv
.venv/bin/python -m unittest -v test_analysis
```

阶段A及基础测试只需要Python标准库，不安装torch/CUDA，也不下载模型。

## 2. 准备已经完成的结果

输入应是包含全部四个worker/shard结果的目录，允许按两个执行波次嵌套。目录下应能递归找到`*.raw.jsonl`，例如：

```text
/data/janus_completed/
  wave0/.../qwen.s0.raw.jsonl
  wave0/.../mistral.s0.raw.jsonl
  wave1/.../qwen.s1.raw.jsonl
  wave1/.../mistral.s1.raw.jsonl
```

不要只传summary.csv、截图或论文表格。也不要把原始数据和同一数据的备份副本一起放在输入目录内，程序会拒绝重复request_id。

已有解压目录可以直接使用；如果只有ZIP，先解压到一个新目录：

```bash
python3 -m zipfile -e /data/JANUS_results.zip /data/janus_completed
```

`/data/...`均为示例路径，请替换成真实路径。若使用的正是论文中那份原归档，可用`sha256sum`对照论文给出的hash；重新打包ZIP后hash可能改变，应保留来源，不据此自动认定记录有误。

本工具已带与v8.9.1相同的112题public/scoring文件和manifest，不需要再下载ARC。运行入口先验证哈希和题号，再开始分析。参考答案仅用于离线评分。

## 3. 阶段A：先跑不依赖tokenizer的分析

```bash
.venv/bin/python run_control.py \
  --run /data/janus_completed \
  --out /data/janus_control_basic
```

应获得：

- `执行结果摘要_zh.md`：可直接阅读的对比表。
- `control_summary.csv`：全请求认证/正确、归档初始可行性、失败forward/耗时。
- `trajectory_preservation.csv`：G原成功时F是否保持、新增多少认证/正确输出。
- `control_scored.jsonl`：含原字段和新离线评分/诊断。
- `checks.json`、`analysis_config.json`、`analysis_scope.json`：输入和代码哈希、缺格及证据范围。

阶段A不会伪造精确死路数，没有tokenizer的字段为NA。若完整核心配对和输入信息齐全，正常状态是`READY_FOR_DISTANCE_RECONSTRUCTION`，意思是可以继续B，不代表论文有效性已经成立。

配对表另给全请求及共同初始可行子集的认证完成率差和保守95%配对区间。它们未对所有模型/预算作多重性调整，属于探索性描述，不能替换原主要检验。零胜负也会有非零区间宽度，不视为等价证明。

本次expected matched记录为5,952，Full/Grammar核心记录为2,304。工具不把未分析的format/wrapper/timing轨道冒充已复算。`matched_grid_complete`检查全部matched组，`missing_core_count`检查核心配对；如只提供部分数据，应先补齐。

每次输出到一个新的空目录，避免覆盖先前分析。

## 4. 阶段B：重建精确预算死路，仍不调用GPU

使用本次实际tokenizer。优先复用原来已安装的环境；如果使用上面的新环境，安装的只是tokenizer相关依赖：

```bash
.venv/bin/python -m pip install -r requirements-tokenizer.txt
```

如果有原`prepare.py`生成的model_manifest.json，其中local_path在当前机器可读：

```bash
.venv/bin/python run_control.py \
  --run /data/janus_completed \
  --out /data/janus_control_distance \
  --model-manifest /data/model_manifest.json \
  --require-distances
```

也可以手工指定路径：

```bash
.venv/bin/python run_control.py \
  --run /data/janus_completed \
  --out /data/janus_control_distance \
  --qwen-tokenizer /models/Qwen2.5-7B-Instruct-1M \
  --mistral-tokenizer /models/Mistral-7B-Instruct-v0.3 \
  --require-distances
```

`AutoTokenizer`只读tokenizer/config，不加载safetensors权重。没有原服务器模型目录时，可只复制tokenizer.json、tokenizer_config.json、相关special token/config及该模型需要的tokenizer.model文件；不必复制14GB模型。脚本使用local_files_only，不会偷偷下载。

子进程的CUDA可见设备被清空，因此阶段A/B均为CPU工作。对约6千条短输出通常是秒到数分钟量级，依赖安装、磁盘和CPU速度另计，实际以日志为准。

## 5. 检查结果，不要只找有利列

先看`checks.json`：

- `missing_core_count`、`unexpected_records`应为0。
- 完整原matched归档应有`matched_grid_complete: true`。
- Full/Grammar的`pair_context_mismatches`、`pair_context_unknown`、token证据缺失应为0，才能清楚解释配对保持性。
- 阶段B应有`exact_distance_checked == exact_distance_required`，完整核心为2,304；重建错误为0。
- `lost_certified`、`lost_correct`若非0，保留并检查语言、prefix、预算、模型分数/数值和执行条件；不能删掉反例。

检查状态：

| 状态 | 含义 | 处理 |
| --- | --- | --- |
| READY_FOR_DISTANCE_RECONSTRUCTION | 基础数据可解释，但缺精确距离证据 | 继续B |
| READY_FOR_INTERPRETATION | 本工具检查范围内证据齐全 | 阅读结果，不等于方法胜出或可直接投稿 |
| REVIEW_NEEDED | 缺格、上下文/重建/轨迹等问题需复核 | 返回码2；文件仍保留，打包日志，不改成0 |

然后看三个局部目标：

1. `feasible_completion_rate`：统一canonical语言的初始可行请求中是否完成，同时看全部请求coverage和correct。
2. `dead_entries/dead_entry_denominator`、`post_dead_calls`：是否减少合法但预算内无法完成的路径，以及其后模型调用。
3. `same_token_records/grammar_certified`、`lost_certified/lost_correct`：原本成功轨迹是否保持；另看`new_certified/new_correct`，不能把新增错误输出隐藏掉。

时间预算在此指token数，不是硬实时毫秒保证。全路径长度和token化必须一致；不能将XGrammar其他合法token化误判为canonical trie逸出。低覆盖的快拒绝不自动等于同质量加速。

## 6. 打包回传

```bash
.venv/bin/python package_results.py \
  --analysis /data/janus_control_distance \
  --out /data/JANUS_control_results.zip
```

请回传`JANUS_control_results.zip`，并同时保留/提供原始结果归档及实际两卡两波执行代码。新ZIP仅含再分析，不含模型权重，也不能代替原始完整归档。即使检查为REVIEW_NEEDED也可以打包，状态会被保留。

## 7. 什么时候再开GPU

先解释A/B：若局部完成/死路收益成立且质量代价可解释，再决定是否进行新确认研究。方案中的64题/1,536请求只是成本规划，不保证功效；需先冻结新样本、主指标、预算和实际两卡/四卡runner，再生成对应正式代码。

当前本目录没有新增GPU确认runner，**不要把旧v8.9.1脚本直接重跑一遍当作新方案已执行**。Top-k、任意字段编辑和候选规模扩展也不在本次可执行再分析中，不能凭本工具写成已有实验结果。
