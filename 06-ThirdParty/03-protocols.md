# 协议集成

> 本文档基于 AST 符号工具对源码符号进行验证分析生成。代码引用处的行号均来自符号工具验证。

## 1. 集成概述

dsh 通过三类协议集成实现「自动化客户端」与「外部 hook 生态」对接：

- **ACP（Agent Client Protocol）**：`@agentclientprotocol/sdk` 0.25.1，JSON-RPC over stdio，让外部 trusted 客户端驱动 dsh agent。
- **JSON-RPC SDK 协议**：`dsh-sdk-protocol` + `dsh-sdk-client` + `dsh-sdk-server` 自定义实现的 newline-delimited JSON-RPC 协议，提供比 ACP 更完整的 SDK 客户端能力（subagent、session tree 等）。
- **Hook 桥接协议**：`dsh-hook-protocol` + `dsh-hooks-claude-code` + `dsh-hooks-codex` 让 dsh 复用 Claude Code 和 Codex 的 hook 配置和命令生态。

三者都基于「Service Definition / Provider / Consumer」三角色模式，但 ACP 和 SDK 是协议层集成（对外暴露 dsh 能力），hook 桥是兼容层集成（消费外部 hook 生态）。

### 设计哲学

- **进程外 SDK 优先**：所有协议均 over stdio JSON-RPC，无 HTTP 监听端口。
- **复用 wire 协议库**：`dsh-sdk-protocol` 把 newline-delimited JSON-RPC transport 抽成共享包，server 与 client 共享。
- **bridge 而非 reimplementation**：hook 桥执行未修改的 Claude Code / Codex hook 命令，不重新实现其语义。
- **共享执行库 + 独立方言**：`dsh-hook-protocol` 提供 matcher / codec / merge / runner，每个 dialect bridge 只 own 自己的 payload / env / substitution / mapping。

## 2. 支持的服务/产品

| 协议 / 服务 | SDK / 库 | 版本 | 状态 | 说明 |
|---|---|---|---|---|
| ACP (Agent Client Protocol) | `@agentclientprotocol/sdk` | 0.25.1 | GA | JSON-RPC over stdio，automation-only |
| DeepSeek Harness SDK | 自实现 | 0.1.0-rc.5 | GA | 自定义 JSON-RPC，比 ACP 多 subagent 支持 |
| Python SDK | Python 客户端 | — | GA | `python/sdk`，与 TS `HarnessClient` 是 design twin |
| Claude Code Hooks | 自实现 bridge | — | GA | 兼容未修改的 `hooks.json` / `settings` |
| Codex Hooks | 自实现 bridge | — | GA | 兼容未修改的 Codex `hooks.json` |
| JSON-RPC wire | 自实现 transport | — | GA | `JsonRpcLineTransport`，newline-delimited |

## 3. 集成方式

### 3.1 ACP Server（`dsh-acp`）

`apply(ctx, config)`（`packages/acp/acp/src/index.ts:105`）：

- `inject = ['agents']`：ACP bridge 创建并 own agents，其他能力由 agent 组合承载。
- `Config`（`index.ts:70`）：`provider` / `model`（创建 agent 时使用） / `stream`（test-only transport override）。
- 使用 `AgentSideConnection`（来自 `@agentclientprotocol/sdk`）作为 SDK 连接。
- 处理的方法：`initialize` / `authenticate` / `newSession` / `prompt` / `cancel`。
- 通过 `session/notification` 推送 turn 事件。
- **ACP 是 automation-only**：只携带 prompt text / committed assistant text / cancellation / one-shot permission，presentation 和 human-interaction 留给 harness UI 模块。

错误转换（`index.ts:60-67`）：

```typescript
function invalidParams(detail: string): RequestError {
  return RequestError.invalidParams(undefined, detail)
}
function internalError(detail: string): RequestError {
  return RequestError.internalError(undefined, detail)
}
```

`PROTOCOL_VERSION` 从 SDK 导入（`index.ts:21`），ACP 客户端必须匹配。

### 3.2 SDK Wire Protocol（`dsh-sdk-protocol`）

`packages/sdk/protocol/src/index.ts:11` 导出：

- `JsonRpcLineTransport` / `JsonRpcResponseError`（来自 `transport.ts`）
- `JsonRpcTransportPeer`（type）
- 类型：`HarnessSdkRequestMap` / `HarnessSdkResultMap` / `HarnessSdkNotificationMap` / `InitializeParams` / `InitializeResult` / `SessionPromptParams` / `SessionPromptResult` / `SessionEventNotification` / `SessionStatusNotification` / `SubagentStartedNotification` / `SubagentFinishedNotification` / `SdkRunStatus`（来自 `types.ts`）

**newline-delimited JSON-RPC**：每行一个 JSON 消息，stdio transport。Server 与 client 共享此 protocol 包，确保两端 type 一致。

### 3.3 SDK Server（`dsh-sdk-jsonrpc-server`）

`HarnessSdkJsonRpcServer`（`packages/sdk/server/src/server.ts:52`）：

- 构造接收 `ctx` + `transport: JsonRpcTransportPeer` + `options`。
- 订阅 `session/event` → `transport.notify('session.event', ...)`（`server.ts:71`）。
- 订阅 `agent/status` → `transport.notify('session.status', ...)`（`server.ts:75`）。
- 订阅 `session/created` → 处理 subagent `session/start` notification。
- 关键方法：
  - `initialize(params)`（`server.ts:110`）：握手。
  - `prompt(params)`（`server.ts:131`）：发起 turn。
  - `shutdown()` / `performShutdown()`（`server.ts:149 / 154`）：优雅关闭。
  - `getOrCreateSession(sessionId)`（`server.ts:202`）+ `createSession(sessionId)`（`server.ts:217`）。
  - `handleRequest(method, params)`（`server.ts:189`）：分发。
  - `hasAdapterFor(provider)`（`server.ts:236`）：检查 LLM adapter 可用性。

`maxTokensAsSuccess` 选项：deployment 可让 `max-tokens` 终止报告为 `ok` 而非 `error`（`server.ts:43`）。

### 3.4 SDK Client（`dsh-sdk-client`）

`HarnessClient`（`packages/sdk/client/src/client.ts:183`）是低层级 client，**运行在 harness context 之外**，直接 spawn runtime subprocess：

- `inject` 无（非 plugin）。
- `start()`（`client.ts:202`）：spawn runtime 子进程。
- `initialize(params)`（`client.ts:267`）：握手。
- `prompt(params)`（`client.ts:282`）：发起 prompt。
- `request(method, params)`（`client.ts:300`）：低层级 JSON-RPC request。
- `subscribe(filter)`（`client.ts:341`）：订阅 notification 流（`AsyncIterable<HarnessNotification>`）。
- `close()` / `performClose()`（`client.ts:379 / 384`）：通过私有 EOF → SIGTERM → SIGKILL ladder 关闭子进程。
- `subscribeSessionTree(sessionId)`（`client.ts:360`）：订阅整个 session 树（含 subagent）。

错误类型（`client.ts:38-65`）：

- `TransportClosedError`：runtime 子进程消失 / unusable。
- `RequestTimeoutError`：请求超时（`HarnessClientOptions.requestTimeoutMs`）。
- `SdkProtocolError`：runtime 返回的响应不符合协议（如 `session/prompt` 缺 `accepted: true`）。

子进程关闭 ladder（`dispose.ts`）：EOF（关闭 stdin）→ SIGTERM → SIGKILL，grace `STREAM_SETTLE_MS = 100` 让 stdio 流沉淀。

### 3.5 Hook Protocol Library（`dsh-hook-protocol`）

`packages/hooks/hook-protocol/src/index.ts:1` 描述：共享、非 plugin 的 hook 协议库——matching / command 执行 / decoding / restrictive outcome merging / durable event helpers / detached run quiescence。

导出（`index.ts:9-25`）：

- 类型：`CommandHook` / `HookDialect` / `HookOutput` / `MatcherGroup` / `MatcherMode`（`types.ts`）
- `matcherDiagnostic` / `matchesMatcher`（`matcher.ts`）
- `parseHookOutput`（`codec.ts`）
- `DEFAULT_HOOK_TIMEOUT_MS` / `runHook`（`runner.ts`）+ `RunHookOptions` / `RunHookResult`
- `mergeHookOutputs`（`merge.ts`）+ `MergedDecision` / `MergedHookOutcome`
- `appendHookInvoked` / `appendHookResult` / `DEFAULT_STDERR_SUMMARY_MAX_CHARS` / `summarizeStderr`（`events.ts`）+ `HookInvocation` / `HookResultRecord`
- `createDetachedRuns`（`detached.ts`）+ `DetachedRuns`

**核心特性**：
- **matcher engine**：支持多种 matcher 模式（regex / substring 等），通过 `MatcherMode` 区分。
- **stdin/exit-code/stdout codec**：hook 命令通过 stdin 传 payload，exit code + stdout 表达决策。
- **restrictive merge**：多 hook 输出合并采用最严格决策（block 优先）。
- **detached runs**：hook 可声明 detached，在主流程返回后继续运行并 quiesce。

### 3.6 Claude Code Hook Bridge（`dsh-hooks-claude-code`）

`packages/hooks/hooks-claude-code/src/index.ts:9` 说明：bridge for unmodified Claude Code command hooks on harness interception extension points。

- `inject = ['shell']`：需要 `bash` 执行 hook 命令，其他扩展点 opportunistic 通过 `ctx.get` 读。
- 支持的扩展点：`SessionStart` / prompt pre/post / tool pre/post / `Stop` / subagent start/stop。
- **Owns Claude payloads / environment / substitution / decision mapping**；shared execution and parsing 在 `dsh-hook-protocol`。
- `updatedInput` 字段被 log + warn 但**不 honor**（设计取舍）。

`Config`（`index.ts:45`）：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `configPath` | string (required) | — | `hooks.json` 或 settings 文件路径 |
| `pluginRoot` | string | — | 替换 `${CLAUDE_PLUGIN_ROOT}` |
| `projectDir` | string | session workspace | 替换 `${CLAUDE_PROJECT_DIR}` + 导出为 env var |
| `defaultTimeoutMs` | number | `DEFAULT_HOOK_TIMEOUT_MS` (600_000) | hook 默认超时 |
| `stderrSummaryMaxChars` | number | `DEFAULT_STDERR_SUMMARY_MAX_CHARS` | 持久化 stderr 摘要上限 |

### 3.7 Codex Hook Bridge（`dsh-hooks-codex`）

`packages/hooks/hooks-codex/src/index.ts:8` 说明：bridge for unmodified Codex command hooks。

- 同样 `inject = ['shell']`。
- 支持五个点：`SessionStart` / prompt pre/post / tool pre/post / `Stop`（**不支持 subagent start/stop**）。
- **regex-only matchers**，**snake_case payloads without trailing newline**。
- **no hook environment or command substitution**。
- **no pre-tool approval or rewrite path**，**只 blocking decisions 被 honor**。
- 每个 payload携带 `model` 字段（`Config.model` 默认 `''`）。

`Config`（`index.ts:44`）：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `configPath` | string (required) | — | Codex `hooks.json` 路径 |
| `model` | string | `''` | stamp 在每个 payload 上的模型名 |
| `defaultTimeoutMs` | number | `DEFAULT_HOOK_TIMEOUT_MS` | hook 默认超时 |
| `stderrSummaryMaxChars` | number | `DEFAULT_STDERR_SUMMARY_MAX_CHARS` | 摘要字符上限 |

## 4. 代码实现

### 4.1 关键类与文件

| 类 / 模块 | 路径 | 行号 | 角色 |
|---|---|---|---|
| `HarnessSdkJsonRpcServer` | `packages/sdk/server/src/server.ts` | 52-239 | SDK server |
| `HarnessClient` | `packages/sdk/client/src/client.ts` | 183-457 | SDK client（spawn 子进程） |
| `TransportClosedError` | `packages/sdk/client/src/client.ts` | 38 | runtime 死亡错误 |
| `RequestTimeoutError` | `packages/sdk/client/src/client.ts` | 47 | 请求超时错误 |
| `SdkProtocolError` | `packages/sdk/client/src/client.ts` | 59 | 协议响应错误 |
| `JsonRpcLineTransport` | `packages/sdk/protocol/src/transport.ts` | — | newline-delimited JSON-RPC transport |
| `AcpConfig` | `packages/acp/acp/src/index.ts` | 70 | ACP plugin config |
| `apply` (ACP) | `packages/acp/acp/src/index.ts` | 105 | ACP server mount |
| `runHook` | `packages/hooks/hook-protocol/src/runner.ts` | — | hook 命令执行 |
| `parseHookOutput` | `packages/hooks/hook-protocol/src/codec.ts` | — | hook 输出解码 |
| `mergeHookOutputs` | `packages/hooks/hook-protocol/src/merge.ts` | — | restrictive outcome 合并 |
| `createDetachedRuns` | `packages/hooks/hook-protocol/src/detached.ts` | — | detached run quiescence |
| `apply` (Claude Code) | `packages/hooks/hooks-claude-code/src/index.ts` | — | Claude Code bridge mount |
| `apply` (Codex) | `packages/hooks/hooks-codex/src/index.ts` | — | Codex bridge mount |

### 4.2 ACP 与 SDK 的差异

| 维度 | ACP | dsh-sdk |
|---|---|---|
| 协议源 | 第三方标准 `@agentclientprotocol/sdk` 0.25.1 | 自实现 wire protocol |
| 状态 | automation-only | 完整 SDK 客户端能力 |
| Transport | stdio JSON-RPC | stdio newline-delimited JSON-RPC |
| Subagent 支持 | 通过 `session/notification` 间接 | 一等公民：`SubagentStartedNotification` / `SubagentFinishedNotification` + `subscribeSessionTree` |
| Client 实现 | 第三方 SDK 提供 | 自实现 `HarnessClient` + Python twin |
| Server 实现 | `apply(ctx, config)` 函数式 | `HarnessSdkJsonRpcServer` class |
| 关闭协议 | ACP 标准关闭 | EOF → SIGTERM → SIGKILL ladder（`dispose.ts`） |

### 4.3 Hook Bridge 架构

```
外部 hooks.json (Claude Code 或 Codex 格式)
  ↓
parseClaudeCodeConfig / parseCodexConfig  [config.ts]
  ↓
matchesMatcher(matcherGroup, payload, mode)  [hook-protocol/matcher.ts]
  ↓
runHook(command, stdin, options)  [hook-protocol/runner.ts]
  - spawn hook 命令
  - 通过 stdin 传 payload
  - timeout 控制
  ↓
parseHookOutput(stdout, exitCode)  [hook-protocol/codec.ts]
  ↓
mergeHookOutputs(outputs)  [hook-protocol/merge.ts]
  - restrictive: block 优先
  ↓
appendHookInvoked / appendHookResult  [hook-protocol/events.ts]
  - 持久化到 session log
  ↓
createDetachedRuns  [hook-protocol/detached.ts]
  - 主流程返回后继续运行
```

每个 dialect bridge 只 override：
- payload 格式（CamelCase vs snake_case，是否带 trailing newline）
- 环境变量（`CLAUDE_PROJECT_DIR` 等）
- 命令 substitution（`${CLAUDE_PLUGIN_ROOT}` 等）
- matcher mode（regex-only vs 多模式）
- 决策 mapping（pre-tool approval 是否支持等）

## 5. 配置与环境变量

### 5.1 环境变量

| 环境变量 | 作用 | 默认 |
|---|---|---|
| (无独立 env vars) | 协议集成不直接读环境变量 | — |

注：hook 桥接通过 `CLAUDE_PROJECT_DIR` 等 env var **导出给 hook 子进程**，但 dsh 自身不读这些 env var。

### 5.2 Plugin Config

#### ACP（`packages/acp/acp/src/index.ts:70`）

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `provider` | string | — | 创建 agent 时使用的 provider route |
| `model` | string | — | 创建 agent 时使用的 model 名 |
| `stream` | `Stream` | — | test-only transport override |

#### Claude Code Hook Bridge（`packages/hooks/hooks-claude-code/src/index.ts:45`）

见 §3.6。

#### Codex Hook Bridge（`packages/hooks/hooks-codex/src/index.ts:44`）

见 §3.7。

## 6. 错误处理

### 6.1 ACP 错误

- `RequestError.invalidParams(detail)`：保留 invalid-parameter detail（`acp/src/index.ts:60`）。
- `RequestError.internalError(detail)`：failed-turn detail 转为 wire internal error（`acp/src/index.ts:65`）。
- 普通 handler 错误 → generic wire internal error。

### 6.2 SDK Client 错误

| 错误类型 | 含义 | 触发 |
|---|---|---|
| `TransportClosedError` | runtime 子进程消失 | exit / stdio closed / spawn 失败（携带 exit code + stderr tail `STDERR_TAIL_LIMIT=400`） |
| `RequestTimeoutError` | 请求超时 | `requestTimeoutMs` 触发 |
| `SdkProtocolError` | 协议响应不符 | 如 `session/prompt` response 无 `accepted: true` |
| `JsonRpcResponseError` | server 返回的 JSON-RPC error | 从 wire 透传 |

### 6.3 Hook 错误

- **timeout**：`DEFAULT_HOOK_TIMEOUT_MS = 600_000` (10 分钟，CC 默认)，hook 超时被 collect 而非抛。
- **stderr 摘要**：`summarizeStderr` 截取到 `stderrSummaryMaxChars` 字符持久化到 `hook/result` session event。
- **detached failure**：detached run 失败被记录但不影响主流程返回值。
- **restrictive merge**：一个 hook 返回 block，整体 block（即使其他 hook 返回 allow）。

## 7. 扩展指南

### 7.1 添加新 ACP 方法

1. **在 `@agentclientprotocol/sdk` 升级后**：dsh 跟随 SDK 版本（当前 0.25.1）。
2. **在 `dsh-acp/src/index.ts` `apply` 中**：通过 `conn.on(method, handler)` 注册新方法 handler。
3. **handler 签发 `RequestError`** 而非 generic Error，保留 invalidParams / internalError 语义。
4. **测试**：用 ACP client SDK + `mock:llm` server 跑端到端。

### 7.2 添加新 SDK 方法

1. **扩展 `HarnessSdkRequestMap` / `HarnessSdkResultMap`**（`packages/sdk/protocol/src/types.ts`）：添加新 method 名 + params / result 类型。
2. **在 `HarnessSdkJsonRpcServer`** 实现 handler 并加入 `handleRequest` dispatch（`server.ts:189`）。
3. **在 `HarnessClient`** 添加 typed 方法（如 `prompt()`，`client.ts:282`）。
4. **同步 Python SDK**（`python/sdk`）：保持 design twin 一致。
5. **测试**：用 `agent-loop-testkit` 跑端到端。

### 7.3 添加新 Hook Dialect Bridge

参考 Claude Code / Codex 双桥实现：

1. **新建 `packages/hooks/hooks-<dialect>/`**，`peerDependencies` 含 `dsh-hook-protocol`。
2. **`config.ts` 实现 `parse<Dialect>Config(path)`**：解析该 dialect 的 hook 配置格式。
3. **`index.ts` `apply(ctx, config)`**：
   - `inject = ['shell']`（hook 命令通过 bash 执行）。
   - 在每个支持的扩展点（SessionStart / prompt pre/post / tool pre/post / Stop）注册 listener。
   - listener 调用 `matchesMatcher` → `runHook` → `parseHookOutput` → `mergeHookOutputs`。
   - 用 `appendHookInvoked` / `appendHookResult` 持久化到 session log。
4. **Own 该 dialect 的差异**：
   - payload 格式（CamelCase / snake_case / trailing newline 等）
   - matcher 模式（regex-only / 支持其他模式）
   - 环境变量（导出给 hook 子进程的）
   - 命令 substitution（`${...}` 占位符）
   - 支持的扩展点集合
   - 决策 mapping（pre-tool approval / rewrite 是否支持）
5. **加入 bundle**：在 `cordis.yml` 加 `- id: hooks-<dialect>`。
6. **测试**：参考 `hooks-claude-code` / `hooks-codex` 的 testkit 集成。

## 8. 关键 SDK 依赖版本

| 依赖 | 版本 | 用途 |
|---|---|---|
| `@agentclientprotocol/sdk` | 0.25.1 | ACP server（`acp/package.json` + 根 devDependencies） |
| `@deepseek-ai/dsh-sdk-protocol` | workspace:^ | 共享 wire 协议 |
| `@deepseek-ai/dsh-sdk-client` | workspace:^ | TS 客户端 |
| `@deepseek-ai/dsh-sdk-jsonrpc-server` | workspace:^ | SDK server |
| `@deepseek-ai/dsh-hook-protocol` | workspace:^ | hook 共享库 |
| `@deepseek-ai/dsh-hooks-claude-code` | workspace:^ | Claude Code bridge |
| `@deepseek-ai/dsh-hooks-codex` | workspace:^ | Codex bridge |

## 9. 关键发现

1. **ACP 与 SDK 是平行而非嵌套**：ACP 是 automation-only 标准（外部 trusted 客户端），SDK 是 dsh 自有的完整客户端协议（含 subagent 一等支持）；两者都 over stdio JSON-RPC 但 wire 不同。
2. **hook bridge 是兼容层而非重写**：执行未修改的 Claude Code / Codex hook 命令，dsh 只 own 自己的 payload / env / mapping，shared execution 在 `dsh-hook-protocol`。这降低迁移成本。
3. **restrictive merge**：多 hook 输出合并采取最严格决策，确保安全（一个 block 则整体 block）。
4. **SDK client 关闭 ladder**：EOF（关闭 stdin）→ SIGTERM → SIGKILL，加 `STREAM_SETTLE_MS = 100` grace 让 stdio 沉淀——这是 process 子进程关闭的稳健模式。
5. **`HarnessClient` 运行在 harness context 之外**：直接 spawn runtime 而非通过 `dsh-subprocess` service（这是 seam 的 documented exception for SDK-managed transports）。
6. **`updatedInput` 在 Claude Code bridge 不 honor**：设计取舍——log + warn 但不应用，因为重新写 prompt 的语义在 dsh 上下文需要 typed native plugin 而非兼容 bridge。
7. **Python SDK 是 TS `HarnessClient` 的 design twin**：两端驱动同一 runtime 协议，必须同步演进（`server.ts:9-10` 注释）。
8. **Codex 比 Claude Code 受限**：regex-only matchers / snake_case / no env / no substitution / no pre-tool approval / no subagent——这反映 Codex 协议本身更窄，而非 dsh 实现差距。
