# 具体执行步骤

日期：2026-10-29。先用`../controllability_v1/执行步骤_zh.md`处理原始结果；本文件只用于确实还需追加的GPU机制实验。

## 1. 获取代码，复用已有环境

```bash
git clone --depth 1 https://github.com/Eov-firefly/learningclass.git learningclass-control-new
cd learningclass-control-new/research_outputs/controllability_gpu_v1
python3 -m unittest -v test_workflow
```

不要在原来的两卡补丁目录中直接覆盖文件。所有`/data/...`都是示例，请替换。当前包依赖相邻的`experiments_v89`及`controllability_v1`；完整克隆或本轮ZIP均保留此目录关系。

已有v8.9.1 CUDA环境可直接使用其Python，例如：

```bash
export JANUS_PY=/data/janus_env/bin/python
"$JANUS_PY" -m unittest -v test_workflow
```

没有环境时，在仓库自带脚本中安装固定版本（需要CUDA驱动支持torch cu124）：

```bash
bash ../experiments_v89/scripts/setup_cuda.sh
export JANUS_PY="$PWD/../experiments_v89/.venv/bin/python"
```

该历史安装脚本末尾仍提到四卡，这是原脚本提示；本次启动使用下面的`run.py`，支持2或4卡。

## 2. 生成/核对本地模型清单

已有正确的model_manifest.json时可复用。路径须当前可读，`spec`须与固定revision一致。建议完整权重hash，避免本地同名目录实际是另一版本。

```bash
cd ../experiments_v89
"$JANUS_PY" -m janus_min.prepare \
  --qwen-path /models/Qwen2.5-7B-Instruct-1M \
  --mistral-path /models/Mistral-7B-Instruct-v0.3 \
  --hash-weights --output /data/model_manifest.json
cd ../controllability_gpu_v1
```

没有本地权重才使用原`prepare --download`；不要让每个worker分别下载。worker会检查清单中文件大小及已有SHA256；未记录完整权重hash时只能检查其大小，不能声称逐字节验证了权重来源。

## 3. 在模型推理前冻结数据和预算

**模式A：直接可用的旧题机制实验。** 不需下载数据，默认从原96题确定性选64题；结果标签一定是exploratory_known_cohort：

```bash
"$JANUS_PY" freeze.py \
  --model-manifest /data/model_manifest.json \
  --source-description "原96题已知ARC队列的64题探索性机制验证" \
  --out /data/control_protocol_known64
```

该步骤只加载tokenizer，不加载权重，不调用GPU。生成protocol.json、public/scoring、languages及models；预算在此冻结，formal worker不读取scoring。token路径及输入代码均hash，后续更改会被拒绝。**当前没有已冻结的新独立64题包。**

**模式B：有真正新来源时使用。** 外部public每行仍是以下字段；scoring另存question_id和gold。`question`需要包含题干和有序选项，options保留相同标签。选题不读取gold值；gold仅检查覆盖并供后续离线评分。

```json
{"question_id":"newarc:12345678abc","split":"eval","question":"Question ...\nA. option one\nB. option two","options":{"A":"option one","B":"option two"}}
```

```bash
"$JANUS_PY" freeze.py \
  --public /data/new_public.jsonl --scoring /data/new_scoring.jsonl \
  --exclude-public ../experiments_v89/data/public.jsonl \
  --exclude-public /data/all_prior_public.jsonl \
  --model-manifest /data/model_manifest.json --n 64 \
  --source-description "填写数据集名称、固定版本、split及来源；排除全部已用队列" \
  --out /data/control_protocol_new64
```

第二个排除文件应覆盖更早用过的所有题，不只是112题；没有文件时不要假装完成了排除。自动检查题号和规范化题文/选项的精确重叠，不能识别所有近重复或模型训练污染，因此外部来源仍标unverified_prior_exposure，需按来源核实。

下文示例使用模式A路径；做模式B时一致替换protocol路径，不能把两套结果混在同一输出目录。

## 4. 检查计划、校准，然后运行

```bash
"$JANUS_PY" run.py --protocol /data/control_protocol_known64 \
  --output /data/control_run_2gpu --devices 0,1 --plan

"$JANUS_PY" run.py --protocol /data/control_protocol_known64 \
  --output /data/control_run_2gpu --devices 0,1 --calibrate-only

"$JANUS_PY" run.py --protocol /data/control_protocol_known64 \
  --output /data/control_run_2gpu --devices 0,1
```

校准只检查环境和粗估成本；正式运行会重新预热/校准，不能根据校准答案改预算。查看`*.log`、`*.eta.json`和`*.progress.json`。普通完整运行额外2/4卡预热校准模型请求上限分别28/56；单独先校准再正式运行会增加一次相同校准开销。

四卡改用一个新的输出目录：

```bash
"$JANUS_PY" run.py --protocol /data/control_protocol_known64 \
  --output /data/control_run_4gpu --devices 0,1,2,3
```

两卡和四卡是替代配置，通常只跑一个；不要两套都跑后择优报告。resume要求相同代码、protocol与GPU分配。原始记录逐条flush/fsync；发生错误保留记录并停止，不静默重试。纯中断且末行完整、无错误记录时重用相同命令可继续。若留有launch.lock，先确认所有旧进程确已停止，再人工删除锁；不要对运行中的目录删锁。

未结束的末行、错误记录或配置变动会被拒绝，保留原始文件，诊断后另建有来源记录的重跑目录；不要删除失败样本再继续当作一次无故障实验。

## 5. CPU评分和精确死路分析

```bash
CUDA_VISIBLE_DEVICES='' "$JANUS_PY" analyze.py \
  --protocol /data/control_protocol_known64 \
  --run /data/control_run_2gpu \
  --out /data/control_analysis_2gpu
```

分析不需GPU或重新加载tokenizer；使用预冻结token路径与实际generated IDs重建。输入只包含这次run，不混原实验或备份副本。

检查`checks.json`，missing、context、token、error、budget、lost_success各项应为0；`READY_FOR_INTERPRETATION`仅指软件检查通过，**不代表有效性成立或可以投稿**。`REVIEW_NEEDED`返回码2，结果仍保留，应原样回传。缺失证据保留NA，不能改为0。

阅读`control_summary.csv`全部五种策略：feasible_completion_rate、certified、correct、wrong_certified、dead_entries及denominator、post_dead_calls、failed成本、candidate_score_tokens/scoring_input_tokens。`trajectory_preservation.csv`检查原G成功时F是否逐token保持，以及新增认证中新增正确的数量。两个控制预算按题/模型变化，不应按其数值混组或当作独立任务。

## 6. 打包回传

先保留protocol、run、analysis三个目录；每个目录之外的新ZIP路径，避免把ZIP自己装进去：

```bash
python3 -m zipfile -c /data/JANUS_control_gpu_results.zip \
  /data/control_protocol_known64 \
  /data/control_run_2gpu \
  /data/control_analysis_2gpu
```

ZIP应包含模型文件清单而不含权重。运行代码由protocol的source_sha256对应本仓库版本；如有本地修改另附实际代码及说明。本次ZIP和原6,976条raw都保留，不能用本轮包替代原始证据。没有GPU条件时只需完成上一轮CPU再分析，不需要为此重复租卡。
