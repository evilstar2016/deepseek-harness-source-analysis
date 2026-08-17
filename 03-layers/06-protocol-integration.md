# L7 协议与集成层

> 参照 [系统组件架构图](../02-architecture/system-component-architecture.puml)。详细集成方案见 [第三方集成文档](../06-ThirdParty/README.md)。

## 1. 层职责

提供进程外通信协议（Typert RPC、JSON-RPC、ACP）、hook 桥接（Claude Code/Codex）与人机协作面（审批、权限、命令、ask-user）。本层是 dsh 与外部世界（SDK 客户端、自动化系统、IDE hook、人类用户）的交互边界。

## 2. 主要组件

| 组件 | 路径 | 职责 |
|---|---|---|
| API 网关 | `api/gateway` + `api/remotes` | 远程 BFF 装配 + Typert RPC 网关 |
| Typert | `typert/generator` + `loader` + `protocol` + `registry` | 类型图生成、加载、运行时注册；跨语言类型契约 |
| SDK | `sdk/` | 进程外运行时 SDK：JSON-RPC 协议 + TS client + server 插件 |
| ACP | `acp/` | 仅自动化的 Agent Client Protocol server（@agentclientprotocol/sdk 0.25.1） |
| Hooks | `hooks/` | Claude Code/Codex hook 桥 + 共享 wire-protocol 库 |
| 交互 | `interaction/` | 审批/交互接缝、权限预设、命令、ask-user 工具 |

## 3. 对外接口

| 接口 | 协议 | 说明 |
|---|---|---|
| Typert RPC | Typert 类型图 | 跨语言（TS/Python）RPC 类型契约 |
| JSON-RPC | JSON-RPC | dsh 自有完整客户端协议（含 subagent 一等支持） |
| ACP | Agent Client Protocol 0.25.1 | automation-only，外部 trusted 客户端 |
| Hook 桥 | Claude Code/Codex wire-protocol | 执行未修改的 hook 命令 |
| `ctx.commands` | — | 人类命令分发，无需模型 turn |
| 审批/权限 | `tools/pre-execute` waterfall | 策略注入 |

## 4. 与其他层的交互

- **上层依赖**：L3（Host 经 api/gateway 暴露 RPC；Client 经 sdk 通信）。
- **下层调用**：L4（api → core/session 读取会话；acp → agent-loop 驱动；hooks → agent-loop）。
- **横向**：interaction 的权限预设注入 `tools/pre-execute`；hooks 与 agent-loop 的 `agent/*` 事件桥接。

## 5. 关键代码路径

```
packages/api/gateway/src/
packages/api/remotes/src/
packages/typert/generator/src/
packages/typert/loader/src/
packages/typert/protocol/src/
packages/typert/registry/src/
packages/sdk/server/src/server.ts    # HarnessSdkJsonRpcServer (L52)
packages/acp/src/
packages/hooks/
packages/interaction/src/
```

## 6. 技术实现

- **Typert 类型图**：generator 从 TS 类型生成类型图 artifact，loader 加载，registry 运行时注册。跨语言类型契约的基础。
- **SDK 与 ACP 平行**：ACP 是 automation-only 标准（外部 trusted 客户端）；SDK 是 dsh 自有完整客户端协议（含 subagent 一等支持）。两者平行而非嵌套。
- **Hook bridge 兼容层**：执行未修改的 Claude Code/Codex hook 命令；shared execution 在 `dsh-hook-protocol`，每个 dialect bridge 只 own 自己的 payload/env/mapping。restrictive merge 保证一个 block 则整体 block。
- **contracts-ready 模式**：typecheck/lint/doc-typecheck 均要求先 `build:lib:host`——因为类型契约跨包生成（declaration merging、`SessionEventMap`）。
- **命令分发**：`ctx.commands` 注册的命令无需模型 turn 即分发。

## 7. 注意事项

- ACP 是 automation-only，不面向交互式人类用户。
- Hook 命令在 dsh 之外定义，bridge 只负责执行与映射，不修改 hook 逻辑。
- Typert 类型图是 generated artifact——`pnpm run gen-cordis-api` / `verify-cordis-api` 维护新鲜度。
- `interaction/` 的权限预设与 `tools/pre-execute` 紧耦合——审批策略变更需同步考虑工具执行管线。
