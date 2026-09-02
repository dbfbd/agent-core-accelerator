# Architecture

## 当前结构：模块 9 Tool Reliability

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
│     ├─ tool_catalog.py # 工具名称、schema与异步handler目录
│     ├─ tool_reliability.py # timeout、错误分类和选择性retry
│     ├─ tool_audit.py # 每一次工具尝试的最小审计账本
│     ├─ scripted_model.py # 确定性假模型
│     ├─ agent_loop.py  # 手工 model-tool-model 循环
│     ├─ graph_state.py # LangGraph 共享状态及部分更新结构
│     ├─ graph_agent.py # LangGraph 节点、条件边和运行入口
│     ├─ agent_events.py # 对外稳定的流式业务事件
│     ├─ streaming_agent.py # 原始图 update 到业务事件的翻译层
│     ├─ thread_archive.py # thread地址、自动存档和会话续接
│     ├─ shared_knowledge.py # 跨thread服务知识Store
│     ├─ action_tools.py # 必须经人工审批的高风险动作
│     ├─ approval_gate.py # 审批申请、暂停和授权匹配
│     ├─ api_models.py # 稳定的HTTP请求、响应和公开消息格式
│     ├─ api_service.py # HTTP契约到thread/graph/history的应用服务
│     └─ api_app.py # FastAPI lifespan、Bearer校验和HTTP/SSE路由
├─ examples/
│  ├─ module_07_approval.py # 批准与拒绝两条可运行路线
│  ├─ module_08_http.py # 真实Uvicorn服务器和HTTP客户端路线
│  └─ module_09_tool_reliability.py # 重试、永久错误和超时路线
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

## 模块 7 调用链

```text
thread_continue(graph, thread_id, HumanMessage)
→ model返回AIMessage(ToolCall: restart_service)
→ route_after_model()识别高风险工具并进入approval节点
→ request_human_approval()构造ApprovalTicket
→ interrupt(ticket)暂停并由checkpointer保存现场
→ checkpoint_load_pending_approval()把申请单交给调用方
→ thread_resume_approval(HumanDecision)
→ Command(resume=decision)回到同一个approval节点
→ pause_for_human()得到恢复值并构造ApprovalProof
→ tools节点把ApprovalProof交给execute_tool_call()
   ├─ 批准且精确匹配：restart_service()返回RestartReceipt
   └─ 拒绝：不调用restart_service()，返回ActionDenied ToolMessage
→ model读取ToolMessage并输出最终AIMessage
```

## 模块 8 调用链

普通 JSON 路线：

```text
HTTP POST /invoke + Bearer token + JSON body
→ FastAPI解析请求并由AgentInvokeRequest校验字段
→ api_app.py:invoke_agent()
→ api_service.py:AgentHttpService.invoke()
→ thread_archive.py:thread_continue()
→ checkpoint-backed LangGraph
→ AgentRunResponse把完整Message转换成稳定JSON
→ HTTP 200响应
```

SSE 路线：

```text
HTTP POST /stream
→ api_app.py:stream_agent()
→ AgentHttpService.open_stream()
→ thread_prepare_turn()准备同一套thread输入
→ streaming_agent.py:stream_compiled_graph()
→ graph.astream(..., stream_mode="updates")
→ AgentStreamEvent
→ ServerSentEvent
→ text/event-stream分批返回客户端
```

人工审批 HTTP 路线：

```text
POST /invoke触发interrupt
→ AgentRunResponse(status="approval_required", approval=ApprovalTicket)
→ POST /resume提交approved/operator/note
→ Command(resume=HumanDecision)
→ ApprovalProof精确匹配原ToolCall
→ restart_service()或ActionDenied
→ 完整ToolMessage与最终AIMessage返回客户端
```

## 模块 9 调用链

```text
AIMessage(ToolCall)
→ graph_agent.py:execute_tools()
→ tool_runtime.py:ToolRuntime.execute()
→ approval_gate检查高风险权限
→ tool_catalog.py:ToolCatalog.resolve()找到ToolSpec
→ tool_reliability.py:run_with_reliability()
   ├─ 每次handler调用由asyncio.timeout限制等待时间
   ├─ retry_safe + timeout/transient + 仍有次数：记录retrying并再次执行
   ├─ permanent或次数耗尽：记录failed并抛出ToolExecutionFailed
   └─ 成功：记录succeeded并返回工具结果
→ ToolRuntime把结果或ToolFailureReceipt转成同ToolCall ID的ToolMessage
→ streaming_agent根据ToolMessage.status发送tool_completed或tool_failed
→ model读取ToolMessage并生成最终AIMessage
```

ToolCatalog只回答“工具在哪里”；ToolReliability只回答“失败后怎么办”；
ToolAuditLog只记录“每次实际发生了什么”；ToolRuntime负责按固定顺序组织三者。
