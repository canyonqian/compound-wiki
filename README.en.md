# 🧠 Compound Wiki

<p align="center">
  <strong>Universal AI-Driven Compound Memory System — Make Knowledge Grow in Value Over Time</strong>
</p>

<p align="center">
  <a href="./README.md">🇨🇳 中文</a> ·
  <a href="./README.en.md">English</a> &nbsp;&nbsp;
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a="#quick-start"><img src="https://img.shields.io/badge/Status-Ready-green" alt="Status"></a>
  <a href="https://github.com/"><img src="https://img.shields.io/badge/PRs-Welcome-blue" alt="PRs Welcome"></a>
</p>

---

## ✨ What is This?

**Compound Wiki** is an **open-source, universal AI Agent memory and knowledge management solution**. Inspired by Andrej Karpathy's [LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) concept and refined with best practices from the OpenClaw three-layer memory system.

> **In a nutshell**: You just feed materials into it, AI handles organizing everything into a structured Wiki. Knowledge auto-connects and continuously evolves — **it gets smarter the more you use it**.

### Core Features

| Feature | Description |
|---------|-------------|
| 🔁 **Compound Growth** | Each operation adds new content AND automatically enhances 10-15 related pages |
| 🤖 **AI-Managed** | Humans only feed materials; AI maintains and updates the entire Wiki |
| 🔗 **Knowledge Network** | Double-link mechanism forces AI to think about connections between concepts |
| 📝 **Pure Markdown** | No database needed, no proprietary software — still readable in 10 years |
| 🔍 **LINT Auditing** | Built-in health checks to prevent error amplification in loops |
| 🔌 **Agent-Agnostic** | Works with Claude Code, Cursor, Copilot, or any AI agent that can read/write files |
| 📦 **Zero Dependencies** | Just need a local folder + an AI that can read and write files |

---

## 📐 Architecture

```
compound-wiki/
│
├── raw/                      📥 Raw Material Layer
│   ├── *.md                  (You drop stuff here)
│   ├── *.txt
│   └── ...
│
├── wiki/                     📝 Knowledge Layer (AI-maintained)
│   ├── index.md              ← Global index
│   ├── changelog.md          ← Change log
│   ├── concept/              ← Concept pages (theories, methods)
│   ├── entity/               ← Entity pages (people, orgs, tools)
│   └── synthesis/            ← Synthesis pages (comparisons, reviews)
│
├── schema/                   ⚙️ Schema Layer (you define rules)
│   ├── CLAUDE.md             ← ⭐ Core! AI behavior specification
│   ├── PERSPECTIVE.md        ← Your perspective preferences (optional)
│   └── templates/            ← Page templates
│       ├── concept.md
│       ├── entity.md
│       └── synthesis.md
│
├── outputs/                  📤 Output Layer (Q&A results)
│
├── plugins/                  🧩 Plugin System (v1.2+)
│   ├── mcp_server.py        ← MCP Protocol Server (6 AI tools)
│   ├── config.json          ← Unified plugin config
│   ├── sources/             ← 9 Data source plugins
│   │   ├── api_source.py    ← REST API endpoint
│   │   ├── browser.py       ← Browser clipper (bookmarklet)
│   │   ├── clipboard.py     ← Clipboard monitor
│   │   ├── email_source.py  ← IMAP email watcher
│   │   ├── rss_source.py    ← RSS feed reader
│   │   ├── bot_telegram.py  ← Telegram bot
│   │   ├── bot_discord.py   ← Discord bot
│   │   ├── webhook_source.py← Webhook receiver
│   │   └── file_watch.py    ← Enhanced file watcher
│   └── adapters/            ← Output adapters
│       ├── obsidian.py      ← Obsidian vault sync
│       └── logseq.py        ← Logseq export
│
├── auto/                     ⚡ Auto Engine (v1.1+)
│   ├── config.py             ← Configuration system
│   ├── state.py              ← State persistence
│   ├── watcher.py            ← File monitor
│   ├── pipeline.py           ← LLM ingestion engine
│   ├── collector.py          ← Web fetcher
│   ├── scheduler.py          ← Task scheduler
│   ├── agent.py              ← Main CLI entry
│   ├── config.json           ← Default config
│   ├── cw-auto.bat           ← Windows launcher
│   └── cw-auto.sh            ← Unix launcher
│
├── scripts/                  🔧 Utility tools
│   ├── cw_tool.py            ← Python toolkit
│   ├── cw.bat                ← Windows launcher
│   └── cw.sh                 ← macOS/Linux launcher
│
└── examples/                 📚 Examples
   └── raw-sample/           ← Sample raw materials
```

### Responsibility Boundary

```
┌─────────────────────────────────────────────┐
│               You (Human)                   │
│                                             │
│  ✅ Drop materials into raw/                │
│  ✅ Define schema/CLAUDE.md rules           │
│  ✅ Define schema/PERSPECTIVE.md view       │
│  ✅ Read contents from wiki/                │
│  ✅ Review LINT reports periodically        │
│                                             │
│  ❌ Do NOT edit wiki/ content directly      │
│  ❌ Do NOT modify core CLAUDE.md rules     │
│                                             │
├─────────────────────────────────────────────┤
│               AI (Agent)                    │
│                                             │
│  ✅ Read raw materials from raw/           │
│  ✅ Create/update all pages in wiki/        │
│  ✅ Build [[double-link]] connections       │
│  ✅ Maintain index.md and changelog.md     │
│  ✅ Execute LINT health audits             │
│  ✅ Answer questions based on Wiki         │
│                                             │
│  ❌ Do NOT modify any files in raw/        │
│  ❌ Do NOT modify schema/ rule files       │
│                                             │
└─────────────────────────────────────────────┘
```

### 🤖 Auto Engine (v1.1+)

> **NEW in v1.1!** Compound Wiki now has full automation capabilities — it can run as a background daemon.

```
compound-wiki/
│
├── auto/                     ⚡ Auto Engine (NEW!)
│   ├── __init__.py          ← Package init
│   ├── config.py            ← Config system (paths, API keys, models)
│   ├── state.py             ← State manager (history, incremental tracking)
│   ├── watcher.py           ← File watcher (monitors raw/ for changes)
│   ├── pipeline.py          ← Ingestion pipeline (LLM-powered processing)
│   ├── collector.py         ← Web collector (URLs → raw/)
│   ├── scheduler.py         ← Cron-like scheduler (timed tasks)
│   ├── agent.py             ← Main entry point & CLI
│   ├── config.json          ← Default config file
│   ├── cw-auto.bat          ← Windows launcher
│   └── cw-auto.sh           ← Unix/macOS launcher
│
├── schema/CLAUDE.md          ← New "Chapter 8: Auto Engine Behavior"
│
... (other dirs unchanged)
```

**Automation Architecture**:

```
┌─────────┐     ┌──────────┐     ┌──────┐
│ Web URL │────▶│ Collector │────▶│ raw/ │
└─────────┘     └──────────┘     └──┬───┘
                                   │ File events
              ┌────────────────────▼──────────────┐
              │           FileWatcher              │
              │  Monitors raw/, detects new files   │
              └────────────────────┬──────────────┘
                                   │ auto-ingest
              ┌────────────────────▼──────────────┐
              │        IngestionPipeline           │
              │  Raw + CLAUDE.md → LLM → Wiki      │
              └────────────────────┬──────────────┘
                                   │ Write pages
                    ┌──────────────▼──────────────┐
                    │            wiki/              │
                    │ concept / entity / synthesis  │
                    └──────────┬──────────┬────────┘
                               │          │
               ┌───────────────▼──┐  ┌────▼─────────┐
               │  Query() Q→A    │  │  Scheduler    │
               │ + Auto-archive  │  │  Daily LINT    │
               └─────────────────┘  │  Weekly summary│
                                    │  Monthly report│
                                    └──────────────┘
```

**CLI Commands**:

```bash
# Initialize (first time only)
python auto/agent.py init

# Full auto mode (runs all modules in background)
python auto/agent.py start

# One-shot operations
python auto/agent.py ingest              # Process pending raw files
python auto/agent.py query "What is X?"  # Query knowledge base
python auto/agent.py lint                 # Health check
python auto/agent.py collect <URL>        # Fetch webpage into raw/

# View stats
python auto/agent.py status               # Statistics dashboard

# Or use the one-click launcher:
auto/cw-auto.bat start        # Windows
./auto/cw-auto.sh start       # Linux/macOS
```

**Automation Capability Matrix**:

| Capability | Manual | Automatic | Notes |
|------------|--------|-----------|-------|
| **Ingestion** | Say "INGEST" | Watcher detects new `raw/` files | 3s debounce + 30s batch window |
| **Web Collection** | Provide URL | Collector fetches | RSS/bookmark/clipboard support |
| **Query & Archive** | Ask question | — | Answers auto-archived as synthesis pages |
| **Health Check** | Say "LINT" | Scheduled daily @ 08:00 | Report written to `outputs/` |
| **Weekly Summary** | — | Every Sunday @ 20:00 | Growth statistics |
| **Monthly Report** | — | 1st of each month @ 09:00 | Compound effect analysis |
| **State Tracking** | — | Fully automatic | SHA256 incremental, atomic writes |

---

## 🚀 Quick Start

### Method A: Use This Project Template

```bash
# 1. Clone or download this project
git clone https://github.com/your-repo/compound-wiki.git
cd compound-wiki

# 2. Edit your knowledge base rules
# Open schema/CLAUDE.md and customize for your needs

# 3. (Recommended) Configure your perspective
cp schema/PERSPECTIVE.example.md schema/PERSPECTIVE.md
# Then edit PERSPECTIVE.md with your info

# 4. Drop materials into raw/

# 5. Open this directory with an AI Agent and issue INGEST command
```

### Method B: Build From Scratch

```bash
# 1. Create directory structure
mkdir compound-wiki && cd compound-wiki
mkdir raw wiki/concept wiki/entity wiki/synthesis schema/templates outputs

# 2. Copy schema/CLAUDE.md (from this project's schema/ directory)

# 3. Drop materials into raw/

# 4. Tell your AI the command below 👇
```

---

## 💬 Core AI Interaction Commands

### INGEST: Process Raw Materials

> Send this to your AI Agent:

```
Please read all new files in the raw/ directory.
Following the rules in schema/CLAUDE.md:
1. Extract core concepts → Create pages in wiki/concept/
2. Extract entities involved → Create pages in wiki/entity/
3. Build [[double-link]] connections between pages
4. Update wiki/index.md
5. Record this operation in wiki/changelog.md
Each page must include complete frontmatter metadata.
Use templates in schema/templates/ as format reference.
```

### QUERY: Ask Questions Based on Knowledge Base

```
Please answer the following question based on wiki/ contents:
[Your Question]

Requirements:
- Cite specific Wiki pages as sources
- Follow [[double-links]] to find related info
- If information is insufficient, identify what's missing
```

### LINT: Health Audit

```
Please run a LINT check on the entire wiki/ directory:
1. Check for contradictory information
2. Find orphaned pages without links
3. Identify conclusions lacking source citations
4. List referenced-but-not-yet-created pages
5. Provide improvement suggestions and output report
```

### SYNTHESIS: Create Comparative Analysis

```
Based on wiki/ content about [Topic A] and [Topic B],
create a comparative analysis page in wiki/synthesis/.
Use the synthesis page template format. Provide clear conclusions and recommendations.
```

---

## 🔄 How The Compound Engine Works

### Why "Compound"?

Traditional knowledge management is **linear** — you get out what you put in.

Compound Wiki is **exponential** — every operation creates cascading value:

```
Round 1: Import material A
  → Create page A
  → +1 page

Round 2: Import material B  
  → Create page B
  → Update page A (establish A↔B link)
  → +2 operations (1 create + 1 update)

Round 3: Q&A query X
  → Generate answer
  → Archive as new synthesis page S
  → Update citation chains between A, B, S
  → +N operations

Round 4: LINT audit
  → Find contradictions and fix them
  → Overall quality improves
  → All future queries benefit
```

### Value Multiplication Per Operation

| Operation | Direct Output | Indirect Value Add |
|-----------|--------------|-------------------|
| Import 1 material | 1 new Wiki page | Auto-update 10~15 related pages |
| 1 Q&A session | Get answer | Can be archived as synthesis/comparison page |
| 1 LINT check | Fix issues | Overall knowledge base accuracy improves |
| Time passes | - | Knowledge network density keeps increasing |

---

## 🧩 Plugin System

### More Than Scripts — A True Plugin Architecture

Compound Wiki v1.2 introduces a complete **plugin-based architecture** with multiple data ingestion channels. **You're no longer limited to manually dropping files into `raw/`.**

```
┌──────────────────────────────────────────────────────┐
│                   Data Input Layer                     │
│                                                      │
│  🌐 Browser Btn   📋 Clipboard    📧 Email           │
│  🤖 Telegram      💬 Discord      📡 RSS Feeds       │
│  🔌 REST API      🪝 Webhook     📁 Drag & Drop      │
└──────────┬─────────┬───────────────┬──────────────────┘
           └─────────┴───────────────┘
                       ▼
              ┌──────────────────┐
              │  SourceRegistry  │  Unified source hub
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  MCP Server      │  Standard AI tool protocol
              │  (cw_ingest,     │  Works with Claude/Cursor/
              │   cw_query, ...) │  Copilot out of the box
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  Wiki Engine     │  Extract → Page → Link → Index
              └────────┬─────────┘
                       ▼
        ┌──────────────┴──────────────┐
        │  Obsidian / Logseq / Web UI │
        └─────────────────────────────┘
```

### MCP Server (Core Plugin)

**MCP (Model Context Protocol)** is the standard AI plugin protocol. Compound Wiki exposes your knowledge base through MCP so any AI tool can operate it directly.

**Installation (Claude Code example):**

```json
// .mcp.json or Claude config
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

After installation, use naturally in conversation:

| You Say | AI Calls | Effect |
|---------|----------|--------|
| "Save this article to my knowledge base" | `cw_ingest` | Auto-extract, create pages, build links |
| "What does my Wiki have about RAG?" | `cw_query` | Structured search + citations |
| "Run a health check on my Wiki" | `cw_lint` | Full health report |
| "How big is my knowledge base now?" | `cw_stats` | Statistics dashboard |

**Supported Platforms:** ✅ Claude Desktop ✅ Claude Code ✅ Cursor ✅ GitHub Copilot ✅ Any MCP-compatible tool

### 9 Data Source Plugins

| Plugin | How to Feed | Config |
|--------|-------------|--------|
| **📁 File Watcher** | Drop files into `raw/` | Enabled by default |
| **🌐 Browser Clipper** | One-click save from browser | Visit `http://localhost:9877/bookmarklet.js` |
| **📋 Clipboard Monitor** | Auto-capture copied text | Set `min_length: 50` |
| **📧 Email Watcher** | Auto-extract from IMAP inbox | Gmail/Outlook/any IMAP |
| **📡 RSS Reader** | Subscribe blogs/arXiv auto-import | Multi-feed + tags |
| **🤖 Telegram Bot** | Forward messages to bot | Create via @BotFather |
| **💬 Discord Bot** | Monitor channel messages | Multi-channel support |
| **🔌 REST API** | POST JSON to local endpoint | Programmatic batch import |
| **🪝 Webhook** | Receive Zapier/IFTTT/n8n pushes | Workflow automation |

> All plugins configured in `plugins/config.json`. Set `"enabled": true` to activate.

### 3 Output Adapters

| Adapter | Usage |
|---------|-------|
| **Obsidian** | Open project folder in Obsidian → get graph view, backlinks, search for free |
| **Logseq** | One-click export to Logseq graph format |
| **Web Dashboard** | Lightweight web browsing interface (optional) |

---

## 🛠️ Built-in Tools

```bash
# Initialize new project
python scripts/cw_tool.py init [path]

# Wiki health LINT check
python scripts/cw_tool.py lint [path]

# Statistics
python scripts/cw_tool.py stats [path]

# Check unprocessed files in raw/
python scripts/cw_tool.py check-raw [path]

# Windows shortcut
cw.bat lint
cw.bat stats

# macOS/Linux shortcut
chmod +x scripts/cw.sh
./cw.sh lint
./cw.sh stats
```

---

## 📖 Use Cases

### Use Case 1: Personal Learning & Academic Research

```bash
# Paper reading
→ Convert PDF papers to MD, drop into raw/
→ AI auto-extracts concepts, methods, results
→ Forms domain knowledge graph
→ New papers auto-link to existing knowledge as they arrive

# Skill learning
→ Collect tutorials, docs, practice notes
→ AI organizes into systematic learning paths
→ Auto-tags prerequisites and next-level directions
```

### Use Case 2: Content Creation & Industry Research

```bash
# Competitor analysis
→ Drop competitor materials in
→ AI generates comparison pages (wiki/synthesis/)
→ New competitors auto-join comparison matrix

# Content creator's素材 library
→ Continuous intake of materials, inspiration, trending topics
→ AI categorizes by topic with cross-references
→ Quick retrieval when writing
```

### Use Case 3: Team Knowledge Management

```bash
# Git collaboration
→ Team shares one compound-wiki repo
→ Each person drops domain-specific materials into raw/
→ AI compiles unified team Wiki
→ New hires onboard fast by reading the Wiki
```

### Use Case 4: AI Agent Long-term Memory

```bash
# As persistent memory layer for Claude Code / Cursor / etc.
→ Write important conversation decisions to outputs/
→ Periodically distill outputs/ highlights back into wiki/
→ Agent auto-loads relevant context in next session
→ Achieves "cross-session memory"
```

---

## ❓ FAQ

### Q: Is this software or methodology?

**Both.** We provide a complete methodology specification (`schema/CLAUDE.md`) + project template + utility tools. The core "compilation" work is done by AI Agents — no specific software dependency.

### Q: Does it conflict with Obsidian?

**Not at all — highly complementary.** Obsidian handles visual editing of Markdown files and graphical display of the double-link network; Compound Wiki defines how AI automatically organizes and maintains those Markdown files. You can open the `wiki/` directory in Obsidian for the best experience.

### Q: What about AI hallucinations?

Four layers of protection:

1. **Raw materials are read-only and traceable** — Every Wiki conclusion cites which `raw/` file and section it came from
2. **LINT periodic audits** — Auto-detect contradictory info and uncited content
3. **Incremental imports for easy verification** — Import small batches for manual spot-checking
4. **Uncertain content explicitly marked** — Inferred information uses cautious wording with separate pending-verification items

### Q: Does it support PDF / images?

- Prefer Markdown / plain text format for raw materials
- PDF can be pre-converted to text, or extracted by multimodal LLM directly
- Images can be recognized by multimodal models and stored as text descriptions in `raw/`
- Future versions may integrate more format preprocessing

### Q: What about retrieval efficiency at scale?

- Small scale (<1000 pages): `index.md` index + `[[double-link]]` navigation = extremely fast
- Large scale: Split into multiple Wiki sub-domains by field, or pair with lightweight vector search
- Design philosophy: **prioritize quality and maintainability first**

### Q: Can I use it offline?

**Absolutely.** Local model (Ollama/Llama/Qwen/etc.) + local files = fully offline private knowledge base. No cloud service required.

### Q: How does this compare with RAG?

| | RAG | Compound Wiki |
|--|-----|---------------|
| Knowledge form | Raw doc chunks + vector index | Structured Wiki pages + double-link network |
| Query method | Re-retrieve + re-synthesize each time | Directly read already-structured content |
| Knowledge persistence | None, use-and-discard | Yes, iterates and persists forever |
| Link strength | Weak (relies on vector similarity) | Strong (AI builds semantic links actively) |
| Long-term value | Low | **Compound growth** |
| Best for | Dynamic massive documents | **Medium-scale deep knowledge systems** |

They can also complement each other: Compound Wiki for core knowledge, RAG for massive temporary reference docs.

---

## 📂 Detailed Project Structure

```
compound-wiki/
├── schema/                    # ⭐ Most important! Rule definitions
│   ├── CLAUDE.md             # AI behavior spec (must-read)
│   ├── PERSPECTIVE.example.md # User perspective template (fill as needed)
│   └── templates/            # Wiki page format templates
│       ├── concept.md        # Concept page template
│       ├── entity.md         # Entity page template
│       └── synthesis.md      # Synthesis page template
│
├── wiki/                      # AI-generated knowledge base (do not edit manually)
│   ├── index.md              # Global index (AI-maintained)
│   ├── changelog.md          # Change log (AI-maintained)
│   ├── concept/              # Concept pages
│   ├── entity/               # Entity pages
│   └── synthesis/            # Synthesis pages
│
├── raw/                       # Raw material drop zone (add only, no delete/edit)
│
├── outputs/                   # AI-generated Q&A and analysis reports
│
├── scripts/                   # Utility tools
│   ├── cw_tool.py            # Main tool (Python 3.6+)
│   ├── cw.bat                # Windows launcher
│   └── cw.sh                 # Unix launcher
│
├── examples/                  # Examples and tutorials
│   └── raw-sample/           # Sample raw materials
│
├── README.md                  # Chinese documentation
├── README.en.md               # English documentation (this file)
└── LICENSE                    # MIT open source license
```

---

## 🤝 Contributing

Contributions are welcome! Here's how to participate:

1. **Fork** this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Submit a Pull Request

### Especially Welcome Contributions

- 🌐 **Multilingual CLAUDE.md** — Translate/adapt behavior specs for different languages
- 🎨 **Better Templates** — Design more professional Wiki page templates
- 🔌 **More Tools** — Auto-import scripts, Obsidian plugins, etc.
- 📖 **Example Knowledge Bases** — Share publicly built Wikis as demos
- 🐛 **Bug Fixes** — Fix utility tool issues

---

## 🙏 Acknowledgments

- **[Andrej Karpathy](https://karpathy.ai/)** — Original author of the LLM-Wiki concept
- **[OpenClaw / ClawdBot](https://github.com/openclaw)** — Three-layer memory system open source implementation
- All developers and researchers exploring the [AI Memory](https://github.com/XiaomingX/awesome-ai-memory) space

---

## 📄 License

This project is licensed under the [MIT License](./LICENSE).

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

## 🙏 Acknowledgments & Inspiration

This project was not created in a vacuum — it stands on the shoulders of giants. Below are the core sources we directly drew inspiration from and built upon:

### Primary Sources of Inspiration

| Source | Contribution | Link |
|--------|-------------|------|
| **Andrej Karpathy — LLM-Wiki** | **Core architectural inspiration**. Karpathy (former OpenAI founding member, former Tesla AI Director) proposed the "three folders + one rule file" knowledge management paradigm in April 2026 — the `raw/wiki/schema` three-layer structure, bi-directional linking mechanism, and AI-full-custody maintenance philosophy form the bedrock of this project. | [Original Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) |
| **OpenClaw / ClawdBot — Three-Layer Memory System** | **Memory layering design**. Its `Knowledge Graph + Daily Notes + Tacit Knowledge` three-layer memory model, atomic fact "supersede rather than delete" strategy, and Hooks auto-trigger mechanism deeply influenced our Wiki page categorization and LINT audit design. | [GitHub 150k+ Stars](https://github.com/openclaw/clawdbot) |
| **老金 (Alibaba Cloud) — AI Auto-Memory System** | **Engineering practice reference**. The Chinese interpretation and implementation of OpenClaw's memory system, including directory structures, Hook script code, and data templates, provided a practical implementation path for this project. | [Article (CN)](https://developer.aliyun.com/article/1710321) |
| **一泽 (53AI) — Compound Effect of AI Memory Assets** | **Philosophical inspiration**. Proposed the concept of AI memory assets from a humanistic perspective, emphasizing the long-term compound value of conversations, thoughts, and insights, as well as the healing value of "being deeply seen." | [Article (CN)](https://www.53ai.com/news/gerentixiao/202512031786.html) |

### Conceptual Lineage

- **RAG (Retrieval-Augmented Generation)** — The limitations of traditional RAG (retrieving from scratch every time, no accumulation) is exactly what LLM-Wiki set out to solve
- **Obsidian Bi-directional Linking** — The `[[wiki-link]]` format draws from Obsidian/Zettelkasten's knowledge network philosophy
- **Zettelkasten (Slipbox)** — Permanent notes, atomicity, and interconnection principles

### Interpretive Articles

The following articles played important roles in interpreting and spreading these ideas:

| Article | Source |
|---------|--------|
| [Karpathy教你搭「第二大脑」：三个文件夹就够了 (CN)](https://www.woshipm.com/ai/6372020.html) | Woshipm (人人都是产品经理) |
| [LLM-Wiki: AI-Driven Self-Evolving Personal Knowledge Base (CN)](https://www.aipuzi.cn/ai-news/llm-wiki.html) | AIPuzi (AI铺子) |
| [Your AI Forgets Every Time: Use Three-Layer Memory for Compound Growth (CN)](https://zhuanlan.zhihu.com/p/2021889682921768658) | Zhihu |

> ⚠️ **Disclaimer**: This project is an **open-source universal Agent memory system framework** that integrates ideas from the above sources with general-purpose adaptations. All original concepts belong to their respective authors. We respect every piece of original work. If any attribution is missing, please open an Issue to let us know.

---

<p align="center">
  <strong>⭐ If this project helps you, please give it a Star! ⭐</strong>
</p>

<p align="center">
  Make knowledge compound · Build knowledge that compounds 🧠
</p>
