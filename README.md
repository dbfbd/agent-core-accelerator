# Reliable DevOps Incident Agent

这是一个从 Python 工程基础逐步演进而来的完整单 Agent 教学母本。最终版本把
LangGraph 状态图、工具调用、可靠性、人工审批、FastAPI JSON/SSE、MCP、RAG、
运行追踪、离线评估、真实 OpenAI 模型入口和 SQLite 检查点接在同一条业务链上。

## 最终能力

- 通过 `/invoke` 获取一次完整回答，通过 `/stream` 接收步骤级 SSE 事件。
- 使用 `thread_id` 延续会话；服务重启后仍能从 SQLite 恢复 Message 历史。
- 只读工具可在本地执行，也可通过 MCP stdio 子进程发现和调用。
- `restart_service` 必须先 interrupt，之后由 `/resume` 提交人的批准或拒绝。
- 工具有 timeout、选择性 retry、受控失败 ToolMessage 和逐次 audit 记录。
- `search_runbooks` 返回带 `source` 的本地运行手册证据。
- 每次运行有独立 `run_id`，可通过 `/trace/{run_id}` 与 `/audit/{run_id}` 检查。
- 默认演示模型不需要账号；切换配置后使用真实 OpenAI Responses API 模型。

## 启动

```powershell
Copy-Item .env.example .env
uv sync
uv run incident-agent
```

默认地址是 `http://127.0.0.1:8000`。复制 `.env.example` 后，应先替换
`INCIDENT_AGENT_API_TOKEN`。默认 `demo` 模式会真实运行整张图和 RAG 工具，但不会
请求外部模型。

真实模型模式：

```dotenv
INCIDENT_AGENT_MODEL_PROVIDER=openai
INCIDENT_AGENT_OPENAI_MODEL=gpt-5.6-luna
OPENAI_API_KEY=your-key
```

`OPENAI_API_KEY` 只放在本地 `.env` 或部署平台的密钥配置中，不要提交到 Git。

## 最终端到端示例

```powershell
uv run python examples/module_13_final_service.py
```

示例会启动真实 Uvicorn 服务，调用 RAG，读取 trace 与 audit，并保存一条等待审批的
高风险路线。关闭服务后，它使用同一 SQLite 文件启动第二次，通过 `/history` 证明
普通 thread 已恢复，再用 `/resume` 继续执行重启前留下的 interrupt。

模块 10–12 的聚焦示例仍可单独运行：

```powershell
uv run python examples/module_10_mcp.py
uv run python examples/module_11_rag.py
uv run python examples/module_12_quality.py
```

## 工程检查

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
git diff --check
```

课程从模块 7 起不再扩展或运行测试文件；每个新模块通过真实、可直接运行的业务
示例验收。课程路线、结构、决策和实际进度分别记录在 `COURSE_PLAN.md`、
`ARCHITECTURE.md`、`DECISIONS.md` 与 `PROGRESS.md`。
