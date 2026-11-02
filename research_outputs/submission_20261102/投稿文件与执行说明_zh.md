# 通用期刊投稿定稿

日期：2026-11-02。基于现有全部结果完成正文、补充材料、引用、声明与投稿附件；没有新增GPU推理。本版是通用期刊稿，未套用某一家期刊的专属模板。

## 文件入口

- 正文：[PDF](../../main.pdf) · [LaTeX](../../main.tex) · [Markdown](../../manuscript.md)
- 补充材料：[PDF](../../supplementary.pdf) · [LaTeX](../../supplementary.tex) · [Markdown](../../supplementary.md)
- 文献库：[references.bib](../../references.bib)
- 投稿信：[cover_letter.md](cover_letter.md)
- Highlights：[highlights.txt](highlights.txt)，5条，每条不超过85字符
- 标题页及声明：[title_page.md](title_page.md)
- 贡献和实验对应：[贡献与证据对应_zh.md](贡献与证据对应_zh.md)
- 作者/声明元数据：[submission_metadata.json](submission_metadata.json)
- 原始数据审计：[raw_audit_20261102](../raw_audit_20261102/README_zh.md)

## 已完成的统一

1. 方法统一称BVC，明确对应原策略键`full`；使用真实章节、表格、公式和命题编号及交叉引用。
2. 把控制器认证、正确提交、文本有效性和成功答案稳定性分开，不把局部领先改写为全面领先。
3. 保留原24-token主比较，另标tight-budget及新稳定性诊断的探索性身份。
4. 将旧早停动机、全预算/全基线表、详细计时和归档信息移入独立补充材料。
5. 主文末章集中描述语言覆盖、语义/拒绝、终止合同、数据/效率及保证条件的限制与未来方向。
6. 根据用户确认，写入无经费、无利益冲突及所有作者同意投稿；按用户要求不写作者贡献章节。没有推定额外作者事实。
7. 保留AI辅助编辑/代码准备的说明，实验数字均有对应raw或离线派生表。

## 如何提交

1. 选定接收该主题和文章类型的期刊，确认其稿件模板、篇幅、参考文献、匿名和附件要求；通用版可直接作为正文内容使用，版式再按该刊规则适配。
2. 上传正文、补充材料、投稿信、Highlights及所需源文件。LaTeX源包须带references.bib和figures目录；提供的打包文件保留这些依赖。
3. 在投稿系统填写作者和通讯信息，数据代码地址为仓库URL。原始raw整理包已公开，体积较大，不重复塞进正文源文件包。
4. 按真实情况完成投稿系统的原创性、是否同时在别处审理等必选声明；本版没有替作者臆造这些事实。若某刊强制要求CRediT，再按该刊要求补其系统字段；本通用稿没有作者贡献章节。

上述是期刊适配和系统提交操作，不是要求把所有结果再跑一遍。送审稿的范围已经限定为现有证据支持的控制方法及机制分析；不把未来工作当作当前结果。

## 本地重新生成

需Python、pdflatex、BibTeX、Pandoc；重绘图额外需要matplotlib/numpy。先在仓库根目录执行：

```bash
python3 research_outputs/submission_20261102/make_figure.py
python3 research_outputs/submission_20261102/build_manuscripts.py
```

第二个命令构建两份PDF、解析引用并同步两份Markdown。已有图时无需重绘。构建日志及报告在本目录build下；不会调用模型或改写raw。

新增答案稳定性表仅复用原1,920条记录：

```bash
python3 research_outputs/submission_20261102/derive_output_stability.py \
  --study /data/实验原始结果整理_20261102/01_单卡补充实验_20261030/已核验完整内容 \
  --out /data/output_stability.csv
```

这里比较的是同一原Grammar已认证子集上的答案标签保持，不把候选评分的确定性插入误当作不同自回归token轨迹，也不把重复预算条件当成独立题目。
