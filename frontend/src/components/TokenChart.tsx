"use client";

import { useEffect, useState } from "react";
import { CHART_COLORS } from "@/lib/constants";
import type { CompactionData } from "@/lib/types";

export default function TokenChart({
    compactionData,
}: {
    compactionData: CompactionData | null;
}) {
    const [Recharts, setRecharts] = useState<typeof import("recharts") | null>(
        null
    );

    useEffect(() => {
        import("recharts").then(setRecharts);
    }, []);

    if (
        !compactionData?.token_progression ||
        compactionData.token_progression.length === 0
    ) {
        return (
            <div className="text-xs text-text-secondary italic py-4">
                No token progression data available.
            </div>
        );
    }

    if (!Recharts) {
        return (
            <div className="w-full h-48 flex items-center justify-center text-xs text-text-secondary">
                Loading chart...
            </div>
        );
    }

    const {
        ResponsiveContainer,
        LineChart,
        Line,
        XAxis,
        YAxis,
        Tooltip,
        ReferenceLine,
    } = Recharts;

    const data = compactionData.token_progression.map(entry => ({
        index: entry.message_index,
        cacheRead: entry.cache_read_tokens,
        input: entry.input_tokens,
        output: entry.output_tokens,
    }));

    const compactionIndices = (compactionData.compaction_events || []).map(
        e => e.message_index
    );

    const formatTick = (value: number) => {
        if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
        if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
        return value.toString();
    };

    return (
        <div className="w-full h-48">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart
                    data={data}
                    margin={{
                        top: 5,
                        right: 10,
                        left: 10,
                        bottom: 5,
                    }}
                >
                    <XAxis
                        dataKey="index"
                        tick={{ fontSize: 10 }}
                        stroke="var(--text-secondary)"
                    />
                    <YAxis
                        tickFormatter={formatTick}
                        tick={{ fontSize: 10 }}
                        stroke="var(--text-secondary)"
                        width={50}
                    />
                    <Tooltip
                        contentStyle={{
                            background: "var(--background-surface)",
                            border: "1px solid var(--border)",
                            borderRadius: "8px",
                            fontSize: "12px",
                        }}
                        labelStyle={{
                            color: "var(--text-primary)",
                        }}
                        formatter={(value: number, name: string) => [
                            formatTick(value),
                            name === "cacheRead"
                                ? "Cache Read"
                                : name === "input"
                                  ? "Input"
                                  : "Output",
                        ]}
                    />
                    {compactionIndices.map((idx, i) => (
                        <ReferenceLine
                            key={`comp-${i}-${idx}`}
                            x={idx}
                            stroke={CHART_COLORS.compaction}
                            strokeDasharray="4 4"
                            strokeWidth={1}
                        />
                    ))}
                    <Line
                        type="monotone"
                        dataKey="cacheRead"
                        stroke={CHART_COLORS.cacheRead}
                        strokeWidth={1.5}
                        dot={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="input"
                        stroke={CHART_COLORS.input}
                        strokeWidth={1.5}
                        dot={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="output"
                        stroke={CHART_COLORS.output}
                        strokeWidth={1.5}
                        dot={false}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
