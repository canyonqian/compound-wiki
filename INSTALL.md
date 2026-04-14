# Compound Wiki — Universal Agent Plugin Installation Guide
# ===========================================================
# Zero-config. Uses Host Agent's LLM. No separate API key needed.

## Quick Install (one command per platform)

### Claude Desktop / Claude Code

```bash
pip install mcp[cli] compound-wiki
```

Then add to your MCP config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "compound-wiki": {
      "command": "python",
      "args": ["-m", "plugins.mcp_server"],
      "env": { "CW_PROJECT_DIR": "<your-wiki-path>" }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "compound-wiki": {
      "command": "python",
      "args": ["-m", "plugins.mcp_server"],
      "env": { "CW_PROJECT_DIR": "${workspaceFolder}" }
    }
  }
}
```

### GitHub Copilot (VS Code)

Add to `.vscode/mcp.json` or VS Code settings:

```json
{
  "github.copilot.mcpServers": {
    "compound-wiki": {
      "command": "python",
      "args": ["-m", "plugins.mcp_server"],
      "env": { "CW_PROJECT_DIR": "${workspaceFolder}" }
    }
  }
}
```

### Windsurf

Add to `.windsurf/mcp.json`:

```json
{
  "mcpServers": {
    "compound-wiki": {
      "command": "python",
      "args": ["-m", "plugins.mcp_server"],
      "env": { "CW_PROJECT_DIR": "${workspaceFolder}" }
    }
  }
}
```

### OpenClaw

OpenClaw uses a webhook bridge pattern. Add to your OpenClaw agent config:

```javascript
// In your OpenClaw agent configuration:
{
  "hooks": {
    "onResponse": {
      "url": "http://localhost:9877/memory/hook",
      "method": "POST"
    }
  },
  // Or use MCP mode if OpenClaw supports it
  "mcpServers": [{
    "name": "compound-wiki",
    "command": "python",
    "args": ["-m", "plugins.mcp_server"]
  }]
}

// Alternative: Use the CLI bridge
// python memory_core/examples/openclaw_integration.py
```

### Cody / JetBrains

Add to `.cody/mcp.json` or JetBrains MCP settings:

```json
{
  "mcpServers": {
    "compound-wiki": {
      "command": "python",
      "args": ["-m", "plugins.mcp_server"],
      "env": { "CW_PROJECT_DIR": "${projectRoot}" }
    }
  }
}
```

### Generic MCP Client (any tool)

```bash
# Start as stdio server (default)
python plugins/mcp_server.py

# Start as SSE server (for remote connections)
python plugins/mcp_server.py sse
# → Connect to http://localhost:8765/sse
```

---

## How It Works (No API Key Needed!)

```
┌─────────────────────────────────────────────────────┐
│                   Your AI Agent                      │
│            (Claude/GPT/Any LLM)                     │
│                                                      │
│  User: "Read this article about RAG"                │
│       ↓                                             │
│  Agent calls: cw_ingest(content="...")              │
│       ↓                                             │
│  ┌─────────────────────────────────┐               │
│  │   Compound Wiki MCP Server v2   │               │
│  │                                 │               │
│  │  1. Saves content → raw/        │               │
│  │  2. Returns EXTRACTION PROMPT   │ ← No API call! │
│  │  ─────────────────────────────  │               │
│  │  3. Agent uses ITS OWN brain     │               │
│  │     to extract knowledge         │               │
│  │  4. Agent calls cw_write_pages() │               │
│  │  5. Wiki updated! ✅             │               │
│  └─────────────────────────────────┘               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**The plugin is pure orchestration + storage.**
**The Agent provides ALL intelligence. Zero extra cost.**

---

## Available Tools After Installation

| Tool | What It Does |
|------|-------------|
| `cw_ingest` | Learn from any content (articles, notes, code, conversations) |
| `cw_write_pages` | Save extracted wiki pages to the knowledge base |
| `cw_update_index` | Refresh the global wiki index |
| `cw_query` | Search and retrieve stored knowledge |
| `cw_stats` | View wiki statistics and health score |
| `cw_lint` | Run quality check on the entire wiki |

---

## Example Conversation (After Install)

> **You:** Help me learn from this article about microservices architecture.
>
> **Agent:** *[calls cw_ingest with article content]*  
> **Plugin:** ✅ Content saved. Now extracting...  
> **Agent:** *[reads extraction prompt, analyzes content with its own LLM]*  
> **Agent:** *[calls cw_write_pages with extracted pages]*  
> **Plugin:** 📝 Created: wiki/concept/microservices.md, wiki/concept/service-mesh.md...  
> **Agent:** *[calls cw_update_index]*  
> **Plugin:** 📑 Index updated. 3 new pages created.
>
> **Agent:** I've learned about your microservices article. Key concepts saved:
> - Microservices architecture patterns
> - Service mesh fundamentals  
> - API gateway design
> 
> **You:** What do you know about service mesh?
> 
> **Agent:** *[calls cw_query("service mesh")]*  
> **Plugin:** Found 1 matching page...  
> **Agent:** Based on the article you shared earlier, here's what's in your wiki about service mesh...

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: mcp` | Run `pip install mcp[cli]` |
| `CW_PROJECT_DIR` not set | Set env var or use default (plugin parent dir) |
| Wiki directory empty after ingest | The Agent needs to follow the extraction prompt and call `cw_write_pages` |
| Pages not linking correctly | Make sure Agent uses `[[]]` format for internal links |

---

*Compound Wiki v2 — Universal AI Memory Plugin*
