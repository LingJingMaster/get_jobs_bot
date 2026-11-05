# Get Jobs — Boss直聘版

Python + TypeScript 本地求职助手，基于原 Get Jobs 项目改写。仅保留 **Boss直聘**；不再需要 Java、Spring Boot、Gradle 或预先下载数据库。

- 后端：Python 3.11+、FastAPI、SQLite、Playwright
- 前端：TypeScript、Next.js、React
- 支持：配置与黑名单、持久浏览器登录、岗位采集和筛选、投递历史与分析、CSV 导出、OpenAI 兼容 AI 招呼语、可选图片简历

> **验证边界：** 自动化测试和前端构建已通过，但尚未使用真实 Boss 账号验证页面选择器、登录检测及消息发送。页面结构变化会导致流程停止。不要把本项目视为已保证可用的无人值守投递工具。

## 启动

需要本机桌面环境、Python 3.11+、Node.js 20.9+ 和 pnpm。只支持本机使用，不要将带有简历、API 密钥与登录会话的服务暴露到公网。

在项目根目录运行：

```sh
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 9527
```

Windows PowerShell 用 `backend\.venv\Scripts\Activate.ps1` 激活环境。

另开终端：

```sh
cd front
pnpm install --frozen-lockfile
pnpm dev
```

访问 <http://127.0.0.1:3000/boss/>，API 文档在 <http://127.0.0.1:9527/docs>。

生产前端预览：

```sh
cd front
pnpm build
pnpm start
```

`pnpm start` 使用 Python 静态服务器提供 `front/out/`，仍需独立运行后端。修改后端地址时，在前端构建前设置 `NEXT_PUBLIC_API_BASE`；后端 CORS 默认仅允许本机 3000 端口。

## 使用流程

1. 保存 Boss 搜索关键词、城市、筛选条件和真实招呼语。默认关闭 AI、重复沟通和图片简历，不附带任何人的履历。
2. 点击“打开浏览器登录”，自行完成扫码及平台验证。项目不会绕过验证码。
3. 点击“采集岗位（不发送消息）”：每次最多 100 个岗位、每关键词最多 10 轮滚动。记录进入投递分析页。
4. 检查记录和黑名单。筛选选项仅内置部分常用城市，行业目前只内置“不限”；API 支持数字平台代码，未知中文项会报错而非被忽略。薪资下限/上限按月薪 K 比较，无法确认单位的岗位在设置了薪资限制时跳过。
5. 点击“开始投递”并确认，每次最多处理 20 个“未投递”岗位。AI 使用环境配置中的 `BASE_URL`、`API_KEY`、`MODEL`；接口需兼容 OpenAI chat completions。
6. 停止任务会取消工作并关闭浏览器。退出登录会先关闭浏览器，再删除项目专用 profile。

### 发送结果与限制

- 发送前记录为“发送待确认”。只有找到本人发送的文本消息气泡才标记“已投递”。中断或结果未知时，不会自动重试该记录；请人工查看 Boss 聊天记录。
- 点击“立即沟通”本身可能触发平台默认问候；即使后续输入失败，也应人工检查。
- 简历上传支持 JPG/PNG/WebP、PDF、Word（DOC/DOCX），文件最大 10MB。文档限 1–5 页，本机渲染为宽 1440px 的 PNG，多页按顺序拼成长图；图片上限 2000 万像素，转换结果不能超过 10MB。Word 转换需安装 LibreOffice 并让 `soffice` 位于 PATH（macOS：`brew install --cask libreoffice`）。转换成功后替换旧图，失败则保留旧图。上传后请预览确认排版；自动发送使用聊天窗口的图片入口，发送后仅记录已提交，不保证送达。
- 默认跳过“继续沟通”。开启重复沟通后，从配置的每行消息中随机选一条；本地已经投递过的记录仍不会自动重复处理。
- 自动 AI 招呼语会把填写的经历与岗位描述发往用户配置的模型服务。请自行确认其隐私条款。
- 暂未移植旧版聊天记录推断黑名单、企业微信通知，以及复杂 iframe/新窗口聊天适配。黑名单可手动维护。
- 原 Java 数据库不自动迁移；请保留备份，不要把 `GETJOBS_DB` 指向旧库。新库默认自动创建于 `backend/db/getjobs.db`。

## 数据与隐私

- 数据库：`backend/db/getjobs.db`，可用 `GETJOBS_DB` 指定其他新数据库路径。
- 登录态：`backend/data/boss-profile/`
- 图片简历：`backend/data/uploads/boss-resume.png`
- 上述目录已加入 Git 忽略。数据库包含配置和 API 密钥，未做静态加密，请保护本机权限。单后端进程运行，不要开启多个 Uvicorn workers。

## 开发与测试

```sh
backend/.venv/bin/python -m pytest backend/tests -q
cd front
pnpm typecheck
pnpm build
```

测试使用临时数据库、模拟 HTTP 服务和模拟浏览器对象，不需要真实账号，也不发送真实招聘消息。

```text
backend/app/main.py       API、任务调度与数据库配置
backend/app/browser.py    浏览器登录与生命周期
backend/app/collector.py  Boss 岗位采集
backend/app/delivery.py   招呼、消息发送与结果确认
backend/app/jobs.py       过滤、持久化与统计
backend/app/ai.py         OpenAI 兼容调用
backend/app/options.py    Boss 选项字典
backend/tests/            自动化测试
front/app/                TypeScript 页面
```

请遵守平台服务条款，不进行无差别骚扰或绕过平台限制。原项目许可证和贡献者协议保留在 `LICENSE`、`CLA.md`；适用 PolyForm Noncommercial 1.0.0，禁止未经授权的商业使用。
