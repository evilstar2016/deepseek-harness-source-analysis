# 框架与构建工具集成

> 本文档基于 AST 符号工具对源码符号进行验证分析生成。代码引用处的行号均来自符号工具验证。

## 1. 集成概述

dsh 的「第三方框架与构建工具」分两类：

- **Vendored 框架**：把 Cordis 生态（`cordis` / `cosmokit` / `schemastery`）从上游 fork 后 vendored 进 `vendor/` 目录，重新 scope 为 `@deepseek-ai/*` 并通过 `linkWorkspacePackages` 与本地源码联动。
- **第三方构建工具**：pnpm workspace、tsdown、oxlint、vitest、TypeScript、tsx、knip、publint、lefthook、jscpd、mermaid 等通过根 `package.json` devDependencies 集中管理。

这层集成的不变主题是 **「vendored 框架提供插件化骨架，第三方工具链保证 monorepo 健康度」**。

### 设计哲学

- **Vendored 而非 dependency**：Cordis 三件套 fork 进仓库，scope 改为 `@deepseek-ai/*`，便于 dsh 在框架层做 in-tree 修复与演进。
- **linkWorkspacePackages: true**：本地源码 override 远程包，确保 `@deepseek-ai/cordis` 始终解析到 workspace pinned 源码而非 npm。
- **allowBuilds 默认拒绝**：pnpm 10+ 严格模式，所有 install/build 脚本默认拒绝，显式 allow 后才运行。
- **patchedDependencies**：必须修改的第三方包通过 patch 文件管理，避免 fork 维护成本。
- **类型契约先行**：所有构建前必须 `npm run build:lib:host` 才能跑 typecheck / lint（contracts-ready pattern）。

## 2. 支持的服务/产品

### 2.1 Vendored 框架

| 包名 | 上游 | 版本 | 角色 |
|---|---|---|---|
| `@deepseek-ai/cordis` | `cordis` (Shigma) | 4.0.1 | Meta-Framework for Modern JavaScript Applications |
| `@deepseek-ai/cosmokit` | `cosmokit` | 1.8.2 | Common utilities |
| `@deepseek-ai/schemastery` | `schemastery` | 3.18.1 | Type driven schema validator |
| `@deepseek-ai/cordis-plugin-include` | cordis 生态 | — | Cordis 插件 |
| `@deepseek-ai/cordis-plugin-loader` | cordis 生态 | — | Cordis 加载器 |
| 其他 vendor 子包 | — | — | `group` / `hmr` / `include` / `loader` / `logger-console` / `timer` |

### 2.2 第三方构建工具

| 工具 | 版本 | 用途 |
|---|---|---|
| pnpm | 11.7.0 | workspace monorepo 包管理器 |
| Node.js | ^22.19.0 \|\| >=24.0.0 | 运行时 |
| TypeScript | ^6.0.3 | 类型系统（注意：peerDependency `typescript: '>=5 <7'`） |
| tsx | ^4.22.4 | ESM TS 执行（CLI bin.ts 入口走 tsx/esm hook） |
| tsdown | ^0.22.2 | 库打包（基于 esbuild） |
| esbuild | (transitive) | 原生 binary，allowBuilds: true |
| oxlint | 1.76.0 | linter |
| oxlint-tsgolint | 7.0.2001 | oxlint TypeScript plugin |
| vitest | ^4.1.8 | 测试框架 |
| @vitest/coverage-v8 | ^4.1.8 | 覆盖率 |
| knip | ^6.16.1 | 未使用代码检测 |
| publint | ^0.3.21 | 发布前 package 配置 lint |
| lefthook | ^2.1.9 | git hooks，allowBuilds: true |
| jscpd | ^5.0.12 | 代码重复检测 |
| mermaid | 11.16.0 | 文档图表渲染 |
| jsdom | 29.1.1 | DOM 测试环境 |
| @testing-library/react | ^16.3.2 | React 组件测试 |
| fast-check | ^4.8.0 | property-based testing |
| execa | ^10.0.0 | 子进程执行 |
| vite-tsconfig-paths | ^6.1.1 | vite 路径别名 |
| lightningcss | ^1.32.0 | CSS 优化 |
| smol-toml | ^1.7.1 | TOML 解析 |
| spdx-expression-parse | ^5.0.0 | SPDX 许可证解析 |
| js-yaml | ^4.2.0 | YAML 解析 |
| mdast-util-* | — | Markdown AST 工具链 |

## 3. 集成方式

### 3.1 Vendored Cordis Workspace

`pnpm-workspace.yaml` 第 1-2 行：

```yaml
packages:
  - vendor/*
  - packages/*/*
```

`vendor/` 下每个子包都是独立 workspace 成员。`linkWorkspacePackages: true`（line 25）让本地源码 override 远程版本。

`overrides`（line 27-29）强制所有传递依赖解析到 vendored 版本：

```yaml
overrides:
  '@deepseek-ai/cosmokit': 'link:vendor/cosmokit'
  '@deepseek-ai/schemastery': 'link:vendor/schemastery'
```

`peerDependencyRules.allowedVersions`（line 31-33）放宽 TypeScript peer：

```yaml
peerDependencyRules:
  allowedVersions:
    typescript: '>=5 <7'
```

#### `@deepseek-ai/cordis` 4.0.1

`vendor/cordis/package.json` 描述：「Meta-Framework for Modern JavaScript Applications」。源码在 `vendor/cordis/src/`（含 `context.ts` / `events.ts` / `fiber.ts` / `logger.ts` / `reflect.ts` / `registry.ts` / `service.ts` / `utils.ts`）。

关键能力：

- **Context + Service**：所有 dsh 能力继承 `Service`（如 `SandboxProvider extends Service`、`TokenMeter extends Service`、`E2BRuntime extends Service`）。
- **declaration merging**：dsh 通过 `declare module '@deepseek-ai/cordis'` 扩展 `Context` 接口（如 `ctx.llm` / `ctx.sandbox` / `ctx.tokenMeter` / `ctx.e2b`）。
- **waterfall events**：`Events` 接口扩展定义 waterfall（如 `'llm/stream'` 在 `packages/llm/llm/src/index.ts:51-66`）。
- **ctx.effect() / ctx.on()**：可逆 effect，plugin 卸载时自动回滚。

`peerDependencies` 含可选的 `@deepseek-ai/cordis-plugin-include` 和 `@deepseek-ai/cordis-plugin-loader`（独立 vendor 子包）。

依赖 `@standard-schema/spec: ^1.1.0` + `@deepseek-ai/cosmokit: workspace:^`。

#### `@deepseek-ai/cosmokit` 1.8.2

`vendor/cosmokit/package.json`：common utilities，零依赖（除标准库），被 cordis 和 schemastery 依赖。

#### `@deepseek-ai/schemastery` 3.18.1

`vendor/schemastery/package.json`：type-driven schema validator。所有 dsh plugin 的 `Config` schema 用 `z = @deepseek-ai/schemastery` 定义。

关键用法（dsh 内）：

- `z.object({...})`：定义 plugin Config。
- `z.string().role('credential-ref')`：标记字段为 credential 引用（不让 secret 进入配置）。
- `z.string().role('secret')`：标记字段为 secret 字面量（web-search-deepseek 支持）。
- `z.number().default(...)` / `z.union([...])` / `z.array(...)`：标准 schema 组合子。
- `static Config: z<Config>`：每个 Service plugin 把 schema 暴露为 static 属性供 loader 读取。

依赖 `@standard-schema/spec: ^1.1.0` + `@deepseek-ai/cosmokit: workspace:^`。

### 3.2 pnpm Workspace + allowBuilds

`pnpm-workspace.yaml` 的 workspace 成员：

```yaml
packages:
  - vendor/*                    # vendored 框架
  - packages/*/*                # dsh 工作区（49 个 group）
  - native/landlock-run         # 原生 addon
  - native/landlock-run/packages/*
  - apps/*                      # 产品装配（CLI、Web）
  - website                     # 文档站点
  - examples                    # 示例（仅 dependency resolution）
  - python/sdk-runtime          # 单 exe 部署根
```

`allowBuilds`（line 40-55，pnpm 10+ strict 模式）：

```yaml
allowBuilds:
  esbuild: true                 # 原生 binary，需 install script
  lefthook: true                # git hooks，需 install script
  node-pty: true                # 跨平台 PTY 后端（含 ConPTY）
  '@google/genai': false        # pi-ai 拉入但脚本 no-op，拒绝
  protobufjs: false             # 同上
  node-addon-require-builtin: false  # 同上
  koffi: true                   # Win32 FFI，MoveFileExW 用于 JSONL durability
  '@deepseek-ai/dsh-subprocess-local@file:packages/subprocess/subprocess-local': true
```

设计原则：

- **默认拒绝**：未列出的包 install/build 脚本一律拒绝（hard install error）。
- **理由**：esbuild（native binary）、lefthook（git hooks）、node-pty（ConPTY）、koffi（FFI）确实需要 install script。
- **拒绝 no-op**：`@google/genai` / `protobufjs` / `node-addon-require-builtin*` 的 lifecycle script 是 no-op，拒绝可加速 install。

`minimumReleaseAgeExclude`（line 57-69）：fresh pi-ai release（0.82.1）和 node-addon-* 0.1.4 排除最小发布年龄限制，因为这些版本携带 model catalog 更新或 native binary 是发布目的本身。

`patchedDependencies`（line 71-72）：

```yaml
patchedDependencies:
  node-pty@1.1.0: patches/node-pty@1.1.0.patch
```

### 3.3 构建工具链

#### tsdown（库打包）

根 `package.json` 的 build 脚本（line 21-23）：

```json
"build:lib": "npm run build:lib:host && npm run build:lib:client",
"build:lib:host": "tsc -b tsconfig.host.json && tsdown --env.DSH_BUILD_FACE host",
"build:lib:client": "tsc -b tsconfig.client.json && tsdown --env.DSH_BUILD_FACE client",
```

两个 face：

- **host**：服务端代码，给 dsh runtime 用。
- **client**：浏览器侧代码，给 Web UI 用。

tsdown 基于 esbuild，单文件 bundle 输出到 `lib/index.js`（每个子包的 `exports['.'].default`）。

#### TypeScript 6.0.3 + tsx 4.22.4

`typescript: ^6.0.3` 是较新版本，peerDependency `typescript: '>=5 <7'` 兼容。

`tsx: ^4.22.4` 提供 ESM TS 执行：

- CLI 入口 `apps/cli/src/bin.ts` 通过 `node --import tsx/esm` 启动（package.json `dsh` 脚本，line 136）。
- 各包的 `src/*` 通过 `./src/*` export 暴露，便于开发期直接 import 源码。
- 例如 `dsh-sandbox-windows-acl/runner` 在开发期通过 `[process.execPath, '--import', 'tsx/esm', sourceEntry]` 启动（`sandbox-local/src/index.ts:563`）。

#### oxlint 1.76.0

`oxlint-tsgolint: 7.0.2001` 是 TypeScript plugin。

Lint 脚本（package.json line 29-32）：

```json
"lint": "npm run build:lib:host && npm run lint:contracts-ready",
"lint:contracts-ready": "tsx scripts/run-oxlint.ts .",
"lint:fix": "npm run build:lib:host && npm run lint:fix:contracts-ready",
"lint:fix:contracts-ready": "tsx scripts/run-oxlint.ts --config .oxlintrc.staged.json packages/typert/generator/tests/fixtures/type-model --fix && tsx scripts/run-oxlint.ts . --fix",
```

**contracts-ready 模式**：先 `build:lib:host` 让 type contracts 可见，再 lint。这是 dsh 反复出现的模式。

`.oxlintrc.staged.json` 是 lefthook staged 用的精简配置。

#### vitest 4.1.8

`vitest: ^4.1.8` + `@vitest/coverage-v8: ^4.1.8`。多种 test 配置：

```json
"test": "vitest run",
"test:coverage": "vitest run --coverage",
"test:e2e": "vitest run --config vitest.e2e.config.ts",
"test:snapshot": "vitest run --config vitest.snapshot.config.ts",
"test:snapshot:record": "DSH_SNAPSHOT=record vitest run --config vitest.snapshot.config.ts --update",
"test:snapshot:refresh": "DSH_SNAPSHOT=refresh vitest run --config vitest.snapshot.config.ts",
"test:web": "npm run build && npm run test:web:built",
"test:web:built": "vitest run --config vitest.web.config.ts",
"test:web:perf": "npm run build && npm run test:web:perf:built",
"test:web:stress": "npm run build && vitest run --config vitest.web-stress.config.ts",
"test:gui": "vitest run packages/client packages/host",
```

Snapshot 测试支持 `record` / `refresh` / `replay` 三种模式（通过 `DSH_SNAPSHOT` env var 控制）。

#### knip 6.16.1

`knip: ^6.16.1` 检测未使用的 exports / dependencies / files。

```json
"knip": "knip --treat-config-hints-as-errors",
```

`--treat-config-hints-as-errors` 让 config 提示也视为错误，确保严格。

#### publint 0.3.21

```json
"publint": "tsx scripts/publint-all.ts",
```

`publint-all.ts` 批量检查所有子包的 `package.json` 配置（exports / files / main / types 等），确保发布前正确。

#### lefthook 2.1.9

`lefthook: ^2.1.9` 管理 git hooks。`postinstall: node scripts/install-lefthook.mjs`（package.json line 142）。

`allowBuilds: lefthook: true` 让其 install script 运行。

#### jscpd 5.0.12

`jscpd: ^5.0.12` 检测代码重复：

```json
"duplication": "jscpd --config .jscpd.json packages scripts",
```

#### mermaid 11.16.0

`mermaid: 11.16.0` 用于文档图表渲染（如 `analysis/02-architecture/system-component-architecture.puml`，虽然 puml 是 PlantUML 但项目也含 mermaid 图）：

```json
"verify-mermaid": "tsx scripts/verify-mermaid.ts",
```

## 4. 代码实现

### 4.1 关键脚本

| 脚本 | 文件 | 用途 |
|---|---|---|
| `build:lib:host` | `tsconfig.host.json` + tsdown | 构建 host face |
| `build:lib:client` | `tsconfig.client.json` + tsdown | 构建 client face |
| `lint:contracts-ready` | `scripts/run-oxlint.ts` | 跑 oxlint |
| `publint` | `scripts/publint-all.ts` | 批量 publint |
| `knip` | (直接 knip) | 未使用代码检测 |
| `verify-md-links` | `scripts/verify-md-links.ts` | 文档链接校验 |
| `verify-md-wrap` | `scripts/verify-md-wrap.ts` | markdown 换行校验 |
| `verify-mermaid` | `scripts/verify-mermaid.ts` | mermaid 图表校验 |
| `verify-package-invariants` | `scripts/verify-package-invariants.ts` | 包不变量校验 |
| `verify-built-package-invariants` | `scripts/verify-built-package-invariants.mjs` | 构建后包不变量校验 |
| `verify-vendored-links` | `scripts/verify-vendored-links.ts` | vendored 链接校验 |
| `verify-cordis-config` | `scripts/verify-cordis-config.ts` | cordis 配置校验 |
| `verify-runtime-closure` | `scripts/verify-runtime-closure.ts` | runtime 闭包校验 |
| `verify-node-next-types` | `scripts/verify-node-next-types.ts` | Node next 类型校验 |
| `verify-dsh-package-licenses` | `scripts/verify-dsh-package-licenses.ts` | 许可证校验 |
| `verify-third-party-notices` | `scripts/gen-third-party-notices.ts --check` | 第三方声明校验 |
| `gen-cordis-catalog` | `scripts/gen-cordis-catalog.ts` | 生成 cordis 目录 |
| `gen-tool-catalog` | `scripts/gen-tool-catalog.ts` | 生成工具目录 |
| `gen-config-catalog` | `scripts/gen-config-catalog.ts` | 生成配置目录 |
| `gen-module-graph` | `scripts/gen-module-graph.ts` | 生成模块图 |
| `gen-doc-graphs` | `scripts/gen-doc-graphs.ts` | 生成文档图 |
| `rescope-vendor` | `scripts/rescope-vendor.ts` | 重 scope vendored 包 |
| `hygiene` | (组合脚本) | 多重卫生检查 |

### 4.2 Contracts-Ready 模式

多个 gate 脚本都遵循 `build:lib:host && gate:contracts-ready` 模式：

```json
"typecheck": "npm run build:lib:host && npm run typecheck:contracts-ready",
"lint": "npm run build:lib:host && npm run lint:contracts-ready",
"doc-typecheck": "npm run build:lib:host && npm run doc-typecheck:contracts-ready",
```

原因：dsh 的 type contracts（如 `SessionEventMap`、`Context` declaration merging）跨包生成，必须先构建 host face 才能让下游包看到完整类型。

### 4.3 Gate 系统

`scripts/run-gates.ts`（package.json line 49-62）封装多种 gate：

```json
"check:all": "tsx scripts/run-gates.ts check-all",
"check:ci": "tsx scripts/run-gates.ts ci-primary",
"check:ci:static": "tsx scripts/run-gates.ts ci-static",
"check:ci:coverage": "tsx scripts/run-gates.ts ci-coverage",
"check:ci:snapshot": "tsx scripts/run-gates.ts ci-snapshot",
"check:ci:artifacts": "tsx scripts/run-gates.ts ci-artifacts",
"check:ci:consumers": "tsx scripts/run-gates.ts ci-consumers",
"check:ci:linux-primary": "tsx scripts/run-gates.ts ci-linux-primary",
"check:ci:windows-blocking": "tsx scripts/run-gates.ts ci-windows-blocking",
"check:ci:windows-complete": "tsx scripts/run-gates.ts ci-windows-complete",
"check:ci:windows-observational": "tsx scripts/run-gates.ts ci-windows-observational",
"check:node-compat": "tsx scripts/run-gates.ts node-compat",
"check:windows-wine": "bash scripts/wine-windows-gates.sh",
```

平台分层：

- **static**：lint / typecheck / docs。
- **linux-primary**：Linux 主流 CI。
- **windows-blocking**：Windows 必跑 gate。
- **windows-observational**：Windows 观察性 gate（不 block）。
- **wine**：通过 Wine 跑 Windows gate（非 Windows 主机）。

### 4.4 Vendored Scope 重写

`scripts/rescope-vendor.ts`（package.json line 101-102）：

```json
"rescope-vendor": "tsx scripts/rescope-vendor.ts",
"rescope-vendor:check": "tsx scripts/rescope-vendor.ts --check",
```

把 vendored 包的 `package.json` 中 `@cordiverse/*` 等 upstream scope 改写为 `@deepseek-ai/*`。`verify-vendored-links.ts` 校验所有内部 import 都用新 scope。

## 5. 配置与环境变量

### 5.1 环境变量

| 环境变量 | 作用 | 默认 |
|---|---|---|
| `DSH_BUILD_FACE` | tsdown 构建目标 face | `host` 或 `client`（由 build 脚本设置） |
| `DSH_SNAPSHOT` | snapshot 测试模式 | `record` / `refresh` / `replay` |
| `NODE_OPTIONS` | Node.js 启动选项 | (隐式含 `--import tsx/esm` for dev) |

### 5.2 关键配置文件

| 文件 | 用途 |
|---|---|
| `pnpm-workspace.yaml` | workspace 配置（packages / overrides / allowBuilds / patchedDependencies） |
| `tsconfig.host.json` | host face TS 配置 |
| `tsconfig.client.json` | client face TS 配置 |
| `tsconfig.base.json` | 共享 TS 配置 |
| `.oxlintrc.json` / `.oxlintrc.staged.json` | oxlint 配置 |
| `vitest.config.ts` / `vitest.e2e.config.ts` / `vitest.snapshot.config.ts` / `vitest.web.config.ts` / `vitest.web.perf.config.ts` / `vitest.web-stress.config.ts` | vitest 配置 |
| `.jscpd.json` | jscpd 配置 |
| `lefthook.yml` | lefthook 配置 |
| `knip.json` / `knip.base.json` | knip 配置 |

## 6. 错误处理

### 6.1 构建错误

| 错误 | 原因 | 处理 |
|---|---|---|
| `tsc -b` 失败 | 类型错误 | 必须修复才能继续 tsdown |
| `tsdown` 失败 | bundle 错误 | 检查 `exports` 配置和 `lib/index.js` |
| `peerDependencyRules` 不满足 | TypeScript 版本不匹配 | 检查 `allowedVersions: typescript: '>=5 <7'` |
| allowBuilds 拒绝 | 未列出的 install script | 加入 `allowBuilds` 或修复 |

### 6.2 CI 错误

gate 系统分层失败：

- **static gate 失败**：lint / typecheck / knip / publint / 链接校验。
- **test gate 失败**：单元测试 / snapshot 不匹配（用 `DSH_SNAPSHOT=record` 更新）/ e2e。
- **platform gate 失败**：Linux 主 CI 失败 block，Windows observational 不 block。

### 6.3 Vendored 链接错误

- `verify-vendored-links.ts`：检查 vendored 包内 import 都用 `@deepseek-ai/*` scope。
- `rescope-vendor:check`：CI 跑 `--check` 模式，确保 `rescope-vendor` 已运行。

### 6.4 包不变量错误

`verify-package-invariants.ts` + `verify-built-package-invariants.mjs`：

- 检查每个包的 `exports` / `files` / `main` / `types` 一致性。
- 检查构建产物存在且匹配配置。
- 防止发布配置错误。

## 7. 扩展指南

### 7.1 升级 Vendored Cordis

1. **拉取上游变更**：从 `cordiverse/cordis` 同步到 `vendor/cordis/src/`。
2. **跑 `rescope-vendor`**：重写所有 scope 为 `@deepseek-ai/*`。
3. **跑 `verify-vendored-links:check`**：确保 import 正确。
4. **跑 `gen-cordis-catalog --check`**：目录生成一致。
5. **跑 `verify-cordis-config`**：配置校验。
6. **跑 `check:all`**：全量 gate。
7. **更新 `vendor/cordis/package.json` 版本**。

### 7.2 添加新子包到 workspace

1. **创建 `packages/<group>/<pkg>/`**，写 `package.json`：
   - `name`: `@deepseek-ai/dsh-<pkg>`
   - `version`: `0.1.0-rc.5`（与 workspace 同步）
   - `peerDependencies`: 含 `@deepseek-ai/cordis: workspace:^`
   - `dependencies`: 含 `@deepseek-ai/schemastery: workspace:^`（如需 schema）
   - `exports['.']` / `exports['./invariant']` / `exports['./src/*']` / `exports['./package.json']`
   - `files`: 列出 `lib/index.js` / `lib/invariant.js` / `lib/types/**/*.d.ts`
2. **加入 `cordis.yml`**：在对应 bundle 的 plugin 列表加 `- id: <pkg>`。
3. **跑 `verify-package-invariants`**：检查配置一致。
4. **跑 `publint`**：发布前 lint。

### 7.3 添加新第三方构建依赖

1. **加入根 `package.json` `devDependencies`**（不要加到子包）。
2. **若包有 install/build script**：
   - 在 `pnpm-workspace.yaml` 的 `allowBuilds` 加 `true`（确实需要）或 `false`（no-op 拒绝）。
   - 若是 native binary 类（如 esbuild），考虑 `minimumReleaseAgeExclude`。
3. **若需 patch**：
   - 创建 `patches/<pkg>@<version>.patch`（用 `pnpm patch`）。
   - 在 `pnpm-workspace.yaml` 的 `patchedDependencies` 加 entry。
4. **集成到 gate 脚本**：在 `scripts/run-gates.ts` 加对应 gate。

## 8. 关键 SDK 依赖版本

### 8.1 Vendored 框架

| 包 | 版本 | 上游 |
|---|---|---|
| `@deepseek-ai/cordis` | 4.0.1 | cordiverse/cordis |
| `@deepseek-ai/cosmokit` | 1.8.2 | cordiverse/cosmokit |
| `@deepseek-ai/schemastery` | 3.18.1 | Shigma/schemastery |
| `@standard-schema/spec` | ^1.1.0 | standard-schema（被 cordis 和 schemastery 依赖） |

### 8.2 构建工具链版本矩阵

| 工具 | 版本 | 必要性 |
|---|---|---|
| pnpm | 11.7.0 | 包管理器（`packageManager` 字段） |
| Node.js | ^22.19.0 \|\| >=24.0.0 | 运行时（`engines.node`） |
| TypeScript | ^6.0.3 | 类型系统 |
| tsx | ^4.22.4 | ESM TS 执行 |
| tsdown | ^0.22.2 | 库打包 |
| oxlint | 1.76.0 | linter |
| oxlint-tsgolint | 7.0.2001 | oxlint TS plugin |
| vitest | ^4.1.8 | 测试 |
| @vitest/coverage-v8 | ^4.1.8 | 覆盖率 |
| knip | ^6.16.1 | 未使用代码检测 |
| publint | ^0.3.21 | 发布 lint |
| lefthook | ^2.1.9 | git hooks |
| jscpd | ^5.0.12 | 代码重复 |
| mermaid | 11.16.0 | 文档图表 |
| jsdom | 29.1.1 | DOM 测试 |
| @testing-library/react | ^16.3.2 | React 测试 |
| fast-check | ^4.8.0 | property-based testing |
| execa | ^10.0.0 | 子进程执行 |
| vite-tsconfig-paths | ^6.1.1 | vite 路径别名 |
| lightningcss | ^1.32.0 | CSS 优化 |
| smol-toml | ^1.7.1 | TOML |
| spdx-expression-parse | ^5.0.0 | SPDX |
| js-yaml | ^4.2.0 | YAML |
| mdast-util-from-markdown | ^2.0.3 | Markdown AST |
| mdast-util-gfm | ^3.1.0 | GFM 扩展 |
| micromark-extension-gfm | ^3.0.0 | GFM parser |
| @types/node | ^22.20.0 | Node 类型 |
| @types/js-yaml | ^4.0.9 | js-yaml 类型 |
| @types/jsdom | ^28.0.3 | jsdom 类型 |
| @types/mdast | ^4.0.4 | mdast 类型 |
| @types/spdx-expression-parse | ^4.0.0 | SPDX 类型 |
| @stylistic/eslint-plugin | ^5.10.0 | ESLint 风格 |
| eslint-plugin-sonarjs | ^4.1.0 | SonarJS 规则 |
| @yarnpkg/cli-dist | 4.17.1 | Yarn CLI（用途未明） |
| istanbul-lib-report | ^3.0.1 | 覆盖率报告 |

## 9. 关键发现

1. **Vendored Cordis 是 in-tree fork**：scope 从 `@cordiverse/*` 改为 `@deepseek-ai/*`，`linkWorkspacePackages: true` + `overrides` 确保本地源码 override 远程，便于 dsh 在框架层快速修复。
2. **`allowBuilds` 是安全防线**：pnpm 10+ 默认拒绝所有 install/build script，dsh 显式 allow 仅需要的（esbuild / lefthook / node-pty / koffi），拒绝 no-op 的（`@google/genai` / `protobufjs`），减少供应链攻击面。
3. **patchedDependencies 用于 node-pty**：1.1.0 版本通过 `patches/node-pty@1.1.0.patch` 自定义修复，无需 fork。
4. **contracts-ready 模式贯穿**：`build:lib:host` 必须在 typecheck / lint / doc-typecheck 前跑，因为 dsh 的 type contracts 跨包生成（declaration merging / SessionEventMap 等）。
5. **双 face 构建**：`host`（服务端）和 `client`（浏览器）分开构建，让 Web UI 不携带 Node-only 代码。
6. **平台分层 CI**：Linux-primary + Windows-blocking + Windows-observational + Wine（非 Windows 主机跑 Windows gate），保证跨平台质量。
7. **大量 verify 脚本**：`verify-md-links` / `verify-mermaid` / `verify-package-invariants` / `verify-vendored-links` / `verify-cordis-config` / `verify-runtime-closure` 等，构成强约束的卫生检查网，但需要维护成本。
8. **TypeScript 6 + peerDependency 5-7**：用 TypeScript 6 但 peer 兼容 5+，下游消费者可灵活选版本。
9. **gen-catalog 系列**：`gen-cordis-catalog` / `gen-tool-catalog` / `gen-config-catalog` / `gen-persistence-catalog` 等从源码生成目录，确保文档与代码同步。
10. **`hygiene` 是组合脚本**：`rescope-vendor:check && knip && publint && constraints && verify-dsh-package-licenses && verify-package-invariants && verify-built-package-invariants && verify-cordis-config && verify-node-next-types && verify-runtime-closure && verify-vendored-links`——一次跑完所有卫生检查。
