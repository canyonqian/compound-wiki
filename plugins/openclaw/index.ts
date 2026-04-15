/**
 * CAM — OpenClaw Plugin v4 (ContextEngine + Tool + Hook Hybrid)
 *
 * 架构升级：从纯 hook 模式改为 LCM 同款 ContextEngine 一等公民模式
 *
 * 三层机制：
 *   1️⃣ ContextEngine (框架自动调用，不受 activateGlobalSideEffects 限制)
 *      - ingest()    → 每条消息自动存入 wiki（框架在消息到达时自动调用）
 *      - assemble()  → 构建 prompt 时召回相关记忆注入上下文
 *
 *   2️⃣ Tool (Agent 主动调用)
 *      - cam_query       → 查询知识库
 *      - cam_stats        → 统计面板
 *      - cam_ingest       → 手动摄入内容
 *      - cam_extract_file → 文件/图片/文档 → LLM提取 → 存入wiki
 *
 *   3️⃣ Hook (补充)
 *      - before_prompt_build → 注入记忆召回结果 + 文件处理指令
 *      - llm_output          → 检测文件/图片处理结果 → 自动提取存入wiki
 */

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type {
  ContextEngine,
  AssembleResult,
  IngestResult,
} from "openclaw/plugin-sdk";

// ============================================================
// 配置
// ============================================================

const DAEMON_URL = process.env.CAM_DAEMON_URL || "http://127.0.0.1:9877";
const DAEMON_TIMEOUT_MS = 10000; // 10s timeout for daemon calls

function resolveConfig(cfg: Record<string, unknown>) {
  return {
    wikiPath: ((cfg.wikiPath as string) || process.env.CAM_PROJECT_DIR || process.cwd()).replace(/\/+$/, ""),
    injectOnPrompt: cfg.injectOnPrompt !== false,
    extractOnOutput: cfg.extractOnOutput !== false,
    daemonUrl: (cfg.daemonUrl as string) || DAEMON_URL,
  };
}

// ============================================================
// Daemon HTTP Client
// ============================================================

interface DaemonResponse {
  success?: boolean;
  status: string;
  facts_extracted?: number;
  facts_written?: number;
  results_found?: number;
  matches?: Array<{
    page: string;
    name: string;
    preview: string;
    content_snippet: string;
  }>;
  question?: string;
  error?: string;
  processing_time_ms?: number;
  throttled?: boolean;
  message?: string;
  [key: string]: unknown;
}

async function daemonPost(
  endpoint: string,
  body: Record<string, unknown>,
  baseUrl?: string,
): Promise<DaemonResponse | null> {
  const url = `${baseUrl || DAEMON_URL}${endpoint}`;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), DAEMON_TIMEOUT_MS);

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!res.ok) {
      console.log(`[cam] ${endpoint}: daemon returned ${res.status}`);
      return null;
    }
    return (await res.json()) as DaemonResponse;
  } catch (_) {
    // Daemon offline — silently skip
    return null;
  }
}

async function daemonGet(endpoint: string, params: Record<string, string> = {}): Promise<DaemonResponse | null> {
  const url = new URL(`${DAEMON_URL}${endpoint}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), DAEMON_TIMEOUT_MS);
    const res = await fetch(url.toString(), { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return null;
    return (await res.json()) as DaemonResponse;
  } catch (_) {
    return null;
  }
}

// ============================================================
// ContextEngine 实现 — 核心层（框架自动调用）
// ============================================================

class CamContextEngine implements ContextEngine {
  private config: ReturnType<typeof resolveConfig>;
  private lastQueryResult: string | null = null;

  constructor(cfg: ReturnType<typeof resolveConfig>) {
    this.config = cfg;
  }

  /** OpenClaw 框架在每条消息到达时自动调用 */
  async ingest(params: {
    sessionId: string;
    sessionKey?: string;
    message: any; // AgentMessage — role + content array
  }): Promise<IngestResult> {
    try {
      const content = this.extractTextContent(params.message);
      if (!content || content.length < 5) return { ingested: false };

      const role = params.message?.role || "unknown";

      const result = await daemonPost("/hook", {
        user_message: role === "user" ? content : "",
        ai_response: role === "assistant" ? content : "",
        conversation: [{ role, content }],
        agent_id: "openclaw",
        session_id: params.sessionKey || params.sessionId || "",
      }, this.config.daemonUrl);

      if (result?.facts_written && result.facts_written > 0) {
        console.log(`[cam-ingest] 🧠 ${result.facts_written} fact(s) stored (${role})`);
      }

      return { ingested: !!result };
    } catch (e) {
      console.log("[cam-ingest] error:", (e as Error).message);
      return { ingested: false };
    }
  }

  /** OpenClaw 框架在构建 prompt 时自动调用 — 召回相关记忆 */
  async assemble(params: {
    sessionId: string;
    sessionKey?: string;
    messages: any[];
    prompt?: string;
    tokenBudget?: number;
  }): Promise<AssembleResult> {
    try {
      // 用当前用户 prompt 查询相关记忆
      const query = params.prompt || "";
      if (!query || query.length < 3 || !this.config.injectOnPrompt) {
        return { messages: [], estimatedTokens: 0 };
      }

      const result = await daemonGet("/query", { q: query, top_k: "5" });
      if (!result || !result.matches || result.matches.length === 0) {
        return { messages: [], estimatedTokens: 0 };
      }

      // 缓存结果供 hook 使用
      this.lastQueryResult = this.formatMatches(result.matches);

      // 返回系统提示追加（注入到 prompt 中）
      const contextBlock = this.formatMatchesForPrompt(result.matches, query);

      return {
        messages: [],
        estimatedTokens: Math.ceil(contextBlock.length / 4),
        systemPromptAddition: contextBlock,
      };
    } catch (e) {
      console.log("[cam-assemble] error:", (e as Error).message);
      return { messages: [], estimatedTokens: 0 };
    }
  }

  /** compact 不需要实现 — CAM 不做上下文压缩 */
  async compact(): Promise<any> {
    return { ok: true, compacted: false, reason: "CAM does not manage compaction" };
  }

  /** 辅助：从 AgentMessage 提取文本内容 */
  private extractTextContent(message: any): string {
    if (!message) return "";
    if (typeof message.content === "string") return message.content;
    if (Array.isArray(message.content)) {
      return message.content
        .filter((p: any) => p.type === "text")
        .map((p: any) => p.text || "")
        .join("\n");
    }
    return String(message.content || "");
  }

  /** 格式化匹配结果为 Markdown */
  private formatMatches(matches: DaemonResponse["matches"]): string {
    if (!matches) return "";
    const lines: string[] = [];
    for (const m of matches!) {
      lines.push(`- **[${m.name}]** (${m.page}): ${m.preview || m.content_snippet?.slice(0, 150)}`);
    }
    return lines.join("\n");
  }

  /** 格式化匹配结果用于 prompt 注入 */
  private formatMatchesForPrompt(matches: DaemonResponse["matches"], query: string): string {
    const parts: string[] = [
      "",
      "---",
      "<cam-memory>",
      `<!-- CAM memory recall for: "${query.slice(0, 80)}" -->`,
    ];
    for (const m of matches!.slice(0, 5)) {
      const preview = m.preview || m.content_snippet?.slice(0, 200) || "";
      parts.push(`**${m.name}**: ${preview}`);
    }
    parts.push("</cam-memory>", "");
    return parts.join("\n");
  }

  /** 获取最后一次查询结果（供 Tool 使用） */
  getLastRecall(): string | null {
    return this.lastQueryResult;
  }
}

// ============================================================
// Tool 定义 — Agent 主动调用
// ============================================================

/** cam_query: 搜索 Wiki 知识库 */
function createCamQueryTool(daemonUrl: string) {
  return {
    name: "cam_query",
    label: "CAM Query",
    description:
      "Search the CAM knowledge base (Wiki) for relevant facts, decisions, preferences, or knowledge. " +
      "Returns structured results from the agent's long-term memory store.",
    parameters: {
      type: "object" as const,
      properties: {
        query: {
          type: "string",
          description: "Search query for the knowledge base",
        },
        top_k: {
          type: "number",
          description: "Number of results to return (default: 5)",
          minimum: 1,
          maximum: 20,
        },
      },
      required: ["query"],
    },
    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const q = String(params.query || "").trim();
      if (!q) return jsonToolResult({ error: "query is required" });
      const k = typeof params.top_k === "number" ? params.top_k : 5;

      const result = await daemonGet("/query", { q, top_k: String(k) });
      if (!result) return jsonToolResult({ error: "CAM daemon is offline" });

      const lines: string[] = [
        "## CAM Knowledge Base Results",
        `**Query:** \`${q}\``,
        `**Found:** ${result.results_found || result.matches?.length || 0} match(es)`,
        "",
      ];

      if (result.matches?.length) {
        for (const m of result.matches) {
          lines.push(`### ${m.name}`);
          lines.push(`**Page:** ${m.page}`);
          lines.push(m.content_snippet || m.preview || "(no preview)");
          lines.push("");
        }
      } else {
        lines.push("No matching facts found.");
      }

      return jsonToolResult({ content: lines.join("\n"), count: result.matches?.length || 0 });
    },
  };
}

/** cam_stats: 获取统计面板 */
function createCamStatsTool() {
  return {
    name: "cam_stats",
    label: "CAM Stats",
    description: "Get CAM memory engine statistics including fact counts, storage size, and health status.",
    parameters: {
      type: "object" as const,
      properties: {},
    },
    async execute() {
      const result = await daemonGet("/stats");
      if (!result) return jsonToolResult({ error: "CAM daemon is offline" });

      return jsonToolResult({
        content: [
          "## CAM Memory Stats",
          `**Status:** ${result.status || "unknown"}`,
          `**Facts:** ${(result as any).total_facts || 0}`,
          `**Pages:** ${(result as any).total_pages || 0}`,
          `**Daemon:** online`,
        ].join("\n"),
        raw: result,
      });
    },
  };
}

/** cam_ingest: 手动摄入内容 */
function createCamIngestTool() {
  return {
    name: "cam_ingest",
    label: "CAM Ingest",
    description:
      "Manually ingest text content into the CAM knowledge base for future retrieval. " +
      "Use this to store important information that should be remembered across sessions.",
    parameters: {
      type: "object" as const,
      properties: {
        content: {
          type: "string",
          description: "Text content to store in the knowledge base",
        },
        source: {
          type: "string",
          description: "Source identifier (optional, e.g., 'user-note', 'document')",
        },
      },
      required: ["content"],
    },
    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const content = String(params.content || "").trim();
      if (!content) return jsonToolResult({ error: "content is required" });

      const source = String(params.source || "manual");

      const result = await daemonPost("/ingest", {
        content,
        source,
        agent_id: "openclaw-manual",
      });

      if (!result) return jsonToolResult({ error: "CAM daemon is offline" });

      return jsonToolResult({
        content: `CAM ingested "${source}": ${result.status}`,
        written: result.facts_written || 0,
      });
    },
  };
}

/** cam_extract_file: 文件/图片/文档 → LLM提取 → 存入wiki */
function createCamExtractFileTool(daemonUrl: string) {
  return {
    name: "cam_extract_file",
    label: "CAM Extract File",
    description:
      "Extract key information from a file, image, or document using LLM analysis, " +
      "then automatically store the extracted knowledge into the CAM Wiki knowledge base. " +
      "Use this when the user shares a project file, image, PDF, or document that contains " +
      "valuable information worth remembering — such as design decisions, requirements, " +
      "architecture notes, user preferences, or technical specifications.",
    parameters: {
      type: "object" as const,
      properties: {
        file_path: {
          type: "string",
          description: "Absolute path to the file/image/document to analyze",
        },
        file_content: {
          type: "string",
          description: "Text content of the file (if already read). Use this instead of file_path when available.",
        },
        description: {
          type: "string",
          description: "Brief description of what the file is and why it matters (helps extraction accuracy).",
        },
        context: {
          type: "string",
          description: "Additional conversation context about this file (what was discussed around it).",
        },
      },
      required: ["file_path"],
    },
    async execute(_toolCallId: string, params: Record<string, unknown>) {
      const filePath = String(params.file_path || "").trim();
      if (!filePath) return jsonToolResult({ error: "file_path is required" });

      const description = String(params.description || "");
      const context = String(params.context || "");

      // 发送给 daemon 的 /hook 端点，带 extracted_facts 标记
      // daemon 会走 Agent-Native 模式：直接存储，不重复做 LLM 提取
      const result = await daemonPost("/hook", {
        user_message: `User shared a file: ${filePath}${description ? `\nDescription: ${description}` : ""}${context ? `\nContext: ${context}` : ""}`,
        ai_response: "",
        agent_id: "openclaw-file-extract",
        session_id: "file-extraction",
        metadata: {
          source_type: "file_extraction",
          file_path: filePath,
          file_description: description,
          conversation_context: context,
        },
      }, daemonUrl);

      if (!result) {
        // Daemon offline but we should still tell the agent what happened
        return jsonToolResult({
          content: `[CAM] File extraction queued for: ${filePath}\n(Daemon offline — will retry when back)`,
          queued: true,
        });
      }

      return jsonToolResult({
        content: [
          `## CAM File Extraction`,
          `**File:** ${filePath}`,
          `**Status:** ${result.status}`,
          result.facts_written ? `**Facts stored:** ${result.facts_written}` : "",
          result.throttled ? `*(Throttled: ${result.message})*` : "",
        ].filter(Boolean).join("\n"),
        factsWritten: result.facts_written || 0,
        throttled: result.throttled || false,
      });
    },
  };
}

/** Helper: format tool output */
function jsonToolResult(data: Record<string, unknown>) {
  return {
    content: data.content
      ? [{ type: "text" as const, text: String(data.content) }]
      : [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
    details: data,
  };
}

// ============================================================
// Hook 处理器 — 补充层
// ============================================================

let _cachedUserMsg = "";
let _cachedUserTs = 0;
const CACHE_TTL_MS = 5 * 60 * 1000;

/**
 * before_prompt_build: 补充注入文件处理指令
 * ContextEngine.assemble() 已经负责了记忆召回，
 * 这里额外添加关于文件提取的提示
 */
export function handleBeforePromptBuild(
  ctx: any & { config?: Record<string, unknown> },
): { prependSystemContext?: string } {
  const config = ctx.config ? resolveConfig(ctx.config) : resolveConfig({});
  if (!config.injectOnPrompt) return {};

  return {
    prependSystemContext: [
      "",
      "<cam-instructions>",
      "When the user sends you a file, image, document, or project artifact that contains important information:",
      "1. Read and understand its contents",
      "2. Use the `cam_extract_file` tool to extract and store key knowledge into the Wiki",
      "3. This includes: design decisions, architecture choices, user preferences, requirements, tech specs, code patterns worth remembering",
      "</cam-instructions>",
      "",
    ].join("\n"),
  };
}

/** message_received: 缓存用户消息 */
export function handleMessageReceived(ctx: any): void {
  const msg =
    ctx.userMessage ||
    ctx.bodyForAgent ||
    ctx.event?.content ||
    (ctx.event && typeof ctx.event === "object" && "content" in ctx.event ? ctx.event.content : "") ||
    "";
  if (msg && typeof msg === "string" && msg.length > 10) {
    _cachedUserMsg = msg;
    _cachedUserTs = Date.now();
  }
}

/**
 * llm_output: 检测是否有文件/图片被讨论 → 触发自动提取
 * 注意：大部分存储工作已由 ContextEngine.ingest() 完成，
 * 这里只做额外的文件检测和补充存储
 */
export async function handleLlmOutput(
  ctx: any & { config?: Record<string, unknown>; aiResponse?: string },
): Promise<void> {
  try {
    const config = ctx.config ? resolveConfig(ctx.config) : resolveConfig({});
    if (!config.extractOnOutput) return;

    const aiResponse = ctx.aiResponse || ctx.lastAssistant || "";
    if (!aiResponse || aiResponse.length < 20) return;

    // 检测 AI 回复中是否涉及文件分析
    const fileIndicators = /\.(ts|js|py|json|yaml|yml|md|txt|pdf|png|jpg|jpeg|svg|csv|xlsx|docx)[`'\"\s]|file.*path|image.*content|document/i;
    const hasFileReference = fileIndicators.test(aiResponse);

    if (hasFileReference) {
      const userMsg = getCachedUserMsg();
      const result = await daemonPost("/hook", {
        user_message: userMsg || "",
        ai_response: aiResponse,
        agent_id: "openclaw-auto-extract",
        session_id: process.env.OPENCLAW_SESSION_ID || "",
        metadata: {
          source_type: "auto_file_detection",
          detected_at: new Date().toISOString(),
        },
      }, config.daemonUrl);

      if (result?.facts_written) {
        console.log(`[cam-auto] 🧠 ${result.facts_written} fact(s) from file discussion`);
      }
    }
  } catch (_) {}
}

function getCachedUserMsg(): string {
  if (!_cachedUserMsg || Date.now() - _cachedUserTs > CACHE_TTL_MS) return "";
  return _cachedUserMsg;
}

// ============================================================
// 插件注册入口
// ============================================================

const camPlugin = {
  id: "cam",
  version: "4.0.0",

  resolveConfig(env: Record<string, string>, value: Record<string, unknown>): Record<string, unknown> {
    const raw = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    return {
      ...raw,
      daemonUrl: (raw.daemonUrl as string) || env.CAM_DAEMON_URL || DAEMON_URL,
    };
  },

  register(api: OpenClawPluginApi): void {
    const config = resolveConfig(api.config);
    const engine = new CamContextEngine(config);

    // ── Layer 1: ContextEngine (框架自动调用) ──
    api.registerContextEngine("cam", () => engine);

    // ── Layer 2: Tools (Agent 主动调用) ──
    api.registerTool(() => createCamQueryTool(config.daemonUrl));
    api.registerTool(() => createCamStatsTool());
    api.registerTool(() => createCamIngestTool());
    api.registerTool(() => createCamExtractFileTool(config.daemonUrl));

    // ── Layer 3: Hooks (补充) ──
    api.on("before_prompt_build", () =>
      handleBeforePromptBuild(config as any),
    );
    api.on("message_received", (event: any) => {
      handleMessageReceived(event);
    });
    api.on("llm_output", (event: any) => {
      handleLlmOutput(event);
    });

    console.log(`[cam] Plugin v4 loaded (ContextEngine mode)`);
    console.log(`[cam] daemon=${config.daemonUrl}`);
    console.log(`[cam] tools: cam_query, cam_stats, cam_ingest, cam_extract_file`);
    console.log(`[cam] hooks: before_prompt_build, message_received, llm_output`);
  },
};

export default camPlugin;
