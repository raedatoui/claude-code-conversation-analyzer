import {
    formatCost,
    formatTokens,
    getCostColor,
    getProjectDisplayName,
} from "@/lib/utils";
import type { Project } from "@/lib/types";

export default function ProjectCard({ project }: { project: Project }) {
    const m = project.metrics;
    const displayName =
        getProjectDisplayName(project.path) ?? project.clean_name;

    const totalCompactions = project.conversations.reduce(
        (sum, c) => sum + (c.compaction_data?.compaction_count ?? 0),
        0
    );

    return (
        <a
            href={`/projects/${project.id}`}
            className="block bg-surface border border-border rounded-lg p-5 hover:border-accent/50 transition-colors"
        >
            <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-base truncate pr-2">
                    {displayName}
                </h3>
                <span
                    className={`text-base font-mono font-semibold ${getCostColor(m.total_cost)}`}
                >
                    {formatCost(m.total_cost)}
                </span>
            </div>

            <div className="flex items-center gap-3 text-sm text-text-secondary">
                <span>{m.total_conversations} conv</span>
                <span>{formatTokens(m.total_tokens)} tok</span>
                {totalCompactions > 0 && (
                    <span className="text-amber-300">
                        {totalCompactions} compact
                    </span>
                )}
            </div>
        </a>
    );
}
