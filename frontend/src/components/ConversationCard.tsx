"use client";

import { useState } from "react";
import {
    formatCost,
    formatDateTime,
    formatTokens,
    getCostColor,
} from "@/lib/utils";
import MessageList from "./MessageList";
import TokenChart from "./TokenChart";
import type { Conversation } from "@/lib/types";

export default function ConversationCard({
    conversation,
}: {
    conversation: Conversation;
}) {
    const [expanded, setExpanded] = useState(false);
    const cm = conversation.cost_metrics;
    const qm = conversation.quality_metrics;
    const cd = conversation.compaction_data;

    return (
        <div className="bg-surface border border-border rounded-lg overflow-hidden hover:border-accent/50 transition-colors">
            {/* Collapsed header — always visible */}
            <button
                type="button"
                onClick={() => setExpanded(e => !e)}
                className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-raised/50 transition-colors cursor-pointer"
            >
                <svg
                    className={`w-4 h-4 text-text-secondary shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                    />
                </svg>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium truncate">
                            {conversation.title}
                        </span>
                        {cd && cd.compaction_count > 0 && (
                            <span className="shrink-0 text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                                {cd.compaction_count} compact
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-3 text-sm text-text-secondary">
                        <span>{formatDateTime(conversation.start_time)}</span>
                        {conversation.duration_minutes != null && (
                            <span>
                                {conversation.duration_minutes.toFixed(0)} min
                            </span>
                        )}
                        <span>
                            {formatTokens(cm.input_tokens)} in /{" "}
                            {formatTokens(cm.output_tokens)} out
                        </span>
                        <span className="font-mono">{cm.primary_model}</span>
                    </div>
                </div>

                <span
                    className={`shrink-0 font-mono font-semibold ${getCostColor(cm.total_cost)}`}
                >
                    {formatCost(cm.total_cost)}
                </span>
            </button>

            {/* Expanded section */}
            {expanded && (
                <div className="border-t border-border px-4 py-4 space-y-4">
                    {/* First user prompt */}
                    {conversation.user_prompts.length > 0 && (
                        <p className="text-sm text-text-primary italic line-clamp-3">
                            {conversation.user_prompts[0]}
                        </p>
                    )}

                    {/* Full transcript link */}
                    <a
                        href={`/sessions/${conversation.session_id}`}
                        className="inline-block text-sm text-accent hover:text-accent-hover transition-colors"
                    >
                        View full transcript &rarr;
                    </a>

                    {/* Metrics grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                        <MetricItem
                            label="Messages"
                            value={qm?.message_count?.toString() ?? "N/A"}
                        />
                        <MetricItem
                            label="Duration"
                            value={
                                conversation.duration_minutes != null
                                    ? `${conversation.duration_minutes.toFixed(0)} min`
                                    : "N/A"
                            }
                        />
                        <MetricItem
                            label="Compactions"
                            value={cd?.compaction_count?.toString() ?? "0"}
                        />
                        <MetricItem
                            label="Avg Tokens/Msg"
                            value={formatTokens(cm.average_tokens_per_message)}
                        />
                    </div>

                    {/* Token progression chart */}
                    <div>
                        <h4 className="text-sm font-medium text-text-secondary mb-2 uppercase tracking-wider">
                            Token Progression
                        </h4>
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

                    {/* Issues */}
                    {conversation.issues.length > 0 &&
                        conversation.issues[0] !== "No analysis available" && (
                            <div>
                                <h4 className="text-sm font-medium text-text-secondary mb-1 uppercase tracking-wider">
                                    Issues
                                </h4>
                                <ul className="text-sm text-warning space-y-0.5">
                                    {conversation.issues.map(issue => (
                                        <li key={issue}>{issue}</li>
                                    ))}
                                </ul>
                            </div>
                        )}

                    {/* Messages */}
                    {conversation.messages &&
                        conversation.messages.length > 0 && (
                            <div>
                                <h4 className="text-sm font-medium text-text-secondary mb-2 uppercase tracking-wider">
                                    Messages ({conversation.messages.length})
                                </h4>
                                <div className="bg-raised rounded-lg p-3 max-h-96 overflow-y-auto">
                                    <MessageList
                                        messages={conversation.messages}
                                    />
                                </div>
                            </div>
                        )}
                </div>
            )}
        </div>
    );
}

function MetricItem({
    label,
    value,
    valueClass = "",
}: {
    label: string;
    value: string;
    valueClass?: string;
}) {
    return (
        <div>
            <p className="text-text-secondary mb-0.5">{label}</p>
            <p className={`font-medium ${valueClass}`}>{value}</p>
        </div>
    );
}
