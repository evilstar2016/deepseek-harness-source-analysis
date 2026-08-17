# core/tools — 工具注册表与执行管线

## 模块概述

`core/tools` 提供作用域工具注册表与受保护的执行管线。它管理工具定义注册、schema 装配、三阶段调度（pre/concurrent execute/post）、barrier 与有界滚动池并发控制、工具结果融合。`ctx.tools` 是其 ctx key。所有面向模型的能力（shell、fs、web、skill 等）都作为 Consumer 工具注册到本模块。

## 主要功能

1. **工具注册**：`register()` 注册 `ToolDefinition`，其 schema 加入 prompt 装配。
2. **分层管理**：`ToolLayer` 管理分层工具，支持 collapse/restrict。
3. **三阶段执行管线**：pre-execute（waterfall 策略/审批）→ concurrent execute → post-execute（waterfall）。
4. **并发控制**：barrier 与有界滚动池（`maxParallelSubCalls`）控制并发度。
5. **执行模式**：`executionMode` / `modeFor` 分类工具调用（同步/异步/延迟）。
6. **结果融合**：`fuseToolSignals` 融合多工具信号。
7. **取消与守卫**：`callerCancelled` / `cancellationResult` / `guard` / `guardReason`。
8. **Code Mode**：`createRunCodeTool`（`code-mode.ts` L293-672）代码执行工具。
9. **SDK 类型生成**：`renderToolsSdk` / `renderToolsSdkPy` 生成 TS/Python SDK schema。

## 目录结构

```
packages/core/tools/src/
├─ index.ts          # ToolRuntime 类 (L786-1862), ToolLayer (L713-753), ToolDefinition (L221-287)
├─ schema.ts         # defineTool (L544-616), DefineToolOptions (L482-535)
├─ code-mode.ts      # createRunCodeTool (L293-672)
├─ presentation.ts   # ToolCallKind, ToolCallView, ToolResultView
├─ ts-types.ts       # renderToolsSdk, ToolSdkSchema
├─ py-types.ts       # renderToolsSdkPy
├─ testing.ts        # 测试工具
└─ invariant.ts      # ToolStage
```

## 核心流程

- [工具执行管线时序图](./01-tool-execution-sequence.puml) — 三阶段调度流程

![工具执行管线时序图](images/01-tool-execution-sequence.png)

> ℹ️ 后处理步骤会在上方链接后自动插入 PNG 图片嵌入。

## 核心符号

| 符号 | 类型 | 位置 | 说明 |
|---|---|---|---|
| `ToolRuntime` | Class | `index.ts` L786-1862 | 工具运行时核心 |
| `ToolRuntime/register` | Method | L1036-1061 | 工具注册 |
| `ToolRuntime/restrict` | Method | L1070-1097 | 工具限制 |
| `ToolRuntime/guard` | Method | L1109-1115 | 守卫 |
| `ToolRuntime/view` | Method | L1151-1192 | 视图 |
| `ToolRuntime/schemas` | Method | L1233-1235 | schema 列表 |
| `ToolRuntime/schemaOf` | Method | L1255-1266 | 单工具 schema |
| `ToolRuntime/executionMode` | Method | L1275-1284 | 执行模式分类 |
| `ToolRuntime/createExecution` | Method | L1363-1450 | 创建执行 |
| `ToolRuntime/prepareExecution` | Method | L1462-1506 | 准备执行 |
| `ToolRuntime/dispatchToolBody` | Method | L1531-1559 | 派发工具体 |
| `ToolRuntime/dispatchScheduledExecution` | Method | L1568-1598 | 派发调度执行 |
| `ToolRuntime/postExecute` | Method | L1741-1780 | 后执行 |
| `ToolRuntime/serviceAsk` | Method | L1688-1728 | 服务询问（ask-user） |
| `ToolRuntime/notifyResult` | Method | L1656-1675 | 通知结果 |
| `ToolRuntime/callerCancelled` | Method | L1509-1514 | 调用方取消 |
| `ToolDefinition` | Interface | L221-287 | 工具定义 schema |
| `ToolLayer` | Class | L713-753 | 分层工具管理 |
| `ToolExecutionInput` | Interface | L313-337 | 执行输入 |
| `ToolResult` | Interface | L290-301 | 工具结果 |
| `ToolExecutionMode` | Variable | L343-345 | 执行模式 |
| `defineTool` | Function | `schema.ts` L544-616 | 工具定义工厂 |
| `fuseToolSignals` | Function | L1888-1915 | 信号融合 |
| `createRunCodeTool` | Function | `code-mode.ts` L293-672 | Code Mode 工具 |

## 执行管线三阶段

| 阶段 | 方法 | 事件 | 说明 |
|---|---|---|---|
| **Pre-execute** | `prepareExecution` (L1462) | `tools/pre-execute` (waterfall) | 策略注入、审批、限制检查 |
| **Execute** | `dispatchToolBody` (L1531) | `tools/execute` (waterfall) | 并发执行工具体 |
| **Post-execute** | `postExecute` (L1741) | `tools/post-execute` (waterfall) | 结果后处理、信号融合 |

## 执行模式（ToolExecutionMode）

| 模式 | 说明 |
|---|---|
| 同步 | 立即执行并返回结果 |
| 异步/延迟 | 经 `dispatchScheduledExecution` 调度 |
| barrier | 需等待的前置屏障 |
| concluding | 收尾执行 |

## 技术栈

| 技术 | 用途 |
|---|---|
| TypeScript ESM | 实现 |
| Cordis | waterfall 事件（pre/execute/post） |
| 有界滚动池 | 并发控制 |

## 依赖关系

### 依赖模块
- `core/scope`（作用域注册）
- `@deepseek-ai/cordis`

### 被依赖模块
- `core/agent-loop`（工具调度）
- 所有 Consumer 工具包：`shell/`、`fs/`、`terminal/`、`web/`、`skill/`、`todo/`、`subagent/`、`jobs/` 等
- `guard/`（工具超时强制器注入 `tools/execute`）
- `interaction/`（审批策略注入 `tools/pre-execute`）

## 相关文档

- [工具执行管线子功能分析](./tool-execution-pipeline/00-overview.md)
- [系统架构 - 能力接缝](../../02-architecture/system-architecture.md#43-能力接缝数据流)
