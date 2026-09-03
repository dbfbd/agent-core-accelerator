# Progress

## 初始诊断：2026-08-25

| 范围 | 已知情况 | 当前判断 |
|---|---|---|
| Python/OOP | 完成过 Python 俄罗斯方块和 Java 飞机大战 | 具备基础项目经验 |
| asyncio | 将 coroutine 描述为“异步结构体” | 核心定义不准确，模块 1 补强 |
| Pydantic/FastAPI | 近似未使用 | 按零基础教授 |
| LLM/Agent | 接触过基础形式 | 尚未证明能追踪完整调用链 |
| 时间 | 希望 20 小时完成 | 压缩讲解，不降低验收标准 |

## 模块 0：诊断与工程初始化

- 状态：已完成
- 已完成：环境诊断、uv、项目声明、依赖锁定、课程文件、可安装包、测试与执行验证
- 验证：锁检查、Ruff lint、Ruff format、pytest、uv 环境导入均成功；pytest 为
  `1 passed`。系统 Python 导入以退出码 1 失败，符合 src layout 预期。
- 待完成：无
- 得分：不单独计分（按学生要求改为教师自问自答和运行验收）
- 是否通过：是（工程初始化和调用链已验证）

## 模块 1：Python Agent 工程必需基础

- 状态：已完成（教师自检与自动验证模式）
- 已实现：Pydantic 输入模型、async 函数、async generator、dataclass 内部结果、
  函数参数式依赖注入、自定义异常和 AsyncMock 测试
- 验证：锁检查、Ruff lint、Ruff format 均通过；完整测试 `7 passed`
- 得分：未单独评分
- 是否通过：工程验收通过；学生独立复述能力未单独测量

## 考核记录格式

后续每次只记录实际发生的题目、回答摘要、得分、错误点、补强内容和通过状态。

## 模块 2：确定性业务工具

- 状态：已完成（教师自检与自动验证模式）
- 已实现：指标、日志、部署三个确定性只读工具；固定 fixture；输入、输出和业务错误
- 验证：锁检查、Ruff lint、Ruff format 均通过；完整测试 `15 passed`
- 得分：未单独评分
- 是否通过：工程验收通过；学生独立复述能力未单独测量

## 模块 3：Messages 与原始 Tool Calling

- 状态：已完成（教师自检与自动验证模式）
- 已实现：LangChain 标准消息、工具 schema、ToolCall 执行桥、ScriptedModel 和手工循环
- 验证：完整 model → tool → model 轨迹、未知工具和步数限制；完整测试 `18 passed`
- 得分：未单独评分
- 是否通过：工程验收通过；学生独立复述能力未单独测量

## 模块 4：LangGraph 核心

- 状态：已完成（教师自检与自动验证模式）
- 已实现：显式 AgentState、消息 reducer、模型节点、工具节点、条件边、图编译和异步运行入口
- 验证：图拓扑、完整 model → tool → model 轨迹和模型调用上限；完整测试 `21 passed`
- 得分：未单独评分
- 是否通过：工程验收通过；学生独立复述能力未单独测量

## 模块 5：Streaming 与事件模型

- 状态：已完成（教师自检与自动验证模式）
- 已实现：LangGraph `updates` 异步流、稳定领域事件、开始/工具请求/工具完成/结束事件和直接回答路径
- 验证：使用 `anext()` 逐个拉取事件，证明开始事件先于模型调用；使用 `values` 流验证四个完整 Message 状态快照；完整测试 `24 passed`
- 得分：未单独评分
- 是否通过：工程验收通过；学生独立复述能力未单独测量

## 模块 6：Thread、Checkpoint、Store

- 状态：已完成（教师自检与自动验证模式）
- 已实现：thread address、InMemorySaver 自动检查点、同线程多轮续接、最新 StateSnapshot 读取、跨线程服务知识 Store
- 验证：第一轮完整保存 System/Human/AI(ToolCall)/ToolMessage/AI，第二轮在同一 thread 追加 Human/AI；不同 thread 状态隔离；共享 Store 跨 thread 可见，且新 thread 的模型输入实际包含共享知识 SystemMessage；完整测试 `30 passed`
- 得分：未单独评分
- 是否通过：工程验收通过；学生独立复述能力未单独测量

## 模块 7：Interrupt、Resume 与人工审批

- 状态：已完成（真实业务示例模式）
- 已实现：高风险重启工具、审批申请单、`interrupt()` 暂停、同 thread 的
  `Command(resume=...)` 恢复、批准凭证精确匹配和拒绝不执行
- 实际示例：批准路线在恢复后产生模拟重启执行回执；拒绝路线只产生明确的拒绝
  ToolMessage。两条路线都保留完整 System/Human/AI(ToolCall)/ToolMessage/AI 状态，
  最终清空一次性审批凭证
- 是否通过：核心暂停与恢复链路已经由可直接运行的用户业务示例完整体现

## 模块 8：FastAPI Agent Service

- 状态：已完成（真实 HTTP 示例模式）
- 已实现：FastAPI lifespan、Bearer 身份验证、Pydantic HTTP 契约、`/health`、
  `/invoke`、`/stream`、`/resume`、`/history/{thread_id}`，以及带 checkpoint 的
  JSON 和 SSE 两种调用方式
- 实际示例：Uvicorn 真实监听 `127.0.0.1:8765`；健康检查返回 200；无令牌调用
  返回 401；普通调用返回完整 System/Human/AI；SSE 依次返回
  agent_started/tools_requested/tool_completed/agent_completed；history 保存完整
  System/Human/AI(ToolCall)/ToolMessage/AI；高风险请求返回 approval_required，
  `/resume` 后才产生 RestartReceipt ToolMessage；高风险 SSE 返回
  agent_started/tools_requested/approval_required
- 验证：锁文件检查、Ruff 静态检查和格式检查通过；未运行测试
- 是否通过：HTTP、SSE、thread、history 和 approval/resume 已由可直接运行的
  本地网络示例完整体现

## 模块 9：Tool Reliability

- 状态：已完成（真实业务示例模式）
- 已实现：统一 ToolCatalog、可注入 ToolRuntime、timeout、暂时/永久/超时错误分类、
  retry_safe 选择性 retry、逐次 ToolAttemptRecord、失败 ToolMessage 和 tool_failed
  流式事件
- 实际示例：暂时故障第一次记录 retrying、第二次成功；永久 ValueError 即使最多
  允许三次也只执行一次；慢工具在 0.01 秒限制后产生 timeout。三条路线均保存完整
  System/Human/AI(ToolCall)/ToolMessage/AI，失败路线仍由模型生成最终解释
- 验证：真实模块九示例、锁文件检查、Ruff 静态检查、格式检查和 Git diff 检查通过；
  未运行测试
- 是否通过：工具成功、可重试失败、不可重试失败和超时路线均有 Message、事件与
  audit 三层一致证据

## 模块 10：MCP

- 状态：已完成（真实 stdio 子进程示例模式）
- 已实现：独立 FastMCP 工具服务器、MCP 客户端生命周期、工具发现、远程调用结果
  归一化，以及远程 ToolSpec 到既有 ToolCatalog/ToolRuntime 的无缝接入
- 实际示例：Python 子进程通过标准输入输出建立 MCP 会话，发现四个工具；模型请求
  `get_service_metrics` 后，调用跨进程到达真实工具并返回匹配 call ID 的 ToolMessage
- 验证：`examples/module_10_mcp.py`、Ruff 与锁文件检查通过；未运行测试
- 是否通过：MCP 不改变 Agent 主循环，外部工具已能沿既有可靠执行链工作

## 模块 11：RAG

- 状态：已完成（真实本地知识检索示例模式）
- 已实现：Markdown 运行手册、文档切块、确定性本地 TF-IDF 检索、带 source/heading/
  score 的结果模型，以及普通 `search_runbooks` ToolSpec
- 实际示例：checkout timeout 查询命中 `checkout-api.md` 的 Payment upstream timeout
  和 Safe response 两节；完整 Message 链保留查询、ToolCall、带来源 ToolMessage 和
  最终引用式 AIMessage
- 验证：`examples/module_11_rag.py` 与 Ruff 通过；未运行测试
- 是否通过：模型回答所用的本地知识已形成可追溯工具证据，而非直接塞入系统提示

## 模块 12：Tracing 与 Evaluation

- 状态：已完成（轨迹重建与离线业务用例模式）
- 已实现：每轮独立 run_id、完整 Message 状态重建 RunTrace、按 run_id 查询工具
  audit、RAG 引用用例、受控失败用例和确定性评分结果
- 实际示例：RAG 路线与依赖失败路线都打印完整 System/Human/AI(ToolCall)/Tool/AI
  轨迹；必需工具、最终答案文本和错误 ToolMessage 等检查全部通过
- 验证：`examples/module_12_quality.py` 与 Ruff 通过；未运行测试
- 是否通过：一次运行的“走了哪条路、用了什么工具、结果是否满足业务条件”可以
  分别由 trace、audit 与 evaluation 回答

## 模块 13：最终服务装配

- 状态：已完成（真实 HTTP + 进程重启恢复模式）
- 已实现：环境配置、demo/OpenAI 模型网关、SQLite checkpointer 生命周期、MCP/RAG/
  runtime/graph 统一装配、可执行 `incident-agent` 命令，以及最终 FastAPI 服务
- 实际示例：第一次 Uvicorn 进程通过 `/invoke` 产生完整 RAG Message 链，并通过
  `/trace/{run_id}` 与 `/audit/{run_id}` 返回运行证据；关闭后第二次启动从同一 SQLite
  文件通过 `/history/{thread_id}` 恢复相同 run_id 和全部 Message；另一条高风险路线
  在第一次进程 interrupt，第二次进程通过 `/resume` 批准并完成模拟重启
- 验证：`examples/module_13_final_service.py`、模块 10–12 示例、历史 HTTP 示例、锁
  文件、Ruff、格式和 diff 检查；未运行测试
- 是否通过：前 12 个模块已被接成一个可配置、可启动、可重启续接的最终母本项目
