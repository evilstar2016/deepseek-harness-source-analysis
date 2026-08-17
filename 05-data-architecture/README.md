# 05 - 数据架构

本目录包含 DeepSeek Harness（`dsh`）项目的数据架构分析文档，基于 AST 符号工具对源码符号验证生成。

## 文件清单

| 文件 | 内容 |
|---|---|
| [data-architecture.md](./data-architecture.md) | 完整数据架构文档（中文，13 章） |
| [data-architecture.puml](./data-architecture.puml) | 数据架构组件图（PlantUML） |
| [data-model-er.puml](./data-model-er.puml) | 数据模型 ER 图（PlantUML） |
| [data-flow.puml](./data-flow.puml) | 数据流程图（PlantUML，含 5 个流程） |

## 文档结构

`data-architecture.md` 包含 13 章：

1. **概述** — 设计理念（事件溯源 + 双后端 + 无兼容承诺）与数据层次
2. **主数据库设计** — SQLite 连接管理、SCHEMA_VERSION、核心 3 表、事务边界、撕裂尾修复
3. **JSONL 会话日志设计** — 文件布局、格式、写透发布（POSIX/Windows）、追加写与回滚、增量扫描
4. **核心数据模型** — SessionEventMap 13 个事件类型、SessionHeader、SessionEvent 信封、Session/SessionStore 类
5. **数据关系图说明** — ER 图关系总览
6. **数据流** — 事件追加→派生→持久化→检索、fork、resume、FTS 索引同步
7. **辅助存储** — attachment 内容寻址、storage hub、spill、settings、credentials、投影缓存
8. **数据一致性保证** — 事件溯源不变式、双后端一致语义、协调器不变式
9. **性能优化** — 写后批合并、chunk 打包、Zstd、seek 读、FTS5、投影缓存等
10. **数据迁移与版本管理** — 双版本体系、无迁移策略、升级路径
11. **安全性设计** — 凭据引用、进程限制、跨进程安全
12. **数据架构组件图** — 组件分层引用
13. **关键发现总结** — 10 条核心发现

## 关键发现

1. **事件溯源是核心**：会话状态是 `SessionEvent` 追加只写日志的派生物
2. **双后端等价语义**：JSONL 与 SQLite 实现同一 `PersistenceBackend` 接口，崩溃修复语义一致
3. **Pre-release 无迁移**：所有 schema 版本不匹配即拒绝，派生索引丢弃重建
4. **写透发布平台分化**：POSIX 用 `link()` + 目录 fsync；Windows 用 `MoveFileExW(MOVEFILE_WRITE_THROUGH)`
5. **模型可见即已记录**：`Session.append` 用 `isJsonValue` 在源头拒绝非可序列化数据
6. **内容寻址附件**：附件 ID 即 sha256，读取时 digest 校验
7. **投影缓存 fail-soft**：派生状态检查点失败仅 warning，下次冷读自愈
8. **凭据分层信任**：进程环境 > 托管 `.credentials.yaml` > `.env`
9. **FTS5 派生索引可弃**：版本不匹配即 `resetDerivedSchema` 重建
10. **双版本体系**：`SESSION_FORMAT_VERSION`（事件词汇表）与 `SCHEMA_VERSION`（表布局）正交

## 关键代码位置

| 模块 | 路径 | 关键符号 |
|---|---|---|
| 核心数据模型 | `packages/core/session/src/types.ts` | `SessionEventMap` (L235-332)、`SessionHeader` (L60-98)、`SessionEvent` (L403-435) |
| 会话运行时 | `packages/core/session/src/index.ts` | `Session` (L424-757)、`SessionStore` (L791-1154)、`append` (L603-654)、`fork` (L1080-1094) |
| SQLite 后端 | `packages/session/session-persistence-sqlite/src/schema.ts` | `SCHEMA_VERSION=15` (L20)、3 表 DDL (L116-147)、`scanRows` (L232-270) |
| SQLite 后端 | `packages/session/session-persistence-sqlite/src/index.ts` | `appendBatch` (L284)、`commitRepair` (L309)、`loadStoredFrom` (L225) |
| JSONL 后端 | `packages/session/session-persistence-jsonl/src/format.ts` | `SessionLogScanner` (L272)、`scanLog` (L388)、`encodeSegment` (L121) |
| JSONL 后端 | `packages/session/session-persistence-jsonl/src/index.ts` | `appendBatch` (L421)、`materialize` (L513)、`appendLines` (L650) |
| Windows 写透 | `packages/session/session-persistence-jsonl/src/win32.ts` | `publishNewFileWin32` (L116)、`ensureDurableDirectoryWin32` (L130) |
| 持久化协调 | `packages/session/session-persistence/src/coordinator.ts` | `PersistenceBackend` 接口 (L127)、`sessionFormatVersionRefusal` (L77) |
| 写后批合并 | `packages/session/session-persistence/src/write-behind.ts` | `SessionWriteBehind` (L22) |
| 检索派生 schema | `packages/session-query/session-query-sqlite/src/schema.ts` | `SESSION_QUERY_SQLITE_SCHEMA_VERSION=8` (L8)、FTS5 表 (L126-168) |
| 检索引擎 | `packages/session-query/session-query-sqlite/src/index.ts` | `SqliteSessionQueryEngine` (L196) |
| 逻辑语料 | `packages/session-query/session-query/src/corpus.ts` | `SessionCorpus` (L32) |
| 附件存储 | `packages/attachment/attachment-local/src/store.ts` | `saveImageFile` (L136)、`readImageFile` (L204) |
| 存储 Hub | `packages/storage/storage/src/backend.ts` | `StorageBackend` (L17)、`KvFacet` (L30)、`KvUnit` (L66) |
| Domain 规范 | `packages/storage/storage-domain/src/spec.ts` | `DomainSpec` (L35)、`defineDomain` (L79) |
| Spill 存储 | `packages/spill/spill-local/src/store.ts` | `saveTextFile` (L107)、`privateRoot` (L27) |
| 投影缓存 | `packages/session/session-projection-cache/src/index.ts` | `SessionProjectionCache` (L71) |
| 投影注册表 | `packages/session/session-projection/src/index.ts` | `ProjectionDefinition` (L42) |
| 设置文件 | `packages/settings/settings-file/src/index.ts` | `FileSettingsProvider` (L105) |
| 凭据文件 | `packages/credentials/credentials-local/src/index.ts` | 分层信任 (L1-35)、`assertOwnerOnly` (L103) |

## 渲染 PUML

```bash
# 使用 PlantUML 渲染（需 Java）
plantuml data-architecture.puml data-model-er.puml data-flow.puml

# 或使用 VS Code PlantUML 插件预览
```

## 相关文档

- [01-项目概览](../01-overview/project-overview.md)
- [02-系统架构](../02-architecture/system-architecture.md)
