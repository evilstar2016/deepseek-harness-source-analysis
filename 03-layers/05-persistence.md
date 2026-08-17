# L6 持久化与检索层

> 参照 [系统组件架构图](../02-architecture/system-component-architecture.puml)。详细数据模型见 [数据架构文档](../05-data-architecture/data-architecture.md)。

## 1. 层职责

提供会话日志的持久化、检索、投影，以及非会话存储（设置、凭据、附件、spill）。采用事件溯源 + 双后端（JSONL/SQLite）设计，pre-release 阶段无兼容性承诺。

## 2. 主要组件

| 组件 | 路径 | 职责 |
|---|---|---|
| 会话持久化 | `session/` | JSONL/SQLite 后端 + 投影 seam + 日志回溯标题 + 会话报告 |
| 会话检索 | `session-query/` | 逻辑语料、有界读、lineage、事件关系、语义过滤、SQLite FTS |
| 非会话存储 | `storage/` | 存储 hub + 后端 + domain form |
| 附件 | `attachment/` | 持久附件身份 + 内容寻址存储（sha256） |
| Spill | `spill/` | 存储接缝 + 本地实现 + 工具结果溢出策略 |
| 设置 | `settings/` | 用户设置 seam + 文件 provider |
| 凭据 | `credentials/` | 凭据引用 seam + env-over-`.env` provider |
| Workspace | `workspace/` | Workspace 实体 |

## 3. 对外接口

| 接口 | 说明 |
|---|---|
| `PersistenceBackend` | JSONL/SQLite 共同实现的持久化接口（`coordinator.ts` L127） |
| `SessionCorpus` | FTS5 检索语料（`corpus.ts` L32） |
| `SessionProjectionCache` | 投影缓存（fail-soft，`index.ts` L71） |
| 凭据解析 | 进程环境 > `.credentials.yaml`(0600) > cwd/.env > DSH_HOME/.env |

## 4. 与其他层的交互

- **上层依赖**：L4（`ctx.sessions` 追加事件 → 持久化）。
- **下层调用**：外部存储介质（SQLite 文件、JSONL 文件、本地 FS）。
- **横向**：session-query 从持久化日志派生 FTS 索引；attachment 为工具结果提供内容寻址存储。

## 5. 关键代码路径

```
packages/session/                     # 持久化后端（JSONL/SQLite）
packages/session-query/src/           # FTS 检索
packages/storage/src/
packages/attachment/src/store.ts      # 内容寻址存储（sha256）
packages/spill/src/
packages/settings/src/
packages/credentials/src/
```

## 6. 技术实现

- **事件溯源**：会话状态是 `SessionEvent` 日志的派生物；持久化即追加事件到 JSONL/SQLite。
- **双后端等价语义**：JSONL 与 SQLite 实现同一 `PersistenceBackend` 接口，崩溃撕裂尾修复语义一致。
- **写透发布**：POSIX 用 `link()` + 目录 fsync；Windows 用 `MoveFileExW(MOVEFILE_WRITE_THROUGH)`（koffi）。
- **版本管理**：`SCHEMA_VERSION`（SQLite 表布局）、`SESSION_QUERY_SQLITE_SCHEMA_VERSION`（FTS）、`SESSION_FORMAT_VERSION`（事件词汇表）三版本正交，不匹配即拒绝/丢弃重建。
- **内容寻址附件**：附件 ID = `sha256:hex`，路径 `objects/<前2位>/<sha256>`，`link()` dedup。
- **凭据分层信任**：进程环境（不可写，胜出）> `.credentials.yaml` > cwd/.env > DSH_HOME/.env；`CredentialRef → string` 严格映射。

## 7. 注意事项

- Pre-release 无迁移：版本不匹配即丢弃重建，只有 pristine 或当前自有版本可打开。
- 投影缓存是 fail-soft 的——失败仅 warning，下次冷读从全日志重放自愈。
- 凭据永不入配置/日志/session event——`apiKeyEnv` 是 `CredentialRef`（branded 环境变量名）。
