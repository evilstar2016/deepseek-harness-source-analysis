# L4 Core API 主干层

> 参照 [系统组件架构图](../02-architecture/system-component-architecture.puml)。本层是产品 API 脊柱，提供稳定 API。所有符号行号均经 AST 工具验证。

## 1. 层职责

提供 Agent Harness 的核心 API：会话事件日志、Agent 接口与注册表、默认驱动循环、工具注册表与执行管线、系统提示装配、per-agent 作用域注册。本层是「一切皆插件」架构的中枢——所有能力接缝与扩展都挂载到本层提供的 `ctx` key 上。

## 2. 主要组件

### 2.1 core/session（会话事件日志）
- **路径**：`packages/core/session/`
- **ctx key**：`ctx.sessions`
- **职责**：追加只写的 `SessionEvent` 日志 + 内存存储；派生模型历史；会话分叉。
- **核心符号**：
  - `Session` 类（`index.ts` L424-757）：会话实例，`append` 方法（L603-654）在源头用 `snapshotJsonValue` 拒绝非可序列化数据。
  - `SessionStore` 类（`index.ts` L791-1154）：会话存储，含 `fork`（分叉）。
  - `SessionEventMap` 接口（`types.ts` L235-332）：声明合并扩展的事件类型体系，13 个事件类型分四类（生命周期/模型可见表面/仅日志/种子标记）。
  - `SessionHeader` 接口（`types.ts` L60-98）：会话头，含 `parentSession`（分叉谱系）。
  - `SessionEvent`（`types.ts` L403-435）：事件联合类型。
- **不变式**：模型可见即已记录——到达模型请求的任何内容必须可从日志重建。

### 2.2 core/agent（Agent 接口与注册表）
- **路径**：`packages/core/agent/`
- **ctx key**：`ctx.agents`
- **职责**：`Agent` 接口、实时注册表、`agent/*` 事件。
- **事件域**：`agent/inbox/*`（队列）、`agent/status`（状态）、`agent/pre-step`（瀑布）、`agent/request`（瀑布）、`agent/request-error`（瀑布）、`agent/turn-stopping`（串行终端，无 `next()`）。

### 2.3 core/agent-loop（默认驱动）
- **路径**：`packages/core/agent-loop/`
- **ctx key**：`ctx.agentLoop`
- **职责**：实现 `Agent` 接口的默认驱动，编排 Turn/Step 生命周期。
- **核心符号**：
  - `AgentLoop` 类（`index.ts` L295-710）：默认驱动实现。
  - `createAgent` 方法（L605-621）：创建 agent。
  - `ReactLoopAgent` 类（`agent.ts` L63-495）：反应式循环 agent。
  - `AgentLoopSettings` 接口（L243-246）、`PreparedAgent` 接口（L149-157）。
- **Turn/Step 流程**：`turn/start` → claim → `agent/pre-step` → `step/start` → `agent/request` → `llm/stream` → `assistant/*` → `tool/call*` → `tools/*` → `tool/result*` → `step/end` → `agent/turn-stopping` → `turn/end`。

### 2.4 core/tools（工具注册表与执行管线）
- **路径**：`packages/core/tools/`
- **ctx key**：`ctx.tools`
- **职责**：作用域工具注册表 + 受保护的执行管线（pre/concurrent execute/post 三阶段）。
- **核心符号**：
  - `ToolRuntime` 类（`index.ts` L786-1862）：工具运行时，含 `dispatchToolBody` 方法（L1531-1559）。
  - `ToolDefinition` 接口（L221-287）：工具定义 schema。
  - `ToolLayer` 类（L713-753）：分层工具管理。
  - `defineTool` 函数（`schema.ts` L544-616）：工具定义工厂。
  - `DefineToolOptions` 接口（`schema.ts` L482-535）。
  - `fuseToolSignals` 函数（L1888-1915）：工具信号融合。
  - `ToolExecutionInput`（L313-337）、`ToolResult`（L290-301）、`ToolExecutionMode`（L343-345）。
- **执行模式**：barrier 与有界滚动池控制并发；pre/post 有序，execute 并发。

### 2.5 core/system-prompt（提示装配）
- **路径**：`packages/core/system-prompt/`
- **ctx key**：`ctx.systemPrompt`
- **职责**：Prompt section 与 tool schema 装配。
- **流程**：`system-prompt/assemble` waterfall——插件注册 prompt section，驱动装配时合并。

### 2.6 core/scope（per-agent 作用域）
- **路径**：`packages/core/scope/`
- **ctx key**：无（库）
- **职责**：per-agent 的作用域注册原语。用某 agent 的 `agent.ctx` 将注册限定到该 agent。

### 2.7 core/agent-default-model / core/agent-tool-presentation
- **路径**：`packages/core/agent-default-model/`、`packages/core/agent-tool-presentation/`
- **职责**：默认模型绑定、工具呈现模式（`ToolPresentationMode` 在 `tools/src/index.ts` L650）。

## 3. 对外接口

| ctx key | 类型 | 说明 |
|---|---|---|
| `ctx.sessions` | SessionStore | 会话创建、追加、分叉、派生 |
| `ctx.agents` | Agent 注册表 | Agent 实时注册与 `agent/*` 事件 |
| `ctx.agentLoop` | AgentLoop | 默认驱动 |
| `ctx.tools` | ToolRuntime | 工具注册与受保护执行 |
| `ctx.systemPrompt` | — | Prompt section 装配 |

## 4. 与其他层的交互

- **上层依赖**：L2（Boot 引入）、L3（Host/Client 驱动与渲染）。
- **下层调用**：
  - agent-loop → `ctx.llm`（L5）：模型请求与流。
  - agent-loop → `ctx.tools`（本层）：工具调度。
  - agent-loop → `ctx.systemPrompt`（本层）：prompt 装配。
  - agent-loop → `ctx.sessions`（本层）：事件追加。
  - tools → Consumer 工具（L5）：shell/fs/web/skill 等。
  - sessions → L6（持久化）：事件日志持久化。

## 5. 关键代码路径

```
packages/core/session/src/index.ts        # Session, SessionStore
packages/core/session/src/types.ts        # SessionEventMap, SessionHeader
packages/core/session/src/invariant.ts    # 会话不变式
packages/core/agent-loop/src/index.ts     # AgentLoop
packages/core/agent-loop/src/agent.ts     # ReactLoopAgent
packages/core/tools/src/index.ts          # ToolRuntime, ToolLayer
packages/core/tools/src/schema.ts         # defineTool, DefineToolOptions
packages/core/system-prompt/src/
packages/core/scope/src/
```

## 6. 技术实现

- **事件溯源**：会话状态是 `SessionEvent` 追加只写日志的派生物。`deriveMessages()` 从日志派生模型历史；raw `assistant/chunk` 保留回放与 UI 保真。
- **Waterfall 事件**：`agent/pre-step`、`agent/request`、`llm/stream`、`tools/pre-execute`、`tools/execute`、`tools/post-execute` 是瀑布——监听者须调 `next()` 委托。
- **串行终端**：`agent/turn-stopping` 无 `next()`，是回合结束的权威检查点。
- **声明合并**：`SessionEventMap` 用 TypeScript declaration merging 扩展，新事件类型由各包追加。JSDoc 需 `@mode` 与 payload `@param`；scoped keys 缺失需 `@dshScopeScan unsupported`。
- **可替换性**：`dsh-agent-loop` 可被替换；UI/hook/工具插件依赖 `dsh-agent`（接口）而非具体 loop。

## 7. 注意事项

- 本层是稳定 API 承诺的核心——改动需谨慎。
- `dsh-agent-loop` 是 swappable 的；扩展插件应依赖 Service Definition（`dsh-agent`）而非具体 Provider。
- 会话日志的不变式（模型可见即已记录）由运行时断言强制——新增模型可见输入必须扩展 `SessionEventMap` 并从日志渲染。
