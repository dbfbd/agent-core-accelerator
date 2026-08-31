# Architecture

## 当前结构：模块 6 Thread、Checkpoint、Store

```text
agent-core-accelerator/
├─ pyproject.toml       # 项目声明
├─ uv.lock              # uv 生成的依赖解析结果
├─ README.md            # 项目入口说明
├─ COURSE_PLAN.md       # 课程地图
├─ PROGRESS.md          # 学习与验收记录
├─ ARCHITECTURE.md      # 当前结构和调用链
├─ DECISIONS.md         # 设计理由和教学简化
├─ .gitignore           # Git 忽略规则
├─ src/
│  └─ incident_agent/
│     ├─ __init__.py    # 包边界
│     ├─ models.py      # 外部输入校验
│     ├─ diagnostics.py # 异步准备流程
│     ├─ fixtures.py    # 固定本地证据
│     ├─ tools.py       # 确定性只读工具
│     ├─ tool_runtime.py # ToolCall 到 Python 工具的桥
│     ├─ scripted_model.py # 确定性假模型
│     ├─ agent_loop.py  # 手工 model-tool-model 循环
│     ├─ graph_state.py # LangGraph 共享状态及部分更新结构
│     ├─ graph_agent.py # LangGraph 节点、条件边和运行入口
│     ├─ agent_events.py # 对外稳定的流式业务事件
│     ├─ streaming_agent.py # 原始图 update 到业务事件的翻译层
│     ├─ thread_archive.py # thread地址、自动存档和会话续接
│     └─ shared_knowledge.py # 跨thread服务知识Store
└─ tests/
   ├─ test_package.py     # 包安装边界测试
   ├─ test_models.py      # 输入校验测试
   ├─ test_diagnostics.py # 异步流程测试
   ├─ test_tools.py       # 工具行为测试
   ├─ test_agent_loop.py  # 手工循环的完整消息轨迹测试
   ├─ test_graph_agent.py # LangGraph 拓扑和消息轨迹测试
   ├─ test_streaming_agent.py # 流式业务事件顺序测试
   ├─ test_thread_archive.py # 同thread续接和thread隔离测试
   └─ test_shared_knowledge.py # 跨thread共享知识测试
```

`.venv/`、缓存和 `.git/` 是工具生成目录，不属于项目源码结构。

## 锁文件检查调用链

```text
uv lock --check
→ uv 读取 pyproject.toml
→ uv 读取 uv.lock
→ uv 比较项目声明与锁定结果
→ 一致时退出码为 0
```

这条调用链全部位于项目配置和 uv 的边界内，不会执行项目业务代码。

## 测试调用链

```text
uv run pytest
→ uv 检查 pyproject.toml、uv.lock 和 .venv（uv 边界）
→ pytest 发现 tests/test_package.py（pytest 边界）
→ test_incident_agent_package_is_importable()（项目测试代码）
→ importlib.import_module("incident_agent")（Python 标准库边界）
→ src/incident_agent/__init__.py（项目源码）
→ pytest 计算 assert 并汇总结果（pytest 边界）
```

## 模块 1 调用链

```text
dict 输入
→ IncidentRequest.model_validate()（Pydantic 边界）
→ prepare_incident()（项目 coroutine）
→ await status_loader(service)（注入依赖）
→ PreparedIncident 或 EvidenceUnavailableError（项目代码）
```

这条模块 1 教学路径仍被保留，但不参与当前 LangGraph Agent 主路径。

## 模块 2 调用链

```text
原始参数
→ MetricsQuery / LogSearchQuery / DeploymentQuery（Pydantic）
→ tools.py 业务规则检查
→ fixtures.py 固定数据过滤
→ 结构化结果或明确业务异常
```

## 模块 3 调用链

```text
agent_loop.py 创建 SystemMessage + HumanMessage
→ scripted_model.py 返回 AIMessage(tool_calls)
→ tool_runtime.py 校验并执行 tools.py
→ tool_runtime.py 创建匹配 call ID 的 ToolMessage
→ scripted_model.py 读取完整消息历史并返回 AIMessage(final)
```

消息类来自 LangChain Core；模型回复来自项目 ScriptedModel；工具执行循环由项目实现。

## 模块 4 调用链

```text
run_graph_agent() 创建初始 AgentState
→ START edge 进入 model node
→ model node 返回 AIMessage，并由 add_messages 合入状态
→ conditional edge 检查 AIMessage.tool_calls
   ├─ 有调用：进入 tools node
   │  → execute_tool_call() 返回 ToolMessage
   │  → tools edge 回到 model node
   └─ 无调用：进入 END
→ graph.ainvoke() 返回最终 AgentState
```

手工循环仍保留为教学对照；LangGraph 版本把循环条件和跳转路线注册为可检查的图结构。

## 模块 5 调用链

```text
stream_graph_agent() 先 yield AgentStartedEvent
→ graph.astream(..., stream_mode="updates", version="v2")
→ model update + ToolCall
→ yield ToolsRequestedEvent
→ tools update + ToolMessage
→ yield ToolCompletedEvent
→ final model update 暂存答案
→ graph 到达 END
→ yield AgentCompletedEvent
```

`AgentState` 表示当前完整现场；LangGraph update 表示一个节点刚改了什么；`AgentStreamEvent` 表示调用方应该知道的业务进展。

## 模块 6 调用链

```text
thread_continue(graph, thread_id, Human1)
→ checkpointer找不到旧状态，创建System + Human1
→ graph保存每步Checkpoint
→ 最终消息为System/Human1/AI(ToolCall)/ToolMessage/AI1

thread_continue(graph, same_thread_id, Human2)
→ checkpointer加载上一轮完整AgentState
→ add_messages追加Human2
→ model读取全部旧消息并返回AI2
→ 最新Checkpoint保存System/Human1/AI/Tool/AI1/Human2/AI2
```

Store独立路径：

```text
store_save_service_note(shared_store, note_from_thread_A)
→ namespace=("service_knowledge", "checkout-api")
→ store_list_service_notes(shared_store, "checkout-api")
→ store_recall_as_system_message() 创建共享知识SystemMessage
→ thread_continue(thread_B, context_messages=[knowledge_message])
→ thread_B模型实际读取主System/共享知识System/Human
```
