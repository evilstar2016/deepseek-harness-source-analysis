# 相关资源（Related Resources）

> 本章汇总理解、运行、扩展与对比 DeepSeek Harness 的一手与延伸资源。
> 编写时间：2026 年 8 月。Harness 处于 **开发者预览期（Developer Preview）**，链接与版本可能随时变动，访问请以官网为准。

## 1. 官方一手资源

| 资源 | 链接 / 说明 |
|---|---|
| GitHub 仓库（MIT，monorepo） | https://github.com/deepseek-ai/deepseek-harness |
| 架构文档（中英双语） | `docs/architecture.zh.md` · [`docs/architecture.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md) |
| 开发指南 | `docs/development.md`（改动 `packages/` 前必读） |
| Web UI 指南 | `docs/user/guide/index.md` |
| 文档站点（VitePress） | 仓库 `website/` 目录构建，本地 `pnpm run website:build` |
| 一键运行（npm） | `npx @deepseek-ai/dsh web`（默认 `http://127.0.0.1:3080`） |
| 底层框架 Cordis | https://github.com/cordiverse/cordis |
| Cordis 设计论文 | [_A Programming Paradigm for Spatiotemporal Composability_](https://github.com/cordiverse/paper) |
| 许可证 | [MIT](https://github.com/deepseek-ai/deepseek-harness/blob/master/LICENSE)；第三方依赖见 `THIRD_PARTY_NOTICES.md` |

> 关键事实（来自官方 README）：`dsh` 由 DeepSeek AI 开发，基于 Cordis 的「一切皆插件」架构；开发者预览阶段 **会出现破坏兼容性的变更**；CLI 与本地 Web UI 双形态；提供中英双语架构文档。发布时间为 2026-08-13（MIT，发布当天开源）。

## 2. 社区与支持

- **GitHub Discussions**：https://github.com/deepseek-ai/deepseek-harness/discussions （反馈 / bug 报告首选）
- **插件可发现性**：为你的插件仓库添加 [`dsh-plugin`](https://github.com/topics/dsh-plugin) 话题
- **官方企微群 / 微信公众号**：见官方仓库 README 底部二维码（小助手、入群问卷、公众号）

## 3. 橙皮书系列 & 同类框架横向对比

本解析是「读源码」视角，下面这些资料是互补的「上手实测 / 同类框架」视角：

- **花叔《DeepSeek Harness：从开机到拆开》**（橙皮书，非代码视角的上手实测）
  https://github.com/alchaincyf/deepseek-harness-orange-book
- **花叔《OpenAI Codex 从入门到精通》**（橙皮书，中英双版）
  https://github.com/alchaincyf/codex-orange-book
- **同类 AI Agent 框架**（用于架构/能力对比）
  - Claude Code（Anthropic）：https://docs.claude.com/en/docs/claude-code/overview
  - OpenAI Codex：https://developers.openai.com/codex/
  - Trae Agent（字节跳动）：https://github.com/bytedance/trae-agent
  - OpenClaw（「养一只你自己的 AI」，见橙皮书系列 / [huasheng.ai](https://www.huasheng.ai/)）
- **本系列其他源码拆解**：`awesome-ai-projects-analysis`（Dify / Langfuse / RAGFlow / dify-1.14.2 等）

## 4. 本分析的方法与工具链

本章的解析并非「读文档转译」，而是「贴着代码跑」：

- **AST 符号验证**：正文中大量「`X 类 L424-757`」「`SessionEventMap 接口 L235-332`」这类行号引用，由 AST 符号工具对源码符号验证生成，不是凭记忆手测（见各章首注）。
- **图表**：架构/时序/ER 图以 [PlantUML](https://plantuml.com/) 源（`.puml`）编写，再渲染为 PNG 随文档内联。
- **文档流水线**：Markdown → [Pandoc](https://pandoc.org/)（`--embed-resources` 图片内联）→ [Google Chrome](https://www.google.com/chrome/) 无头 `--print-to-pdf` 生成单文件离线 PDF/HTML。
- **数据源**：本地克隆的 `deepseek-ai/deepseek-harness` 源码（commit 级快照）。复现请以你本机的 `git log` 与运行输出为准。

## 5. 延伸阅读 / 第三方解读

- 社区 wiki / 博客（如 [`deepseek-harness-book`](https://github.com/kuangre123/deepseek-harness-book/wiki) 等第三方梳理）
- [Awesome-AITools](https://github.com/ikaijua/Awesome-AITools) 等工具清单中的 Harness 条目
- 官方 `.agents/`（Agent 工作流 + Agent Notes）、`docs/postmortem/`（事故复盘）是理解「它踩过哪些坑」的一手材料

## 6. 版本与时效说明

- 当前为 **开发者预览**：版本号形如 `0.1.0-rc.x`，**不承诺兼容性**，会话格式版本固定为 `0`、SQLite `SCHEMA_VERSION` 单调但无兼容承诺。
- 本文档基于某一 commit 快照编写；仓库迭代极快（官方描述「快速迭代」），复现任何命令或数字时，请以你本机输出为准，并在引用处标注取数时间。
- 如要跟进最新，直接 `git clone` 后 `pnpm dsh web` 跑起来，比看任何二手资料都准。

---

> 下一站：回到 [README](../README.md) 查看完整目录与定位；或直接打开合并版 PDF / HTML（仓库根 `combined/`）。
