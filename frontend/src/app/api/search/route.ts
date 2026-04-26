import { NextResponse } from "next/server";
import { openDb, tableExists } from "../db";

interface FtsRow {
    session_id: string;
    project_id: number;
    message_index: number;
    timestamp: string | null;
    snippet: string;
    project_path: string | null;
    session_first_timestamp: string | null;
}

interface SnippetSegment {
    text: string;
    match: boolean;
}

interface SearchResult {
    session_id: string;
    project_id: number;
    project_name: string;
    message_index: number;
    timestamp: string | null;
    session_first_timestamp: string | null;
    snippet: SnippetSegment[];
}

/**
 * Sentinels passed to FTS5's snippet() to wrap matched tokens. We split on
 * these in JS to build a React-safe segment list. Chosen to be a combination
 * of characters extremely unlikely to appear in user prompts — if they
 * somehow do, the worst case is a misplaced highlight, not XSS, because the
 * frontend renders text (not HTML).
 */
const MARK_OPEN = "FTS_MATCH_OPEN";
const MARK_CLOSE = "FTS_MATCH_CLOSE";

function sanitizeQuery(raw: string): string {
    const cleaned = raw.replace(/["()*:]/g, " ").trim();
    if (!cleaned) return "";
    return `"${cleaned}"`;
}

function projectNameFromPath(path: string | null): string {
    if (!path) return "unknown";
    const parts = path.split("/");
    return parts[parts.length - 1] ?? path;
}

function splitSnippet(raw: string): SnippetSegment[] {
    const segments: SnippetSegment[] = [];
    let rest = raw;
    while (rest.length > 0) {
        const openIdx = rest.indexOf(MARK_OPEN);
        if (openIdx === -1) {
            segments.push({ text: rest, match: false });
            break;
        }
        if (openIdx > 0) {
            segments.push({ text: rest.slice(0, openIdx), match: false });
        }
        const afterOpen = rest.slice(openIdx + MARK_OPEN.length);
        const closeIdx = afterOpen.indexOf(MARK_CLOSE);
        if (closeIdx === -1) {
            // Malformed — treat remainder as plain text
            segments.push({ text: afterOpen, match: false });
            break;
        }
        segments.push({
            text: afterOpen.slice(0, closeIdx),
            match: true,
        });
        rest = afterOpen.slice(closeIdx + MARK_CLOSE.length);
    }
    return segments;
}

export async function GET(request: Request): Promise<NextResponse> {
    const url = new URL(request.url);
    const q = (url.searchParams.get("q") ?? "").trim();
    const limitRaw = Number(url.searchParams.get("limit") ?? "50");
    const limit =
        Number.isFinite(limitRaw) && limitRaw > 0 && limitRaw <= 200
            ? Math.floor(limitRaw)
            : 50;

    if (!q) {
        return NextResponse.json(
            { error: "Missing query parameter 'q'" },
            { status: 400 }
        );
    }

    const matchExpr = sanitizeQuery(q);
    if (!matchExpr) {
        return NextResponse.json({ results: [], indexed: true });
    }

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
        if (!tableExists(db, "user_prompts_fts")) {
            db.close();
            return NextResponse.json({ results: [], indexed: false });
        }

        const rows = db
            .prepare(
                `SELECT
                    f.session_id,
                    f.project_id,
                    f.message_index,
                    f.timestamp,
                    snippet(user_prompts_fts, 0, ?, ?, '…', 16) AS snippet,
                    p.project_path AS project_path,
                    s.first_timestamp AS session_first_timestamp
                FROM user_prompts_fts f
                LEFT JOIN projects p ON p.id = f.project_id
                LEFT JOIN sessions s ON s.session_id = f.session_id
                WHERE user_prompts_fts MATCH ?
                ORDER BY rank
                LIMIT ?`
            )
            .all(MARK_OPEN, MARK_CLOSE, matchExpr, limit) as FtsRow[];

        const results: SearchResult[] = rows.map(r => ({
            session_id: r.session_id,
            project_id: r.project_id,
            project_name: projectNameFromPath(r.project_path),
            message_index: r.message_index,
            timestamp: r.timestamp,
            session_first_timestamp: r.session_first_timestamp,
            snippet: splitSnippet(r.snippet),
        }));

        db.close();
        return NextResponse.json({ results, indexed: true });
    } catch (err) {
        db.close();
        const message = err instanceof Error ? err.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
