# Reliable DevOps Incident Agent Lab

这是一个从工程基础逐步演进为单 Agent 的教学母本。

## 当前阶段

模块 9：Tool Reliability。

当前已有确定性故障证据工具、显式 LangGraph state/node/edge、稳定流式业务事件、
同thread检查点续接、跨thread共享知识、高风险动作的人工批准/拒绝恢复链路，
FastAPI JSON/SSE HTTP 边界，以及带 timeout、选择性 retry 和 audit 的可靠工具执行层。
真实 LLM 将在后续集成中接入。

## 模块 9 实际示例

```powershell
uv run python examples/module_09_tool_reliability.py
```

该示例运行暂时故障重试成功、永久错误不重试和超时失败三条真实 LangGraph 路线，
并打印业务事件、完整 Message 历史和每一次工具尝试的 audit 记录。

## 当前命令

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
```

这些命令分别检查锁文件、静态问题和格式。模块 7 起保留历史测试不动，模块验收
改用直接运行的完整业务示例。
