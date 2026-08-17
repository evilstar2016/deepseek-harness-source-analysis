# 第三方集成总览

> 本文档基于 AST 符号工具对源码符号进行验证分析生成。代码引用处的行号均来自符号工具验证。

## 1. 集成概述

DeepSeek Harness（dsh）是「一切皆插件」的 Agent 框架。第三方集成的核心设计模式是 **能力接缝（Capability Seam）三角色**：

- **Service Definition（接口声明）**：抽象 service + 词汇 + 错误分类，零运行时依赖。
- **Service Provider（实现）**：注册具体 adapter / provider 到 `ctx.<capability>`。
- **Consumer（消费方）**：通过 `ctx.<capability>` 调用能力（通常是面向模型的工具）。

每个第三方服务集成严格遵循此模式，让 dsh 在不修改核心代码的前提下扩展新 LLM provider、新沙箱 backend、新协议、新 hook dialect。

dsh 的第三方集成可分为四大类：

| 类别 | 包数 | 文档 |
|---|---|---|
| LLM 与 AI 框架 | 5 个子包 | [01-llm-integration.md](./01-llm-integration.md) |
| 沙箱与执行环境 | 4 个子包 + 1 个原生 addon | [02-sandbox-execution.md](./02-sandbox-execution.md) |
| 协议集成 | 8 个子包 | [03-protocols.md](./03-protocols.md) |
| 框架与构建工具 | 3 个 vendored + 多个工具链 | [04-framework-vendor.md](./04-framework-vendor.md) |

## 2. 集成类别列表

### 2.1 LLM 与 AI 框架（详见 [01-llm-integration.md](./01-llm-integration.md)）

| 包 | 角色 | 第三方依赖 |
|---|---|---|
| `@deepseek-ai/dsh-llm` | Service Definition | (无第三方) |
| `@deepseek-ai/dsh-llm-deepseek` | Provider（直连 fetch + SSE） | `eventsource-parser@^3.1.0` |
| `@deepseek-ai/dsh-llm-pi-ai` | Provider（pi-ai 库多协议） | `@earendil-works/pi-ai@^0.82.1`（含 `@google/genai`） |
| `@deepseek-ai/dsh-llm-retry` | Consumer（agent loop 失败恢复） | (无第三方) |
| `@deepseek-ai/dsh-token-meter` | Consumer（replay-aware 计量） | `zod@^4.4.3` |

**核心抽象**：`LlmAdapter`（`packages/llm/llm/src/index.ts:180`）只有一个必需方法 `stream(options)`。

### 2.2 沙箱与执行环境（详见 [02-sandbox-execution.md](./02-sandbox-execution.md)）

| 包 | 角色 | 第三方依赖 |
|---|---|---|
| `@deepseek-ai/dsh-sandbox` | Service Definition | (无第三方) |
| `@deepseek-ai/dsh-sandbox-local` | Provider（本地多 runner 链） | `@deepseek-ai/node-addon-landlock-run@workspace:^` |
| `@deepseek-ai/dsh-sandbox-windows-acl` | Provider（Windows ACL FFI） | `koffi@^3.1.0` |
| `@deepseek-ai/dsh-sandbox-policy` | Consumer（per-call policy 解析） | (无第三方) |
| `@deepseek-ai/node-addon-landlock-run` | 原生 addon（C + 预编译二进制） | BSD-3-Clause，Linux only |
| `@deepseek-ai/dsh-e2b` + `dsh-fs-e2b` + `dsh-subprocess-e2b` | Provider（远程沙箱 POC） | `e2b@2.29.1` |
| (node-pty) | 持久 PTY 后端 | `node-pty@1.1.0` (patched) |

**核心抽象**：`SandboxProvider.confine(argv, policy)` 返回 `ConfinedArgv`，fail-closed 不允许 unconfined passthrough。

### 2.3 协议集成（详见 [03-protocols.md](./03-protocols.md)）

| 包 | 角色 | 第三方依赖 |
|---|---|---|
| `@deepseek-ai/dsh-acp` | Provider（ACP server） | `@agentclientprotocol/sdk@0.25.1` |
| `@deepseek-ai/dsh-sdk-protocol` | Service Definition（共享 wire） | (无第三方) |
| `@deepseek-ai/dsh-sdk-client` | Client（TS） | (无第三方) |
| `@deepseek-ai/dsh-sdk-jsonrpc-server` | Provider（SDK server） | (无第三方) |
| `@deepseek-ai/dsh-hook-protocol` | 共享 hook 库 | (无第三方) |
| `@deepseek-ai/dsh-hooks-claude-code` | Bridge（Claude Code hooks） | (无第三方) |
| `@deepseek-ai/dsh-hooks-codex` | Bridge（Codex hooks） | (无第三方) |
| (Python SDK) | Client（Python twin） | (在 `python/sdk`) |

### 2.4 框架与构建工具（详见 [04-framework-vendor.md](./04-framework-vendor.md)）

| 类别 | 包 | 角色 |
|---|---|---|
| Vendored 框架 | `@deepseek-ai/cordis@4.0.1` | Meta-Framework（插件骨架） |
| Vendored 框架 | `@deepseek-ai/cosmokit@1.8.2` | Common utilities |
| Vendored 框架 | `@deepseek-ai/schemastery@3.18.1` | Schema validator |
| 工具链 | pnpm 11.7.0 | Workspace monorepo |
| 工具链 | TypeScript 6.0.3 + tsx 4.22.4 | 类型 + ESM 执行 |
| 工具链 | tsdown 0.22.2 + esbuild | 库打包 |
| 工具链 | oxlint 1.76.0 + oxlint-tsgolint 7.0.2001 | Linter |
| 工具链 | vitest 4.1.8 | 测试框架 |
| 工具链 | knip 6.16.1 + publint 0.3.21 + jscpd 5.0.12 | 卫生检查 |
| 工具链 | lefthook 2.1.9 | git hooks |

## 3. 统一接口设计：能力接缝三角色

### 3.1 三角色定义

```
┌─────────────────────────────────────────────────────────────┐
│  Service Definition (interface)                             │
│  - abstract class / interface / branded types               │
│  - error taxonomy (HarnessError codes)                      │
│  - zero runtime dependencies                                 │
│  - declare module for Context / Events (Cordis)             │
└────────────────┬────────────────────────────────────────────┘
                 │ extends / implements
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Service Provider (implementation)                          │
│  - registers with ctx.<capability>.register<Provider>()     │
│  - owns third-party SDK / FFI / network calls               │
│  - per-request resolution (config + credential snapshots)   │
│  - fail-closed or fail-loud semantics                       │
└────────────────┬────────────────────────────────────────────┘
                 │ called by
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Consumer (caller)                                          │
│  - reads ctx.<capability>                                   │
│  - typically model-facing tools (tool_<name>)               │
│  - applies per-call policy / config resolution             │
│  - normalizes errors via shared taxonomy                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 各能力接缝对照

| 能力 | Service 类 | Provider 注册方法 | ctx 字段 | 典型 Consumer |
|---|---|---|---|---|
| LLM | `LlmAdapter` (`llm/src/index.ts:180`) | `ctx.llm.registerAdapter([providers], adapter)` (`:337`) | `ctx.llm` | `dsh-agent-loop`, `dsh-token-meter` |
| LLM configurable provider dir | (无独立类) | `ctx.llm.registerConfigurableProviders(entries)` (`:430`) | (同上) | settings page |
| LLM model discovery | (callback) | `ctx.llm.registerModelDiscovery(ns, fn)` (`:503`) | (同上) | settings page |
| Sandbox | `SandboxProvider` (`sandbox/src/index.ts:158`) | (extends + super(ctx, 'sandbox')) | `ctx.sandbox` | `dsh-shell`, `dsh-subprocess`, `dsh-code-runtime` |
| Sandbox policy | (callback) | (consumer 解析 per-call policy) | `ctx.sandboxPolicy` | (consumer 内部) |
| E2B | `E2BRuntime` (`e2b/src/index.ts:74`) | (extends + super(ctx, 'e2b')) | `ctx.e2b` | `dsh-fs-e2b`, `dsh-subprocess-e2b` |
| Token meter | `TokenMeter` (`token-meter/src/index.ts:74`) | (extends + super(ctx, ...)) | `ctx.tokenMeter` | `dsh-compaction`, UI |
| Web search | `WebSearchProvider` | `ctx.web.registerSearchProvider(...)` | `ctx.web` | `dsh-tool-web` |
| Web fetch | `WebFetchProvider` | `ctx.web.registerFetchProvider(...)` | `ctx.web` | `dsh-tool-web` |
| LSP | `LspProvider` | `ctx.lsp.registerProvider(...)` | `ctx.lsp` | `dsh-tool-lsp` |
| ACP server | (function plugin) | `apply(ctx, config)` | (无 ctx field) | 外部 ACP 客户端 |
| SDK server | `HarnessSdkJsonRpcServer` (`sdk/server/src/server.ts:52`) | (plugin apply) | (无 ctx field) | 外部 SDK 客户端 |
| Hook bridges | (function plugin) | `apply(ctx, config)` 注册到 interception 扩展点 | (无独立 ctx field) | agent loop, tool exec |

### 3.3 注册与销毁

所有 provider 注册都通过 `ctx.effect()` / registration handle 实现**可逆 effect**：

- 注册时返回 disposer（如 `AdapterRegistrationHandle`，`llm/src/index.ts:238`）。
- disposer 既可作函数调用（释放所有路由），也提供 `replace(providers)` 原子替换路由集。
- plugin 卸载时 cordis 自动调用 disposer，无需手动 cleanup。
- `ctx.on(event, listener)` 注册的事件监听同样可逆。

### 3.4 凭据引用模式

dsh 的核心安全设计：**配置永不承载 secret**。

- 配置字段 `apiKeyEnv: string` (role: `'credential-ref'`) 只存环境变量名。
- 运行时通过 `ctx.get('credentials')` 接缝或 `launchEnvironmentOf(ctx).get(ref)` 解析。
- secret 永不进入 settings 文档、永不入日志、永不入 session event。
- `assertUsableApiKey(raw, pkg, ref)`（`llm/src/index.ts:137`）共享校验逻辑，错误消息引导用户修改 `ref` 而非回显 secret。

## 4. 环境变量清单

| 环境变量 | 类别 | 作用 | 默认 / fallback |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | LLM | DeepSeek chat-completions API key | 必填 |
| `DEEPSEEK_BASE_URL` | LLM | DeepSeek chat-completions endpoint | `https://api.deepseek.com` |
| `DEEPSEEK_SEARCH_BASE_URL` | Web | DeepSeek web search endpoint（Anthropic-compatible） | (独立于 chat-completions) |
| `OPENAI_API_KEY` | LLM (pi-ai) | OpenAI 路由凭据（profile 指定） | — |
| `ANTHROPIC_API_KEY` | LLM (pi-ai) | Anthropic 路由凭据 | — |
| `<provider>_API_KEY` | LLM (pi-ai) | 自定义 provider 凭据 | — |
| `E2B_API_KEY` | Sandbox | E2B 远程沙箱 API key（POC） | 必填 |
| `DSH_BUILD_FACE` | Build | tsdown 构建目标 face | `host` / `client` |
| `DSH_SNAPSHOT` | Test | snapshot 测试模式 | `record` / `refresh` / `replay` |

注：沙箱 native addon（`landlock-run`）**故意不提供任何环境变量 override**，防止 ambient env 控制哪个 binary 限制进程。

## 5. 扩展指南

### 5.1 添加新 LLM Provider

参考 [01-llm-integration.md §7](./01-llm-integration.md#7-扩展指南添加新-llm-provider)。

### 5.2 添加新沙箱 Backend

参考 [02-sandbox-execution.md §7](./02-sandbox-execution.md#7-扩展指南添加新沙箱-backend)。

### 5.3 添加新协议或 Hook Dialect

参考 [03-protocols.md §7](./03-protocols.md#7-扩展指南)。

### 5.4 通用扩展流程

无论添加什么新能力，遵循以下步骤：

1. **新建 Service Definition 子包** `packages/<group>/<capability>/`：
   - 抽象 `Service` 子类或纯 interface。
   - 错误 taxonomy（继承 `HarnessError`）。
   - `declare module '@deepseek-ai/cordis'` 扩展 `Context` 接口。
   - 零运行时第三方依赖。
2. **新建 Provider 子包** `packages/<group>/<capability>-<provider>/`：
   - 继承抽象类，实现必需方法。
   - 在 `apply(ctx, config)` 中注册到 `ctx.<capability>`。
   - 用 `schemastery` 定义 `Config` schema。
   - 凭据字段用 `role: 'credential-ref'`，secret 字段用 `role: 'secret'`。
3. **新建 Consumer 子包**（如需模型可见工具）`packages/<group>/tool-<capability>/`：
   - 通过 `ctx.<capability>` 调用能力。
   - 应用 per-call policy（来自 `ctx.sandboxPolicy` 或类似）。
   - 错误用 `HarnessError` 包装为 `tool/result` structured error。
4. **加入 bundle**：在对应 `cordis.yml`（如 `apps/cli/cordis.yml` 或 `examples/<bundle>/cordis.yml`）加 plugin entry。
5. **测试**：
   - 用 `dsh-test-support` 的 testkit / invariant 检查。
   - 跨平台 gate（Linux + Windows + Wine）。
   - snapshot 测试（如适用）。
6. **文档**：
   - 子包 `README.md` + `README.zh.md`（i18n）。
   - 加入 `gen-catalog` 系列（如 `gen-tool-catalog`）。
   - 加入 `verify-package-invariants` 校验。
7. **卫生检查**：`npm run hygiene` 全套（knip + publint + constraints + licenses + invariants + cordis-config + node-types + runtime-closure + vendored-links）。

## 6. 关键设计原则

### 6.1 接缝优先

核心包零运行时第三方依赖，所有 SDK / FFI / 网络调用下沉到 Provider 子包。这让接缝稳定、Provider 可独立演进。

### 6.2 Per-request Resolution

LLM adapter 的连接事实和凭据每请求解析一次，in-flight 流不观察配置变化。沙箱 ACL grant per-session 隔离。配置错误保留 lastGood 而非 crash running session。

### 6.3 Fail-Closed / Fail-Loud

- 沙箱：无可用 backend 抛 `SANDBOX_UNAVAILABLE`，命令永不 unconfined 运行。
- 凭据：缺失抛 `MISSING_CREDENTIAL`，不静默 fallback。
- AclGrant：半 materialized 失败时撤销 + 清理后才抛。
- 重试：`retryableCodes` 配置不可为空。

### 6.4 Atomic Replace

- LLM `AdapterRegistrationHandle.replace(providers)`：原子替换路由集，无空窗。
- Windows ACL `AclWriteGrant`：standing workspace ACE 跨 session 复用，避免 dispose-then-register 留空窗。

### 6.5 No Secret in Config

所有 `apiKeyEnv` 是环境变量名，secret 永不入配置 / 日志 / session event。错误消息引导用户修改 `ref` 而非回显 secret。

### 6.6 Contracts-Ready Pattern

`build:lib:host && gate:contracts-ready` 模式贯穿 typecheck / lint / doc-typecheck，因为 dsh 的 type contracts 跨包生成（declaration merging、`SessionEventMap` 等）。

## 7. 关键发现

1. **Vendored Cordis**：scope 从 `@cordiverse/*` 改为 `@deepseek-ai/*`，`linkWorkspacePackages: true` + `overrides` 确保本地源码 override 远程。便于在框架层做 in-tree 修复。
2. **`allowBuilds` 严格模式**：pnpm 10+ 默认拒绝所有 install/build script，dsh 显式 allow 仅需要的（esbuild / lefthook / node-pty / koffi），减少供应链攻击面。
3. **`patchedDependencies`**：node-pty@1.1.0 通过 patch 文件修复，无需 fork 维护。
4. **landlock-run 二进制无 env override**：故意设计，防止 ambient env 控制哪个 binary 限制进程（安全考虑）。
5. **dsh-llm-pi-ai 是 design-verification twin**：与 dsh-llm-deepseek 共享 `LlmAdapter` 契约，覆盖 OpenAI / Anthropic / 自定义网关，是设计验证而非主流。
6. **dsh-sdk 与 ACP 平行**：ACP 是 automation-only 标准（外部 trusted 客户端），SDK 是 dsh 自有完整客户端协议（含 subagent 一等支持）。
7. **Hook bridge 是兼容层**：执行未修改的 Claude Code / Codex hook 命令，shared execution 在 `dsh-hook-protocol`，每个 dialect bridge 只 own payload / env / mapping。
8. **restrictive merge**：多 hook 输出合并采取最严格决策（block 优先），保证安全。
9. **SDK client 关闭 ladder**：EOF → SIGTERM → SIGKILL，加 grace 让 stdio 沉淀——子进程关闭稳健模式。
10. **大量 verify 脚本构成卫生检查网**：从 `verify-md-links` 到 `verify-runtime-closure`，确保 monorepo 健康度但需维护成本。
