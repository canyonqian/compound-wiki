/**
 * CAM — Compound Agent Memory Plugin v10.0 (Autonomous Knowledge Brain)
 *
 * 核心理念：CAM 自主学习知识，不教 Agent 做事。
 *
 * 流程：
 *   1. 用户发消息 → message_received 钩子 → 异步调 Ollama LLM → 提取知识 → 写 wiki
 *   2. Agent 回答前 → before_prompt_build → 召回 wiki 知识注入上下文
 *
 * 架构：
 *   L1 Hooks（独立于 ContextEngine slot）
 *     - message_received    → 拦截用户消息 + 异步 LLM 提取知识
 *     - before_prompt_build → 召回 wiki 知识注入 prompt
 *   L2 Tool（Agent 可选调用）
 *     - cam_query  → 搜索 CAM wiki
 *     - cam_stats  → 显示 wiki 统计
 *
 * v10.0 关键修复：用 message_received 钩子代替 ContextEngine.ingest()，
 *        因为 ContextEngine slot 被 lossless-claw 占用，ingest() 永远不会被调用。
 */

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type {
  ContextEngine,
  AssembleResult,
  IngestResult,
} from "openclaw/plugin-sdk";
import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  statSync,
  appendFileSync,
} from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";

// ============================================================
// Autonomous LLM extraction — CAM calls Ollama itself
// ============================================================

const EXTRACT_SYSTEM_PROMPT = `你是 CAM（Compound Agent Memory）的知识提取引擎。你的任务是从用户消息中提取有持久价值的知识。

## 提取什么

提取**实际知识**（技术原理、工作机制、问题解决方法、API 模式、算法、技术对比），跳过：
- 项目决策（"我们选了 SQLite"）
- 用户偏好（"我喜欢 pytest"）
- 项目约定（"所有 API 测试用 pytest"）
- 问候、确认、闲聊
- 会议记录

## 输出格式

输出严格的 JSON：
{"facts": [
  {"type": "concept", "content": "完整的知识陈述，描述原理/机制/方法"},
  {"type": "entity", "content": "具体的人/项目/工具名 + 简要描述"}
]}

- concept：知识性内容（原理、机制、方法、模式、算法）
- entity：具体的可命名对象（工具、项目、服务、人名）

如果没有值得提取的知识：{"facts": []}`;

/**
 * Call Ollama LLM to extract knowledge from a user message.
 * Non-blocking — fires and forgets. Stores results directly to wiki.
 */
function llmExtractAsync(
  userMessage: string,
  store: CamMemoryStore,
): void {
  // Skip short/greeting messages
  if (userMessage.trim().length < 10) return;

  const ollamaUrl = process.env.CAM_LLM_URL || "http://localhost:11434";
  const modelName = process.env.CAM_LLM_MODEL || "qwen3.5:9b";

  const payload = {
    model: modelName,
    messages: [
      { role: "system", content: EXTRACT_SYSTEM_PROMPT },
      { role: "user", content: userMessage },
    ],
    stream: false,
    options: {
      temperature: 0,
      num_predict: 2000,
    },
  };

  const req = require("http").request(
    new URL(`${ollamaUrl}/api/chat`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeout: 120000, // 2 min — LLM needs time to think
    },
    (res: any) => {
      let body = "";
      res.on("data", (chunk: string) => (body += chunk));
      res.on("end", () => {
        try {
          const data = JSON.parse(body);
          const text = data.message?.content || "";
          if (!text) {
            console.log(`[cam-llm] Ollama returned empty response`);
            return;
          }
          const jsonMatch = text.match(/\{[\s\S]*"facts"[\s\S]*\}/);
          if (!jsonMatch) {
            console.log(`[cam-llm] No JSON in response: ${text.slice(0, 200)}`);
            return;
          }
          const parsed = JSON.parse(jsonMatch[0]);
          if (!parsed.facts?.length) return;

          const typeToCategory: Record<string, string> = {
            concept: "concept",
            entity: "entity",
          };

          for (const fact of parsed.facts) {
            const content = (fact.content || "").trim();
            if (!content || content.length < 5) continue;

            store.storeFact({
              name: content.slice(0, 80),
              category: (typeToCategory[fact.type] || "concept") as any,
              content,
              tags: ["llm-extracted", fact.type || "concept"],
              agentId: "cam-autonomous",
              timestamp: new Date().toISOString(),
              sourceSnippet: "> CAM autonomous extraction\n> " + userMessage.slice(0, 200),
            });
          }
          console.log(`[cam-llm] Extracted ${parsed.facts.length} facts from user message`);
        } catch (e: any) {
          console.log(`[cam-llm] Failed: ${e.message}`);
        }
      });
    },
  );

  req.on("error", (e: any) => {
    console.log(`[cam-llm] Ollama unavailable: ${e.message}`);
  });

  req.on("timeout", () => {
    req.destroy();
    console.log(`[cam-llm] Extraction timed out (120s)`);
  });

  req.write(JSON.stringify(payload));
  req.end();
}

// ============================================================
// Config
// ============================================================

function resolveConfig(cfg: Record<string, unknown>) {
  let wikiPath = (cfg.wikiPath as string) || "";
  if (!wikiPath && typeof cfg.config === "object" && cfg.config !== null) {
    wikiPath = ((cfg.config as Record<string, unknown>).wikiPath as string) || "";
  }
  if (typeof cfg.plugins === "object" && cfg.plugins !== null) {
    const plugins = cfg.plugins as Record<string, unknown>;
    if (typeof plugins.cam === "object" && plugins.cam !== null) {
      const cam = plugins.cam as Record<string, unknown>;
      if (typeof cam.config === "object" && cam.config !== null) {
        wikiPath = ((cam.config as Record<string, unknown>).wikiPath as string) || "";
      }
    }
    if (!wikiPath && typeof plugins.entries === "object" && plugins.entries !== null) {
      const entries = plugins.entries as Record<string, unknown>;
      if (typeof entries.cam === "object" && entries.cam !== null) {
        const camEntry = entries.cam as Record<string, unknown>;
        if (typeof camEntry.config === "object" && camEntry.config !== null) {
          wikiPath = ((camEntry.config as Record<string, unknown>).wikiPath as string) || "";
        }
      }
    }
  }
  wikiPath = wikiPath || process.env.CAM_WIKI_PATH || process.env.CAM_PROJECT_DIR || "/root/cam/wiki";

  return {
    wikiPath,
    injectOnPrompt: cfg.injectOnPrompt !== false,
    maxRecallPages: Math.min(Math.max((cfg.maxRecallPages as number) || 5, 1), 20),
  };
}

// ============================================================
// CamMemoryStore
// ============================================================

type FactCategory = "entity" | "concept" | "synthesis";

interface StoredFact {
  name: string;
  category: FactCategory;
  content: string;
  tags: string[];
  agentId: string;
  timestamp: string;
  sourceSnippet: string;
}

class CamMemoryStore {
  private wikiPath: string;
  private indexPath: string;
  private index: Map<string, StoredFact> = new Map();
  private dirty = false;

  constructor(wikiPath: string) {
    this.wikiPath = wikiPath.replace(/\/+$/, "");
    this.indexPath = join(this.wikiPath, ".cam-index.json");
    for (const dir of ["entity", "concept", "synthesis"]) {
      const p = join(this.wikiPath, dir);
      if (!existsSync(p)) mkdirSync(p, { recursive: true });
    }
    if (!existsSync(join(this.wikiPath, "raw"))) {
      mkdirSync(join(this.wikiPath, "raw"), { recursive: true });
    }
    this.loadIndex();
  }

  private loadIndex(): void {
    try {
      if (existsSync(this.indexPath)) {
        const data = JSON.parse(readFileSync(this.indexPath, "utf-8"));
        if (data.facts && Array.isArray(data.facts)) {
          for (const f of data.facts) this.index.set(f.name, f);
        }
        console.log(`[cam-store] Loaded index: ${this.index.size} facts`);
      }
    } catch (e) {
      console.warn(`[cam-store] Failed to load index: ${e}`);
      this.index = new Map();
    }
  }

  private saveIndex(): void {
    if (!this.dirty) return;
    try {
      const data = {
        version: 1,
        updatedAt: new Date().toISOString(),
        facts: Array.from(this.index.values()),
      };
      writeFileSync(this.indexPath, JSON.stringify(data, null, 2), "utf-8");
      this.dirty = false;
    } catch (e) {
      console.error(`[cam-store] Failed to save index: ${e}`);
    }
  }

  private similarity(a: string, b: string): number {
    const wordsA = new Set(a.toLowerCase().split(/\s+/));
    const wordsB = new Set(b.toLowerCase().split(/\s+/));
    if (wordsA.size === 0 || wordsB.size === 0) return 0;
    let intersection = 0;
    for (const w of wordsA) { if (wordsB.has(w)) intersection++; }
    const union = wordsA.size + wordsB.size - intersection;
    return union > 0 ? intersection / union : 0;
  }

  storeFact(fact: StoredFact): boolean {
    // Dedup
    for (const [, other] of this.index) {
      if (other.category !== fact.category) continue;
      if (other.name === fact.name) return false; // exact dup
      const sim = this.similarity(fact.content, other.content);
      if (sim >= 0.6) return false; // near-dup
    }

    const pagePath = this.getWikiPagePath(fact.category, fact.name);
    const dir = join(this.wikiPath, fact.category);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

    writeFileSync(pagePath, this.renderWikiPage(fact), "utf-8");
    this.index.set(fact.name, fact);
    this.dirty = true;
    this.saveIndex();
    return true;
  }

  storeRawConversation(userMsg: string, aiResponse: string, agentId: string, sessionId: string): void {
    const rawDir = join(this.wikiPath, "raw");
    if (!existsSync(rawDir)) mkdirSync(rawDir, { recursive: true });
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const filename = `${timestamp}-${agentId}-${sessionId.slice(0, 8)}.md`;
    const content = [
      `# Conversation Turn`,
      `- **Agent**: ${agentId}`,
      `- **Time**: ${new Date().toISOString()}`,
      `## User`,
      userMsg,
      `## Assistant`,
      aiResponse,
    ].join("\n");
    writeFileSync(join(rawDir, filename), content, "utf-8");
  }

  query(question: string, topK: number = 5): Array<{ name: string; category: FactCategory; content: string; relevance: number }> {
    const keywords = this.extractKeywords(question);
    if (keywords.length === 0) return [];
    const results: Array<{ name: string; category: FactCategory; content: string; relevance: number }> = [];
    for (const [name, fact] of this.index) {
      const searchText = `${name} ${fact.content} ${fact.tags.join(" ")}`.toLowerCase();
      let matchCount = 0;
      for (const kw of keywords) { if (searchText.includes(kw.toLowerCase())) matchCount++; }
      if (matchCount > 0) {
        const pagePath = this.getWikiPagePath(fact.category, fact.name);
        let pageContent = fact.content;
        try { if (existsSync(pagePath)) pageContent = readFileSync(pagePath, "utf-8").slice(0, 500); } catch {}
        results.push({ name, category: fact.category, content: pageContent, relevance: matchCount / keywords.length });
      }
    }
    results.sort((a, b) => b.relevance - a.relevance);
    return results.slice(0, topK);
  }

  getStats(): Record<string, unknown> {
    const byCategory: Record<string, number> = { entity: 0, concept: 0, synthesis: 0 };
    for (const [, fact] of this.index) byCategory[fact.category] = (byCategory[fact.category] || 0) + 1;
    let totalBytes = 0, totalPages = 0;
    for (const dir of ["entity", "concept", "synthesis"]) {
      const p = join(this.wikiPath, dir);
      try {
        const files = readdirSync(p).filter((f) => f.endsWith(".md"));
        totalPages += files.length;
        for (const f of files) try { totalBytes += statSync(join(p, f)).size; } catch {}
      } catch {}
    }
    return { totalFacts: this.index.size, totalPages, totalBytes, byCategory, wikiPath: this.wikiPath };
  }

  private getWikiPagePath(category: FactCategory, name: string): string {
    const safeName = name.replace(/[^a-zA-Z0-9\u4e00-\u9fff\s]/g, " ").replace(/\s+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
    const hash = this.simpleHash(name).slice(0, 8);
    return join(this.wikiPath, category, `${safeName}-${hash}.md`);
  }

  private simpleHash(str: string): string {
    let h = 0;
    for (let i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
    return Math.abs(h).toString(16);
  }

  private renderWikiPage(fact: StoredFact): string {
    const catLabel = fact.category === "entity" ? "entity" : fact.category === "concept" ? "concept" : "synthesis";
    let emoji: string, typeLabel: string;
    const tags = fact.tags.join(" ");
    if (tags.includes("concept")) { emoji = "\u{1F4A1}"; typeLabel = "Concept"; }
    else if (tags.includes("entity")) { emoji = "\u{1F3AF}"; typeLabel = "Entity"; }
    else if (tags.includes("mechanism")) { emoji = "\u2699\uFE0F"; typeLabel = "Mechanism"; }
    else if (tags.includes("problem-solving")) { emoji = "\u{1F527}"; typeLabel = "Problem Solving"; }
    else if (tags.includes("comparison")) { emoji = "\u2696\uFE0F"; typeLabel = "Comparison"; }
    else if (tags.includes("actionable")) { emoji = "\u{1F680}"; typeLabel = "Actionable"; }
    else { emoji = "\u{1F4DD}"; typeLabel = "Knowledge"; }

    const confidence = 85;
    const filled = 8, empty = 2;
    const bar = "\u2588".repeat(filled) + "\u2591".repeat(empty);

    return [
      `# ${catLabel} \u2192 ${fact.name}`,
      "",
      "> Auto-learned by CAM Knowledge Brain",
      "",
      "---",
      "",
      `${emoji} **${typeLabel}** | Confidence: \`${bar}\` (${confidence}%)`,
      "",
      fact.content,
      "",
      `*Source*: ${fact.sourceSnippet || "*Autonomous extraction*"}`,
      `*Tags*: ${fact.tags.map((t) => `\`${t}\``).join(" ")}`,
      "",
      "---",
      "",
    ].join("\n");
  }

  private extractKeywords(text: string): string[] {
    const words = text.toLowerCase().split(/[\s,，。.!！?？:：;；\-\(\)（）\[\]【】{}]+/).filter((w) => w.length >= 2);
    const stopWords = new Set(["the","a","an","is","are","was","were","be","been","being","have","has","had","do","does","did","will","would","could","should","may","might","shall","can","need","to","of","in","for","on","with","at","by","from","as","into","through","during","before","after","above","below","between","out","off","over","under","again","further","then","once","and","but","or","nor","not","so","yet","both","either","neither","each","every","all","any","few","more","most","other","some","such","no","only","own","same","than","too","very","just","because","的","了","在","是","我","有","和","就","不","人","都","一","一个","上","也","很","到","说","要","去","你","会","着","没有","看","好","自己","这"]);
    return [...new Set(words.filter((w) => !stopWords.has(w)))];
  }
}

// ============================================================
// CamContextEngine
// ============================================================

class CamContextEngine implements ContextEngine {
  private store: CamMemoryStore;
  private config: ReturnType<typeof resolveConfig>;
  private recentAttachments: Array<{ type: string; name: string; detected: number }> = [];
  private agentId = "unknown";
  private sessionId = "unknown";
  private pendingUserMsg = "";

  constructor(config: ReturnType<typeof resolveConfig>) {
    this.config = config;
    this.store = new CamMemoryStore(config.wikiPath);
    console.log(`[cam-engine] Initialized, wikiPath=${config.wikiPath}`);
  }

  async ingest(params: {
    sessionId: string;
    sessionKey?: string;
    message: {
      role: string;
      content?: string | Array<{ type: string; text?: string; image_url?: { url: string }; file_url?: { url: string } }>;
    };
    isHeartbeat?: boolean;
  }): Promise<IngestResult> {
    if (params.isHeartbeat) return { ingested: false };
    const { sessionId, message } = params;
    if (!message || typeof message !== "object") return { ingested: false };

    this.sessionId = sessionId;
    const sk = params.sessionKey || "";
    if (sk.startsWith("agent:")) this.agentId = sk.split(":")[1] || "unknown";

    let userText = "";
    let aiText = "";
    if (message.role === "user") {
      userText = this.extractText(message.content);
      this.pendingUserMsg = userText;

      // ── Autonomous LLM extraction (non-blocking) ──
      if (userText.trim().length > 10) {
        llmExtractAsync(userText, this.store);
      }
    } else if (message.role === "assistant") {
      aiText = this.extractText(message.content);
    }

    const attachments = this.detectAttachments(message);
    if (attachments.length > 0) {
      this.recentAttachments = attachments.map((a) => ({ ...a, detected: Date.now() }));
    }

    if (!userText.trim() && !aiText.trim() && attachments.length === 0) {
      return { ingested: false };
    }

    // Store raw conversation
    this.store.storeRawConversation(
      userText || "(file/image attachment)",
      aiText || "(processing)",
      this.agentId,
      sessionId,
    );

    return { ingested: true };
  }

  async assemble(params: { sessionId: string; sessionKey?: string; budget?: number }): Promise<AssembleResult> {
    const stats = this.store.getStats();
    const totalPages = stats.totalPages as number;
    if (totalPages === 0) return { content: "", tokenCount: 0 };

    const indexPath = join(this.config.wikiPath, ".cam-index.json");
    const contextParts: string[] = [];
    try {
      if (existsSync(indexPath)) {
        const data = JSON.parse(readFileSync(indexPath, "utf-8"));
        const facts = data.facts || [];
        const recent = facts.slice(-this.config.maxRecallPages);
        for (const fact of recent) {
          const pagePath = this.store["getWikiPagePath"](fact.category, fact.name);
          let preview = fact.content || "";
          try { if (existsSync(pagePath)) preview = readFileSync(pagePath, "utf-8").slice(0, 300); } catch {}
          contextParts.push(`**[${fact.category}] ${fact.name}**\n${preview}`);
        }
      }
    } catch {}

    if (contextParts.length === 0) return { content: "", tokenCount: 0 };

    const content = [
      "## CAM Knowledge Recall",
      "",
      `The following knowledge has been learned and stored in CAM (${totalPages} pages):`,
      "",
      ...contextParts,
      "",
      "Use this knowledge to inform your answers.",
    ].join("\n");

    return { content, tokenCount: Math.ceil(content.length / 4) };
  }

  async compact(): Promise<void> {}

  getStore(): CamMemoryStore { return this.store; }
  getRecentAttachments(): Array<{ type: string; name: string; detected: number }> {
    const now = Date.now();
    this.recentAttachments = this.recentAttachments.filter((a) => now - a.detected < 60000);
    return this.recentAttachments;
  }
  getAgentId(): string { return this.agentId; }

  private extractText(content?: string | Array<{ type: string; text?: string }>): string {
    if (!content) return "";
    if (typeof content === "string") return content;
    if (Array.isArray(content)) return content.filter((c) => c.type === "text" && c.text).map((c) => c.text || "").join("\n");
    return String(content);
  }

  private detectAttachments(message: { role: string; content?: unknown }): Array<{ type: string; name: string }> {
    const attachments: Array<{ type: string; name: string }> = [];
    const content = message.content;
    if (!content) return attachments;
    if (Array.isArray(content)) {
      for (const block of content) {
        if (block && typeof block === "object") {
          if (block.type === "image" || block.type === "image_url") attachments.push({ type: "image", name: block.text || "image" });
          else if (block.type === "file" || block.type === "file_url") attachments.push({ type: "file", name: block.text || (block as any).filename || "file" });
        }
      }
    }
    return attachments;
  }
}

// ============================================================
// Tools
// ============================================================

function createCamQueryTool(store: CamMemoryStore): any {
  return {
    name: "cam_query",
    description: "Search the CAM knowledge wiki for relevant facts and concepts.",
    parameters: {
      type: "object",
      properties: {
        question: { type: "string", description: "What to search for" },
        top_k: { type: "number", description: "Max results (default: 5)" },
      },
      required: ["question"],
    },
    async execute(args: { question: string; top_k?: number }): Promise<string> {
      const results = store.query(args.question, args.top_k || 5);
      if (results.length === 0) return "No matching knowledge in CAM wiki.";
      const lines = results.map((r, i) => `${i + 1}. **[${r.category}] ${r.name}**\n   ${r.content.slice(0, 200)}`);
      return `CAM Query Results:\n\n${lines.join("\n\n")}`;
    },
  };
}

function createCamStatsTool(store: CamMemoryStore): any {
  return {
    name: "cam_stats",
    description: "Show CAM knowledge wiki statistics.",
    parameters: { type: "object", properties: {} },
    async execute(): Promise<string> {
      const stats = store.getStats();
      return [`CAM Knowledge Wiki:`, ``, `- Total: ${stats.totalFacts} facts, ${stats.totalPages} pages`, `- Concepts: ${stats.byCategory.concept}`, `- Entities: ${stats.byCategory.entity}`, `- Wiki: ${stats.wikiPath}`].join("\n");
    },
  };
}

// ============================================================
// Hook — just recall, no instructions
// ============================================================

function handleBeforePromptBuild(
  config: ReturnType<typeof resolveConfig>,
  engine: CamContextEngine,
): (event: any, ctx: any) => Promise<{ prependSystemContext?: string; prependContext?: string }> {
  return async (event, ctx) => {
    if (!config.injectOnPrompt) return {};
    try {
      const store = engine.getStore();
      const stats = store.getStats();
      const totalPages = stats.totalPages as number;
      if (totalPages === 0) return {};

      const parts: string[] = [];
      const indexPath = join(config.wikiPath, ".cam-index.json");
      try {
        if (existsSync(indexPath)) {
          const data = JSON.parse(readFileSync(indexPath, "utf-8"));
          const facts = data.facts || [];
          const recent = facts.slice(-config.maxRecallPages);
          for (const fact of recent) {
            const pagePath = join(config.wikiPath, fact.category, `${fact.name.replace(/[^a-zA-Z0-9\u4e00-\u9fff\s]/g, " ").replace(/\s+/g, "-").slice(0, 60)}-${Math.abs([...fact.name].reduce((h, c) => ((h << 5) - h) + c.charCodeAt(0) | 0, 0)).toString(16).slice(0, 8)}.md`);
            let preview = fact.content || "";
            try { if (existsSync(pagePath)) preview = readFileSync(pagePath, "utf-8").slice(0, 300); } catch {}
            parts.push(`**[${fact.category}] ${fact.name}**\n${preview}`);
          }
        }
      } catch {}

      if (parts.length === 0) return {};
      return {
        prependSystemContext: [
          "## CAM Knowledge Recall",
          `Learned knowledge (${totalPages} pages):`,
          "",
          ...parts,
          "",
        ].join("\n"),
      };
    } catch (e) {
      return {};
    }
  };
}

// ============================================================
// Plugin Registration
// ============================================================

const camPlugin = {
  id: "cam",
  version: "10.0.0",

  configSchema: {
    parse(value: unknown) {
      const raw = value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
      return resolveConfig(raw);
    },
  },

  register(api: OpenClawPluginApi): void {
    const config = resolveConfig(api.config || {});
    const engine = new CamContextEngine(config);
    const store = engine.getStore();

    // L1: Hooks (independent of ContextEngine slot)

    // Capture user messages for autonomous LLM extraction
    api.on("message_received", (event: any) => {
      console.log(`[cam-hook] message_received: ${typeof event.content === "string" ? event.content.slice(0, 80) : "(non-string)"}`);
      if (typeof event.content === "string" && event.content.trim().length > 10) {
        console.log(`[cam-hook] Triggering LLM extraction for: "${event.content.slice(0, 60)}..."`);
        llmExtractAsync(event.content, store);
      }
    });

    // Recall wiki knowledge before prompt build
    api.on("before_prompt_build", handleBeforePromptBuild(config, engine));

    // L2: ContextEngine (registered but not active unless slot = "cam")
    api.registerContextEngine("cam", () => engine);

    // L3: Tools
    api.registerTool(() => createCamQueryTool(store));
    api.registerTool(() => createCamStatsTool(store));

    console.log(`[cam] Plugin v10.0 loaded (Autonomous Knowledge Brain)`);
    console.log(`[cam] wikiPath=${config.wikiPath}`);
    console.log(`[cam] Autonomous LLM extraction via message_received hook → Ollama`);
    console.log(`[cam] Tools: cam_query, cam_stats`);
  },
};

export default camPlugin;
