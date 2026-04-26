"use client";

import { useMemo, useState } from "react";
import EmptyState from "@/components/EmptyState";
import Header from "@/components/Header";
import ProjectCard from "@/components/ProjectCard";
import SearchFilter from "@/components/SearchFilter";
import SortSelect from "@/components/SortSelect";
import SummaryCards from "@/components/SummaryCards";
import { useApp } from "@/context/AppContext";
import { filterProjects, sortProjects } from "@/lib/utils";
import type { SortDirection, SortKey } from "@/lib/types";

const PROJECT_SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: "cost", label: "Cost" },
    { key: "conversations", label: "Conversations" },
    { key: "name", label: "Name" },
];

export default function HomePage() {
    const { data, loading, error } = useApp();
    const [search, setSearch] = useState("");
    const [sortKey, setSortKey] = useState<SortKey>("cost");
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

    const projects = useMemo(() => {
        if (!data) return [];
        const filtered = filterProjects(data.projects, search);
        return sortProjects(filtered, sortKey, sortDirection);
    }, [data, search, sortKey, sortDirection]);

    if (loading) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center gap-3">
                <div className="flex items-center gap-1.5">
                    <span
                        className="w-2 h-2 rounded-full bg-accent animate-pulse"
                        style={{ animationDelay: "0ms" }}
                    />
                    <span
                        className="w-2 h-2 rounded-full bg-accent animate-pulse"
                        style={{ animationDelay: "150ms" }}
                    />
                    <span
                        className="w-2 h-2 rounded-full bg-accent animate-pulse"
                        style={{ animationDelay: "300ms" }}
                    />
                </div>
                <span className="text-sm text-text-secondary">
                    Loading analysis data...
                </span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center gap-4">
                <svg
                    className="w-10 h-10 text-danger opacity-60"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                </svg>
                <div className="text-center">
                    <h2 className="text-lg font-medium text-text-primary mb-1">
                        Failed to load data
                    </h2>
                    <p className="text-sm text-text-secondary mb-3">{error}</p>
                    <p className="text-sm text-text-secondary">
                        Run{" "}
                        <code className="font-mono text-accent bg-raised px-1.5 py-0.5 rounded text-xs">
                            cd backend && make conversations-analysis
                        </code>{" "}
                        to populate the database.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex flex-col">
            <Header title="Claude Code Conversations Analyzer" />
            <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-6 space-y-6">
                <SummaryCards projects={projects} />
                <div className="flex items-center gap-4">
                    <div className="flex-1">
                        <SearchFilter
                            value={search}
                            onChange={setSearch}
                            placeholder="Search projects..."
                        />
                    </div>
                    <SortSelect
                        options={PROJECT_SORT_OPTIONS}
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
                {projects.length === 0 ? (
                    <EmptyState />
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {projects.map(project => (
                            <ProjectCard key={project.id} project={project} />
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}
