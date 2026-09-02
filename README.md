# Reliable DevOps Incident Agent Lab

这是一个从工程基础逐步演进为单 Agent 的教学母本。

## 当前阶段

模块 8：FastAPI Agent Service。

当前已有确定性故障证据工具、显式 LangGraph state/node/edge、稳定流式业务事件、
同thread检查点续接、跨thread共享知识、高风险动作的人工批准/拒绝恢复链路，
以及 FastAPI JSON/SSE HTTP 边界。真实 LLM 将在后续集成中接入。

## 模块 8 实际示例

```powershell
uv run python examples/module_08_http.py
```

该示例启动真实本地 Uvicorn 服务器，访问 health、invoke、stream、history 和
resume，并打印 JSON、SSE、完整 Message 历史与审批结果。

## 当前命令

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

这些命令分别检查锁文件、静态问题、格式和测试。当前测试覆盖数据模型、异步准备
流程、三个业务工具、Agent运行轨迹、流式事件顺序、会话存档和共享知识隔离。
