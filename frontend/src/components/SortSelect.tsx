"use client";

import type { SortDirection, SortKey } from "@/lib/types";

interface SortOption {
    key: SortKey;
    label: string;
}

export default function SortSelect({
    options,
    sortKey,
    sortDirection,
    onSortKeyChange,
    onDirectionToggle,
}: {
    options: SortOption[];
    sortKey: SortKey;
    sortDirection: SortDirection;
    onSortKeyChange: (key: SortKey) => void;
    onDirectionToggle: () => void;
}) {
    return (
        <div className="flex items-center gap-2">
            <select
                value={sortKey}
                onChange={e => onSortKeyChange(e.target.value as SortKey)}
                className="bg-raised border border-border rounded-md text-text-primary text-sm px-3 py-2 focus:outline-none focus:border-accent transition-colors cursor-pointer"
            >
                {options.map(opt => (
                    <option key={opt.key} value={opt.key}>
                        {opt.label}
                    </option>
                ))}
            </select>
            <button
                type="button"
                onClick={onDirectionToggle}
                className="bg-raised border border-border rounded-md px-3 py-2 text-text-secondary hover:text-text-primary cursor-pointer transition-colors text-sm"
                aria-label={`Sort ${sortDirection === "asc" ? "descending" : "ascending"}`}
            >
                {sortDirection === "asc" ? "\u2191" : "\u2193"}
            </button>
        </div>
    );
}
