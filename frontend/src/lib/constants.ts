export const PAGE_SIZE = 20;

export const SEVERITY_COLORS: Record<string, string> = {
    none: "text-success",
    low: "text-success",
    moderate: "text-warning",
    high: "text-danger",
    extreme: "text-danger",
};

export const MESSAGE_LABEL_COLORS: Record<
    string,
    { bg: string; text: string }
> = {
    USER: { bg: "bg-sky-500/20", text: "text-sky-300" },
    ASSISTANT: { bg: "bg-emerald-500/20", text: "text-emerald-300" },
    META: { bg: "bg-zinc-500/20", text: "text-zinc-400" },
    TOOL_RESULT: { bg: "bg-violet-500/20", text: "text-violet-300" },
};

export const CHART_COLORS = {
    cacheRead: "#ef4444",
    input: "#3b82f6",
    output: "#22c55e",
    compaction: "#f59e0b",
};
