# 复用组件、来源与责任边界

核查日期：2026-11-06。锁定版本：requirements.lock.txt。库的使用权不等于招聘数据或模型输出的再分发授权。

|组件|版本/提交|来源|许可|本项目用途与改动|
|---|---|---|---|---|
|scikit-learn|1.7.2|https://github.com/scikit-learn/scikit-learn|BSD-3-Clause|TF-IDF、KMeans、轮廓系数、ARI；配置参数，不修改库|
|jieba|0.42.1|https://github.com/fxsjy/jieba|MIT|中文分词；运行时增加19个领域词，原库不改|
|Matplotlib|3.10.7|https://github.com/matplotlib/matplotlib|Matplotlib/PSF衍生许可证，见安装包许可证|统计图和流程图；不修改库|
|python-docx|1.2.0|https://github.com/python-openxml/python-docx|MIT|保留封面结构、生成Word报告|
|pypdfium2|5.0.0|https://github.com/pypdfium2-team/pypdfium2|BSD-3-Clause / Apache-2.0，PDFium另附依赖许可|检查PDF页数、文本与渲染|
|LibreOffice|本机命令行安装，版本记录于交付环境文件|https://www.libreoffice.org/|MPL-2.0等，按发行包说明|封面DOC转DOCX、报告DOCX转PDF|
|Resume Builder|642e82b3e5237bd46c98496d7f09dd560b58a06f|https://github.com/Jichengyuuuuu/resume-builder-skill|未找到明确LICENSE（GitHub仓库license为null）|既有简历分支；改提示词、结构化输出、占位符校验。不参与本次聚类，交付分析包不复制其正文|
|Humanizer-zh|f4518a8eab97b8bfebc66a89d34320a89bef6930|https://github.com/op7418/humanizer-zh|MIT；仓库本地快照保留LICENSE|既有简历可选润色分支；未用于本次数值分析，不声称改善聚类|
|Boss直聘岗位文本|2026-11-04至2026-11-06入库快照|https://www.zhipin.com/|第三方内容，无本项目授予的开源许可|仅本地分析核验；不公开完整JD或招聘者信息|
|job-demand-analysis|1.0.0，本项目新增|本目录SKILL.md和Python脚本|项目自编流程，不声明上游原创归属|定义分析步骤、模型选择条件、输入输出和限制|

## 原创、配置与复用的区别

本次新增的快照导出、字段脱敏、规则表、实验调度、模型选择、近重复检查、报告生成与测试由AI辅助编写。TF-IDF、K-Means、分词及绘图库算法复用成熟实现，不声称自行提出。固定领域词表属于配置适配；实验数据来自真实本地快照；demo.json为明确标识的合成数据。

## Skill深入核验记录

Resume Builder说明要求读取背景材料、按目标岗位组织技能、生成HTML/DOCX与顾问建议。应用未授予该文本独立文件执行权限，而是将其作为模型指令并由后端控制解析和导出。旧应用与上游占位符建议共同造成最终正文残留“待补充”，项目增加输出校验并测试拒绝行为。该经验用于本分析流程的边界设计：不让说明、来源标签或未知字段被改写成事实。

截至本次审阅，原快照中的部分通用建议与本地覆盖规则仍同时存在，文本规则不应视为强制安全保证。后端校验与用户核对仍必要。该局限在报告中明确，没有伪称完成全面Skill评估。
