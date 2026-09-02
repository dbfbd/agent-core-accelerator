# Decisions

## D-001：使用 uv 管理项目

- 选择：由 `pyproject.toml` 声明依赖，由 `uv.lock` 保存解析结果。
- 原因：统一项目环境、依赖锁定和命令执行。
- 拒绝：全局 `pip install`，因为安装状态容易与项目声明分离。

## D-002：采用 src layout

- 选择：后续把导入包放在 `src/incident_agent/`。
- 原因：只有正确安装项目后才能导入，避免根目录导致的偶然成功。
- 代价：开发环境必须执行安装或使用 `uv run`。

## D-003：依赖按教学需要逐步加入

- 选择：模块 0 只加入格式检查和测试工具。
- 拒绝：提前安装 LangChain、LangGraph、FastAPI 和 MCP SDK。
- 原因：依赖应在它所解决的问题出现时加入，否则会隐藏学习边界。

## S-001：教学阶段的简化

1. 简化内容：当前只验证项目声明、安装和导入，不构建部署制品。
2. 简化原因：模块 0 尚无业务行为。
3. 生产替代：CI 中构建 wheel，并在干净、多版本环境中安装测试。
4. 当前限制：本模块通过不能证明 Agent 正确、安全或可部署。

## D-004：边界输入使用 Pydantic，内部结果使用 dataclass

- 外部字典通过 `IncidentRequest` 做运行时校验。
- 已验证输入和本地假数据组合成 `PreparedIncident`，不重复执行 Pydantic 校验。
- 状态加载能力通过函数参数注入，使业务逻辑无需绑定真实 I/O 客户端。

## D-005：工具使用异步接口和同步本地 fixture

- 三个工具暴露 `async def` 接口，为未来网络 I/O 保留一致调用方式。
- 当前固定数据查询不伪造延迟，因此 coroutine 被 await 后会连续完成本地过滤。
- fixture 使用 tuple 和 frozen 记录，工具只读取并返回新结果容器。

## D-006：使用 LangChain 消息，手工实现 Tool Calling 循环

- 使用 `langchain-core` 的标准消息类型，不复制消息协议。
- ScriptedModel 按预设 AIMessage 返回结果，使测试不依赖真实模型。
- 当前循环显式执行并回填 ToolMessage；LangGraph 自动循环留到模块 4。

## D-007：保留手工循环并新增显式 LangGraph 状态图

- 保留 `agent_loop.py` 作为模型、工具和消息轮转的可读基线。
- 使用自定义 `AgentState` 和 `add_messages` reducer，明确消息如何跨节点累计。
- 使用项目自己的工具执行节点复用 `execute_tool_call()`，暂不引入预构建 `ToolNode`，以便先看清节点职责。
- 条件边显式列出 `tools` 与 `END` 路线，使运行和图拓扑都可验证。

## D-008：对外流式事件与 LangGraph 原始 update 解耦

- 使用 `graph.astream(..., stream_mode="updates", version="v2")` 获取节点完成后的状态更新。
- 由 `streaming_agent.py` 把内部 node/update 结构翻译为稳定的 Pydantic 业务事件。
- 当前 ScriptedModel 不支持 token chunk，因此不伪造逐 token 输出；本模块实现真实的步骤级流。
- 事件模型预留给后续 FastAPI SSE 层，接口无需直接依赖 LangGraph 内部 update 字典。

## D-009：强区分线程存档与跨线程知识

- `thread_*` 只处理会话地址和继续会话；`checkpoint_*` 只处理图状态存档；`store_*` 只处理跨线程知识。
- 由 `InMemorySaver` 自动保存每个 graph super-step，并以 `thread_id` 隔离消息历史。
- 每次新用户轮次把 `model_calls` 重置为 0，但通过 `add_messages` 与同 thread 的已存消息合并。
- Store 使用 `("service_knowledge", service)` namespace，明确不把 `thread_id` 放进共享知识地址。
- Store 知识先转换成带稳定 message ID 的独立 `SystemMessage`，再由 `thread_continue()` 注入模型输入；该消息与主系统规则保持可见区分。
- InMemorySaver 与 InMemoryStore 仅用于课程和测试，进程退出后数据消失；生产版本改用数据库实现。

## D-010：高风险动作使用动态 interrupt 审批门

- 只读工具继续走 `model -> tools`；`restart_service` 走
  `model -> approval -> tools`，避免无风险查询也被迫等待人工操作。
- `interrupt()` 前只构造纯数据申请单，因为恢复时审批节点会从开头重新执行。
- 人的决定与原始 tool call 的 ID、名称和参数组成 `ApprovalProof`，防止一张批准单
  被挪用到另一项动作。
- 拒绝会形成与原 ToolCall ID 对应的 ToolMessage，让模型能解释“未执行”的原因，
  但不会调用高风险函数。
- 课程仍使用内存 checkpointer 和模拟重启；生产环境应使用持久化 checkpointer，
  并把实际执行器接到受审计的运维系统。

## D-011：FastAPI 只作为现有 Agent 的 HTTP 边界

- FastAPI 路由只做请求校验、Bearer 身份验证、错误映射和响应转换，不复制
  LangGraph 节点、工具执行或审批逻辑。
- 应用 lifespan 在启动时创建一张带 InMemorySaver 的共享图，因此 `/invoke`、
  `/stream`、`/resume` 和 `/history` 使用同一套 thread 状态。
- JSON 接口返回稳定的 PublicMessage，避免让客户端依赖 LangChain 消息类的全部
  内部字段。
- SSE 直接复用模块 5 的 AgentStreamEvent；模块 8 只负责转换成 ServerSentEvent，
  并补充模块 7 的 approval_required 事件。
- Bearer 令牌只提供最小身份验证，不代表完整授权；高风险动作仍由 ApprovalProof
  和工具执行层校验。
- 当前服务使用固定教学令牌、ScriptedModel、内存 checkpointer 和单进程 Uvicorn。
  生产环境应使用安全的密钥管理、真实模型客户端、持久化 checkpointer、多实例
  状态协调、速率限制、结构化日志和更完整的权限策略。
