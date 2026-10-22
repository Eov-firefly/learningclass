# JANUS v8 补充实验包

本包针对 v6/v7 稿件的接口有效性、门控机制和监测成本问题。它包含**新的参考实现**，不是缺失的原 v5 runner 源码。所有旧结果原样保留；新结果不能冒充旧协议下的重跑或替代旧数据。

已附带从原始逐调用记录恢复的序列化 prompt、问题、标准答案、原 Uniform token ID 和原计时子集成员标识。新实验无需重新下载 GSM8K/ARC；没有把恢复后的文件称作原始输入清单。两个模型分别使用自己的原序列化 prompt，token 数不符时立即报错。请遵守来源数据及模型的使用许可。

## 先看哪些文件

- AUDIT_AND_EXPERIMENTS_zh.md：本轮独立核验结论及实验优先级。
- audit/audit_report.json：机器核验结果；contract_sensitivity.csv / contract_paired.json：新增回顾性合同敏感性；discordant_pairs.json：全部114个主实验不一致案例。
- plan.json：完整新实验配置；不根据结果自动挑阈值。
- janus_v8/：解析器、GPU推理、轨迹重放、汇总与审计代码。
- data/：已恢复的输入与原基线路径，带独立哈希。
- tests/：解析器、统计及离线真实 Transformers generate 集成测试。

## GPU服务器准备

建议 Linux、Python 3.11、支持 BF16 的单张 GPU（建议至少24GB显存，并留足余量）、至少32GB系统内存、兼容 CUDA12.4 的驱动。原实验使用 A800 80GB、driver570；不同硬件的新结果应单独报告。模型权重及虚拟环境建议预留至少45GB磁盘空间。脚本不安装系统驱动、不启用远程自定义模型代码、不降低TLS/校验要求。

解压后进入此目录，运行：

```bash
bash setup_gpu.sh
export HF_HOME="$PWD/.cache/huggingface"
source .venv/bin/activate
python -m janus_v8.preflight --out preflight-server.json
```

安装器在项目内创建独立 .venv，安装 torch2.6.0+cu124 及固定版本依赖，不降级系统 Python。若有现成合适环境，可自行装 requirements-gpu.txt 并设置 JANUS_PYTHON 为该环境 Python；仍需确认 torch==2.6.0 及 CUDA 可用。不同版本必须保留记录，不能声称与原环境完全一致。

模型在首次运行时通过 Hugging Face 加载已固定的 commit；需网络访问和足够下载时间。模型下载和载入不计入请求计时。已有本地权重可逐模型使用 `--local-model /path/to/snapshot`，但程序只记录该覆盖项，**不能证明它就是固定commit**；作者需提供权重来源证据。不要在聊天或输出包里放HF密钥。

运行前确保目标GPU无其他推理/训练。程序使用同GPU锁并通过 nvidia-smi 检查已有计算进程；不会终止其他进程。可以设置 `CUDA_VISIBLE_DEVICES=0` 选择物理GPU，程序内部使用 cuda:0。多进程推理会破坏正式计时，因此默认串行。

## 推荐执行顺序

### 1. Smoke：必须先运行

```bash
bash run_stage.sh smoke
python -m janus_v8.analyze --runs runs --out analysis-smoke
```

两个模型共48条计分调用，另24条预热。检查无OOM、prompt token数匹配、运行完整、Complete/entropy_observe严格输出相同，及新Uniform与旧Uniform的token兼容性。Smoke只做实现检查，不证明科学结论。

若新旧Uniform不一致，不代表自动失败或旧数据错误；它表示新实现/运行环境的轨迹不同。所有后续策略仍须在新环境配对，不能用旧Uniform和新策略混合比较。差异应在论文中披露并进一步检查。

### 2. Trace：优先补充门控机制

```bash
bash run_stage.sh trace
python -m janus_v8.analyze --runs runs --out analysis-trace
```

共240条计分调用，每模型/任务60题，在完整Uniform轨迹上记录每步熵、完成指示及包装结构状态。分析器重放3个阈值×2个稳定窗口×2个最小步数，比较同时门控与缓存早期完成前缀的行为。**重放是机制分析，不是真实策略延迟实验。** Trace的时间均标为诊断，分析器不把它当正式计时。

当前缺少旧源码，EMA初始化/索引采用本包明确定义：第t步pre-token logits得到H_t，平滑有符号熵差，比较其绝对值，连续window步满足阈值，再结合min_steps。不要把它描述成已认证的旧Legacy复刻。只有取得旧源码后才能做旧规则的源级修复消融。

### 3. Quality：检验实际结构交付规则

```bash
bash run_stage.sh quality
python -m janus_v8.analyze --runs runs --out analysis-quality
```

共7200条计分调用：两模型×两任务×600题×Uniform/Complete/structured_complete。最后一种策略等待允许格式闭合且有限wrapper检查通过的答案前缀；它不是完整Markdown或LaTeX语法验证器。所有策略用相同的5种评分规则重评，分别报告实际生成与返回token。

本批题已在旧实验和本轮审计中被观察，属于后续探索性评估；不能宣称新的未见测试集或外部预注册确认性结果。

### 4. Timing pilot：先检查代价与方差

```bash
bash run_stage.sh timing_pilot
python -m janus_v8.analyze --runs runs --out analysis-timing-pilot
```

共400条计分调用，另40条预热。用于确认运行成本、测量噪声及门控输出身份。不要将pilot混入正式计时；本包没有凭空保证样本量足够检出百分之一差异。

### 5. Timing：独立会话计时

```bash
bash run_stage.sh timing
python -m janus_v8.analyze --runs runs --out analysis-final
```

共10800条计分调用，另120条预热。每模型3个独立Python/模型载入会话；模型会话顺序交替，每会话内部随机化。每模型/任务60题，每策略3次重复。主要对照：

| 对比 | 识别的内容 | 输出约束 |
|---|---|---|
| boundary_observe − Uniform | 边界检测回调路径开销 | generated IDs必须一致 |
| entropy_observe − Complete | 完成停止路径上增加熵观察的开销 | generated IDs必须一致 |
| entropy_uniform − boundary_observe | 基线终止长度下增加熵路径的开销 | generated IDs必须一致 |
| Complete − Uniform | 实际停止与检测的总效果 | 配对轨迹前缀检查 |

这些是路径总开销，不是独立CUDA kernel下界。分析器先在题内平均重复，再按问题bootstrap，并按独立会话分别输出；不把所有重复假装成独立实验。三个会话仍不足以自动声称跨硬件普适性，当前不输出伪精确的总体跨会话置信区间。

汇总同时给出调用级nearest-rank P50/P95，以及各合同下实际生成token/计分正确调用数；零正确时后者为缺失值，不是0，也不代表语义质量或实际费用。未测首token时间、吞吐、能耗或队列时间，不据此生成这些指标。

上述阶段按旧运行每请求约4秒粗估，全部正式新推理可能需约20小时以上；实际取决于GPU、输出长度和回调实现。请先看pilot耗时再安排正式计时。网络下载、模型加载及预热另计，不把这个粗估当实测。

## 运行失败与继续

每个会话独立目录、记录哈希和完整job顺序在运行前保存。运行失败会保留failed状态及部分记录；不会静默忽略或补成成功。相同目录禁止覆盖。

正式计时中断需完整重启该会话，使用新的输出根目录或 `--label retry1`，记录重试原因。**汇总时不要同时放入同一session的两个重试版本**，分析器会拒绝重复。不要从中选择结果更好的一次；按预先确定的完整性规则选定，并保留排除说明。对正式timing，六个模型会话齐全后才可通过完整性检查。

示例单独运行：

```bash
python -u -m janus_v8.run --stage timing --model qwen --session 0 --out retry-runs --label retry1
```

若修改 plan.json 或源码，将新方案放入独立输出根目录。分析器拒绝混合不同plan哈希；原始cohort文件若改动需显式重建manifest，不可绕过数据校验。

## 需要交回的文件

请保留全部 runs、分析输出、preflight-server.json、实际 plan.json、本包源码和安装/运行日志。每个runs目录必须带meta.json、records.jsonl、warmups.jsonl。无需上传模型权重或缓存。可以压缩这些内容返回；失败会话也请保留并单独标注。

人工语义评分仍需独立评审者，代码不会生成或伪装人工结论。正式投稿前仍需补原始v5源码、补足相关文献并核查目标期刊要求。
