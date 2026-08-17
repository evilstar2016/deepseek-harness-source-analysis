# 沙箱与执行环境集成

> 本文档基于 AST 符号工具对源码符号进行验证分析生成。代码引用处的行号均来自符号工具验证。

## 1. 集成概述

dsh 的沙箱能力负责在执行模型触发的 shell / subprocess 命令时施加文件系统约束。它同样遵循能力接缝三角色：

- **Service Definition**：`@deepseek-ai/dsh-sandbox` 声明 `SandboxProvider` 抽象类、`SandboxPolicy` / `ConfinedArgv` 词汇、`SandboxUnavailableError` fail-closed 错误。
- **Service Provider**：
  - `dsh-sandbox-local`：本地进程沙箱（Linux bwrap/Landlock、macOS Seatbelt、Windows ACL restricted-token runner）。
  - `dsh-sandbox-windows-acl`：Windows ACL 后端独立子包。
  - `@deepseek-ai/node-addon-landlock-run`：原生 addon（C 代码 + 静态预编译二进制）。
  - `dsh-e2b` + `dsh-fs-e2b` + `dsh-subprocess-e2b`：E2B 远程沙箱 POC。
- **Consumer**：`dsh-shell`（bash 执行）、`dsh-subprocess`（子进程树）、`dsh-code-runtime`（worker-thread）、`dsh-terminal`（PTY）通过 `ctx.sandbox.confine(argv, policy)` 包装 argv。

### 设计哲学

- **fail-closed**：无可用 backend 时拒绝运行 unconfined 命令，抛 `SANDBOX_UNAVAILABLE`。
- **per-call policy**：`SandboxPolicy` 携带 `mode` / `workspaceRoot` / `sessionId`，不同 consumer 可同时使用不同 policy。
- **denial dialect**：每个 backend 报告自己的 `denialSignatures`（EROFS / EACCES / EPERM），consumer 只匹配本 backend 的方言而非并集。
- **runner failure 区分**：`RunnerFailureRule` 结构化 stderr 匹配规则，先识别 runner 自身失败（命令未运行），再识别 denial（confinement 工作并阻止了）。

## 2. 支持的服务/产品

| 服务名 | 版本 / API | 平台 | 状态 | 说明 |
|---|---|---|---|---|
| Bubblewrap (`bwrap`) | 命令行 | Linux | GA | Linux 首选 runner，mount profile 接近 mode 词汇 |
| Landlock | Linux Kernel ABI | Linux | GA | `landlock-run` 原生 launcher，allow-list 语义 |
| Seatbelt (`sandbox-exec`) | macOS 内核 | macOS | GA | macOS 唯一候选，`sandbox-exec -p` profile |
| Windows ACL | Win32 API | Windows | GA（partial） | restricted-token + capability-SID ACE，需 koffi FFI |
| E2B | `e2b` SDK 2.29.1 | 远程 Linux | POC | 远程 Linux 沙箱，通过 `Sandbox.create()` |
| node-pty | 1.1.0 (patched) | 跨平台 | GA | 持久 PTY 后端（非沙箱，但执行环境相关） |
| koffi | ^3.1.0 | Windows | GA | Win32 FFI 加载器，用于 Windows ACL |
| runnerCommand override | 自定义 | 任意 | 可选 | operator 断言已配置 runner，跳过 probe |

## 3. 集成方式

### 3.1 Service Definition：`SandboxProvider` 与 `SandboxPolicy`

`SandboxProvider`（`packages/sandbox/sandbox/src/index.ts:158`）是抽象 Service：

```typescript
abstract class SandboxProvider extends Service {
  constructor(ctx: Context) { super(ctx, 'sandbox') }
  abstract confine(argv: readonly string[], policy: SandboxPolicy): ConfinedArgv
}
```

`SandboxMode`（`index.ts:29`）：`'read-only' | 'workspace-write' | 'danger-full-access'`。`danger-full-access` 不进入 `SandboxPolicy`（不是 confinement）。

`SandboxExecutionPolicy`（`index.ts:39`）：
- `mode: SandboxMode`
- `workspaceRoot: string`（绝对路径）
- `sessionId?: SessionId`（branded，用于 per-session 状态隔离）

`SandboxPolicy extends SandboxExecutionPolicy`（`index.ts:69`）：把 `mode` 收窄到 `ConfinedSandboxMode`。

`ConfinedArgv`（`index.ts:95`）是 `confine()` 的返回：
- `argv: string[]`：wrapped argv（runner + profile args + `--` + 原 argv）
- `enforcement: 'full' | 'partial'`：本次执行的强制完整性
- `denialSignatures: readonly string[]`：本 backend 的 denial stderr 子串
- `runnerFailureRules: readonly RunnerFailureRule[]`：runner 失败识别规则

`SandboxUnavailableError`（`index.ts:131`）携带 `SANDBOX_UNAVAILABLE` code，message 列出平台对应的可用 backend 安装建议。

### 3.2 Provider：`LocalSandboxProvider`（多 runner 链）

`LocalSandboxProvider`（`packages/sandbox/sandbox-local/src/index.ts:250`）是 `SandboxProvider` 的本地实现。它选择平台 runner 链（`index.ts:159`）：

```typescript
const PLATFORM_CHAINS: Record<string, readonly SelectedRunner['runner'][]> = {
  linux: ['bwrap', 'landlock'],
  darwin: ['seatbelt'],
  win32: ['windows-acl'],
}
```

每个平台的链按优先级排序，**sole candidate 直接选用不 probe**（其运行时拒绝仍 fail-closed），多 candidate 才 probe 仲裁。

`STATIC_ENFORCEMENT`（`index.ts:177`）：bwrap / landlock / seatbelt = `'full'`，windows-acl = `'partial'`（因 `WRITE_RESTRICTED` 需保留 `Everyone` + NTFS hard link 可跨路径别名）。

`DENIAL_SIGNATURES`（`index.ts:205`）：
- bwrap: `['read-only file system']`
- landlock: `['permission denied']`
- seatbelt: `['operation not permitted']`
- windows-acl: `['access is denied', 'access to the path', 'permission denied']`

`RUNNER_FAILURE_RULES`（`index.ts:231`）：每个 runner 的 fatal stderr 前缀 + exit code 限制：
- bwrap: `{ fatalSignatures: ['bwrap: '] }`
- landlock: `{ allowedExitCodes: [125], fatalSignatures: ['landlock-run: '], informationalLines: ['landlock-run: partial enforcement (older Landlock ABI)'] }`
- seatbelt: `{ fatalSignatures: ['sandbox-exec: '] }`
- windows-acl: `{ allowedExitCodes: [127], fatalSignatures: ['windows-acl-run: '] }`

`confine(argv, policy)`（`index.ts:316`）：
- 若有 `runnerCommand` override：直接 `[...runnerCommand, ...bwrapProfileArgs(policy), '--', ...argv]` + `enforcement: 'full'`。
- 否则 `selectRunner(policy.mode)` 选 rung，调用对应 `runnerArgv()` 拼装。

### 3.3 Provider：`dsh-sandbox-windows-acl`（koffi FFI）

独立子包 `@deepseek-ai/dsh-sandbox-windows-acl`（依赖 `koffi: ^3.1.0`）：

- **`ffi.ts`**（`packages/sandbox/sandbox-windows-acl/src/ffi.ts`）：lazy koffi bindings，非 Windows 进程永不加载 Win32 库。每个函数签名对照 MinGW headers 验证，struct layouts 在 `verify/abi-probe.cpp` 加载时断言。
- **`runner.ts`**（`runner.ts:44`）：argv-prefix wrapper，创建 `WRITE_RESTRICTED` token + workspace write-SID allowlist，spawn 子进程并 mirror exit code，temp grant 在 exit 时撤销。稳定 argv 契约：`[node, runner.js, '--workspace', <dir>, '--temp', <dir>, '--mode', <mode>, ['--write-sid', <sid>, '--temp-write-sid', <sid>], '--', <argv...>]`。
- **`AclWriteGrant`**：standing workspace-root grant per workspace（cross-session 复用缓存）+ revocable private-temp grant per live session/workspace pair。
- **`workspaceWriteSid(workspaceRoot)` / `tempWriteSid(tempDir)`**：基于路径派生稳定 capability-SID。

`LocalSandboxProvider.materializeAclGrant(sessionId, workspaceRoot)`（`sandbox-local/src/index.ts:392`）：fail-closed，半 materialized 的 temp grant 被撤销 + 目录删除后才抛错。

### 3.4 Native Addon：`@deepseek-ai/node-addon-landlock-run`

`native/landlock-run/packages/entry/src/index.ts` 提供 JS API over 预编译 `landlock-run` 二进制：

- `LAUNCHER_BIN = 'landlock-run'`（`index.ts:22`）
- `LAUNCHER_FAILURE_EXIT = 125`（`index.ts:31`）：每个 launcher 级失败的 exit code（usage error、unenforcing kernel、unopenable grant root、failed exec）。
- `LandlockEnforcement = 'full' | 'partial' | 'unusable'`（`index.ts:41`）：probe 的裁决结果。
- `LauncherGrants`（`index.ts:47`）：`readOnly` / `readWrite` 路径列表（Landlock 是 allow-list）。
- `launcherPath()`（`index.ts:69`）：从 `@deepseek-ai/node-addon-landlock-run-${process.platform}-${process.arch}` 解析二进制路径；npm 的 `os` / `cpu` 字段让安装只 fetch 匹配平台的 optional dependency。
- `probe()`：spawnSync 启动 launcher，依据 exit code 与 stderr 判断 enforcement level。

**关键设计**：本模块**故意不提供任何环境变量 override**（`index.ts:14` 注释）——「which binary confines a process must never be decidable by the ambient environment」。测试注入通过函数参数。

二进制构建：

- `native/landlock-run/packages/entry/src/main.c` 是 C 源码。
- 平台预编译包：`packages/linux-arm64` / `packages/linux-x64`。
- BSD-3-Clause license（与 MIT 主体不同）。

### 3.5 Provider：E2B 远程沙箱（POC）

`dsh-e2b`（`packages/e2b/e2b/src/index.ts`）使用 `e2b: 2.29.1` SDK：

`E2BRuntime`（`index.ts:74`）extends `Service`：

- `static Config`（`index.ts:75`）：`apiKey`（默认读 `E2B_API_KEY`）、`cwd`（默认 `/home/user/workspace`）、`timeoutMs`（默认 300_000）。
- `validate()`（`index.ts:139`）：apiKey 必填、cwd 必须是绝对 Linux 路径、timeoutMs 正有限。
- `open()`（`index.ts:151`）：`Sandbox.create({ apiKey, timeoutMs, secure: true, lifecycle: { onTimeout: 'kill' } })`，然后 `files.makeDir` 创建 cwd 和 `.dsh-e2b` runtimeRoot，`chmod 700`。
- `getSandbox()`（`index.ts:130`）：返回共享 live SDK handle；adapters await 此 promise 后才执行首次操作。
- `ctx.effect(() => async () => { sandbox.kill() })`：dispose 时 kill 沙箱。
- `quoteE2BShellArg(value)`（`index.ts:27`）：为 SDK 的 `/bin/bash -l -c` 强制层正确引用参数。
- `e2bControlEnvs(overrides)`（`index.ts:36`）：随机化 `HOME` 路径隔离 E2B 的硬编码 login shell。

E2B 是 POC：`fs-e2b` 提供 filesystem 实现，`subprocess-e2b` 提供 subprocess 实现，三者共享同一 `E2BRuntime` handle 进入同一远程 Linux world。

### 3.6 node-pty（patched 1.1.0）

`pnpm-workspace.yaml` 配置（第 71-72 行）：

```yaml
patchedDependencies:
  node-pty@1.1.0: patches/node-pty@1.1.0.patch
```

`allowBuilds: node-pty: true` 允许其 install/build 脚本运行（含 ConPTY Windows）。patch 文件 `patches/node-pty@1.1.0.patch` 自定义修改。

`dsh-subprocess-local` 的 postinstall（`pnpm-workspace.yaml:55`）也允许：`@deepseek-ai/dsh-subprocess-local@file:packages/subprocess/subprocess-local: true`，用于 Python runtime deploy 时恢复 macOS spawn helper 的 executable bit。

## 4. 代码实现

### 4.1 关键类与文件

| 类 / 模块 | 路径 | 行号 | 角色 |
|---|---|---|---|
| `SandboxProvider` | `packages/sandbox/sandbox/src/index.ts` | 158-176 | 抽象 service |
| `SandboxUnavailableError` | `packages/sandbox/sandbox/src/index.ts` | 131 | fail-closed 错误 |
| `LocalSandboxProvider` | `packages/sandbox/sandbox-local/src/index.ts` | 250-565 | 多 runner 链本地 provider |
| `PLATFORM_CHAINS` | `packages/sandbox/sandbox-local/src/index.ts` | 159 | 平台到 runner 链映射 |
| `DENIAL_SIGNATURES` | `packages/sandbox/sandbox-local/src/index.ts` | 205 | 各 backend denial 方言 |
| `RUNNER_FAILURE_RULES` | `packages/sandbox/sandbox-local/src/index.ts` | 231 | runner 失败识别规则 |
| `confine()` | `packages/sandbox/sandbox-local/src/index.ts` | 316 | argv 包装入口 |
| `materializeAclGrant()` | `packages/sandbox/sandbox-local/src/index.ts` | 392 | Windows ACL grant 物化 |
| `selectRunner()` | `packages/sandbox/sandbox-local/src/index.ts` | 492 | 链选择 + probe 仲裁 |
| `windowsAclRunnerArgv()` | `packages/sandbox/sandbox-local/src/index.ts` | 358 | Windows ACL runner argv |
| `ffi.ts` | `packages/sandbox/sandbox-windows-acl/src/ffi.ts` | 1 | koffi lazy bindings |
| `runner.ts` | `packages/sandbox/sandbox-windows-acl/src/runner.ts` | 44 | Windows ACL runner |
| `E2BRuntime` | `packages/e2b/e2b/src/index.ts` | 73-179 | E2B 共享沙箱生命周期 |
| `LAUNCHER_BIN` | `native/landlock-run/packages/entry/src/index.ts` | 22 | landlock-run 二进制名 |
| `launcherPath()` | `native/landlock-run/packages/entry/src/index.ts` | 69 | 平台二进制路径解析 |
| `probe()` | `native/landlock-run/packages/entry/src/index.ts` | — | landlock 功能探针 |

### 4.2 平台选择与 probe 流程

```
confine(argv, policy)  [sandbox-local/src/index.ts:316]
  ↓
selectRunner(mode)  [index.ts:492]
  ↓
chainVerdict()  [index.ts:499]
  - 读 PLATFORM_CHAINS[platform]
  - sole candidate → 直接返回 + STATIC_ENFORCEMENT
  - 多 candidate → 顺序 probeRunner() 直到首个非 'unusable'
  - 全部 unusable → 'unavailable' → throw SandboxUnavailableError
  ↓
runnerArgv(selected.runner, policy)  [index.ts:336]
  - bwrap: ['bwrap', ...bwrapProfileArgs(policy)]
  - landlock: [landlockLauncher(), ...landlockProfileArgs(policy)]
  - seatbelt: [seatbeltExec(), ...seatbeltProfileArgs(policy)]
  - windows-acl: windowsAclRunnerArgv(policy)  [index.ts:358]
  ↓
return { argv, enforcement, denialSignatures, runnerFailureRules }
```

## 5. 配置与环境变量

### 5.1 环境变量

| 环境变量 | 作用 | 默认 |
|---|---|---|
| `E2B_API_KEY` | E2B 远程沙箱 API key | 必填（仅 POC 使用） |

**沙箱 deliberately 不提供环境变量 override**（`landlock-run/packages/entry/src/index.ts:14`）：runner 选择由 `process.platform` + probe 决定，不允许 ambient env 干预。

### 5.2 Plugin Config（`dsh-sandbox-local`）

`Config` interface（`packages/sandbox/sandbox-local/src/index.ts:43`）：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `runnerCommand` | string[] | `[]` | 自定义 runner argv（非空则跳过 probe，断言 full enforcement） |
| `runnerFailureSignatures` | string[] | `[]` | runner 拒绝 profile 时的 stderr 子串（与 `runnerCommand` 互为必填） |
| `probeTimeoutMs` | number | 5_000 | 每次 functional probe 超时 |

约束：
- `runnerCommand` 非空时 `runnerFailureSignatures` 必填，反之亦然（`index.ts:283-291`）。
- `runnerFailureSignatures` 每条必须非空、单行（无 `\r\n`）。
- `probeTimeoutMs` 必须正有限（`assertPositiveFinite`，`index.ts:194`）。

### 5.3 Plugin Config（`dsh-e2b`）

`Config` interface（`packages/e2b/e2b/src/index.ts:43`）：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `apiKey` | string | `process.env.E2B_API_KEY` | E2B API key（永不转发入沙箱） |
| `cwd` | string | `/home/user/workspace` | 远程共享工作目录 |
| `timeoutMs` | number | 300_000 | 沙箱生命周期，到期自动 kill |

## 6. 错误处理

### 6.1 错误码表

| Code | 含义 | 触发 |
|---|---|---|
| `SANDBOX_UNAVAILABLE` | 无可用 backend | `SandboxUnavailableError`（`sandbox/src/index.ts:131`） |
| `SANDBOX_DENIED`（隐式） | confinement 拒绝写操作 | 通过 stderr `denialSignatures` 匹配 |
| Runner exit 125 | landlock-run launcher 失败 | `LAUNCHER_FAILURE_EXIT` |
| Runner exit 127 | windows-acl runner 失败 | `WINDOWS_ACL_RUNNER_FAILURE_EXIT`（`sandbox-local/src/index.ts:216`） |

### 6.2 Runner Failure vs Denial 区分

consumer 在收到非零 exit code 时按顺序处理：

1. 应用 `runnerFailureRules[].allowedExitCodes` 过滤（如 landlock 只在 exit 125 时考虑 runner failure）。
2. 移除 `informationalLines`（如 landlock 的 `partial enforcement (older Landlock ABI)` 提示，非 fatal）。
3. 在剩余 stderr 行中 case-insensitive 匹配 `fatalSignatures`（如 `landlock-run: `）。
4. 命中 → runner failure（命令从未运行）；未命中 → 检查 `denialSignatures` → 命中 → confinement denial（命令运行了但被阻止写）。

### 6.3 Probe 失败 = fail-closed

每个 backend 的 probe（`probeRunner`，`sandbox-local/src/index.ts:513`）返回 `'full' | 'partial' | 'unusable'`：

- bwrap：`spawnSync('bwrap', [...profileArgs, '--', 'true'])` exit 0 = full。
- landlock：调用 `@deepseek-ai/node-addon-landlock-run` 的 `probe()`，返回 full / partial / unusable。
- seatbelt：`spawnSync('sandbox-exec', [...profileArgs, '--', 'true'])` exit 0 = full。
- windows-acl：`spawnSync(runnerInvocation, [..., '--mode', 'read-only', '--', 'cmd', '/c', 'exit', '0'])` exit 0 = partial（Windows 默认 partial）。

链上所有 rung `unusable` → `chainVerdict()` 返回 `'unavailable'` → `confine()` throw `SandboxUnavailableError`，**命令永不 unconfined 运行**。

### 6.4 ACL Grant 清理

`revokeAclGrants()`（`sandbox-local/src/index.ts:454`）在 provider dispose 时：

- 撤销每个 `tempCapabilities` 的 temp ACE + 删除 temp 目录。
- `workspaceGrants`（standing workspace ACE）**保留**（cross-session 复用缓存，跨 provider 生命周期）。
- 清理失败被收集后 `logger.warn`，**不抛**（cordis teardown 不能被 grant cleanup 中断）。
- 崩溃时跳过 cleanup，但新 provider 永不复用旧路径或 SID（随机性保证）。

## 7. 扩展指南：添加新沙箱 Backend

### 7.1 新增本地 runner

1. **在 `dsh-sandbox-local/src/profiles.ts` 添加 `<new-runner>ProfileArgs(policy)`**：构造新 runner 的 profile argv。
2. **扩展 `SelectedRunner['runner']` 类型**：加入新成员。
3. **更新 `PLATFORM_CHAINS`**：在对应平台链加入新 runner（保持优先级）。
4. **更新 `STATIC_ENFORCEMENT`**：若 sole candidate 则填入 enforcement level。
5. **更新 `DENIAL_SIGNATURES`** + `RUNNER_FAILURE_RULES`：定义本 backend 的 stderr 方言。
6. **在 `runnerArgv()` switch 加入 case**：返回 `[<runner>, ...profileArgs]`。
7. **更新 `probeRunner()`**：调用 functional probe（spawnSync 一个 `-- true` 类似的最小命令）。
8. **测试**：用 `SandboxInternals` 注入 fake chain / fake probe 跨平台验证。

### 7.2 新增独立 Provider 包（参考 E2B）

1. **新建 `packages/<cap>/sandbox-<name>/`**，`peerDependencies` 含 `@deepseek-ai/dsh-sandbox`。
2. **继承 `SandboxProvider`**：实现 `confine(argv, policy)`。
3. **(可选) 实现 `fs-<name>` / `subprocess-<name>`**：如果新沙箱需要替代 host filesystem 或子进程。
4. **加入 bundle**：在 `cordis.yml` 加 `- id: sandbox-<name>`。

### 7.3 SandboxPolicy 设计原则

新 consumer 在调用 `ctx.sandbox.confine(argv, policy)` 前：

1. **per-call 解析 policy**：从 `ctx.sandboxPolicy`（`dsh-sandbox-policy` 包）解析 mode + workspaceRoot + sessionId。
2. **不假设 enforcement 完整性**：检查 `ConfinedArgv.enforcement`，`'partial'` 时告知用户边界。
3. **匹配 denial dialect**：使用 `ConfinedArgv.denialSignatures` 而非硬编码。
4. **应用 `runnerFailureRules`**：在分类 stderr 时严格按规则。

## 8. 关键 SDK 依赖版本

| 依赖 | 版本 | 用途 |
|---|---|---|
| `koffi` | ^3.1.0 | Win32 FFI（`sandbox-windows-acl/package.json`） |
| `e2b` | 2.29.1 | E2B SDK（`e2b/package.json`） |
| `node-pty` | 1.1.0 (patched) | PTY 后端（patches/node-pty@1.1.0.patch） |
| `@deepseek-ai/node-addon-landlock-run` | 0.1.1 (workspace) | landlock launcher JS API + 二进制 |
| `@deepseek-ai/node-addon-landlock-run-linux-x64` | 0.1.4 (workspace) | x64 预编译二进制 |
| `@deepseek-ai/node-addon-landlock-run-linux-arm64` | 0.1.4 (workspace) | arm64 预编译二进制 |

`pnpm-workspace.yaml` 关键 allowBuilds 配置：

```yaml
allowBuilds:
  esbuild: true         # 原生 binary
  lefthook: true        # git hooks
  node-pty: true        # 跨平台 PTY 后端（含 ConPTY）
  '@google/genai': false   # pi-ai 拉入但脚本 no-op，拒绝
  protobufjs: false       # 同上
  koffi: true             # Win32 FFI 用于 MoveFileExW
  '@deepseek-ai/dsh-subprocess-local@file:packages/subprocess/subprocess-local': true
```

`patchedDependencies`：`node-pty@1.1.0: patches/node-pty@1.1.0.patch`。

## 9. 关键发现

1. **fail-closed 是硬约束**：`SandboxProvider.confine` 必须返回 enforcing argv 或在 wrap/runner-execution 时失败，**禁止 silent unconfined passthrough**（`sandbox/src/index.ts:154` 注释）。
2. **per-platform 链 + 优先级 probe**：Linux 上 bwrap 优先于 landlock（mount profile 更接近 mode 词汇），多 candidate 才 probe。
3. **Windows ACL 的 partial 强制**：`WRITE_RESTRICTED` token 需保留 `Everyone`（进程初始化需要）+ NTFS hard link 可跨路径别名，所以永远报告 `partial`。
4. **standing vs revocable grant 分离**：workspace-root ACE 跨 session 复用（O(1) exact-ACE skip），private-temp ACE per-session 随机化并 dispose 时撤销。
5. **landlock-run 二进制不存在环境变量 override**：故意设计，防止 ambient env 控制哪个 binary 限制进程（安全考虑）。
6. **E2B 是 POC**：当前只提供 `E2BRuntime` 共享 handle + `fs-e2b` + `subprocess-e2b`，未集成进 `cordis.yml` 默认 bundle。
7. **node-pty 1.1.0 是 patched 版本**：项目通过 `patchedDependencies` 自定义修复（patch 文件可读但具体修改未在本次分析范围）。
8. **runner argv 契约稳定**：`windows-acl` 的 argv 契约文档化（`runner.ts:9-14`），未来 native-exe 替换保持同契约只需替换 `[node, runner.js]` 前缀。
