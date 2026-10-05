# AI 心情搭子

这是 Rich 的第一个完整 AI 应用项目。

## 项目目标

用户输入一段当日心情，应用返回结构化的情绪反馈和一个短小、可执行的行动建议，并保存历史记录。

## 里程碑

- [x] M1：需求与验收标准
- [x] M2：可运行的网页原型（假 AI）
- [x] M3：数据持久化
- [x] M4：接入真实 AI
- [x] M5：异常处理与安全边界（学习版，小样本模型评估）
- [x] M6：自动化测试与浏览器验收
- [x] M7：文档、源码打包与干净环境验收

## 当前阶段

2026-10-05：本机单用户 MVP v1.0 完成。50 项 Python 测试、10 项前端测试通过；DeepSeek 真实联调、6 条模型评估、桌面/390px 窄屏浏览器验收及全新虚拟环境安装启动通过。见 `docs/acceptance.md` 和 `docs/evaluation.md`。不是公网商业产品，也不是医疗工具。

## 本地运行（PowerShell）

前置条件：Windows、Python 3.14、可访问 Python 包仓库及所选模型服务的网络。
仅运行网页不需要 Node；运行前端自动测试才需要安装 Node.js（建议 22+）。
解压 ZIP 后，进入包含 `README.md` 的 `ai-mood-buddy` 目录，在该目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

已有环境可以跳过创建步骤。交付包故意不包含 `.env`、个人数据库和虚拟环境。
上面的复制只在 `.env` 不存在时执行，不会覆盖已有密钥。
当前默认使用 DeepSeek。在本机 `.env` 中填写：

```dotenv
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_MODEL=deepseek-flash
```

不要粘贴密钥到聊天、前端或 Git。DeepSeek 不需要 OpenAI API 额度，使用自己的 API 账户。
若要切回 OpenAI，将 `AI_PROVIDER` 改为 `openai`，再填写 `OPENAI_API_KEY` 和 `OPENAI_MODEL`（示例 `gpt-4o-mini`）。
两家密钥分开读取，不会跨供应商回退；请求地址固定为对应官方域名。
环境变量优先于 `.env`。配置每次请求读取，修改后刷新页面即可。

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/ 。无需激活虚拟环境。Ctrl+C 停止服务。
以后可双击 `start.cmd` 启动。必须保持终端运行；不要直接双击 `index.html`，页面需要后端。
缺少密钥时首页和历史仍可使用，分析按钮提示配置问题；不会返回伪造 AI 结果。
本阶段仅供本机单用户使用，没有登录鉴权，不要直接暴露到公网。

## 自动测试（不调用收费模型）

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

Python 测试用临时数据库和模拟 HTTP 响应验证官方 SDK、输入输出校验和失败路径。
Node 测试使用 DOM 替身检查页面事件行为，另做了真实浏览器验收；两者不能互相替代。
可选隔离演示：运行 `.\.venv\Scripts\python.exe -m tests.browser_server`，打开 `http://127.0.0.1:8001/`。
这是明确标记的模拟服务，不收费、不读取密钥，记录在临时库；停止后自动清理测试库。
输入 `测试失败` 进入错误分支，输入 `安全测试` 进入支持分支，其他输入返回固定测试卡片。

## AI 数据流与边界

`浏览器 → 输入校验 → ai_service → 所选供应商 → MoodAnalysis 校验 → SQLite → 网页`

- 每次只发送当前心情和固定提示词，不发送历史；密钥只在后端使用。
- OpenAI 使用 Responses 结构化输出（`store=False`）；DeepSeek 使用 Chat Completions JSON Output，并在本地用同一个模型校验字段。JSON 语法正确不代表字段必然正确。
- DeepSeek 请求关闭思考模式，适用于当前短小的单轮分析任务。供应商数据保留政策需另行查看，不能声称无日志保留。
- 网络操作超时配置为 30 秒，不自动重试；网页等待上限为 45 秒。
- 格式错误、拒答、截断、超时和上游错误返回明确提示，均不写记录。
- 前端超时不一定终止后端处理，遇到此情况先查看历史再重试，避免重复记录。
- 模型返回 `support_needed` 时展示固定支持提示，不保存成普通分析。
- 格式验证不保证内容准确；安全分支依赖模型判断，可能漏报/误报。已完成 6 条小样本评估，不构成安全保证。
- 本机服务限制 Host，并拒绝带非同源 Origin 的写请求；页面启用内容安全策略和禁止缓存。没有账号认证，其他本机程序仍可调用接口。
- 字符长度按去掉首尾空白后的 Unicode 码点计算，前后端保持一致；组合 emoji 可能占多个字符。
- `intensity` 是粗略的情绪强度估计，不是临床量表。
- 历史仍可能包含 M2/M3 的假数据；没有自动删除或改写这些旧记录。
- 旧浏览器 localStorage 记录没有自动迁入 SQLite，也没有被本次改动删除。

## 真实请求验收

2026-10-05：以虚构心情输入通过 DeepSeek 真实调用，HTTP 200；数据库查询确认保存成功。
仅清理了本次测试记录。此前连接错误是运行沙箱拒绝联网（Windows 10013），已获准在允许联网的环境启动后端，仍仅监听本机地址。
OpenAI 分支只完成模拟验证。以下步骤可用于后续手动验收：

填好密钥后，用非敏感的虚构描述提交一次。确认回应与描述相关、记录保存、刷新仍存在。
这一步会把测试文本发送至所选供应商，并可能产生 API 费用。
随后评估积极、疲惫、含糊输入和安全支持场景，内容质量需人工判断。
已完成上述六场景的小样本评估，详见 `docs/evaluation.md`；尚未完成大规模、重复采样或专业人员评估。

## 官方参考

- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- [DeepSeek 模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)

## 模块

- `app/config.py`：服务端配置读取。
- `app/schemas.py`：输入、模型输出的数据规则。
- `app/ai_service.py`：提示词、模型调用、错误转换。
- `app/main.py`：HTTP 接口和保存顺序。
- `app/database.py`：SQLite 读写与连接关闭。
- `app/static/`：网页结构、样式、交互。

## 日常使用与排错

- 分析成功后自动保存；历史列表的“查看”可重新打开完整卡片。列表只显示最近 20 条，旧记录仍在数据库；“清空记录”会删除全部，非仅当前 20 条。
- 记录在 `data/mood_buddy.db`，是未加密的本地文件。不要公开分享该文件或 `.env`。需要备份时先停止服务，再复制数据库到你自己的安全位置；恢复前先备份当前库。
- “已配置”只表示存在密钥，不表示额度或联网已验证。密钥失效、余额/频率限制、网络不通时按页面提示检查，不要把密钥发给别人排错。
- 端口 8000 被占用：先确认是否已有本项目在运行；不要随意结束不明进程。也可将启动命令的端口改成 8003，再打开对应地址。
- 本地数据库不可写：检查目录权限、磁盘空间，关闭其他数据库编辑工具后重试。数据库错误不会暴露文件路径或 SQL。
- 浏览器等待超时：先刷新历史确认结果再重试。当前未实现请求幂等键，无法保证网络中断后的重试恰好保存一次。
- 跨站请求被拒绝：从启动命令对应的本机地址打开完整页面，不要从 `file://` 页面调用接口。

## 发布与范围

`requirements.txt` 记录直接依赖；`requirements.lock` 固定本次验证的完整依赖版本，不会自动跟随最新版本。更新依赖后要重跑测试。

生成源码包（目标文件如已存在会覆盖，请选好路径）：

```powershell
.\.venv\Scripts\python.exe scripts/build_release.py mood-buddy-source.zip
```

打包采用白名单，包含代码、文档、测试、启动入口和空白配置模板，排除 `.env`、数据库、虚拟环境、缓存与 Git 元数据；同时生成 SHA-256 校验文件。它是源码交付包，不是免安装 EXE。

本次在同一台 Windows 上用全新虚拟环境与解压副本验证；没有验证另一台物理电脑、Linux、Docker、云部署或 OpenAI 真实调用。公网版需要另做登录鉴权、配额/限流、HTTPS、备份恢复与监控；这些不属于本机单用户 v1 范围。
