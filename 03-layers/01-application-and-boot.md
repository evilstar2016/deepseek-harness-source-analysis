# L1-L2 应用入口与 Boot 组合层

> 参照 [系统组件架构图](../02-architecture/system-component-architecture.puml)。本文档覆盖 L1（应用入口）与 L2（Boot 组合）。

## 1. 层职责

### L1 应用入口
提供用户可达的启动入口：CLI（`dsh` 命令）与 Web UI（浏览器）。负责命令行解析、参数分发、启动 Boot 组合器。

### L2 Boot 组合
将分散的插件包按 Profile/Bundle 有序层组合为一棵可运行的插件树。读取 profile 配置 → 加载 bundle 列表 → 应用 patch overlay → 构建 Cordis 上下文。

## 2. 主要组件

### 2.1 apps/cli（L1）
- **路径**：`apps/cli/`
- **职责**：`dsh` CLI 入口，拥有 `dsh` bin。
- **核心**：`apps/cli/src/bin.ts`（经 `node --import tsx/esm` 启动）；`config/`（CLI 配置）、`reference/`、`tests/`。
- **启动命令**：`pnpm dsh web` / `pnpm dsh --profile headless "task"`。

### 2.2 apps/web（L1）
- **路径**：`apps/web/`
- **职责**：Web UI 前端，Vite 构建。
- **核心**：`index.html` 入口、`vite.config.ts`、`src/`、`stress-tests/`、`tests/`。
- **默认端口**：`http://127.0.0.1:3080`。

### 2.3 boot/app-boot（L2）
- **路径**：`packages/boot/app-boot/`
- **职责**：Profile/Bundle 层组合核心。层应用顺序：每个 bundle（profile 列出顺序）→ profile `cordis.patch.yml` → home 级 `cordis.patch.yml` → `--patch` overlay。
- **配置查看**：`dsh --profile <name> --dump-config`。

### 2.4 boot/cmdline（L2）
- **路径**：`packages/boot/cmdline/`
- **职责**：命令行参数解析，分发到对应 profile 启动。

### 2.5 bundle/*（L2）
- **路径**：`packages/bundle/`
- **子包**：
  - `base`：每个 profile 的第一层——模型适配器、工具、持久化、沙箱、审批策略、设置、凭据、遥测。
  - `web-app`：添加浏览器应用层。
  - `headless`：添加无服务器一次性运行层。
- **声明方式**：`package.json` 的 `dsh.bundle` 字段指向补丁文件；`dsh.profile` 列出 profile 的 bundle。

## 3. 对外接口

| 接口 | 参数 | 说明 |
|---|---|---|
| `dsh web` | — | 启动 Web UI |
| `dsh --profile <name>` | profile 名 | 按指定 profile 启动 |
| `dsh --profile <name> --dump-config` | — | 打印插件树不启动 |
| `dsh --profile headless "task"` | 任务文本 | 一次性 headless 运行 |
| `dsh --patch <file>` | 补丁文件 | 叠加 overlay |

## 4. 与其他层的交互

- **上层依赖**：无（最顶层）。
- **下层调用**：
  - L1 → L2：CLI 解析后调用 `app-boot` 组合插件树。
  - L2 → L3：组合完成后启动 Host（Web 模式）或直接驱动 AgentLoop（headless 模式）。
  - L2 → L4/L5/L6：bundle 引入 Core、能力接缝、持久化插件。

## 5. 关键代码路径

```
apps/cli/src/bin.ts              # dsh bin 入口
apps/web/index.html              # Web UI HTML 入口
packages/boot/app-boot/src/      # Profile/Bundle 组合
packages/boot/cmdline/src/       # 命令行解析
packages/bundle/base/            # dsh-base 第一层
packages/bundle/web-app/         # Web 应用层
packages/bundle/headless/        # Headless 层
```

## 6. 技术实现

- **tsx ESM-only hook**：CLI 源码启动经 `node --import tsx/esm`，所达模块必须保持 ESM。
- **层组合是 patchable 的**：每个 bundle 插入的行可被上层 patch 替换（按 id 替换整行 config 或插入新行）。
- **Pre-release 自由重构**：无外部消费者，profile/bundle 可自由重命名并同步更新引用。
