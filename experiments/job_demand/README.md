# AI / FDE / Agent 岗位需求分析

这是既有求职助手的离线分析子任务：输入本地 JD，输出规则统计、TF-IDF/K-Means 对照、证据 ID 和图表。只读 SQLite，不启动浏览器、不使用模型 API、不发送招聘消息。工作流约束见 [SKILL.md](SKILL.md)。

## 运行

在仓库根目录，使用 Python 3.12（与后端虚拟环境隔离）：

```sh
uv venv --python python3.12 .venv-analysis
uv pip install --python .venv-analysis/bin/python -r experiments/job_demand/requirements.lock.txt
.venv-analysis/bin/python experiments/job_demand/analysis.py --snapshot experiments/job_demand/demo.json --out reports/demo
.venv-analysis/bin/python -m pytest experiments/job_demand/test_analysis.py -q
```

`demo.json` 为本项目构造的合成岗位，**只用于验证流程，不能重现报告中的真实岗位分布**。真实实验须使用本地冻结快照，其 SHA-256 记录在报告中。已有个人数据库可以只读导出，但新采样结果自然不同：

```sh
.venv-analysis/bin/python experiments/job_demand/analysis.py --db db/getjobs.db --out reports/job-demand-new
.venv-analysis/bin/python experiments/job_demand/sensitivity.py --snapshot reports/job-demand-new/input/snapshot.json --out reports/job-demand-sensitivity
```

可从浏览器打开输出目录 `index.html`。输出包含 results.json、trials.csv、assignments.json 和三张 PNG。`assignments.json` 包含JD，应保留本地；`source_map_PRIVATE.json` 含来源映射，绝不公开。目录名不会自动改变数据权限。

## 分析口径

- 以完整 JD 去空白后的摘要去重，少于50字符者排除；至少12条有效JD。
- 标题 AI/FDE/Agent 为可重叠标签，不是搜索来源，不进入聚类特征。
- 技能字段是正则提及，未区分否定和要求强度；学历未提及不等于不限。
- 月薪仅解析 K 区间；日薪/年薪不混算；中点中位数不等于实际工资。
- 基线/领域词表均使用 min_df=2、max_df=.9、sublinear_tf 与 L2；19个领域词见代码。
- k=2…8，5个固定种子，n_init=20；最小簇≥3时按平均余弦轮廓系数选择，固定展示seed=7。
- ARI比较不同随机种子；没有监督标签，不计算分类准确率。
- sensitivity.py 固定字符3–5gram与余弦阈值.90，保留首个近重复代表；结果是阈值敏感性检查，非完美语义去重。

算法只支持探索性结论。弱分离、小样本、来源丢失或同义改写都可能使结果不稳定。本次报告没有独立人工金标准，未报告抽取F1。

## 实验交付与隐私

真实快照位于本机 `reports/job-demand/experiment/input/snapshot.json`，不提交Git。报告及所有产物也在 `reports/`，避免误发布招聘文本。分析不读取姓名、简历、API密钥或浏览器登录态。原始JD来自第三方平台，脱敏并不授予公开再分发许可。

报告生成入口 `build_report.py` 接收经过核对的 Markdown 与 DOCX 封面模板；依赖 LibreOffice 转换PDF。封面个人信息留空，禁止猜填。

第三方版本与许可见 [COMPONENTS.md](COMPONENTS.md)。项目全部源码仓库：https://github.com/LingJingMaster/get_jobs_bot 。
