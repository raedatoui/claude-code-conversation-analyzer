"use client";

import { use, useMemo, useState } from "react";
import ConversationCard from "@/components/ConversationCard";
import EmptyState from "@/components/EmptyState";
import Header from "@/components/Header";
import SearchFilter from "@/components/SearchFilter";
import SortSelect from "@/components/SortSelect";
import { useApp } from "@/context/AppContext";
import {
    filterConversations,
    formatCost,
    formatDate,
    formatTokens,
    getCostColor,
    getProjectDisplayName,
    sortConversations,
} from "@/lib/utils";
import type { SortDirection, SortKey } from "@/lib/types";

const CONV_SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: "date", label: "Date" },
    { key: "cost", label: "Cost" },
    { key: "duration", label: "Duration" },
    { key: "compactions", label: "Compactions" },
];

export default function ProjectPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const { data, loading } = useApp();
    const [search, setSearch] = useState("");
    const [modelFilter, setModelFilter] = useState("all");
    const [sortKey, setSortKey] = useState<SortKey>("date");
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

    const projectId = Number(id);
    const project = data?.projects.find(p => p.id === projectId);

    const modelOptions = useMemo(() => {
        if (!project) return [];
        const models = new Set(
            project.conversations.map(c => c.cost_metrics.primary_model)
        );
        return [...models].sort();
    }, [project]);

    const conversations = useMemo(() => {
        if (!project) return [];
        let filtered = filterConversations(project.conversations, search);
        if (modelFilter !== "all") {
            filtered = filtered.filter(
                c => c.cost_metrics.primary_model === modelFilter
            );
        }
        return sortConversations(filtered, sortKey, sortDirection);
    }, [project, search, modelFilter, sortKey, sortDirection]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-text-secondary animate-pulse">
                    Loading...
                </div>
            </div>
        );
    }

    if (!project) {
        return (
            <div className="min-h-screen flex flex-col">
                <Header title="Project Not Found" backHref="/" />
                <main className="flex-1 flex items-center justify-center">
                    <EmptyState message={`No project found with id ${id}.`} />
                </main>
            </div>
        );
    }

    const m = project.metrics;
    const displayName =
        getProjectDisplayName(project.path) ?? project.clean_name;

    return (
        <div className="min-h-screen flex flex-col">
            <Header
                title={displayName}
                backHref="/"
                subtitle={project.path ?? undefined}
            />
            <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-6 space-y-4">
                {/* Metric pills */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <MetricCard
                        label="Conversations"
                        value={m.total_conversations.toString()}
                    />
                    <MetricCard
                        label="Cost"
                        value={formatCost(m.total_cost)}
                        valueClass={getCostColor(m.total_cost)}
                    />
                    <MetricCard
                        label="Tokens"
                        value={`${formatTokens(m.total_tokens)}`}
                    />
                    <MetricCard
                        label="Avg Score"
                        value={
                            m.average_score > 0
                                ? m.average_score.toFixed(0)
                                : "N/A"
                        }
                    />
                    <MetricCard
                        label="First Session"
                        value={formatDate(m.date_range_start)}
                    />
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex-1">
                        <SearchFilter
                            value={search}
                            onChange={setSearch}
                            placeholder="Search conversations..."
                        />
                    </div>
                    <select
                        value={modelFilter}
                        onChange={e => setModelFilter(e.target.value)}
                        className="bg-raised border border-border rounded-md text-text-primary text-sm px-3 py-2 focus:outline-none focus:border-accent transition-colors cursor-pointer"
                    >
                        <option value="all">All models</option>
                        {modelOptions.map(m => (
                            <option key={m} value={m}>
                                {formatModelName(m)}
                            </option>
                        ))}
                    </select>
                    <SortSelect
                        options={CONV_SORT_OPTIONS}
                        sortKey={sortKey}
                        sortDirection={sortDirection}
                        onSortKeyChange={setSortKey}
                        onDirectionToggle={() =>
                            setSortDirection(d =>
                                d === "asc" ? "desc" : "asc"
                            )
                        }
                    />
                </div>
                {conversations.length === 0 ? (
                    <EmptyState />
                ) : (
                    <div className="space-y-3">
                        {conversations.map(conv => (
                            <ConversationCard
                                key={conv.session_id}
                                conversation={conv}
                            />
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}

function formatModelName(model: string): string {
    return model.replace(/^claude-/, "").replace(/-\d{8}$/, "");
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
