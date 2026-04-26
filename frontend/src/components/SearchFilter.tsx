"use client";

export default function SearchFilter({
    value,
    onChange,
    placeholder = "Search...",
}: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
}) {
    return (
        <div className="relative">
            <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
            >
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
            </svg>
            <input
                type="text"
                value={value}
                onChange={e => onChange(e.target.value)}
                placeholder={placeholder}
                className="w-full pl-9 pr-3 py-2 bg-raised border border-border rounded-md text-text-primary placeholder:text-text-secondary text-sm focus:outline-none focus:border-accent transition-colors"
            />
        </div>
    );
}
