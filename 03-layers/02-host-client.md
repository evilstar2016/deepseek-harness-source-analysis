# L3 Host / Client 双半层

> 参照 [系统组件架构图](../02-architecture/system-component-architecture.puml)。

## 1. 层职责

Web-GUI 拆为 host（Node 服务端）与 client（浏览器侧）两半，各自独立打包。Host 提供 API 网关与 HTTP 路由；Client 提供浏览器 shell、wire 协议、object services 与大量 `ui-*` 插件。双半通过 tsdown 的 host/client 双 face 构建匹配。

## 2. 主要组件

### 2.1 host/（服务端半）
- **路径**：`packages/host/`
- **子包**（8 个）：
  - `apiproxy`：API 代理。
  - `webserver`：HTTP 路由服务器。
  - `frontend-static`：静态前端资源服务。
  - `plugin-inventory`：插件清单管理。
  - `directory-picker` / `directory-picker-auto` / `directory-picker-browse` / `directory-picker-native`：目录选择器（多实现）。

### 2.2 client/（浏览器半）
- **路径**：`packages/client/`
- **子包**（约 30 个）：
  - **核心运行时**：`connection`（连接管理）、`runtime`（浏览器运行时）、`hmr`（热替换）、`locale`（国际化）、`web`、`web-react`。
  - **基础设施**：`modules`、`schema-form`、`ui-slots`、`ui-primitives`、`ui-layout`、`ui-sidebar`、`ui-theme`。
  - **会话交互**：`ui-conversation`（对话）、`ui-input-trigger`、`ui-message-feedback`、`ui-trajectory`、`ui-user-questions`。
  - **功能面板**：`ui-tool`、`ui-plan`、`ui-goal`、`ui-jobs`、`ui-skill`、`ui-subagent`、`ui-workflow-run`、`ui-deliverables`。
  - **设置**：`ui-settings`、`ui-settings-general`、`ui-settings-models`、`ui-settings-plugins`、`ui-settings-plugin-inventory`、`ui-permission-presets`、`ui-model-selection`、`ui-agent-preset`。
  - **其他**：`ui-attachment`、`ui-commands`、`ui-workspace`、`ui-directory-picker-browse`、`ui-directory-picker-native`。

## 3. 对外接口

| 接口 | 说明 |
|---|---|
| HTTP 路由（host/webserver） | Web UI 与 API 的 HTTP 端点 |
| API 代理（host/apiproxy） | 代理前端请求到后端服务 |
| ConversationNodeDefinition（client） | 注册 Web Client Chat 节点 + keyed renderer |
| `ui-*` 插件槽（client） | 浏览器侧可扩展 UI 插件接口 |

## 4. 与其他层的交互

- **上层依赖**：L1（CLI/Web 启动入口）+ L2（Boot 组合引入 web-app bundle）。
- **下层调用**：
  - host → L7（api/gateway、typert）：API 网关经 Typert RPC。
  - host → L4（core/session）：读取会话事件渲染。
  - client → L7（sdk）：浏览器侧经 JSON-RPC SDK 通信。
  - client → L4（ctx.agents）：驱动 agent 并从 `session/event` 渲染。

## 5. 关键代码路径

```
packages/host/apiproxy/src/
packages/host/webserver/src/
packages/host/frontend-static/src/
packages/client/connection/src/
packages/client/runtime/src/
packages/client/ui-conversation/src/
packages/client/ui-settings/src/
packages/client/web-react/
packages/client/tsdown.client.ts    # client face 构建配置
```

## 6. 技术实现

- **双 face 构建**：`tsdown --env.DSH_BUILD_FACE host` 与 `client` 分别打包，匹配 Host/Client 双半。
- **Vite 前端**：`apps/web` 用 Vite 构建，`vite-tsconfig-paths` 解析路径。
- **HMR**：`client/hmr` 支持开发时热替换。
- **扩展点**：新增 Web Client Chat 节点 = 注册 `ConversationNodeDefinition` + keyed renderer。

## 7. 注意事项

- Host 与 Client 分属不同 tsconfig（`tsconfig.host.json` / `tsconfig.client.json`），构建顺序为先 host 后 client（host 的类型契约需先就绪）。
- `contracts-ready` 模式：typecheck/lint/doc-typecheck 均要求先 `build:lib:host` 再跑 client gate，因为类型契约跨包生成（declaration merging、`SessionEventMap`）。
