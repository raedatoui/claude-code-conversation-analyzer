import os from "node:os";
import path from "node:path";
import Database from "better-sqlite3";

export function getDbPath(): string {
    return (
        process.env.CCLOG_DB_PATH ??
        path.join(os.homedir(), ".claude/projects/claude-code-log-cache.db")
    );
}

export function openDb(): Database.Database {
    return new Database(getDbPath(), { readonly: true });
}

export function tableExists(db: Database.Database, name: string): boolean {
    const row = db
        .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name=?")
        .get(name) as { name: string } | undefined;
    return !!row;
}

export function decompressContent(
    blob: Buffer | null
): Record<string, unknown> {
    if (!blob) return {};
    try {
        const { inflateSync } = require("node:zlib");
        const decompressed = inflateSync(blob);
        return JSON.parse(decompressed.toString("utf-8"));
    } catch {
        return {};
    }
}

export function extractText(content: unknown): string {
    if (!content) return "";
    if (typeof content === "string") return content;
    if (Array.isArray(content)) {
        const parts: string[] = [];
        for (const item of content) {
            if (typeof item !== "object" || item === null) continue;
            const block = item as Record<string, unknown>;
            if (block.type === "text") parts.push((block.text as string) ?? "");
            else if (block.type === "tool_use")
                parts.push(`[Tool: ${block.name ?? "Unknown"}]`);
            else if (block.type === "tool_result")
                parts.push(String(block.content ?? ""));
        }
        return parts.join("\n");
    }
    return String(content);
}

export function determineLabel(
    msgType: string,
    isMeta: boolean,
    text: string,
    rawContent: unknown
): string {
    if (msgType === "assistant") return "ASSISTANT";
    if (isMeta) return "META";
    if (text.includes("<command-name>")) return "COMMAND";
    if (text.includes("<local-command-stdout>")) return "COMMAND_OUTPUT";
    if (Array.isArray(rawContent)) {
        for (const item of rawContent) {
            if (
                typeof item === "object" &&
                item !== null &&
                (item as Record<string, unknown>).type === "tool_result"
            )
                return "TOOL_RESULT";
        }
    }
    return "USER";
}

export function truncate(s: string, max: number): string {
    return s.length > max ? `${s.slice(0, max)}...` : s;
}

export interface SessionRow {
    session_id: string;
    project_id: number;
    first_timestamp: string | null;
    last_timestamp: string | null;
    message_count: number | null;
    cwd: string | null;
    total_input_tokens: number | null;
    total_output_tokens: number | null;
    total_cache_creation_tokens: number | null;
    total_cache_read_tokens: number | null;
    summary: string | null;
    first_user_message: string | null;
}

export interface CostRow {
    session_id: string;
    total_cost: number;
    cost_per_message: number;
    primary_model: string | null;
    model_breakdown: string | null;
}

export interface QualityRow {
    session_id: string;
    overall_score: number | null;
    grade: string | null;
    query_specificity_score: number | null;
    context_utilization_score: number | null;
    prompt_efficiency_score: number | null;
    vague_queries_count: number | null;
    specific_queries_count: number | null;
    redundant_requests_count: number | null;
    cache_read_millions: number | null;
    cache_read_severity: string | null;
    cache_score: number | null;
    length_severity: string | null;
    length_score: number | null;
    message_count: number | null;
    compaction_count: number | null;
    should_have_compacted: number | null;
    compaction_events: string | null;
    token_progression: string | null;
}

export interface MessageRow {
    type: string;
    timestamp: string | null;
    _is_meta: number | null;
    _parent_uuid: string | null;
    content: Buffer | null;
}

/**
 * Find the first actual USER prompt for a session by skipping
 * COMMAND, COMMAND_OUTPUT, TOOL_RESULT, and META messages.
 */
export function findFirstUserPrompt(
    db: Database.Database,
    sessionId: string
): string | null {
    const rows = db
        .prepare(
            "SELECT content, _is_meta FROM messages WHERE session_id = ? AND type = 'user' AND _parent_uuid IS NULL ORDER BY timestamp ASC LIMIT 10"
        )
        .all(sessionId) as {
        content: Buffer | null;
        _is_meta: number | null;
    }[];

    for (const row of rows) {
        if (row._is_meta) continue;
        const parsed = decompressContent(row.content);
        const rawContent =
            parsed.content ??
            (parsed.message as Record<string, unknown> | null)?.content ??
            "";
        const text = extractText(rawContent);
        const label = determineLabel("user", false, text, rawContent);
        if (label === "USER" && text.trim()) {
            return text.replace(/\s+/g, " ");
        }
    }
    return null;
}

export interface FallbackMessageRow {
    type: string;
    message_label: string | null;
    timestamp: string | null;
    content: string;
    is_meta: number;
}
