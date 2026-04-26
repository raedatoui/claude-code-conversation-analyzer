import { NextResponse } from "next/server";
import {
    type CostRow,
    decompressContent,
    determineLabel,
    extractText,
    type FallbackMessageRow,
    type MessageRow,
    openDb,
    type QualityRow,
    type SessionRow,
    tableExists,
    truncate,
} from "../../db";
import type {
    CompactionData,
    ConversationMessage,
    QualityMetrics,
    SessionDetail,
} from "@/lib/types";

interface FallbackSessionRow {
    session_id: string;
    project_id: number;
    title: string | null;
    first_timestamp: string | null;
    last_timestamp: string | null;
    duration_minutes: number | null;
    message_count: number | null;
    total_input_tokens: number | null;
    total_output_tokens: number | null;
    total_cache_creation_tokens: number | null;
    total_cache_read_tokens: number | null;
    total_cost: number | null;
}

interface ProjectRow {
    id: number;
    project_path: string;
}

interface FallbackProjectRow {
    id: number;
    display_name: string;
}

export async function GET(
    _request: Request,
    { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
    const { id } = await params;

    let db: ReturnType<typeof openDb>;
    try {
        db = openDb();
    } catch {
        return NextResponse.json(
            { error: "Cannot open database" },
            { status: 500 }
        );
    }

    try {
        // Try cclog sessions table first
        const session = db
            .prepare("SELECT * FROM sessions WHERE session_id = ?")
            .get(id) as SessionRow | undefined;

        if (session) {
            return NextResponse.json(buildCclogSession(db, session, id));
        }

        // Try fallback sessions
        if (tableExists(db, "fallback_sessions")) {
            const fbSession = db
                .prepare("SELECT * FROM fallback_sessions WHERE session_id = ?")
                .get(id) as FallbackSessionRow | undefined;

            if (fbSession) {
                return NextResponse.json(
                    buildFallbackSession(db, fbSession, id)
                );
            }
        }

        db.close();
        return NextResponse.json(
            { error: "Session not found" },
            { status: 404 }
        );
    } catch (err) {
        db.close();
        const message = err instanceof Error ? err.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}

function buildCclogSession(
    db: ReturnType<typeof openDb>,
    session: SessionRow,
    sid: string
): SessionDetail {
    const hasCosts = tableExists(db, "session_costs");
    const hasQuality = tableExists(db, "session_quality");

    // Look up project name
    const project = db
        .prepare("SELECT id, project_path FROM projects WHERE id = ?")
        .get(session.project_id) as ProjectRow | undefined;
    const pathParts = (project?.project_path ?? "").split("/");
    const projectName = pathParts[pathParts.length - 1] ?? "unknown";

    // Cost data
    let cost: CostRow | undefined;
    if (hasCosts) {
        cost = db
            .prepare("SELECT * FROM session_costs WHERE session_id = ?")
            .get(sid) as CostRow | undefined;
    }

    // Quality data
    let quality: QualityRow | undefined;
    if (hasQuality) {
        quality = db
            .prepare("SELECT * FROM session_quality WHERE session_id = ?")
            .get(sid) as QualityRow | undefined;
    }

    const sInput = session.total_input_tokens ?? 0;
    const sOutput = session.total_output_tokens ?? 0;
    const sCacheCreation = session.total_cache_creation_tokens ?? 0;
    const sCacheRead = session.total_cache_read_tokens ?? 0;
    const sCost = cost?.total_cost ?? 0;
    const msgCount = session.message_count ?? 1;

    // Build quality metrics
    let qm: QualityMetrics | null = null;
    let compactionData: CompactionData | null = null;

    if (quality) {
        qm = {
            overall_score: quality.overall_score ?? 0,
            grade: quality.grade ?? "F",
            query_specificity_score: quality.query_specificity_score ?? 0,
            context_utilization_score: quality.context_utilization_score ?? 0,
            prompt_efficiency_score: quality.prompt_efficiency_score ?? 0,
            vague_queries_count: quality.vague_queries_count ?? 0,
            specific_queries_count: quality.specific_queries_count ?? 0,
            redundant_requests_count: quality.redundant_requests_count ?? 0,
            cache_read_millions: quality.cache_read_millions ?? null,
            cache_read_severity: quality.cache_read_severity ?? null,
            cache_score: quality.cache_score ?? null,
            length_severity: quality.length_severity ?? null,
            length_score: quality.length_score ?? null,
            message_count: quality.message_count ?? null,
        };

        compactionData = {
            compaction_count: quality.compaction_count ?? 0,
            should_have_compacted: !!quality.should_have_compacted,
            messages_per_compaction: 0,
            compaction_events: quality.compaction_events
                ? JSON.parse(quality.compaction_events)
                : [],
            token_progression: quality.token_progression
                ? JSON.parse(quality.token_progression)
                : [],
        };
    }

    // Read ALL messages — no truncation
    const rawMsgs = db
        .prepare(
            "SELECT type, timestamp, _is_meta, _parent_uuid, content FROM messages WHERE session_id = ? ORDER BY timestamp ASC"
        )
        .all(sid) as MessageRow[];

    const messages: ConversationMessage[] = [];
    const userPrompts: string[] = [];

    for (const m of rawMsgs) {
        const content = decompressContent(m.content);
        const rawContent =
            content.content ??
            (content.message as Record<string, unknown> | null)?.content ??
            "";
        const text = extractText(rawContent);
        const isMeta = !!m._is_meta;
        const label = determineLabel(m.type, isMeta, text, rawContent);

        messages.push({
            type: m.type,
            content: text,
            timestamp: m.timestamp,
            message_label: label,
            is_meta: isMeta,
        });

        if (m.type === "user" && !isMeta && !m._parent_uuid && text.trim()) {
            userPrompts.push(text);
        }
    }

    const title =
        userPrompts.length > 0
            ? truncate(userPrompts[0].replace(/\s+/g, " "), 100)
            : (session.summary ?? `Session ${sid.slice(0, 8)}`);

    let durationMinutes: number | null = null;
    if (session.first_timestamp && session.last_timestamp) {
        const start = new Date(session.first_timestamp).getTime();
        const end = new Date(session.last_timestamp).getTime();
        if (!Number.isNaN(start) && !Number.isNaN(end)) {
            durationMinutes = (end - start) / 60000;
        }
    }

    db.close();

    return {
        session_id: sid,
        title,
        project_id: project?.id ?? 0,
        project_name: projectName,
        start_time: session.first_timestamp,
        duration_minutes: durationMinutes,
        cost_metrics: {
            total_cost: sCost,
            cost_per_message: cost?.cost_per_message ?? 0,
            total_tokens: sInput + sOutput,
            average_tokens_per_message:
                (sInput + sOutput) / Math.max(msgCount, 1),
            input_tokens: sInput,
            output_tokens: sOutput,
            primary_model: cost?.primary_model ?? "unknown",
            cache_creation_tokens: sCacheCreation,
            cache_read_tokens: sCacheRead,
        },
        quality_metrics: qm,
        compaction_data: compactionData,
        messages,
    };
}

function buildFallbackSession(
    db: ReturnType<typeof openDb>,
    session: FallbackSessionRow,
    sid: string
): SessionDetail {
    // Look up project name
    const fbProj = db
        .prepare("SELECT id, display_name FROM fallback_projects WHERE id = ?")
        .get(session.project_id) as FallbackProjectRow | undefined;
    const projectName = fbProj?.display_name ?? "unknown";

    const sInput = session.total_input_tokens ?? 0;
    const sOutput = session.total_output_tokens ?? 0;
    const sCacheCreation = session.total_cache_creation_tokens ?? 0;
    const sCacheRead = session.total_cache_read_tokens ?? 0;
    const sCost = session.total_cost ?? 0;
    const msgCount = session.message_count ?? 1;

    // Read fallback messages — no truncation
    let messages: ConversationMessage[] = [];
    if (tableExists(db, "fallback_messages")) {
        const fbMsgs = db
            .prepare(
                "SELECT type, message_label, timestamp, content, is_meta FROM fallback_messages WHERE session_id = ? AND project_id = ?"
            )
            .all(sid, session.project_id) as FallbackMessageRow[];

        messages = fbMsgs.map(m => ({
            type: m.type,
            content: m.content,
            timestamp: m.timestamp,
            message_label: m.message_label ?? m.type.toUpperCase(),
            is_meta: !!m.is_meta,
        }));
    }

    const userPrompts = messages
        .filter(m => m.type === "user" && !m.is_meta && m.content.trim())
        .map(m => m.content);

    const title =
        session.title ??
        (userPrompts.length > 0
            ? truncate(userPrompts[0].replace(/\s+/g, " "), 100)
            : `Session ${sid.slice(0, 8)}`);

    db.close();

    return {
        session_id: sid,
        title,
        project_id: -session.project_id,
        project_name: projectName,
        start_time: session.first_timestamp,
        duration_minutes: session.duration_minutes,
        cost_metrics: {
            total_cost: sCost,
            cost_per_message: sCost / Math.max(msgCount, 1),
            total_tokens: sInput + sOutput,
            average_tokens_per_message:
                (sInput + sOutput) / Math.max(msgCount, 1),
            input_tokens: sInput,
            output_tokens: sOutput,
            primary_model: "unknown",
            cache_creation_tokens: sCacheCreation,
            cache_read_tokens: sCacheRead,
        },
        quality_metrics: null,
        compaction_data: null,
        messages,
    };
}
