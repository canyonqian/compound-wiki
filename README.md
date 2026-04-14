# 🧠 Compound Wiki

<p align="center">
  <strong>AI 驱动的通用复利记忆系统 — 让知识越积累越值钱</strong>
</p>

<p align="center">
  <a href="./README.md">🇨🇳 中文</a> ·
  <a href="./README.en.md">English</a> &nbsp;&nbsp;
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="#快速开始"><img src="https://img.shields.io/badge/状态-可用-green" alt="Status"></a>
  <a href="https://github.com/"><img src="https://img.shields.io/badge/PRs-Welcome-blue" alt="PRs Welcome"></a>
</p>

---

## ✨ 这是什么？

**Compound Wiki（复利维基）** 是一套 **开源的、通用的 AI Agent 记忆与知识管理方案**。灵感来自 Andrej Karpathy 的 [LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 思想，结合了 OpenClaw 三层记忆系统的最佳实践。

> **一句话概括**: 你只管往里塞资料，AI 负责整理成结构化 Wiki，知识自动关联、持续演化，**越用越聪明**。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🔁 **复利增长** | 每次操作不仅新增内容，还自动增强 10-15 个关联页面 |
| 🤖 **AI 全托管** | 人只负责投喂资料，Wiki 由 AI 自动维护和更新 |
| 🔗 **知识网络** | 双链机制强制 AI 思考知识点之间的关联 |
| 📝 **纯 Markdown** | 无需数据库、无需专用软件、十年后依然可读 |
| 🔍 **LINT 审计** | 内置健康检查机制，防止错误在循环中被放大 |
| 🔌 **Agent 通用** | MCP 插件零配置接入 Claude/Cursor/Copilot/OpenClaw 等 |
| 📦 **pip 安装** | `pip install compound-wiki` 一行命令全局注册 |
| 🔑 **零配置 API** | 不需要单独配 Key，用 Host Agent 的 LLM 能力 |

---

## 📐 架构设计

```
compound-wiki/
├── pyproject.toml           ⭐ Python 包配置（pip install 入口）
├── requirements.txt         依赖清单（备用）
│
├── compound_wiki/           ⭐ CLI 命令入口
│   ├── __init__.py
│   └── cli.py               统一命令行接口
│
├── memory_core/             🧠 Memory Core v2.0 核心
│   ├── config.py / hook_engine.py / extractor.py
│   ├── deduplicator.py / shared_wiki.py / agent_sdk.py
│   ├── memory_graph.py / mcp_server.py
│   └── examples/
│
├── schema/                  ⚙️ 规则层
│   ├── CLAUDE.md            ⭐ AI 行为规范手册
│   └── templates/
│
├── raw/                     📥 原始资料
├── wiki/                    📝 知识库（AI 维护）
├── outputs/                 📤 产出层
├── auto/                    ⚡ 自动化引擎
├── plugins/                 🧩 插件系统
├── scripts/cw_tool.py       🔧 辅助工具
├── examples/                📚 示例
├── README.md / README.en.md
└── LICENSE                  MIT

### 权责边界

```
┌─────────────────────────────────────────────┐
│              你 (人类)                       │
│                                             │
│  ✅ 往 raw/ 扔资料                           │
│  ✅ 定义 schema/CLAUDE.md 规则               │
│  ✅ 定义 schema/PERSPECTIVE.md 视角          │
│  ✅ 读 wiki/ 中的内容                        │
│  ✅ 定期审查 LINT 报告                       │
│                                             │
│  ❌ 不编辑 wiki/ 中的内容                    │
│  ❌ 不修改 schema/CLAUDE.md 中的核心规则     │
│                                             │
├─────────────────────────────────────────────┤
│              AI (Agent)                     │
│                                             │
│  ✅ 读取 raw/ 中的原始资料                   │
│  ✅ 创建/更新 wiki/ 中的所有页面             │
│  ✅ 建立 [[双链]] 关联                       │
│  ✅ 维护 index.md 和 changelog.md           │
│  ✅ 执行 LINT 健康审计                      │
│  ✅ 基于 Wiki 回答问题                       │
│                                             │
│  ❌ 不修改 raw/ 中的任何文件                 │
│  ❌ 不修改 schema/ 中的规则文件              │
│                                             │
└─────────────────────────────────────────────┘
```

### 🤖 自动化引擎（Auto Engine）

> **v1.1 新增！** Compound Wiki 现在具备完整的自动化能力，可以**后台持续运行**。

```
compound-wiki/
│
├── auto/                     ⚡ 自动化引擎（NEW!）
│   ├── __init__.py          ← 包初始化
│   ├── config.py            ← 配置系统（路径、API密钥、模型）
│   ├── state.py             ← 状态管理（处理历史、增量追踪）
│   ├── watcher.py           ← 文件监听器（监控 raw/ 变化）
│   ├── pipeline.py          ← 摄取管道（调用 LLM 处理资料）
│   ├── collector.py         ← 网页采集器（URL → raw/）
│   ├── scheduler.py         ← 定时调度器（Cron 任务）
│   ├── agent.py             ← 主控入口（CLI + 生命周期）
│   ├── config.json          ← 默认配置文件
│   ├── cw-auto.bat          ← Windows 一键启动
│   └── cw-auto.sh           ← Unix 一键启动
│
├── schema/CLAUDE.md          ← 新增「第八章：自动化行为规范」
│
...（其他目录不变）
```

**自动化架构总览**：

```
┌─────────┐     ┌──────────┐     ┌──────┐
│ Web URL │────▶│ Collector │────▶│ raw/ │
└─────────┘     └──────────┘     └──┬───┘
                                   │ 文件事件
              ┌────────────────────▼──────────────┐
              │           FileWatcher              │
              │   (监控 raw/，检测新/修改的文件)      │
              └────────────────────┬──────────────┘
                                   │ auto-ingest
              ┌────────────────────▼──────────────┐
              │        IngestionPipeline           │
              │  原始资料 + CLAUDE.md → LLM → Wiki  │
              └────────────────────┬──────────────┘
                                   │ 写入页面
                    ┌──────────────▼──────────────┐
                    │            wiki/              │
                    │ concept / entity / synthesis  │
                    └──────────┬──────────┬────────┘
                               │          │
               ┌───────────────▼──┐  ┌────▼─────────┐
               │  Query() Q→A    │  │  Scheduler    │
               │ + 自动归档       │  │  每日LINT     │
               └─────────────────┘  │  每周摘要      │
                                    │  月度报告      │
                                    └──────────────┘
```

**CLI 命令一览**：

```bash
# 初始化（首次使用）
cw init .

# 全自动模式（后台运行所有模块）
cw start

# 单次操作
cw ingest              # 处理 raw/ 中的原始资料
cw query "什么是X?"     # 查询知识库
cw lint                # 健康检查
cw stats               # 统计面板
cw collect <URL>       # 抓取网页入库

# 或使用旧版（兼容）
python auto/agent.py start    # 启动自动化引擎
```

**自动化能力矩阵**：

| 能力 | 手动模式 | 自动模式 | 说明 |
|------|----------|----------|------|
| **资料摄取** | 你说 "INGEST" | Watcher 自动检测 `raw/` 新文件 | 防抖3s + 批量30s窗口 |
| **网页采集** | 你提供 URL | Collector 自动抓取 | 支持RSS/书签/剪贴板 |
| **知识问答** | 你提问 | — | 回答自动归档为 synthesis |
| **健康检查** | 你说 "LINT" | 每天定时执行 | 默认每天08:00 |
| **周报摘要** | — | 每周日20:00生成 | 写入 `outputs/` |
| **月度报告** | — | 每月1日09:00生成 | 复利效应分析 |
| **状态追踪** | — | 全自动 | SHA256增量、原子写入 |

---

## 🧬 Memory Core — AI 对话自动记忆（v2.0 核心）

> **这是 Compound Wiki 最重要的创新。** 从"人喂资料 → AI整理"进化为 **"AI 对话自动产生记忆，全程无感"**。

### 它解决了什么问题？

```
❌ 传统模式：
   你跟AI聊天 → 聊完就没了 → 下次从头交代背景
   第100次对话 = 第1次的体验（AI完全不记得你）

✅ Memory Core 模式：
   你跟AI聊天 → AI后台自动提取知识 → 存入Wiki
   下次对话AI自动参考已有知识 → 回答更精准
   第100次对话 = AI比你还懂你的项目/偏好/历史决策
```

### 工作原理（3 行代码集成）

```python
from memory_core import MemoryCore

# 1. 初始化（一次）
mc = MemoryCore(wiki_path="./wiki")
await mc.initialize()

# 2. 在对话循环中加一行
result = await mc.remember(user_message, ai_response)
# ← 自动提取事实 → 去重 → 写入 Wiki → 更新图谱

# 3. 或者更简单——用装饰器（零代码侵入）
@mc.hook
async def chat(user_message: str) -> str:
    return await my_llm.generate(user_message)  # 就这！
```

### 自动提取什么？

| 类型 | 示例 | 价值 |
|------|------|------|
| ✅ **决策** | "选择了 Redis 而非 Memcached" | 记录决策脉络 |
| 🎯 **偏好** | "用户喜欢简洁注释风格" | 让 AI 越来越懂你 |
| 📌 **事实** | "项目使用 Python 3.11+" | 建立上下文基础 |
| 💡 **概念** | "CQRS 分离读写模型" | 积累技术知识库 |
| 📋 **任务** | "周五前完成认证中间件" | 追踪待办事项 |
| 🏷️ **实体** | "Team Alpha, 项目 Beta" | 构建关系网络 |

### 多 Agent 共享一个 Wiki

```
Agent A (代码审查) ──→ 提取: "应该用 async/await"
                         ↓
                    SharedWiki (并发安全)
                    ├─ 文件锁保证原子性
                    ├─ 冲突检测
                    └─ 来源追踪
                         ↓
Agent B (文档生成) ──→ 提取: "文档用 Markdown 格式"
                         
两个 Agent 同时写同一个 Wiki，零冲突、零丢失。
```

### 集成方式一览

```python
# 方式 A: 装饰器（推荐）
@mc.hook
async def chat(msg): return await llm.chat(msg)

# 方式 B: 手动 Hook
result = await mc.remember(user_msg, ai_response)

# 方式 C: MCP Server（Claude/Cursor/VS Code）
# 在 MCP 配置中加入 compound-wiki server

# 方式 D: HTTP API
POST http://localhost:9877/memory/hook
{"user_message": "...", "assistant_response": "..."}
```

### 完整文件结构

```
memory_core/
├── __init__.py           # 包导出 + 文档字符串
├── config.py             # 配置系统（提取规则/去重参数/并发设置）
├── hook_engine.py        # ⭐ Hook 引擎（事件驱动，对话自动触发）
├── extractor.py          # ⭐ LLM 提取器（6种事实类型，智能触发）
├── deduplicator.py       # ⭐ 去重引擎（相似度检测+合并+冲突标记）
├── shared_wiki.py        # ⭐ 并发安全 Wiki（文件锁+原子写入）
├── agent_sdk.py          # ⭐ Agent SDK（装饰器/MCP/HTTP多模式适配）
├── memory_graph.py       # 知识图谱构建器（节点+边+Mermaid/D3导出）
├── mcp_server.py         # MCP 协议服务端（6个工具）
└── examples/
    └── quick_start.py    # 5分钟上手示例（4种集成方式演示）
```

详细架构说明见 [schema/CLAUDE.md 第十章](./schema/CLAUDE.md)。

---

## 🚀 快速开始

> ⚡ **零配置接入任何 AI Agent，无需单独配 API Key！**

### 🎯 方式一：MCP 插件（推荐 — 适用于所有主流 Agent）

```bash
# 1. 安装
pip install 'compound-wiki[mcp]'

# 2. 在你的 AI 工具中添加 MCP Server（见 [INSTALL.md](./INSTALL.md)）
#    支持: Claude Desktop · Claude Code · Cursor · Copilot · Windsurf · OpenClaw

# 3. 完成！在对话中直接使用：
#    "帮我记住这篇文章的内容" → Agent 自动调用 cw_ingest
#    "我之前学过什么关于 X 的？" → Agent 自动调用 cw_query
```

**为什么不需要 API Key？**  
Compound Wiki 使用 **Agent-Native 模式**：插件只负责存储和编排，调用它的 AI Agent 用自己的大脑做知识提取。零额外成本。

### 📦 方式二：CLI 命令行（独立使用）

```bash
# 1. 一行安装（自动注册 cw 命令）
pip install compound-wiki

# 2. 初始化你的知识库
cw init my-knowledge-base

# 3. 进入项目目录
cd my-knowledge-base

# 4. （可选）编辑你的视角偏好
cp schema/PERSPECTIVE.example.md schema/PERSPECTIVE.md
# 然后用你喜欢的编辑器打开编辑

# 5. 把资料扔进 raw/

# 6. 开始使用！
cw ingest          # 处理资料 → AI 编译 Wiki
cw stats           # 查看知识库统计
cw lint            # Wiki 健康检查
cw query "什么是X?" # 基于知识库提问
```

**前置条件**：Python 3.8+（[下载](https://www.python.org/downloads/)）

**可选依赖**（按需安装）：
```bash
pip install 'compound-wiki[auto]'      # 自动化引擎（文件监听 + 定时任务）
pip install 'compound-wiki[anthropic]' # Anthropic Claude 模型支持
pip install 'compound-wiki[openai]'    # OpenAI GPT 模型支持
pip install 'compound-wiki[all]'       # 全部功能
```

### 🛠️ 方式三：从源码安装（开发者）

```bash
# 1. Clone 本项目
git clone https://github.com/canyonqian/compound-wiki.git
cd compound-wiki

# 2. 以可编辑模式安装（开发时修改代码即时生效）
pip install -e .

# 或者只安装核心依赖，不注册命令：
pip install -r requirements.txt

# 3. 初始化知识库
cw init .

# 后续步骤同上...
```

---

## 💬 与 AI 交互的核心指令

### INGEST：让 AI 处理原始资料

> 将以下指令发给你的 AI Agent：

```
请读取 raw/ 目录中的所有新文件。
按照 schema/CLAUDE.md 中的规则：
1. 提取核心概念 → 创建 wiki/concept/ 下的概念页
2. 提取涉及实体 → 创建 wiki/entity/ 下的实体页
3. 建立页面间的 [[双链]] 关联
4. 更新 wiki/index.md 索引
5. 在 wiki/changelog.md 中记录本次操作
每个页面必须包含完整的 frontmatter 元数据。
使用 schema/templates/ 中的模板作为格式参考。
```

### QUERY：基于知识库提问

```
请基于 wiki/ 中的内容回答以下问题：
[你的问题]

要求：
- 引用具体的 Wiki 页面作为来源
- 追踪 [[双链]] 获取关联信息
- 如果信息不足，指出缺失的部分
```

### LINT：执行健康审计

```
请对整个 wiki/ 目录执行 LINT 检查：
1. 检查是否存在矛盾的信息
2. 查找孤立无链接的页面
3. 发现缺少来源引用的结论
4. 列出被引用但尚未创建的页面
5. 给出改进建议并输出报告
```

### SYNTHESIS：创建综合分析

```
请基于 wiki/ 中关于 [主题A] 和 [主题B] 的内容，
创建一个对比分析页面到 wiki/synthesis/ 目录。
使用综合页模板格式，给出明确的结论和建议。
```

---

## 🔄 复利引擎工作原理

### 为什么叫"复利"?

传统知识管理是**线性的**——你存多少就是多少。

Compound Wiki 是**指数的**——每次操作都会产生连锁增值：

```
第1轮: 导入资料A
  → 新建页面 A
  → +1 个页面

第2轮: 导入资料B  
  → 新建页面 B
  → 更新页面 A（建立 A↔B 关联）
  → +2 个操作（1新建 + 1更新）

第3轮: 问答查询X
  → 生成答案
  → 可归档为新的综述页 S
  → 同时更新 A、B、S 之间的引用链
  → +N 个操作

第4轮: LINT审计
  → 发现矛盾并修正
  → 整体质量提升
  → 所有后续查询受益
```

### 单次操作的增值效应

| 操作类型 | 直接产出 | 间接增值 |
|---------|---------|---------|
| 导入1篇资料 | 1个新Wiki页面 | 自动更新10~15个关联页面 |
| 1次查询问答 | 得到答案 | 可沉淀为综述/对比页面 |
| 1次LINT检查 | 修复问题 | 整体知识库准确性提升 |
| 时间推移 | - | 知识网络密度持续增加 |

---

## 🧩 插件系统（Plugin System）

### 不只是脚本 — 真正的插件架构

Compound Wiki v1.2 引入了完整的 **插件化架构**，支持多种数据摄取方式，**不再局限于手动往 raw/ 扔文件**。

```
┌──────────────────────────────────────────────────────┐
│                   数据输入层                          │
│                                                      │
│  🌐 浏览器按钮    📋 复制文本     📧 邮件Newsletter   │
│     │              │               │                 │
│  🤖 Telegram      💬 Discord      📡 RSS订阅         │
│     │              │               │                 │
│  🔌 REST API      🪝 Webhook     📁 拖拽文件         │
│     │              │               │                 │
└─────┼──────────────┼───────────────┼─────────────────┘
      └──────────────┼───────────────┘
                     ▼
           ┌──────────────────┐
           │  SourceRegistry  │  统一数据源注册中心
           └────────┬─────────┘
                    ▼
           ┌──────────────────┐
           │  MCP Server      │  AI 工具协议（标准接口）
           │  (cw_ingest,     │  Claude/Cursor/Copilot
           │   cw_query, ...) │  原生支持
           └────────┬─────────┘
                    ▼
           ┌──────────────────┐
           │  Wiki Engine     │  提取→建页→链接→索引
           └────────┬─────────┘
                    ▼
        ┌───────────┴───────────┐
        │  Obsidian / Logseq /  │  可视化 & 展示
        │  Web Dashboard       │
        └───────────────────────┘
```

### MCP Server（核心插件）

**MCP (Model Context Protocol)** 是 AI Agent 的标准插件协议。Compound Wiki 通过它让任何 AI 工具都能直接操作你的知识库。

**安装（以 Claude Code 为例）：**

```json
// .mcp.json 或 Claude 配置
{
  "mcpServers": {
    "compound-wiki": {
      "command": "python",
      "args": ["plugins/mcp_server.py"],
      "env": { "CW_PROJECT_DIR": "${workspaceFolder}" }
    }
  }
}
```

安装后，在对话中直接使用：

| 你说 | AI 调用 | 效果 |
|------|---------|------|
| "把这篇文章存到我的知识库" | `cw_ingest` | 自动提取、建页面、建立链接 |
| "我的Wiki里有什么关于RAG的内容？" | `cw_query` | 结构化搜索+来源引用 |
| "给我的Wiki做个体检" | `cw_lint` | 完整健康报告 |
| "我的知识库现在有多少内容了？" | `cw_stats` | 统计面板 |

**支持的 AI 平台：**
✅ Claude Desktop ✅ Claude Code ✅ Cursor ✅ GitHub Copilot ✅ 任何 MCP 兼容工具

### 9 种数据源插件

| 插件 | 投喂方式 | 配置 |
|------|---------|------|
| **📁 File Watcher** | 往 raw/ 放文件即自动检测 | 默认开启 |
| **🌐 Browser Clipper** | 浏览器按钮一键保存 | 启动后访问 `http://localhost:9877/bookmarklet.js` |
| **📋 Clipboard Monitor** | 复制文本自动捕获 | 设置 `min_length: 50` 过滤短文本 |
| **📧 Email Watcher** | IMAP邮箱自动提取 | 支持 Gmail/Outlook/任意IMAP |
| **📡 RSS Reader** | 订阅博客/arXiv自动入库 | 支持多Feed + 标签分类 |
| **🤖 Telegram Bot** | 转发消息给Bot | 通过 @BotFather 创建 |
| **💬 Discord Bot** | 监控频道消息 | 支持多频道 |
| **🔌 REST API** | POST JSON到本地接口 | 适合程序化批量导入 |
| **🪝 Webhook** | 接收Zapier/IFTTT/n8n推送 | 自动化工作流集成 |

> 所有插件的配置统一在 `plugins/config.json`，设置 `"enabled": true` 即可启用。

### 3 种输出适配器

| 适配器 | 用法 |
|--------|------|
| **Obsidian** | 直接用 Obsidian 打开项目文件夹 → 自动获得图谱视图、反向链接、全文搜索 |
| **Logseq** | 一键导出为 Logseq 图谱格式 |
| **Web Dashboard** | 轻量级 Web 浏览界面（可选） |

---

## 🛠️ 辅助工具

安装后全局可用 **`cw`** 命令：

```bash
# 初始化新知识库
cw init my-wiki

# Wiki 健康 LINT 检查
cw lint

# 统计信息
cw stats

# 查看 raw/ 未处理文件
cw check-raw

# 处理资料（提示 AI 执行 INGEST）
cw ingest

# 基于知识库提问
cw query "什么是RAG？"

# 运行状态总览
cw status

# 显示版本
cw version
```

---

## 📖 使用场景

### 场景 1：个人学习 & 学术研究

```bash
# 论文阅读
→ 把论文 PDF 转 MD 扔进 raw/
→ AI 自动提取概念、方法、实验结果
→ 形成领域知识图谱
→ 后续论文进来时自动关联已有知识

# 技能学习
→ 收集教程、文档、实践笔记
→ AI 整理成系统化的学习路径
→ 自动标注前置知识和进阶方向
```

### 场景 2：内容创作 & 行业研究

```bash
# 竞品分析
→ 各竞品的资料扔进去
→ AI 生成对比页 (wiki/synthesis/)
→ 新竞品进来时自动加入对比矩阵

# 自媒体素材库
→ 素材、灵感、热点事件持续摄入
→ AI 按主题归类并建立交叉引用
→ 写作时快速检索相关素材
```

### 场景 3：团队知识管理

```bash
# Git 协作
→ 团队共享一个 compound-wiki 仓库
→ 每人把各自领域的资料扔进 raw/
→ AI 编译为统一的团队 Wiki
→ 新人入职直接读 Wiki 快速上手
```

### 场景 4：AI Agent 长期记忆

```bash
# 作为 Claude Code / Cursor / 其他 Agent 的持久记忆层
→ 对话中的重要决策写入 outputs/ 
→ 定期将 outputs/ 中的精华回填到 wiki/
→ Agent 下次会话自动加载相关上下文
→ 实现"跨会话记忆"
```

---

## ❓ FAQ

### Q: 这是软件还是方法论？

**两者皆是。** 我们提供了一套完整的方法论规范（`schema/CLAUDE.md`）+ 项目模板 + 辅助工具。核心"编译"工作由 AI Agent 完成，不依赖特定软件。

### Q: 和 Obsidian 冲突吗？

**完全不冲突，高度互补。** Obsidian 负责 Markdown 文件的可视化编辑、图形化展示双链网络；Compound Wiki 负责定义 AI 如何自动整理和维护这些 Markdown 文件。你可以用 Obsidian 打开 `wiki/` 目录获得最佳体验。

### Q: AI 产生幻觉怎么办？

四重防护机制：

1. **原始资料只读可溯源** — 每个 Wiki 结论都标注了来自哪个 `raw/` 文件的哪部分
2. **LINT 定期审计** — 自动检测矛盾信息和缺乏引用的内容
3. **增量导入便于校验** — 一次导入少量资料，方便人工抽查质量
4. **不确定内容明确标记** — 推断性信息使用谨慎措辞，单独列出待验证项

### Q: 支持 PDF / 图片吗？

- 优先使用 Markdown / 纯文本格式的原始资料
- PDF 可以先用转换工具转成文本，或多模态 LLM 直接提取
- 图片可以由多模态模型识别后以文本描述形式存入 `raw/`
- 未来版本可能集成更多格式的自动预处理

### Q: 内容多了检索效率如何？

- 小规模（<1000 页）：通过 `index.md` 索引 + `[[双链]]` 跳转即可，速度极快
- 大规模：建议按领域拆分为多个 Wiki 子库，或配合轻量级向量检索
- 本方案的设计哲学是**优先保证质量和可维护性**

### Q: 能离线使用吗？

**完全可以。** 本地模型（Ollama/Llama/Qwen 等）+ 本地文件 = 完全离线的私有知识库。不需要任何云端服务。

### Q: 和 RAG 有什么区别？

| | RAG | Compound Wiki |
|--|-----|---------------|
| 知识形态 | 原始文档切片 + 向量索引 | 结构化 Wiki 页面 + 双链网络 |
| 查询方式 | 每次重新检索 + 重新合成 | 直接读取已整理好的结构化内容 |
| 知识沉淀 | 无，用完即弃 | 有，持续迭代永久保存 |
| 关联能力 | 弱（依赖向量相似度） | 强（AI 主动建立语义链接） |
| 长期价值 | 低 | **复利增长** |
| 适用场景 | 动态海量文档 | **中规模深度知识体系** |

两者也可以结合：Compound Wiki 处理核心知识体系，RAG 处理海量临时参考文档。

---

## 📂 项目结构

```
compound-wiki/
├── pyproject.toml           # Python 包配置（pip install 入口）
├── requirements.txt         # 依赖清单
│
├── compound_wiki/           # CLI 命令入口
│   ├── __init__.py
│   └── cli.py               # cw 命令实现
│
├── memory_core/             # Memory Core v2.0 核心
│   ├── config.py / hook_engine.py / extractor.py
│   ├── deduplicator.py / shared_wiki.py / agent_sdk.py
│   ├── memory_graph.py / mcp_server.py
│   └── examples/
│
├── schema/                  # 规则层
│   ├── CLAUDE.md            # AI 行为规范手册
│   ├── PERSPECTIVE.example.md
│   └── templates/
│
├── raw/                     # 原始资料
├── wiki/                    # 知识库（AI 维护）
├── outputs/                 # 产出层
├── auto/                    # 自动化引擎
├── plugins/                 # 插件系统
├── scripts/cw_tool.py       # 辅助工具（兼容旧版）
├── examples/                # 示例
├── README.md / README.en.md
└── LICENSE                  MIT
```

---

## 🤝 贡献指南

欢迎贡献！以下是参与方式：

1. **Fork** 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交改动 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

### 特别欢迎的贡献方向

- 🌐 **多语言 CLAUDE.md** — 将行为规范翻译/适配到不同语言环境
- 🎨 **更好的模板** — 设计更专业的 Wiki 页面模板
- 🔌 **更多辅助工具** — 如自动导入脚本、Obsidian 插件等
- 📖 **示例知识库** — 分享你搭建好的公开知识库作为范例
- 🐛 **Bug 修复** — 修复辅助工具的问题

---

## 🙏 致谢

- **[Andrej Karpathy](https://karpathy.ai/)** — LLM-Wiki 原始思想的提出者
- **[OpenClaw / ClawdBot](https://github.com/openclaw)** — 三层记忆系统的开源实现
- 所有在 [AI Memory](https://github.com/XiaomingX/awesome-ai-memory) 领域探索的开发者和研究者

---

## 📄 开源许可

本项目采用 [MIT License](./LICENSE) 开源协议。

```
MIT License

Copyright (c) 2026 Compound Wiki Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## 🙏 致谢与灵感来源

本项目并非凭空创造，而是站在巨人肩膀上的整合与创新。以下是我们直接借鉴和受启发的核心来源：

### 核心思想来源

| 来源 | 贡献 | 链接 |
|------|------|------|
| **Andrej Karpathy — LLM-Wiki** | **核心架构灵感**。Karpathy（前 OpenAI 创始成员、前特斯拉 AI 总监）于 2026 年 4 月提出的"三个文件夹 + 一个规则文件"知识管理范式——`raw/wiki/schema` 三层结构、双链机制、AI 全托管维护的思想，是本项目的基石。 | [Gist 原文](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) |
| **OpenClaw / ClawdBot — 三层记忆系统** | **记忆分层设计**。其 `知识图谱 + 每日笔记 + 隐性知识` 的三层记忆模型、原子事实的替代而非删除策略、Hooks 自动触发机制，深刻影响了本项目的 Wiki 页面分类和 LINT 审计设计。 | [GitHub 150k+ Star](https://github.com/openclaw/clawdbot) |
| **老金（阿里云）— AI 自动记忆方案** | **工程实践参考**。对 OpenClaw 记忆系统的中文解读和落地实践，包括目录结构、Hook 脚本代码、数据模板等，为项目提供了可操作的实现路径。 | [阿里云文章](https://developer.aliyun.com/article/1710321) |
| **一泽（53AI）— AI 记忆资产的复利效应** | **理念启发**。从人文角度提出 AI 记忆资产的概念，强调对话、思考、灵感的长期复利价值，以及"被深刻看见"的治愈价值，拓展了项目的应用场景视野。 | [原文](https://www.53ai.com/news/gerentixiao/2025120317865.html) |

### 概念延伸

- **RAG（检索增强生成）** — 传统 RAG 的局限（每次从头检索、无沉淀）正是 LLM-Wiki 要解决的问题
- **Obsidian 双链笔记** — `[[wiki-link]]` 格式的设计借鉴了 Obsidian/Zettelkasten 的知识网络思想
- **Zettelkasten 卡片盒笔记法** — 永久笔记、原子性、互相关联的核心理念

### 文章解读参考

以下文章对本项目有重要的解读和传播作用：

| 文章 | 来源 |
|------|------|
| [Karpathy教你搭「第二大脑」：三个文件夹就够了](https://www.woshipm.com/ai/6372020.html) | 人人都是产品经理 |
| [LLM-Wiki：AI驱动的自动演化个人知识库](https://www.aipuzi.cn/ai-news/llm-wiki.html) | AI铺子 |
| [你的AI每次都失忆：用三层记忆系统让知识积累复利](https://zhuanlan.zhihu.com/p/2021889682921768658) | 知乎 |

> ⚠️ **声明**：本项目是一个**开源的通用 Agent 记忆系统框架**，整合了上述来源的思想并进行了通用化改造。所有原始思想的版权归原作者。我们尊重每一份原创工作，如有遗漏欢迎通过 Issue 补充。

---

<p align="center">
  <strong>⭐ 如果这个项目对你有帮助，请给一个 Star 支持一下！⭐</strong>
</p>

<p align="center">
  让知识产生复利 · Build knowledge that compounds 🧠
</p>
