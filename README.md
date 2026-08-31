# Reliable DevOps Incident Agent Lab

这是一个从工程基础逐步演进为单 Agent 的教学母本。

## 当前阶段

模块 6：Thread、Checkpoint、Store。

当前已有确定性故障证据工具、显式 LangGraph state/node/edge、稳定流式业务事件、
同thread检查点续接和跨thread共享知识。真实 LLM 与 HTTP 服务将在后续模块接入。

## 当前命令

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

这些命令分别检查锁文件、静态问题、格式和测试。当前测试覆盖数据模型、异步准备
流程、三个业务工具、Agent运行轨迹、流式事件顺序、会话存档和共享知识隔离。
