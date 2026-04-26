import { NextResponse } from "next/server";
import {
    type CostRow,
    findFirstUserPrompt,
    openDb,
    type QualityRow,
    type SessionRow,
    tableExists,
    truncate,
} from "../db";
import type {
    AnalysisData,
    CompactionData,
    Conversation,
    OverallMetrics,
    Project,
    ProjectMetrics,
    QualityMetrics,
} from "@/lib/types";

interface ProjectRow {
    id: number;
    project_path: string;
}

interface FallbackProjectRow {
    id: number;
    project_path: string;
    display_name: string;
    total_cost: number;
    earliest_timestamp: string | null;
    latest_timestamp: string | null;
}

interface FallbackSessionRow {
    session_id: string;
    title: string | null;
    first_timestamp: string | null;
    last_timestamp: string | null;
    duration_minutes: number | null;
    message_count: number | null;
    cwd: string | null;
    total_input_tokens: number | null;
    total_output_tokens: number | null;
    total_cache_creation_tokens: number | null;
    total_cache_read_tokens: number | null;
    total_cost: number | null;
}

export async function GET(): Promise<NextResponse> {
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
        const hasCosts = tableExists(db, "session_costs");
        const hasQuality = tableExists(db, "session_quality");
        const hasFallbackProjects = tableExists(db, "fallback_projects");
        const hasFallbackSessions = tableExists(db, "fallback_sessions");
        const hasFallbackMessages = tableExists(db, "fallback_messages");

        // 1. Read all cclog projects
        const projects = db
            .prepare("SELECT id, project_path FROM projects")
            .all() as ProjectRow[];

        // 2. Read all sessions
        const allSessions = db
            .prepare("SELECT * FROM sessions")
            .all() as SessionRow[];
        const sessionsByProject = new Map<number, SessionRow[]>();
        for (const s of allSessions) {
            const list = sessionsByProject.get(s.project_id) ?? [];
            list.push(s);
            sessionsByProject.set(s.project_id, list);
        }

        // 3. Read costs and quality in bulk
        const costsBySession = new Map<string, CostRow>();
        if (hasCosts) {
            const costs = db
                .prepare("SELECT * FROM session_costs")
                .all() as CostRow[];
            for (const c of costs) costsBySession.set(c.session_id, c);
        }

        const qualityBySession = new Map<string, QualityRow>();
        if (hasQuality) {
            const qualities = db
                .prepare("SELECT * FROM session_quality")
                .all() as QualityRow[];
            for (const q of qualities) qualityBySession.set(q.session_id, q);
        }

        // 4. Build project data
        const resultProjects: Project[] = [];
        let grandTotalCost = 0;
        let grandTotalConversations = 0;
        let grandTotalTokens = 0;
        let scoreSum = 0;
        let scoreCount = 0;

        for (const proj of projects) {
            const sessions = sessionsByProject.get(proj.id) ?? [];

            // Encoded dir name as stable URL key
            const projectName =
                proj.project_path.split("/").pop() ?? proj.project_path;

            // Derive actual CWD from most common session cwd
            const cwdCounts = new Map<string, number>();
            for (const s of sessions) {
                if (s.cwd)
                    cwdCounts.set(s.cwd, (cwdCounts.get(s.cwd) ?? 0) + 1);
            }
            let projectCwd: string | null = null;
            let maxCount = 0;
            for (const [cwd, count] of cwdCounts) {
                if (count > maxCount) {
                    maxCount = count;
                    projectCwd = cwd;
                }
            }
            const conversations: Conversation[] = [];

            let projCost = 0;
            let projTokens = 0;
            let projInput = 0;
            let projOutput = 0;
            let projScoreSum = 0;
            let projScoreCount = 0;
            const projIssues = 0;
            let dateMin: string | null = null;
            let dateMax: string | null = null;

            for (const session of sessions) {
                const sid = session.session_id;
                const cost = costsBySession.get(sid);
                const quality = qualityBySession.get(sid);

                const sInput = session.total_input_tokens ?? 0;
                const sOutput = session.total_output_tokens ?? 0;
                const sCacheCreation = session.total_cache_creation_tokens ?? 0;
                const sCacheRead = session.total_cache_read_tokens ?? 0;
                const sCost = cost?.total_cost ?? 0;

                projCost += sCost;
                projInput += sInput;
                projOutput += sOutput;
                projTokens += sInput + sOutput;

                if (session.first_timestamp) {
                    if (!dateMin || session.first_timestamp < dateMin)
                        dateMin = session.first_timestamp;
                    if (!dateMax || session.first_timestamp > dateMax)
                        dateMax = session.first_timestamp;
                }

                // Build quality metrics
                let qm: QualityMetrics | null = null;
                let compactionData: CompactionData | null = null;

                if (quality) {
                    const overallScore = quality.overall_score ?? 0;
                    projScoreSum += overallScore;
                    projScoreCount++;

                    qm = {
                        overall_score: overallScore,
                        grade: quality.grade ?? "F",
                        query_specificity_score:
                            quality.query_specificity_score ?? 0,
                        context_utilization_score:
                            quality.context_utilization_score ?? 0,
                        prompt_efficiency_score:
                            quality.prompt_efficiency_score ?? 0,
                        vague_queries_count: quality.vague_queries_count ?? 0,
                        specific_queries_count:
                            quality.specific_queries_count ?? 0,
                        redundant_requests_count:
                            quality.redundant_requests_count ?? 0,
                        cache_read_millions:
                            quality.cache_read_millions ?? null,
                        cache_read_severity:
                            quality.cache_read_severity ?? null,
                        cache_score: quality.cache_score ?? null,
                        length_severity: quality.length_severity ?? null,
                        length_score: quality.length_score ?? null,
                        message_count: quality.message_count ?? null,
                    };

                    const compEvents = quality.compaction_events
                        ? JSON.parse(quality.compaction_events)
                        : [];
                    const tokProg = quality.token_progression
                        ? JSON.parse(quality.token_progression)
                        : [];

                    compactionData = {
                        compaction_count: quality.compaction_count ?? 0,
                        should_have_compacted: !!quality.should_have_compacted,
                        messages_per_compaction: 0,
                        compaction_events: compEvents,
                        token_progression: tokProg,
                    };
                }

                // Build title from first actual USER prompt
                let title = session.summary ?? `Session ${sid.slice(0, 8)}`;
                const firstUserPrompt = findFirstUserPrompt(db, sid);
                if (firstUserPrompt) {
                    title = truncate(firstUserPrompt, 100);
                }

                // Calculate duration
                let durationMinutes: number | null = null;
                if (session.first_timestamp && session.last_timestamp) {
                    const start = new Date(session.first_timestamp).getTime();
                    const end = new Date(session.last_timestamp).getTime();
                    if (!Number.isNaN(start) && !Number.isNaN(end)) {
                        durationMinutes = (end - start) / 60000;
                    }
                }

                const msgCount = session.message_count ?? 1;

                conversations.push({
                    session_id: sid,
                    title,
                    start_time: session.first_timestamp,
                    duration_minutes: durationMinutes,
                    user_prompts: firstUserPrompt ? [firstUserPrompt] : [],
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
                    issues: [],
                    compaction_data: compactionData,
                });
            }

            // Sort conversations by date descending
            conversations.sort((a, b) =>
                (b.start_time ?? "").localeCompare(a.start_time ?? "")
            );

            const avgScore =
                projScoreCount > 0 ? projScoreSum / projScoreCount : 0;

            grandTotalCost += projCost;
            grandTotalConversations += conversations.length;
            grandTotalTokens += projTokens;
            scoreSum += avgScore;
            scoreCount++;

            const metrics: ProjectMetrics = {
                total_conversations: conversations.length,
                total_cost: projCost,
                total_tokens: projTokens,
                total_input_tokens: projInput,
                total_output_tokens: projOutput,
                average_score: avgScore,
                total_issues: projIssues,
                date_range_start: dateMin,
                date_range_end: dateMax,
            };

            resultProjects.push({
                id: proj.id,
                name: projectName,
                clean_name: projectName,
                path: projectCwd,
                conversations,
                metrics,
            });
        }

        // 6. Fallback projects
        if (hasFallbackProjects && hasFallbackSessions) {
            const fbProjects = db
                .prepare("SELECT * FROM fallback_projects")
                .all() as FallbackProjectRow[];

            for (const fbProj of fbProjects) {
                const fbSessions = db
                    .prepare(
                        "SELECT * FROM fallback_sessions WHERE project_id = ?"
                    )
                    .all(fbProj.id) as FallbackSessionRow[];

                const conversations: Conversation[] = [];
                let projCost = 0;
                let projTokens = 0;
                let projInput = 0;
                let projOutput = 0;

                for (const fbs of fbSessions) {
                    const sInput = fbs.total_input_tokens ?? 0;
                    const sOutput = fbs.total_output_tokens ?? 0;
                    const sCacheCreation = fbs.total_cache_creation_tokens ?? 0;
                    const sCacheRead = fbs.total_cache_read_tokens ?? 0;
                    const sCost = fbs.total_cost ?? 0;

                    projCost += sCost;
                    projInput += sInput;
                    projOutput += sOutput;
                    projTokens += sInput + sOutput;

                    // Build title from first fallback user message
                    let fbTitle =
                        fbs.title ?? `Session ${fbs.session_id.slice(0, 8)}`;
                    let fbFirstPrompt: string | null = null;
                    if (!fbs.title && hasFallbackMessages) {
                        const firstFb = db
                            .prepare(
                                "SELECT content FROM fallback_messages WHERE session_id = ? AND project_id = ? AND type = 'user' AND (is_meta = 0 OR is_meta IS NULL) ORDER BY timestamp ASC LIMIT 1"
                            )
                            .get(fbs.session_id, fbProj.id) as
                            | { content: string }
                            | undefined;
                        if (firstFb?.content?.trim()) {
                            fbFirstPrompt = firstFb.content.replace(
                                /\s+/g,
                                " "
                            );
                            fbTitle = truncate(fbFirstPrompt, 100);
                        }
                    }

                    const msgCount = fbs.message_count ?? 1;

                    conversations.push({
                        session_id: fbs.session_id,
                        title: fbTitle,
                        start_time: fbs.first_timestamp,
                        duration_minutes: fbs.duration_minutes,
                        user_prompts: fbFirstPrompt ? [fbFirstPrompt] : [],
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
                        issues: ["Fallback project"],
                        compaction_data: null,
                    });
                }

                conversations.sort((a, b) =>
                    (b.start_time ?? "").localeCompare(a.start_time ?? "")
                );

                grandTotalCost += projCost;
                grandTotalConversations += conversations.length;
                grandTotalTokens += projTokens;

                resultProjects.push({
                    id: -fbProj.id,
                    name: fbProj.display_name,
                    clean_name: fbProj.display_name,
                    path: fbProj.project_path ?? null,
                    conversations,
                    metrics: {
                        total_conversations: conversations.length,
                        total_cost: projCost,
                        total_tokens: projTokens,
                        total_input_tokens: projInput,
                        total_output_tokens: projOutput,
                        average_score: 0,
                        total_issues: 0,
                        date_range_start: fbProj.earliest_timestamp,
                        date_range_end: fbProj.latest_timestamp,
                    },
                });
            }
        }

        const overallMetrics: OverallMetrics = {
            total_projects: resultProjects.length,
            total_conversations: grandTotalConversations,
            total_cost: grandTotalCost,
            average_score: scoreCount > 0 ? scoreSum / scoreCount : 0,
            total_tokens: grandTotalTokens,
        };

        const data: AnalysisData = {
            projects: resultProjects,
            overall_metrics: overallMetrics,
            analysis_timestamp: new Date().toISOString(),
            generator_info: {
                tool: "cclog-db-api",
                version: "3.0.0",
                export_timestamp: new Date().toISOString(),
            },
        };

        db.close();
        return NextResponse.json(data);
    } catch (err) {
        db.close();
        const message = err instanceof Error ? err.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
