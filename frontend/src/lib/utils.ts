import type { Conversation, Project, SortDirection, SortKey } from "./types";

export function formatCost(cost: number): string {
    return `$${cost.toFixed(2)}`;
}

export function formatTokens(tokens: number): string {
    if (tokens >= 1_000_000) {
        return `${(tokens / 1_000_000).toFixed(1)}M`;
    }
    if (tokens >= 1_000) {
        return `${(tokens / 1_000).toFixed(1)}K`;
    }
    return Math.round(tokens).toString();
}

export function formatDate(isoString: string | null): string {
    if (!isoString) return "N/A";
    const d = new Date(isoString);
    return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

export function formatDateTime(isoString: string | null): string {
    if (!isoString) return "N/A";
    const d = new Date(isoString);
    return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

export function getGradeColors(grade: string): {
    bg: string;
    text: string;
    border: string;
} {
    switch (grade) {
        case "A":
            return {
                bg: "bg-emerald-500/20",
                text: "text-emerald-300",
                border: "border-emerald-500/40",
            };
        case "B":
            return {
                bg: "bg-sky-500/20",
                text: "text-sky-300",
                border: "border-sky-500/40",
            };
        case "C":
            return {
                bg: "bg-amber-500/20",
                text: "text-amber-300",
                border: "border-amber-500/40",
            };
        case "D":
            return {
                bg: "bg-orange-500/20",
                text: "text-orange-300",
                border: "border-orange-500/40",
            };
        default:
            return {
                bg: "bg-red-500/20",
                text: "text-red-300",
                border: "border-red-500/40",
            };
    }
}

export function getCostColor(cost: number): string {
    if (cost > 50) return "text-danger";
    if (cost > 10) return "text-warning";
    return "text-success";
}

export function getProjectDisplayName(path: string | null): string | null {
    if (!path) return null;
    const last = path.split("/").filter(Boolean).pop();
    return last ?? null;
}

export function filterProjects(projects: Project[], search: string): Project[] {
    if (!search) return projects;
    const lower = search.toLowerCase();
    return projects.filter(
        p =>
            p.clean_name.toLowerCase().includes(lower) ||
            p.name.toLowerCase().includes(lower)
    );
}

export function sortProjects(
    projects: Project[],
    sortKey: SortKey,
    direction: SortDirection
): Project[] {
    const sorted = [...projects].sort((a, b) => {
        switch (sortKey) {
            case "cost":
                return a.metrics.total_cost - b.metrics.total_cost;
            case "conversations":
                return (
                    a.metrics.total_conversations -
                    b.metrics.total_conversations
                );
            case "name":
                return a.clean_name.localeCompare(b.clean_name);
            default:
                return 0;
        }
    });
    return direction === "desc" ? sorted.reverse() : sorted;
}

export function filterConversations(
    conversations: Conversation[],
    search: string
): Conversation[] {
    if (!search) return conversations;
    const lower = search.toLowerCase();
    return conversations.filter(
        c =>
            c.title.toLowerCase().includes(lower) ||
            c.session_id.toLowerCase().includes(lower)
    );
}

export function sortConversations(
    conversations: Conversation[],
    sortKey: SortKey,
    direction: SortDirection
): Conversation[] {
    const sorted = [...conversations].sort((a, b) => {
        switch (sortKey) {
            case "date":
                return (a.start_time ?? "").localeCompare(b.start_time ?? "");
            case "cost":
                return a.cost_metrics.total_cost - b.cost_metrics.total_cost;
            case "compactions":
                return (
                    (a.compaction_data?.compaction_count ?? 0) -
                    (b.compaction_data?.compaction_count ?? 0)
                );
            case "duration":
                return (a.duration_minutes ?? 0) - (b.duration_minutes ?? 0);
            default:
                return 0;
        }
    });
    return direction === "desc" ? sorted.reverse() : sorted;
}
