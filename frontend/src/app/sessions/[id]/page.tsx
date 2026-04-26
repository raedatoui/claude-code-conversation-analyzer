"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import GradeBadge from "@/components/GradeBadge";
import Header from "@/components/Header";
import SearchFilter from "@/components/SearchFilter";
import SessionMessageList from "@/components/SessionMessageList";
import TokenChart from "@/components/TokenChart";
import { MESSAGE_LABEL_COLORS } from "@/lib/constants";
import {
    formatCost,
    formatDateTime,
    formatTokens,
    getCostColor,
} from "@/lib/utils";
import type { ConversationMessage, SessionDetail } from "@/lib/types";

export default function SessionPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const urlParams = useSearchParams();
    const urlQ = urlParams.get("q") ?? "";
    const urlMsg = urlParams.get("msg");
    const scrollToIndex = urlMsg !== null ? Number(urlMsg) : null;

    const [session, setSession] = useState<SessionDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());

    useEffect(() => {
        fetch(`/api/session/${encodeURIComponent(id)}`)
            .then(res => {
                if (!res.ok)
                    throw new Error(`Session not found (${res.status})`);
                return res.json();
            })
            .then(setSession)
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, [id]);

    // Deep links from /search carry q= for highlight + msg= for scroll. We
    // don't auto-populate the filter box so the user sees the match in
    // context rather than a 1-message filtered list.
    const highlightTerm = search.trim() || urlQ;

    const { filteredMessages, originalIndices } = useMemo(() => {
        const out: ConversationMessage[] = [];
        const idxs: number[] = [];
        if (!session?.messages)
            return { filteredMessages: out, originalIndices: idxs };
        const lower = search.trim().toLowerCase();
        session.messages.forEach((m, i) => {
            if (
                typeFilter.size > 0 &&
                !typeFilter.has(m.message_label || "OTHER")
            )
                return;
            if (lower && !m.content.toLowerCase().includes(lower)) return;
            out.push(m);
            idxs.push(i);
        });
        return { filteredMessages: out, originalIndices: idxs };
    }, [session, search, typeFilter]);

    const typeCounts = useMemo(() => {
        if (!session?.messages) return {};
        const counts: Record<string, number> = {};
        for (const msg of session.messages) {
            const label = msg.message_label || "OTHER";
            counts[label] = (counts[label] || 0) + 1;
        }
        return counts;
    }, [session]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-text-secondary animate-pulse">
                    Loading session...
                </div>
            </div>
        );
    }

    if (error || !session) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center gap-4">
                <div className="text-danger text-lg">
                    {error ?? "Session not found"}
                </div>
                <a
                    href="/"
                    className="text-accent hover:text-accent-hover transition-colors"
                >
                    Back to dashboard
                </a>
            </div>
        );
    }

    const cm = session.cost_metrics;
    const qm = session.quality_metrics;
    const cd = session.compaction_data;

    return (
        <div className="min-h-screen flex flex-col">
            <Header
                title={session.title}
                backHref={`/projects/${session.project_id}`}
                subtitle={
                    <>
                        <a
                            href={`/projects/${session.project_id}`}
                            className="hover:text-accent transition-colors"
                        >
                            {session.project_name}
                        </a>
                        {" · "}
                        {formatDateTime(session.start_time)}
                    </>
                }
            >
                {qm?.grade && (
                    <GradeBadge
                        grade={qm.grade}
                        score={qm.overall_score ?? undefined}
                    />
                )}
            </Header>

            <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-6 space-y-6">
                {/* Metric cards */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <MetricCard
                        label="Cost"
                        value={formatCost(cm.total_cost)}
                        valueClass={getCostColor(cm.total_cost)}
                    />
                    <MetricCard label="Model" value={cm.primary_model} />
                    <MetricCard
                        label="Duration"
                        value={
                            session.duration_minutes != null
                                ? `${session.duration_minutes.toFixed(0)} min`
                                : "N/A"
                        }
                    />
                    <MetricCard
                        label="Tokens"
                        value={`${formatTokens(cm.input_tokens)} in / ${formatTokens(cm.output_tokens)} out`}
                    />
                    <MetricCard
                        label="Messages"
                        value={session.messages.length.toString()}
                    />
                </div>

                {/* Token progression chart */}
                <div>
                    <h2 className="text-sm font-medium text-text-secondary mb-2 uppercase tracking-wider">
                        Token Progression
                    </h2>
                    <TokenChart compactionData={cd} />
                    {cd?.compaction_events &&
                        cd.compaction_events.length > 0 && (
                            <div className="mt-2 flex items-center gap-3 text-xs text-text-secondary">
                                <span className="flex items-center gap-1">
                                    <span className="w-3 h-0.5 bg-amber-500 inline-block" />{" "}
                                    Compaction
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="w-3 h-0.5 bg-red-500 inline-block" />{" "}
                                    Cache Read
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="w-3 h-0.5 bg-blue-500 inline-block" />{" "}
                                    Input
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="w-3 h-0.5 bg-green-500 inline-block" />{" "}
                                    Output
                                </span>
                            </div>
                        )}
                </div>

                {/* Search + messages */}
                <div>
                    <div className="flex items-center gap-3 mb-3 flex-wrap">
                        <h2 className="text-sm font-medium text-text-secondary uppercase tracking-wider">
                            Transcript
                        </h2>
                        <span className="text-xs text-text-secondary">
                            {search.trim() || typeFilter.size > 0
                                ? `${filteredMessages.length} of ${session.messages.length} messages`
                                : `${session.messages.length} messages`}
                        </span>
                        <div className="flex items-center gap-1.5">
                            {Object.entries(typeCounts).map(
                                ([label, count]) => {
                                    const active =
                                        typeFilter.size === 0 ||
                                        typeFilter.has(label);
                                    const colors =
                                        MESSAGE_LABEL_COLORS[label] ??
                                        MESSAGE_LABEL_COLORS.META;
                                    return (
                                        <button
                                            type="button"
                                            key={label}
                                            onClick={() => {
                                                setTypeFilter(prev => {
                                                    const next = new Set(prev);
                                                    if (next.has(label)) {
                                                        next.delete(label);
                                                    } else {
                                                        next.add(label);
                                                    }
                                                    return next;
                                                });
                                            }}
                                            className={`text-xs px-2 py-0.5 rounded-full font-medium cursor-pointer transition-opacity ${colors.bg} ${colors.text} ${active ? "opacity-100" : "opacity-35"}`}
                                        >
                                            {label} {count}
                                        </button>
                                    );
                                }
                            )}
                        </div>
                    </div>
                    <div className="mb-3">
                        <SearchFilter
                            value={search}
                            onChange={setSearch}
                            placeholder="Search messages..."
                        />
                    </div>
                    <div className="bg-raised rounded-lg p-3">
                        <SessionMessageList
                            messages={filteredMessages}
                            originalIndices={originalIndices}
                            searchTerm={highlightTerm}
                            scrollToIndex={scrollToIndex}
                        />
                    </div>
                </div>
            </main>
        </div>
    );
}

function MetricCard({
    label,
    value,
    valueClass = "",
}: {
    label: string;
    value: string;
    valueClass?: string;
}) {
    return (
        <div className="bg-surface border border-border rounded-lg p-5">
            <p className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">
                {label}
            </p>
            <p
                className={`text-lg font-bold font-mono break-words ${valueClass}`}
            >
                {value}
            </p>
        </div>
    );
}
