**中文** | [English summary](#english-summary)

<p align="center">
  <img src="banner.svg" width="70%" alt="DeepSeek Harness 源码深度解析 封面" />
</p>

# DeepSeek Harness 源码深度解析

> v2026.08

把 DeepSeek 开源的 agent harness（`dsh`）从仓库根目录一路拆到每一行关键代码：七层架构、三大核心模块、双后端数据架构、第三方集成全景。不是「读文档转译」，而是「贴着代码跑」——正文里每一个「`X 类 L424-757`」都来自 AST 符号工具对源码的验证。

2026 年 8 月 13 日，DeepSeek 以 MIT 协议开源了 `dsh`（发布当天开源，开发者预览）。官方文档告诉你「它怎么设计」；这本书补上「**代码里它到底怎么落地**」。

## 📌 项目定位（Repo Positioning）

这是一份**工程师向的源码级深度解析**，采用橙皮书式的可读编排（章节化、图示化、带一手代码证据）。它与现有资料的关系是：

- **对照官方文档**：官方 `docs/` 是「架构应该怎么设计」；本文是「设计在代码里如何落地」——带符号验证的行号、可复现的命令、被忽略的边界条件。
- **对照花叔《从开机到拆开》**：花叔版是「不写代码的人上手实测」（会不会花我的钱、会不会动我硬盘）；本解析是「写代码 / 做二次开发的人读源码」的补充视角。**两者互补，均已收入[相关资源](07-resources/related-resources.md)。**
- **视角主张**：可验证（AST 符号工具验证）、可复现（给出命令与数据源）、可对照（每个论断都能回到源码行号）。

## 📑 这本书有什么（官方文档 / 其他资料里没有的）

全部基于本地克隆源码的 AST 解析与人工核对：

- **七层架构逐层拆解**——从 L1 应用入口 / Boot，到 L7 协议与集成，每一层给「职责 / 主要组件 / 对外接口 / 与其他层的交互 / 关键代码路径」。
- **三大核心模块深度**——`agent-loop`（默认驱动）、`session`（事件溯源日志）、`tools`（工具注册表与执行管线），含时序图与生命周期。
- **数据架构全景**——SQLite + JSONL 双后端、ER 图、事务边界、**撕裂尾修复（scanRows）**、Windows 下 MoveFileExW 写透发布。
- **第三方集成地图**——LLM、沙箱执行、协议（MCP / ACP / hooks）、框架厂商，逐项说明「能直接接入 / 要自己装 / 用不了」。
- **每个关键论断附 AST 验证的行号证据**，而非「大概在某某文件」。
- **构建与质量门禁解读**——每文件 100% 覆盖率门禁、`oxlint` / `knip` / `jscpd` / `hygiene` 综合卫生检查。

## 📖 本书结构

| 部分 | 内容 |
|------|------|
| **01 项目概览** | 基本信息 · 目录结构（49 包族）· 主要功能模块 · 核心依赖 · 构建与部署 · 环境配置 |
| **02 系统架构** | 架构模式与设计原则 · 系统分层 · 核心组件 · 数据流 · 技术选型 · 扩展性 |
| **03 分层解析** | L1–L7 七层：应用入口/Boot · Host/Client · Core API · 能力接缝 · 持久化 · 协议集成 |
| **04 核心模块** | `core/agent-loop` · `core/session` · `core/tools` 三大支柱 + 工具执行管线三阶段 |
| **05 数据架构** | SQLite 持久化后端 · JSONL 会话日志 · ER 图 · 数据流程图 · 事务与写透 |
| **06 第三方集成** | LLM 集成 · 沙箱执行 · 协议（MCP/ACP/hooks）· 框架与厂商 |
| **07 相关资源** | 官方一手资源 · 社区 · 橙皮书系列 & 同类框架对比 · 本分析工具链 · 延伸阅读 |

每章首部标注「基于 AST 符号工具验证」，可回到源码行号复核。

## 👥 适合谁读

- **想做二次开发 / 写 `dsh` 插件的工程师**——直接给到 `ctx` key、包职责与扩展点地图。
- **评估是否采用 `dsh` 的架构决策者**——能直接接入 / 要自己装 / 用不了，逐项说清。
- **想理解「一切皆插件 + Cordis」范式的开发者**——能力接缝（Service Definition / Provider / Consumer）是替换一个能力就改变整个产品的关键。
- **已经读过花叔上手实测、想再往下看代码的人**——本书是那本书的「源码下册」。

## 🔬 方法论与时效

- **AST 符号验证**：正文行号引用由符号工具对源码验证生成，非手测。
- **数据源**：本地克隆的 `deepseek-ai/deepseek-harness` 源码（commit 级快照）。
- **时效**：Harness 处于**开发者预览期**，`0.1.0-rc.x`，**破坏性变更频繁**；本文档基于某一 commit 编写，复现任何命令或数字请以你本机输出为准，引用处已尽量标注取数时间。

## 🔗 相关资源（速览）

完整清单见 [07 相关资源](07-resources/related-resources.md)：

- 官方仓库：https://github.com/deepseek-ai/deepseek-harness  ·  底层框架 Cordis：https://github.com/cordiverse/cordis
- 橙皮书《从开机到拆开》：https://github.com/alchaincyf/deepseek-harness-orange-book
- 同类框架对比：Claude Code · OpenAI Codex · Trae Agent · OpenClaw

## 📥 下载（合并版）

| 格式 | 文件 | 说明 |
|------|------|------|
| PDF | [`combined/deepseek-harness-source-analysis.pdf`](combined/deepseek-harness-source-analysis.pdf) | 离线阅读，图片已内联 |
| HTML（单文件） | [`combined/deepseek-harness-source-analysis.html`](combined/deepseek-harness-source-analysis.html) | 浏览器直接打开，图片已 base64 内联 |

> 💡 PDF 建议下载后阅读，GitHub 在线预览可能无法完整渲染。

## ⚖️ 协议与免责声明

- 本仓库为**独立的技术分析 / 评论**，与 DeepSeek AI 无隶属或背书关系。
- DeepSeek Harness 本身以 **MIT** 协议开源；本文中的架构图、时序图与文字解析可依据 **CC BY-NC-SA 4.0** 分享与演绎（非商用，保留署名）。
- 所有代码引用均指向[上游 MIT 仓库](https://github.com/deepseek-ai/deepseek-harness)，版权归原作者所有。
- 封面色块（banner.svg）为本仓库原创，可随文档一同使用。

## English summary

**DeepSeek Harness Source-Code Deep Dive** (Chinese, orange-book style, v2026.08) — a code-level teardown of DeepSeek's open-source agent harness `dsh` (MIT, developer preview, released 2026-08-13). Unlike the official docs (which describe the design) or the hands-on orange book (which targets non-coders), this analysis is for engineers: seven-layer architecture (L1–L7), the three core modules (`agent-loop` / `session` / `tools`), dual-backend data architecture (SQLite + JSONL, with ER diagrams), and a third-party integration map. Every key claim carries AST-verified source line numbers. Complements (not competes with) the official docs and the community orange book. Chinese only for now.

## 协议

<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">
  <img alt="CC BY-NC-SA 4.0" src="https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png" />
</a>

本作品基于[CC BY-NC-SA 4.0](http://creativecommons.org/licenses/by-nc-sa/4.0/)协议发布。在保留署名的前提下，可自由分享和改编（非商用）。
