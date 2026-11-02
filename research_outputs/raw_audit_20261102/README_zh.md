# 2026-11-02：原始数据核验与论文修订

本次核验基于用户上传至`main`的`实验原始结果整理_20261102.zip`（提交`6956d7e`）。没有新增GPU推理。最新论文见仓库根目录[main.tex](../../main.tex)、[manuscript.md](../../manuscript.md)和[main.pdf](../../main.pdf)。

- [核验结论、修改与剩余工作](核验结论与论文修订_zh.md)
- [可重运行的离线审计程序](audit_raw.py)
- [核查范围与实质性限制](analysis/audit_scope.json)
- [全基线结果与成本](analysis/single_all_baselines.csv)
- [正确选项可达性分析](analysis/reference_reachability.csv)
- [成功轨迹与新增提交转移](analysis/trajectory_transitions.csv)
- [逐题新增完成案例](analysis/rescued_cases.csv)
- [结束条件敏感性](analysis/terminal_policy_sensitivity.csv)
- [原96题研究全基线结果](analysis/double_matched_baselines.csv)

## 重跑审计

在仓库根目录执行。只需Python、numpy、scipy；不加载torch、tokenizer或模型权重。依赖也已包含在原实验环境中。

```bash
python3 -m zipfile -e 实验原始结果整理_20261102.zip /data/janus_raw
python3 research_outputs/raw_audit_20261102/audit_raw.py \
  --bundle /data/janus_raw/实验原始结果整理_20261102 \
  --out /data/janus_audit_new
```

输出目录必须新建或为空。包中的wave副本、aggregate副本、既有analysis/scored文件不重复计数。程序只读取数据/源码进行校验，不运行包中的调度、远程关闭或其他基础设施脚本。距离重建以冻结的单卡canonical路径为准，不把它当作对所有合法token化的全局距离。

历史评分使用归档中原版的解析/评分函数前缀，源哈希见[historical_contract_source.json](historical_contract_source.json)。它的列首marker和数字语法与后续原型不同；不可混用后续宽松解析器来“复算”历史敏感性结果。每次运行均核对归档原函数的来源和本地快照。

软件检查：

```bash
cd research_outputs/raw_audit_20261102
python3 -m unittest -v test_audit
```

4项CPU检查通过，含500个有限语言案例的条件性保持检查。这不是模型准确率实验。

`analysis/`仅保留小型派生表和核查JSON；逐条评分JSONL在本地重跑时重新生成，完整原始数据已在原上传包内，不在此重复复制。论文中的旧24-token主比较和新的探索性终点分别保留，没有重标原始状态或事后删题。
