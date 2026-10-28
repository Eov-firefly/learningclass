# 局部优势研究方案与现有结果再分析

推荐入口：[具体执行步骤](执行步骤_zh.md)。`run_control.py`统一核对输入、调用再分析、生成中文摘要和checks；本文件后面的`analyze_control.py`命令为底层用法。

本目录已包含原v8.9.1冻结的public/scoring/manifest，无需重新下载数据集。阶段A仅Python标准库；阶段B按需安装requirements-tokenizer.txt，不加载模型权重。

最短命令：

```bash
python run_control.py --run /data/janus_completed --out /data/janus_control_basic
```

精确死路诊断：

```bash
python run_control.py --run /data/janus_completed --out /data/janus_control_distance \
  --model-manifest /data/model_manifest.json --require-distances
```

输出到新的空目录。随后用`package_results.py --analysis /data/janus_control_distance --out /data/JANUS_control_results.zip`打包回传；原raw归档另保留。

本包不包含新的GPU结果。局部突破实验方案_zh.md给出可作为核心贡献的控制目标、定义、强对照及低成本执行顺序。

优先利用现有raw检查：预算内认证完成、起点可行性、合法但无法预算内完成的死路、死路后模型调用、已有成功轨迹保持。Top-k不适合作为当前四选一greedy实验的直接替代指标。

## 先不加载tokenizer做结果转移分析

```bash
python analyze_control.py \
  --run /path/to/completed_run \
  --public /path/to/experiments_v89/data/public.jsonl \
  --scoring /path/to/experiments_v89/data/scoring.jsonl \
  --out control_reanalysis
```

只读取matched轨道。其他轨道计数在analysis_scope.json中列明；不把它当全部6,976条grid审计。无scoring参数时只能做控制诊断，正确答案相关量为NA。

## 加载实际tokenizer，重建精确预算死路

只需已安装的Transformers和tokenizer文件，不加载模型权重，不进行GPU推理：

```bash
python analyze_control.py \
  --run /path/to/completed_run \
  --public /path/to/experiments_v89/data/public.jsonl \
  --scoring /path/to/experiments_v89/data/scoring.jsonl \
  --qwen-tokenizer /models/Qwen2.5-7B-Instruct-1M \
  --mistral-tokenizer /models/Mistral-7B-Instruct-v0.3 \
  --out control_reanalysis_with_distance
```

必须使用本次实际模型tokenizer。脚本核对语言hash和公共prefix，失败时明确标记，不能把未核实的距离当成0。token路径诊断只适用于使用相同canonical trie的Full/Grammar；不能据此把XGrammar的其他合法token化误判成逸出。

输出：control_summary.csv、trajectory_preservation.csv、control_scored.jsonl、analysis_scope.json。没有tokenizer时精确死路量为NA。检测到同组matched重复题时停止，避免把重复当独立题或覆盖配对。

结果仍属于本轮探索性再分析，不能追认为原24-token预注册主要终点。新确认研究须事先冻结指标和条件。请将新增CSV与原raw一起回传；不能只挑最有利列。

## 软件检查

`python -m unittest -v test_analysis`。13项检查覆盖死路/成功/起点不可行、语法逸出区分、转移和token证据、输入哈希、配对上下文、保守区间、统一入口和打包状态。它们不代表本次真实模型结果已复算。
