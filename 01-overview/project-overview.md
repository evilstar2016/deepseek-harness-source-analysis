# DeepSeek Harness (dsh) - 项目概览

> 本文档基于 AST 符号工具对源码符号进行验证分析生成。代码引用处的行号均来自符号工具验证。

## 1. 项目基本信息

| 项 | 值 |
|---|---|
| **项目名称** | DeepSeek Harness（`dsh`，npm scope `@deepseek-ai/dsh-*`） |
| **根包名** | `@deepseek-ai/dsh-root` |
| **版本** | `0.1.0-rc.5`（Developer Preview，迭代中，存在破坏性变更） |
| **项目描述** | 由 DeepSeek AI 开发的开源 Agent Harness（智能体框架）。采用「一切皆插件」架构，基于 [Cordis](https://github.com/cordiverse/cordis) 框架构建。 |
| **开发语言** | TypeScript（全 ESM），附带 Python SDK 与原生 Node Addon |
| **运行时** | Node.js `^22.19.0 || >=24.0.0`（CLI 源码启动走 tsx 的 ESM-only hook） |
| **包管理器** | pnpm `11.7.0`（workspace monorepo） |
| **许可证** | MIT |
| **仓库地址** | https://github.com/deepseek-ai/deepseek-harness |

### 核心架构理念

- **一切皆插件**：没有特权核心。扩展 dsh 的方式是在其他插件旁挂载一个插件；注册是可逆的 effect（`ctx.effect()` / `ctx.on()`），插件卸载时自动回滚。
- **能力接缝（Capability Seams）**：每个可替换能力由三角色构成——Service Definition（接口声明）、Service Provider（实现）、Consumer（消费方，通常是面向模型的工具）。三者缺一不可。
- **模型可见即已记录**：任何到达模型请求的内容都必须能从会话日志重建。新增模型可见输入需扩展 `SessionEventMap` 并从日志渲染。
- **Profile / Bundle 组合**：运行中的 `dsh` 是启动时按有序层组合的插件树。`dsh-base` 是每个 profile 的第一层。

## 2. 项目目录结构

```
deepseek-harness/
├── packages/          # @deepseek-ai/dsh-<pkg> 工作区（49 个 group，详见第 3 节）
│   ├── core/            # 产品 API 主干：session、system-prompt、tools、agent、agent-loop
│   ├── api/             # 远程 BFF 装配 + Typert RPC 网关
│   ├── typert/          # 类型图生成、加载、运行时注册
│   ├── llm/             # LLM 能力：Service Definition + DeepSeek/pi-ai 适配器
│   ├── e2b/             # E2B 沙箱 POC
│   ├── shell/           # Bash 能力：执行接缝 + local/pwsh provider + 工具
│   ├── subprocess/      # 子进程能力 + 本地进程树 provider
│   ├── terminal/        # 持久 PTY 会话
│   ├── code-runtime/    # 代码执行能力：worker-thread provider + Code Mode
│   ├── sandbox/         # 进程限制接缝：bwrap/Landlock/Seatbelt
│   ├── fs/              # 文件系统能力 + 策略
│   ├── lsp/             # LSP 能力
│   ├── skill/           # Skill provider 注册表 + 本地实现 + catalog/loader 工具
│   ├── web/             # Web 能力：search/fetch provider + 工具
│   ├── compaction/      # 压缩能力 + basic provider
│   ├── context/         # 请求上下文插件（workspace 指令、时间上下文）
│   ├── subagent/        # 子 agent 能力：provider 注册表 + 委派工具
│   ├── jobs/            # 通用后台任务 + job_* 工具
│   ├── workflow/        # workflow 接缝 + worker-thread 引擎 + ralph 工具
│   ├── todo/            # todo_write 工具
│   ├── plan/            # 计划协作状态（直接进入 + 审核退出）
│   ├── preset/          # 预设 cordis.yml 的 per-session agent 组合
│   ├── guard/           # 循环卫生守卫 + 工具超时强制器
│   ├── extensions/      # Agent 运行时自修改（实时插件挂载/卸载）
│   ├── hooks/           # Claude Code/Codex hook 桥 + wire-protocol 库
│   ├── session/         # 持久会话数据：JSONL/SQLite 后端、投影、标题
│   ├── session-query/   # 会话检索：FTS、lineage、语义过滤
│   ├── settings/        # 用户设置接缝 + 文件 provider
│   ├── credentials/     # 凭据引用接缝 + env/.env provider
│   ├── storage/         # 非会话存储 hub + 后端
│   ├── workspace/       # Workspace 实体
│   ├── attachment/      # 持久附件身份 + 内容寻址存储
│   ├── spill/           # Spill 能力：存储接缝 + 工具结果溢出策略
│   ├── goal/            # 同会话目标持久化与生命周期
│   ├── schedule/        # 会话本地定时跟进
│   ├── feedback/        # 人类反馈
│   ├── identity/        # 匿名身份
│   ├── sdk/             # 进程外运行时 SDK：JSON-RPC 协议 + TS client + server
│   ├── acp/             # 仅自动化的 Agent Client Protocol server
│   ├── interaction/     # 人机协作面：审批/交互接缝、权限、命令、ask-user
│   ├── boot/            # 共享 app-bin 启动胶水
│   ├── host/            # Web-GUI host 半：API 网关 + HTTP 路由
│   ├── client/          # Web-GUI 浏览器半：shell、wire、ui-* 插件
│   ├── bundle/          # 可安装的 dsh --profile 补丁层（base/headless/web-app）
│   ├── examples/        # 示例 bundle（agent-spine + CLI/ACP/JSON-RPC bin）
│   ├── test-support/    # 测试基础设施（testkit、invariant、replay）
│   └── util/            # 零依赖底层工具（Branded、路径、超时）
├── apps/              # 产品装配
│   ├── cli/             # dsh CLI 入口（拥有 dsh bin：apps/cli/src/bin.ts）
│   └── web/             # Web UI 前端（Vite，默认 http://127.0.0.1:3080）
├── vendor/            # vendored Cordis 源码（cosmokit、schemastery 重 scope 为 @deepseek-ai/*）
├── native/            # @deepseek-ai/node-addon-landlock-run 原生 addon 源码
├── python/            # Python SDK + 捆绑运行时（python/sdk-runtime 为部署 workspace）
├── examples/          # 可运行 cordis.yml 叶子（demo bundle）
├── docs/              # 双语架构文档、生成目录、cookbook、postmortem
│   ├── subsystems/     # 子系统深度文档
│   ├── cookbook/        # 扩展 cookbook
│   ├── cordis-tutorial/
│   └── postmortem/
├── scripts/           # 仓库门禁与生成器（TS，经 tsx 运行）
├── website/           # VitePress 文档站点投影
├── .agents/           # Agent 工作流 + Agent Notes（notes/）
├── patches/           # 依赖补丁（node-pty@1.1.0.patch）
└── 配置文件：package.json / pnpm-workspace.yaml / tsconfig*.json / tsdown.config.ts / vitest*.config.ts / oxlintrc*.json / knip.json / lefthook.yml / .jscpd.json
```

## 3. 主要功能模块

### 3.1 核心 API 主干（`packages/core/`，8 个包）

产品 API 脊柱，提供稳定 API。每个包贡献一个 `ctx` key。

| 包 | 职责 | ctx key |
|---|---|---|
| `core/session` | 追加只写的 `SessionEvent` 日志 + 内存存储（符号验证：`Session` 类 L424-757、`SessionStore` 类 L791-1154、`SessionEventMap` 接口 L235-332） | `ctx.sessions` |
| `core/system-prompt` | Prompt section 与 tool schema 装配 | `ctx.systemPrompt` |
| `core/tools` | 作用域工具注册表 + 受保护的执行管线 | `ctx.tools` |
| `core/agent` | `Agent` 接口、实时注册表、`agent/*` 事件 | `ctx.agents` |
| `core/agent-loop` | 实现该接口的默认驱动 | `ctx.agentLoop` |
| `core/agent-default-model` | 默认模型绑定 | — |
| `core/agent-tool-presentation` | 工具呈现 | — |
| `core/scope` | 每 agent 的作用域注册原语（库，无 ctx key） | — |

### 3.2 LLM 能力族（`packages/llm/`，5 个包）

| 包 | 职责 |
|---|---|
| `llm/llm` | 消息与流词汇表 + 适配器接缝（`ctx.llm`） |
| `llm/llm-deepseek` | DeepSeek 官方适配器 |
| `llm/llm-pi-ai` | `@earendil-works/pi-ai` 可选后端（含 Google GenAI） |
| `llm/llm-retry` | 重试策略 |
| `llm/token-meter` | Token 计量 |

### 3.3 能力接缝族（执行环境类）

| 包族 | 能力 | 核心 ctx key |
|---|---|---|
| `shell/` | Bash 执行（local + pwsh） | `ctx.shell` |
| `subprocess/` | 子进程（本地进程树） | `ctx.subprocess` |
| `terminal/` | 持久 PTY 会话 | `ctx.terminals` |
| `code-runtime/` | 代码执行（worker-thread + Code Mode） | — |
| `sandbox/` | 进程限制（bwrap / Landlock / Seatbelt） | `ctx.sandbox` |
| `fs/` | 文件系统 + 策略 | `ctx.fs` |
| `lsp/` | 语言服务器协议 | — |
| `e2b/` | E2B 远程沙箱（POC） | — |

### 3.4 能力接缝族（模型协作类）

| 包族 | 能力 | 核心 ctx key |
|---|---|---|
| `skill/` | Skill provider 注册表 + 本地实现 + catalog/loader 工具 | — |
| `web/` | Web search/fetch | — |
| `compaction/` | 上下文压缩 | — |
| `context/` | 请求上下文（workspace 指令、时间） | — |
| `subagent/` | 子 agent 委派 | — |
| `jobs/` | 后台任务 + `job_*` 工具 | `ctx.jobs` |
| `workflow/` | workflow 接缝 + ralph 工具 | — |
| `todo/` | `todo_write` 工具 | — |
| `plan/` | 计划协作状态 | — |
| `preset/` | 预设 cordis.yml 组合 | — |
| `guard/` | 循环卫生守卫 + 工具超时 | — |
| `extensions/` | 运行时自修改（实时插件挂载/卸载） | — |

### 3.5 持久化与检索

| 包族 | 能力 |
|---|---|
| `session/` | 持久会话数据面：JSONL/SQLite 后端、投影、标题、报告 |
| `session-query/` | 会话检索：FTS、lineage、事件关系、语义过滤 |
| `storage/` | 非会话存储 hub + 后端 |
| `attachment/` | 持久附件身份 + 内容寻址存储 |
| `spill/` | Spill 存储 + 工具结果溢出策略 |
| `settings/` | 用户设置接缝 + 文件 provider |
| `credentials/` | 凭据引用接缝 + env-over-`.env` provider |
| `workspace/` | Workspace 实体 |
| `goal/` | 同会话目标持久化 |
| `schedule/` | 会话本地定时跟进 |
| `feedback/` | 人类反馈 |
| `identity/` | 匿名身份 |

### 3.6 协议与集成

| 包族 | 能力 |
|---|---|
| `api/` | 远程 BFF 装配 + Typert RPC 网关（gateway + remotes） |
| `typert/` | 类型图生成（generator）+ 加载（loader）+ 协议（protocol）+ 注册表（registry） |
| `sdk/` | 进程外运行时 SDK：JSON-RPC 协议 + TS client + server 插件 |
| `acp/` | 仅自动化的 Agent Client Protocol server |
| `hooks/` | Claude Code/Codex hook 桥 + wire-protocol 库 |
| `interaction/` | 人机协作面：审批/交互接缝、权限、命令、ask-user 工具 |

### 3.7 应用装配与 Boot

| 包族 | 能力 |
|---|---|
| `bundle/` | 可安装 profile 补丁层：`base`（模型/工具/持久化/沙箱/审批/设置/凭据/遥测）、`headless`（无服务器一次性运行）、`web-app`（浏览器应用） |
| `boot/` | 共享 app-bin 启动胶水 |
| `host/` | Web-GUI host 半：API 网关 + HTTP 路由 |
| `client/` | Web-GUI 浏览器半：shell、wire、object services、ui-* 插件 |

### 3.8 应用入口（`apps/`）

| 应用 | 路径 | 说明 |
|---|---|---|
| `apps/cli` | `apps/cli/src/bin.ts` | `dsh` CLI 入口，经 `node --import tsx/esm` 启动；含 config、reference、tests |
| `apps/web` | `apps/web/` | Web UI 前端，Vite 构建，`index.html` 入口，默认服务在 `http://127.0.0.1:3080` |

## 4. 核心依赖分析

### 4.1 框架与核心

| 依赖 | 版本 | 用途 |
|---|---|---|
| `@deepseek-ai/cordis` | vendored（workspace peer） | 插件/上下文框架，每个 harness 包的 peerDependency |
| `@deepseek-ai/cosmokit` | `link:vendor/cosmokit`（override） | Cordis 工具库（vendored 重 scope） |
| `@deepseek-ai/schemastery` | `link:vendor/schemastery`（override） | 配置 schema（vendored 重 scope） |
| `@agentclientprotocol/sdk` | `0.25.1` | ACP 协议 SDK |
| `@earendil-works/pi-ai` | （可选） | 可选 LLM API 后端（拉入 `@google/genai`） |

### 4.2 构建与工具链

| 依赖 | 版本 | 用途 |
|---|---|---|
| `typescript` | `^6.0.3`（peer `>=5 <7`） | 类型系统 |
| `tsdown` | `^0.22.2` | 运行时打包（host/client 双 face） |
| `tsx` | `^4.22.4` | ESM-only TS 执行 hook（CLI 源码启动 + scripts） |
| `vitest` | `^4.1.8` | 测试框架 |
| `@vitest/coverage-v8` | `^4.1.8` | 覆盖率（per-file 100% 门禁） |
| `oxlint` | `1.76.0` | Lint（非 eslint） |
| `oxlint-tsgolint` | `7.0.2001` | oxlint 的 TS 类型规则 |
| `knip` | `^6.16.1` | 未使用代码检测 |
| `publint` | `^0.3.21` | 发布字段检查 |
| `jscpd` | `^5.0.12` | 重复代码检测 |
| `lefthook` | `^2.1.9` | Git hooks |
| `vite-tsconfig-paths` | `^6.1.1` | Vite 路径解析 |
| `lightningcss` | `^1.32.0` | CSS 处理 |
| `mermaid` | `11.16.0` | 图表渲染（文档校验） |

### 4.3 测试与质量

| 依赖 | 版本 | 用途 |
|---|---|---|
| `@testing-library/dom` | `^10.4.1` | DOM 测试 |
| `@testing-library/react` | `^16.3.2` | React 组件测试 |
| `fast-check` | `^4.8.0` | 属性测试 |
| `jsdom` | `29.1.1` | DOM 模拟 |
| `execa` | `^10.0.0` | 进程执行 |
| `mdast-util-from-markdown` / `mdast-util-gfm` | — | Markdown 解析（文档校验） |

### 4.4 原生与系统

| 依赖 | 说明 |
|---|---|
| `node-pty` `1.1.0`（patched） | 跨平台 PTY 后端（含 Windows ConPTY）；补丁见 `patches/node-pty@1.1.0.patch` |
| `koffi` | Windows MoveFileExW 写透发布（JSONL 持久化） |
| `@deepseek-ai/node-addon-landlock-run` | Landlock 沙箱原生 addon（源码在 `native/`） |
| `esbuild` | 原生二进制打包（允许 build 脚本） |

### 4.5 持久化

- **SQLite**：单调 `SCHEMA_VERSION`，无兼容性承诺（pre-release）。
- **JSONL**：会话日志持久化，Windows 下用 MoveFileExW 写透发布。
- `dsh-session` 维持 `SESSION_FORMAT_VERSION = 0`，无兼容性承诺。

## 5. 构建与部署

### 5.1 开发环境

```sh
# 前置：Node.js ^22.19 || >=24，pnpm 11.7.0
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install          # workspace 安装（触发 lefthook postinstall）
pnpm run build        # build:lib:host + build:lib:client + build:web
pnpm dsh web          # 启动 Web UI（http://127.0.0.1:3080）
```

### 5.2 构建命令矩阵

| 命令 | 作用 |
|---|---|
| `pnpm run build:lib:host` | `tsc -b tsconfig.host.json` + `tsdown --env.DSH_BUILD_FACE host` |
| `pnpm run build:lib:client` | `tsc -b tsconfig.client.json` + `tsdown --env.DSH_BUILD_FACE client` |
| `pnpm run build:web` | `pnpm --filter @deepseek-ai/dsh-web-frontend run build`（Vite） |
| `pnpm run clean` | `tsx scripts/clean.ts`（清理构建产物与已删包残留） |
| `pnpm run typecheck` | `build:lib:host` + `tsc -b tsconfig.client.json` |

构建产物双 face 设计：`host`（Node 服务端）与 `client`（浏览器侧），通过 `DSH_BUILD_FACE` 环境变量切换。

### 5.3 运行方式

| 方式 | 命令 | 说明 |
|---|---|---|
| 从 npm 运行 | `npx @deepseek-ai/dsh web` | 无需克隆，启动 Web UI |
| 从源码运行 | `pnpm dsh web` | 需先 build |
| Headless 任务 | `pnpm dsh --profile headless "task"` | 一次性运行，需 `DEEPSEEK_API_KEY` |
| 查看插件树 | `dsh --profile web --dump-config` | 打印启动时实际加载的插件树 |
| Demo | `pnpm run demo:cordis` / `demo:acp` | 演示（需 key） |
| LLM Mock | `pnpm run mock:llm` | 本地 LLM mock server（测试用） |
| Web 开发 | `pnpm run dev:web` | Vite 开发模式（轮询） |

### 5.4 测试命令

| 命令 | 作用 |
|---|---|
| `pnpm run test` | `vitest run`（单元测试） |
| `pnpm run test:coverage` | CI 覆盖率门禁：`packages/*/*/src` 每文件 100% |
| `pnpm run test:e2e` | 真实 API 测试，无 `DEEPSEEK_API_KEY` 自动跳过 |
| `pnpm run test:snapshot` | 无 key 的 ACP/headless 回放；`-t <name>` 过滤 |
| `pnpm run test:snapshot:record` | 重新录制期望输出（需 key） |
| `pnpm run test:web` / `test:web:stress` / `test:web:perf` | Web 测试矩阵 |

### 5.5 质量门禁

```sh
pnpm run lint         # oxlint（先 build:lib:host 再 lint）
pnpm run duplication  # jscpd（packages + scripts）
pnpm run knip         # --treat-config-hints-as-errors
pnpm run publint      # 发布字段
pnpm run constraints  # workspace 约束
pnpm run hygiene      # 综合卫生检查（rescope + knip + publint + constraints + 许可证 + 包不变量 + cordis-config + node-next-types + runtime-closure + vendored-links）
pnpm run doc-sync     # 所有文档门禁
pnpm run website:build # VitePress 构建（兼作死链检查）
```

### 5.6 部署形态

- **npm 包发布**：`@deepseek-ai/dsh-*` 系列，`publishConfig.access: public`。
- **单可执行文件**：`python/sdk-runtime` 是部署根，其依赖闭包是 exe 捆绑内容，由 Python 运行时分发。
- **无 Docker/K8s**：仓库未包含容器化部署配置，面向本地/CLI/SDK 集成场景。

## 6. 环境配置

### 6.1 必需环境变量

| 变量名 | 用途 | 必需 | 示例 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek 真实 API 调用（e2e 测试、demo、headless 运行） | 运行真实 API 时必需 | `sk-...` |

### 6.2 可选环境变量

| 变量名 | 用途 | 说明 |
|---|---|---|
| `DEEPSEEK_BASE_URL` | DeepSeek API 基址覆盖 | 可选 |
| `DSH_BUILD_FACE` | 构建面选择 | `host` / `client` |
| `DSH_SNAPSHOT` | 快照测试模式 | `record` / `refresh` / `replay` |
| `NODE_PATH` | managed workspace 模块解析 | `C:\...\node\workspace\node_modules` |

### 6.3 配置文件

| 文件 | 作用 |
|---|---|
| `.env`（根） | `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`（不提交） |
| `cordis.yml` | 插件组合配置；`!!js` 允许（非 `!js`）用于 plugin `config` 与 entry `disabled`，其余元数据保持字面量 |
| `cordis.patch.yml` | profile 级 / home 级补丁，按 id 替换整行 config 或插入新行 |
| `tsconfig.host.json` / `tsconfig.client.json` | 双 face TypeScript 构建 |
| `tsdown.config.ts` | 运行时打包配置 |
| `vitest.*.config.ts` | 多套测试配置（unit/e2e/snapshot/web/stress/perf） |
| `.oxlintrc.json` / `.oxlintrc.staged.json` | Lint 规则 |
| `knip.json` | 未使用代码检测配置 |
| `lefthook.yml` | Git hooks 配置 |
| `.jscpd.json` | 重复代码检测配置 |
| `pnpm-workspace.yaml` | workspace 与 override（cosmokit/schemastery link 到 vendor） |

### 6.4 Profile 组合顺序

层按以下顺序应用到空 entry 列表：

1. profile 列出的每个 bundle（按列出顺序）
2. profile 的 `cordis.patch.yml`
3. home 级 `cordis.patch.yml`
4. 任何 `--patch` overlay

任一行可通过 patch 替换。`dsh-base` 是每个 profile 的第一层（模型适配器、工具、持久化、沙箱、审批策略、设置、凭据、遥测）。

---

> 下一步：[系统架构](../02-architecture/system-architecture.md)
