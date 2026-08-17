# L5 能力接缝层

> 参照 [系统组件架构图](../02-architecture/system-component-architecture.puml) 与 [能力接缝文档](../../02-architecture/system-architecture.md#3-核心组件)。

## 1. 层职责

提供 Agent 可调用的全部能力，以**能力接缝（Capability Seams）**模式组织。每个接缝由三角色构成：
- **Service Definition**：零依赖接口声明（声明能力存在）。
- **Service Provider**：实现接口（绑定具体后端，如 local / sandbox / e2b）。
- **Consumer**：使用能力（通常是面向模型的工具，注册到 `ctx.tools`）。

换一个 Provider 即可迁移整个执行世界（如本地→远程沙箱），无需 Consumer 分叉。

## 2. 主要组件

### 2.1 执行环境能力接缝

| 接缝 | 包 | ctx key | Provider | 说明 |
|---|---|---|---|---|
| Bash 执行 | `shell/` | `ctx.shell` | local、pwsh | 经 `ctx.subprocess` 生成进程 |
| 子进程 | `subprocess/` | `ctx.subprocess` | 本地进程树 | 进程树管理 |
| 持久终端 | `terminal/` | `ctx.terminals` | local PTY | owner-scoped 会话，node-pty（ConPTY） |
| 代码执行 | `code-runtime/` | — | worker-thread | Code Mode Consumer |
| 进程限制 | `sandbox/` | `ctx.sandbox` | bwrap / Landlock / Seatbelt / Windows ACL | 限制生成进程能力 |
| 文件系统 | `fs/` | `ctx.fs` | local | 文件读写 + 策略 + bash-backed 发现工具 |
| LSP | `lsp/` | — | generic stdio | 语言服务器协议 |
| 远程沙箱 | `e2b/` | — | E2B 云 | POC |

### 2.2 模型协作能力接缝

| 接缝 | 包 | ctx key | 说明 |
|---|---|---|---|
| LLM 适配 | `llm/` | `ctx.llm` | 消息/流词汇 + 适配器接缝；DeepSeek + pi-ai |
| Skill | `skill/` | — | provider 注册表 + 本地实现 + catalog/loader 工具 |
| Web | `web/` | — | search/fetch provider + 工具 |
| 上下文压缩 | `compaction/` | — | basic provider + 命令 Consumer |
| 请求上下文 | `context/` | — | workspace 指令、时间上下文 |
| 子 agent | `subagent/` | — | provider 注册表 + 委派工具 |
| 后台任务 | `jobs/` | `ctx.jobs` | `job_*` 控制工具 |
| 工作流 | `workflow/` | — | worker-thread 引擎 + ralph 工具 |
| Todo | `todo/` | — | `todo_write` 工具 |
| 计划 | `plan/` | — | 计划协作状态（直接进入 + 审核退出） |
| 预设组合 | `preset/` | — | 预设 cordis.yml 的 per-session agent 组合 |
| 循环守卫 | `guard/` | — | 重复调用提醒 + 工具超时强制器 |
| 运行时自修改 | `extensions/` | — | 实时插件/服务检查 + 模型挂载/卸载插件 |
| 目标 | `goal/` | `ctx.goals` | 同会话目标持久化 |
| 定时 | `schedule/` | — | 会话本地定时跟进 |
| 反馈 | `feedback/` | — | 人类反馈 |
| 身份 | `identity/` | — | 匿名身份 |

## 3. 对外接口

能力接缝通过 `ctx.*` key 暴露。Consumer 工具通过 `ctx.tools` 注册，其 schema 自动加入 prompt 装配。

| 能力 | 注册方式 |
|---|---|
| 面向模型的工具 | `ctx.tools` 注册；schema 加入 prompt |
| 给某会话不同能力集 | 组合 agent preset；service 行需 `isolate` realm |
| 添加 shell 执行 | 注册 `ctx.shell` 后端 |
| 添加持久终端 | 注册 `ctx.terminals` 后端 + `dsh-tool-terminal` |
| 添加文件系统策略 | 注册 `ctx.fs` provider 或监听 `fs/*` 事件 |
| 限制生成进程 | `ctx.sandbox` 后端；consumer 在 spawn 前包装 argv |

## 4. 与其他层的交互

- **上层依赖**：L4（Core API）——能力 Consumer 通过 `ctx.tools` 注册，Provider 通过 `ctx.*` 接缝挂载。
- **下层调用**：
  - 执行环境接缝 → 外部系统：本地 FS/PTY、E2B 云、DeepSeek API。
  - shell/subprocess → sandbox：生成进程前经 sandbox 包装 argv。
  - terminal → subprocess：PTY 经 subprocess 生成。
  - code-runtime → sandbox：代码执行经 sandbox 限制。
- **横向**：能力接缝之间通过 `ctx.tools` 协作（如 fs 工具与 shell 工具共享执行世界）。

## 5. 关键代码路径

```
packages/llm/llm/src/                  # LLM 接缝 (ctx.llm)
packages/llm/llm-deepseek/src/         # DeepSeek 适配器
packages/shell/                        # Bash 能力 (ctx.shell)
packages/subprocess/                   # 子进程 (ctx.subprocess)
packages/terminal/                     # 持久终端 (ctx.terminals)
packages/sandbox/                      # 进程限制 (ctx.sandbox)
packages/fs/                           # 文件系统 (ctx.fs)
packages/lsp/                          # LSP
packages/skill/                        # Skill
packages/web/                          # Web search/fetch
packages/compaction/                   # 上下文压缩
packages/subagent/                     # 子 agent
packages/jobs/                         # 后台任务 (ctx.jobs)
packages/workflow/                     # 工作流
packages/extensions/                   # 运行时自修改
```

## 6. 技术实现

- **三角色解耦**：Service Definition（接口）零依赖；Provider 绑定 SDK；Consumer 注册到 `ctx.tools`。这使 provider 可替换迁移整个执行世界。
- **共享执行世界**：fs + subprocess + sandbox + shell 共享一个执行世界。指向远程沙箱即可迁移 Bash、PTY、LSP，无 provider 分叉。
- **isolate realm**：给某会话不同能力集时，preset 的 service 行需 `isolate` realm 隔离。
- **waterfall 策略注入**：`tools/pre-execute` waterfall 注入审批/策略；`fs/*`、`tools/*`、`telemetry/*` 事件附加策略而不导入 loop。
- **模型可见上下文**：`agent.inject()` 将上下文落入下次 admitted 请求；注入的上下文在 inbox 中等待直至另一消息到达。

## 7. 注意事项

- 扩展插件应依赖 Service Definition（如 `dsh-llm`），而非具体 Provider（如 `dsh-llm-deepseek`）。
- 能力接缝三角色必须同时设计——一个角色单独不构成接缝。
- 添加新能力需同时考虑：接口声明、默认 provider、模型可见工具。
- `extensions/` 允许 agent 在运行时检查并挂载/卸载自己的插件（自指 cordis toolset）。
