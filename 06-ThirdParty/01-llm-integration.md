# LLM 与 AI 框架集成

> 本文档基于 AST 符号工具对源码符号进行验证分析生成。代码引用处的行号均来自符号工具验证。

## 1. 集成概述

dsh 的 LLM 能力是「能力接缝三角色」模式的典型示例：

- **Service Definition（接口声明）**：`@deepseek-ai/dsh-llm` 声明 `LlmAdapter` 抽象类、`LlmRuntime` 注册表与 `llm/stream` waterfall 事件。
- **Service Provider（实现）**：`dsh-llm-deepseek`（直连 fetch + SSE）、`dsh-llm-pi-ai`（基于 pi-ai 库的多协议适配器）注册具体 Adapter。
- **Consumer（消费方）**：`dsh-agent-loop`、`dsh-token-meter`、`dsh-llm-retry` 等通过 `ctx.llm` 调用模型流。

每个 Provider 都有自己的 retryPolicy，但统一的执行器 `dsh-llm-retry` 在 agent loop 失败恢复扩展点上调度重试。

### 设计哲学

- **接缝优先**：核心包 `dsh-llm` 完全 provider-neutral，不含任何 HTTP 或 SDK 依赖。
- **凭据引用**：配置仅承载 `apiKeyEnv`（环境变量名），永不承载 secret 本身。
- **每请求解析**：连接事实和凭据在一次 stream 调用内冻结，避免 in-flight 流观察到配置变化。
- **可重启路由**：`AdapterRegistrationHandle.replace()` 原子替换路由集，无空窗。

## 2. 支持的服务/产品

| 服务名 | SDK / API | 版本 | 状态 | 说明 |
|---|---|---|---|---|
| DeepSeek Chat Completions | 直连 fetch + SSE | OpenAI 兼容 | GA | 默认 Provider，`deepseek-official` 路由，V4-Flash / V4-Pro |
| OpenAI | `@earendil-works/pi-ai` | 0.82.1 | 可选 | 通过 pi-ai 适配器，`openai-completions` 协议 |
| Anthropic | `@earendil-works/pi-ai` | 0.82.1 | 可选 | `anthropic-messages` 协议，Claude 模型 |
| OpenAI Responses | `@earendil-works/pi-ai` | 0.82.1 | 可选 | `openai-responses` 协议 |
| Bedrock / Vertex / Azure | pi-ai catalog | 0.82.1 | 受限 | pi-ai 自带 catalog provider，但本适配器无 SigV4/OAuth/ADC 配置形状，需 route 自带 auth |
| 自定义 OpenAI 兼容网关 | pi-ai `createProvider` | — | 可选 | `acme-gateway` 路由示例：自定义 `baseURL` + `api: openai-completions` |
| DeepSeek Web Search | Anthropic Messages API | `web_search_20250305` | 可选 | 见 `dsh-web-search-deepseek`，与 chat-completions 使用不同的 baseURL |

## 3. 集成方式

### 3.1 Service Definition：`LlmRuntime` 与 `LlmAdapter`

`LlmRuntime`（`packages/llm/llm/src/index.ts:283`）是注册表中枢。它声明 `ctx.llm`（`index.ts:48`）和 `llm/stream` waterfall 事件（`index.ts:64`），核心方法：

- `registerAdapter(providers, adapter): AdapterRegistrationHandle`（`index.ts:337`）：注册一个 Adapter 实例到多个 provider 路由，返回带 `replace()` 的 disposer。
- `registerConfigurableProviders(entries)`（`index.ts:430`）：声明可配置 Provider 目录（settings page 显示）。
- `registerModelDiscovery(namespace, fn)`（`index.ts:503`）：注册端点模型发现回调。
- `prepareCall(options)`（`index.ts:778`）：返回 `PreparedLlmCall`，捕获 config + retryPolicy + adapterDefaults。
- `stream(options)`（`index.ts:912`）：触发 `llm/stream` waterfall 后调用 adapter。

`LlmAdapter`（`index.ts:180`）抽象类只有一个必需方法：

```typescript
abstract stream(options: GenerateOptions): AsyncIterable<StreamChunk>
```

可选 override：`providerInfo`（`index.ts:186`）、`providerRetryPolicy`（`index.ts:195`）、`listModels`（`index.ts:206`）、`resolveModel`（`index.ts:219`）。

### 3.2 Provider：`DeepSeekAdapter`（直连 fetch）

`DeepSeekAdapter`（`packages/llm/llm-deepseek/src/adapter.ts:158`）继承 `LlmAdapter`，是第一个原生实现：

- **transport-only**：连接事实通过 thunk 每操作解析一次，bearer token 通过 per-request resolver，注册插件拥有验证、分层、凭据策略。
- 不依赖任何 SDK，直接 `fetch()` DeepSeek 的 `/chat/completions`。
- 使用 `eventsource-parser` 解析 SSE 流（`packages/llm/llm-deepseek/src/sse.ts:14`）。
- `stream(options)`（`adapter.ts:213`）：单次 resolution 冻结连接事实和凭据快照，复用 `idleWatchdog` 监控空闲。
- `httpErrorCode(status, error)`（`adapter.ts:138`）：把 HTTP 状态码映射到稳定 LlmError code（401/403→`AUTH`、429→`RATE_LIMIT`、5xx→`SERVER`、`quota_deceeded`→`QUOTA_EXCEEDED`）。

构造选项 `DeepSeekAdapterOptions`（`adapter.ts:74`）：

```typescript
interface DeepSeekAdapterOptions {
  options: () => DeepSeekConnectionOptions  // 每操作调用一次
  resolveApiKey: (connection: DeepSeekConnectionOptions) => Promise<string>
  resolveUserId: () => AnonymousUserId
}
```

连接事实 `DeepSeekConnectionOptions`（`adapter.ts:49`）包含 `baseURL`、`apiKeyEnv: CredentialRef`、`defaults`、`maxTokens`、`defaultContextWindow`、`models`、`streamIdleTimeoutMs`、`retryPolicy`。

### 3.3 Provider：`PiAiAdapter`（pi-ai 库）

`PiAiAdapter`（`packages/llm/llm-pi-ai/src/adapter.ts:186`）是 `dsh-llm-deepseek` 的 design-verification twin：

- 基于 `@earendil-works/pi-ai` 库，支持多 provider 路由共享一个 adapter 实例。
- 路由命名 pi-ai 已安装的 provider 时继承其 endpoint/protocol/catalog；命名 pi-ai 未识别的 key 时整体声明。
- `current()`（`adapter.ts:199`）：memoize snapshot，profiles 引用相等即复用。
- `stream(options)`（`adapter.ts:275`）：路由到对应 pi-ai provider 的 stream。
- `providerInfo`（`adapter.ts:227`）：使用配置的 `displayName` 而非路由 key。

支持协议表（`packages/llm/llm-pi-ai/src/provider.ts:47`）：

```typescript
const PROTOCOLS: Readonly<Record<string, () => ProviderStreams>> = {
  'openai-completions': openAICompletionsApi,
  'openai-responses': openAIResponsesApi,
  'anthropic-messages': anthropicMessagesApi,
}
```

`buildProvider(spec)`（`provider.ts:167`）构造 pi-ai Provider：catalog 路由 + 同协议 → `reuseCatalogProvider`（`provider.ts:144`）保留原生实现；其他 → `createProvider` 通过 PROTOCOLS 表构造。

### 3.4 凭据解析

两个 adapter 共用 `assertUsableApiKey(raw, pkg, ref)`（`packages/llm/llm/src/index.ts:137`）：

- 从 `dsh-credentials` 接缝或环境变量获取原始字符串。
- 拒绝空字符串和非 HTTP-header 安全字符。
- 错误消息引导用户修改 `ref` 指向的环境变量，绝不回显 secret。
- 缺失时抛 `LlmError('MISSING_CREDENTIAL')`。

`dsh-llm-pi-ai` 多了一个 detail：profile 不命名 `apiKeyEnv` 时返回 `undefined`，让 pi-ai 的 provider-native ambient discovery 生效（OAuth 等）。一旦命名就 fail-loud，避免 pi-ai 拾取无关的 ambient key（如 `OPENAI_API_KEY`）。

## 4. 代码实现

### 4.1 关键类与文件

| 类 / 模块 | 路径 | 行号 | 角色 |
|---|---|---|---|
| `LlmRuntime` | `packages/llm/llm/src/index.ts` | 283-927 | Adapter 注册表、waterfall 调度 |
| `LlmAdapter` | `packages/llm/llm/src/index.ts` | 180-232 | 抽象 Adapter 基类 |
| `LlmError` | `packages/llm/llm/src/index.ts` | 83 | 类型化错误（AUTH/RATE_LIMIT/NO_ADAPTER 等） |
| `assertUsableApiKey` | `packages/llm/llm/src/index.ts` | 137 | 凭据校验共享逻辑 |
| `AdapterRegistrationHandle` | `packages/llm/llm/src/index.ts` | 238 | 注册句柄（disposer + replace） |
| `DeepSeekAdapter` | `packages/llm/llm-deepseek/src/adapter.ts` | 158-345 | 直连 fetch 适配器 |
| `DeepSeekConnectionOptions` | `packages/llm/llm-deepseek/src/adapter.ts` | 49-71 | 连接事实快照 |
| `httpErrorCode` | `packages/llm/llm-deepseek/src/adapter.ts` | 138 | HTTP 状态到 LlmError code 映射 |
| `parseSse` | `packages/llm/llm-deepseek/src/sse.ts` | 28 | SSE 流解析（基于 eventsource-parser） |
| `PiAiAdapter` | `packages/llm/llm-pi-ai/src/adapter.ts` | 186-357 | pi-ai 多协议适配器 |
| `buildProvider` | `packages/llm/llm-pi-ai/src/provider.ts` | 167 | pi-ai Provider 构造 |
| `TokenMeter` | `packages/llm/token-meter/src/index.ts` | 73-310 | Replay-aware token 计量 |
| `resolveRetryPolicy` | `packages/llm/llm/src/retry-policy.ts` | 145 | Retry policy 解析 |

### 4.2 Provider 插件 apply 流程

`dsh-llm-deepseek` 的 `apply(ctx, config)`（`packages/llm/llm-deepseek/src/index.ts:200`）：

1. **memoized resolver**：`options()` 函数捕获 `lastRaw` + `lastGood`，settings snapshot 失败时保留上一个 good 配置。
2. **resolveApiKey**：通过 `ctx.get('credentials')` 接缝或 `launchEnvironmentOf(ctx).get(ref)` 解析。
3. **构造 adapter**：`new DeepSeekAdapter({ options, resolveApiKey, resolveUserId })`。
4. **registerConfigurableProviders**：声明 `deepseek-official` 路由。
5. **registerAdapter**：注册 `[PROVIDER]` 路由，捕获 `registration`。
6. **installSettingsSection**：挂载 `llm-deepseek` settings namespace，`onChange` 触发 `ensureRegistrationFacts`（retryPolicy 变化时 `registration.replace([PROVIDER])` 原子替换）。

`dsh-llm-pi-ai` 的 `apply`（`packages/llm/llm-pi-ai/src/index.ts:150`）多一步 `directoryEntries` 维护：合并 catalog provider 和 hand-declared route，通过 `directory.replace(entries)` 原子更新 configurable-provider 目录。

## 5. 配置与环境变量

### 5.1 环境变量

| 环境变量 | 作用 | 默认值 / fallback |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek chat-completions 的 API key | 必填（无默认） |
| `DEEPSEEK_BASE_URL` | DeepSeek chat-completions endpoint | `https://api.deepseek.com`（`PUBLIC_BASE_URL`，`llm-deepseek/src/index.ts:104`） |
| `DEEPSEEK_SEARCH_BASE_URL` | DeepSeek web search endpoint（Anthropic-compatible） | 见 `web-search-deepseek/src/index.ts:82`，区别于 chat-completions |
| `E2B_API_KEY` | E2B 远程沙箱 API key（POC） | 见 `dsh-e2b`，非 LLM |
| `<provider>_API_KEY`（如 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`） | pi-ai 路由凭据 | profile 的 `apiKeyEnv` 字段指定 |

### 5.2 Plugin Config（`dsh-llm-deepseek`）

`Config` interface（`packages/llm/llm-deepseek/src/index.ts:62`）：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `apiKeyEnv` | string (credential-ref) | `DEEPSEEK_API_KEY` | 凭据引用 |
| `baseURL` | string | `DEEPSEEK_BASE_URL` 或 `PUBLIC_BASE_URL` | endpoint base |
| `thinking` | `'enabled' \| 'disabled'` | — | 部署 thinking 策略 |
| `reasoningEffort` | `'off' \| 'high' \| 'max'` | `high` | 默认 thinking 强度 |
| `maxTokens` | number | `DEFAULT_MAX_TOKENS` = 256_000 | 每请求输出上限 |
| `defaultContextWindow` | number | `DEFAULT_CONTEXT_WINDOW` = 1_000_000 | 模型未声明时使用 |
| `models` | `DeepSeekCatalogModel[]` | V4-Flash + V4-Pro | 公告模型列表 |
| `streamIdleTimeoutMs` | number | `DEFAULT_STREAM_IDLE_TIMEOUT_MS` = 300_000 | 流读空闲超时 |
| `retryPolicy` | `RetryPolicyConfig` | normal defaults | Provider-owned 重试策略 |

### 5.3 Retry Policy Schema

`RetryPolicySchema`（`packages/llm/llm/src/retry-policy.ts:100`）是 union：

- **normal**（`NormalRetryPolicyConfig`，`retry-policy.ts:36`）：`mode: 'normal'` + `maxRetries`（默认 2）+ `retryableCodes`（默认 `[EMPTY_RESPONSE, RATE_LIMIT, SERVER, TIMEOUT, TRANSPORT]`）+ `backoff`。
- **always**（`AlwaysRetryPolicyConfig`，`retry-policy.ts:48`）：`mode: 'always'` 无限重试直到成功/取消/dispose。
- `BackoffConfig`（`retry-policy.ts:27`）：`initialDelayMs` (500) + `maxDelayMs` (10_000) + `jitterRatio` (0.1) 对称抖动。

## 6. 错误处理

### 6.1 LlmError Code 表

| Code | 含义 | 触发场景 |
|---|---|---|
| `AUTH` | 认证失败 | HTTP 401/403 |
| `RATE_LIMIT` | 速率限制 | HTTP 429 |
| `QUOTA_EXCEEDED` | 配额耗尽 | 错误体含 `quota` 关键字 |
| `CONTEXT_WINDOW_EXCEEDED` | 上下文超长 | HTTP 400 + context window 关键字 |
| `INVALID_REQUEST` | 请求无效 | HTTP 400 其他情况 |
| `SERVER` | 服务端错误 | HTTP ≥ 500 |
| `HTTP_<status>` | 其他 HTTP 错误 | 未识别状态码 |
| `MISSING_CREDENTIAL` | 凭据缺失 | `assertUsableApiKey` 失败 |
| `INVALID_CREDENTIAL_CODE` | 凭据格式错误 | key 含非 HTTP-header 字符 |
| `NO_ADAPTER` | 无适配器 | provider 路由未注册 |
| `UNKNOWN_MODEL` | 未知模型 | pi-ai provider 无该 model |
| `STREAM_CLOSED` | 流异常关闭 | SSE 未见 `[DONE]`（`sse.ts:39`） |
| `LLM_STREAM_IDLE_TIMEOUT` | 流空闲超时 | `streamIdleTimeoutMs` 触发 |
| `EMPTY_RESPONSE_CODE` | 空响应 | 见 `error.ts` |
| `TRANSPORT` | 传输错误 | 网络层失败 |
| `TIMEOUT` | 超时 | 整体请求超时 |
| `REGISTRATION_DISPOSED` | 注册已释放 | `replace()` 在 dispose 后调用 |

### 6.2 重试策略

`dsh-llm-retry`（`packages/llm/llm-retry/src/index.ts:99`）在 agent loop 的 `request-error` 扩展点执行：

- `apply(ctx, config, internals)` 注入 `agents` 服务。
- `localDelay(policy, retry, random)`（`index.ts:58`）：指数退避 + 对称抖动，`Math.min(initialDelayMs * 2^exponent, maxDelayMs) * jitter`。
- `cancellableDelay(delayMs, signal)`（`index.ts:78`）：可被 abort signal 取消的 delay。
- 每次调度重试在 wait 前持久化（durable before cancellable wait）。
- `retryPolicyKey(policy)`（`index.ts:65`）：序列化 policy 用于去重 / 比较。

### 6.3 降级：保留上一个 good 配置

`dsh-llm-deepseek` 的 `options()` resolver（`index.ts:204`）在 settings snapshot 解析失败时：

- 首次失败直接抛出（无 lastGood 可用）。
- 后续失败：保留上一个 `lastGood`，记录 `logger.error`，继续服务 in-flight 请求。
- 这样配置错误不会让运行中的会话崩溃。

## 7. 扩展指南：添加新 LLM Provider

### 7.1 直连方式（参考 `dsh-llm-deepseek`）

1. **新建子包** `packages/llm/llm-<your-provider>/`，`peerDependencies` 含 `@deepseek-ai/dsh-llm`。
2. **实现 `LlmAdapter` 子类**：必填 `stream(options)`，可选 override `providerInfo` / `providerRetryPolicy` / `listModels` / `resolveModel`。
3. **构造 `AdapterOptions`**：包含 `options: () => ConnectionOptions`、`resolveApiKey: (conn) => Promise<string>`、`resolveUserId`。
4. **在 `apply(ctx, config)`**：
   - 调用 `ctx.llm.registerConfigurableProviders([...])`。
   - 调用 `ctx.llm.registerAdapter([PROVIDER], adapter)` 拿到 `registration`。
   - `installSettingsSection(ctx, NS, Config, config, { setSource, onChange })`。
   - 在 `onChange` 中根据 retryPolicy 变化调用 `registration.replace([...])`。
5. **配置 schema**：用 `schemastery` 定义 `Config`，包含 `apiKeyEnv`（role: `'credential-ref'`）、`baseURL`、`retryPolicy: RetryPolicySchema`。
6. **加入 bundle**：在 `apps/cli/cordis.yml` 或对应 `cordis.yml` 加入 `- id: llm-<your-provider>`。
7. **测试**：用 `dsh-llm-mock-server`（见 `packages/test-support`）做集成测试。

### 7.2 pi-ai 库方式（参考 `dsh-llm-pi-ai`）

如果新 provider 已被 `@earendil-works/pi-ai` 收录（catalog provider）：

1. **不需要新 adapter**：直接在 `dsh-llm-pi-ai` 的 `Config.providers` 下加一条路由，命名 pi-ai 的 provider key 即可继承 endpoint / protocol / catalog。
2. **覆盖字段**：用 `models` 数组缩小 catalog、`apiKeyEnv` 指定凭据、`api` 覆盖协议、`baseURL` 重指 endpoint。
3. **新增协议**：若 pi-ai 未收录，在 `provider.ts:47` 的 `PROTOCOLS` 表加 entry（如 `bedrock` 需要 SigV4 auth，超出当前配置形状不能表达）。

### 7.3 Token 计量

`TokenMeter`（`packages/llm/token-meter/src/index.ts:73`）是 replay-aware service：

- 自动 fold 每个 `StreamChunk` 的 `TokenUsage`，无需新 provider 干预。
- `_estimateProviderAssistant`（`index.ts:276`）在 provider 未返回 usage 时用 `estimateMessage` 估算。
- 新 provider 只需在 `StreamChunk` 中正确产出 `usage` 字段。

## 8. 关键 SDK 依赖版本

| 依赖 | 版本 | 用途 |
|---|---|---|
| `@agentclientprotocol/sdk` | 0.25.1 | ACP（非 LLM 直接相关，但 llm-retry 测试用） |
| `@earendil-works/pi-ai` | ^0.82.1 | pi-ai 适配器后端（`llm-pi-ai/package.json`） |
| `@google/genai` | (transitive) | 由 pi-ai 拉入，`allowBuilds: false` 拒绝其 lifecycle 脚本 |
| `eventsource-parser` | ^3.1.0 | DeepSeek SSE 解析（`llm-deepseek/package.json`） |
| `zod` | ^4.4.3 | token-meter schema |

## 9. 关键发现

1. **唯一必填方法**：`LlmAdapter.stream` 是唯一抽象方法（`index.ts:232`），其他都有默认实现，最小化新 provider 实现成本。
2. **retryPolicy 在注册时捕获**：runtime 在 `registerAdapter` 时 freeze policy，运行时改变只能通过 `registration.replace()` 原子重注册。
3. **dsh-llm-pi-ai 是 dsh-llm-deepseek 的 design-verification twin**：两者共享同一 `LlmAdapter` 契约，pi-ai 路径覆盖 OpenAI / Anthropic / 自定义网关，是设计验证。
4. **凭据永不入配置**：所有 `apiKeyEnv` 都是环境变量名（`CredentialRef` brand），通过 `dsh-credentials` 接缝或 `launchEnvironmentOf(ctx)` 解析，secret 永不进入 settings 文档。
5. **流式响应空闲超时**：`DEFAULT_STREAM_IDLE_TIMEOUT_MS = 300_000`（5 分钟），`idleWatchdog` 监控单次读操作间隔，避免 hang。
6. **pi-ai catalog drift gate**：`MODALITY_GATE`（`catalog.ts:42`）和 `THINKING_LEVEL_GATE`（`catalog.ts:69`）用 `Record<...>` 编译期检查 pi-ai 升级引入的 modality / thinking level 漂移。
