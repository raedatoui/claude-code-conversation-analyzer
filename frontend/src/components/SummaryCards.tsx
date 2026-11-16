"use client";

import type { Project } from "@/lib/types";
import { formatCost, formatDate, formatTokens } from "@/lib/utils";

interface SummaryCardsProps {
    projects: Project[];
}

interface CardData {
    label: string;
    value: string;
    subtext?: string;
}

export default function SummaryCards({ projects }: SummaryCardsProps) {
    if (projects.length === 0) return null;

    const totalConversations = projects.reduce(
        (sum, p) => sum + p.conversations.length,
        0
    );
    const totalCost = projects.reduce(
        (sum, p) => sum + p.metrics.total_cost,
        0
    );
    const totalTokens = projects.reduce(
        (sum, p) => sum + p.metrics.total_tokens,
        0
    );
    const totalCompactions = projects.reduce(
        (sum, p) =>
            sum +
            p.conversations.reduce(
                (s, c) => s + (c.compaction_data?.compaction_count ?? 0),
                0
            ),
        0
    );
    const periodStart = projects.reduce<string | null>((min, p) => {
        const start = p.metrics.date_range_start;
        return start && (!min || start < min) ? start : min;
    }, null);
    const periodEnd = projects.reduce<string | null>((max, p) => {
        const end = p.metrics.date_range_end;
        return end && (!max || end > max) ? end : max;
    }, null);

    const cards: CardData[] = [
        {
            label: "Projects",
            value: projects.length.toString(),
            subtext: `${totalConversations} conversations`,
        },
        {
            label: "Total Cost",
            value: formatCost(totalCost),
            subtext: `${formatCost(totalCost / Math.max(totalConversations, 1))} avg/conv`,
        },
        {
            label: "Total Tokens",
            value: formatTokens(totalTokens),
        },
        {
            label: "Compactions",
            value: totalCompactions.toString(),
            subtext: "context resets",
        },
    ];

    return (
        <div className="space-y-2">
            {periodStart && periodEnd && (
                <p className="text-sm text-text-secondary">
                    Sessions from {formatDate(periodStart)} to{" "}
                    {formatDate(periodEnd)}
                </p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {cards.map(card => (
                    <div
                        key={card.label}
                        className="bg-surface border border-border rounded-lg p-5"
                    >
                        <p className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">
                            {card.label}
                        </p>
                        <p className="text-3xl font-bold">{card.value}</p>
                        {card.subtext && (
                            <p className="text-sm text-text-secondary mt-1">
                                {card.subtext}
                            </p>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
