"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import SearchFilter from "@/components/SearchFilter";
import { formatDateTime } from "@/lib/utils";

interface SnippetSegment {
    text: string;
    match: boolean;
}

interface SearchResult {
    session_id: string;
    project_id: number;
    project_name: string;
    message_index: number;
    timestamp: string | null;
    session_first_timestamp: string | null;
    snippet: SnippetSegment[];
}

interface SearchResponse {
    results?: SearchResult[];
    indexed?: boolean;
    error?: string;
}

function SearchContent() {
    const router = useRouter();
    const params = useSearchParams();
    const urlQ = params.get("q") ?? "";

    const [input, setInput] = useState(urlQ);
    const [results, setResults] = useState<SearchResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [indexed, setIndexed] = useState(true);

    // Sync URL → input when user navigates back/forward
    useEffect(() => {
        setInput(urlQ);
    }, [urlQ]);

    // Debounce URL updates so every keystroke doesn't push history
    useEffect(() => {
        const trimmed = input.trim();
        const handle = setTimeout(() => {
            const next = new URLSearchParams();
            if (trimmed) next.set("q", trimmed);
            const query = next.toString();
            router.replace(query ? `/search?${query}` : "/search");
        }, 250);
        return () => clearTimeout(handle);
    }, [input, router]);

    // Fetch when the URL query changes
    useEffect(() => {
        const trimmed = urlQ.trim();
        if (!trimmed) {
            setResults([]);
            setError(null);
            setIndexed(true);
            return;
        }

        const controller = new AbortController();
        setLoading(true);
        setError(null);

        fetch(`/api/search?q=${encodeURIComponent(trimmed)}`, {
            signal: controller.signal,
        })
            .then(async res => {
                const json = (await res.json()) as SearchResponse;
                if (!res.ok) {
                    throw new Error(
                        json.error ?? `Request failed (${res.status})`
                    );
                }
                setResults(json.results ?? []);
                setIndexed(json.indexed !== false);
            })
            .catch(err => {
                if (err.name === "AbortError") return;
                setError(err instanceof Error ? err.message : "Unknown error");
                setResults([]);
            })
            .finally(() => setLoading(false));

        return () => controller.abort();
    }, [urlQ]);

    return (
        <div className="min-h-screen flex flex-col">
            <Header title="Search" backHref="/" />

            <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-6 space-y-4">
                <SearchFilter
                    value={input}
                    onChange={setInput}
                    placeholder="Search your conversations..."
                />

                {!indexed && (
                    <div className="bg-raised border border-border rounded-lg p-4 text-sm text-text-secondary">
                        Search index not built yet. Run{" "}
                        <code className="font-mono bg-surface px-1.5 py-0.5 rounded">
                            make conversations-analysis
                        </code>{" "}
                        in the backend to generate it.
                    </div>
                )}

                {error && (
                    <div className="bg-raised border border-danger/40 rounded-lg p-4 text-sm text-danger">
                        {error}
                    </div>
                )}

                {loading && (
                    <div className="text-sm text-text-secondary animate-pulse">
                        Searching...
                    </div>
                )}

                {!loading &&
                    urlQ.trim() &&
                    results.length === 0 &&
                    !error &&
                    indexed && (
                        <div className="text-sm text-text-secondary">
                            No matches for{" "}
                            <span className="font-mono">{urlQ}</span>.
                        </div>
                    )}

                {results.length > 0 && (
                    <div className="space-y-2">
                        <p className="text-xs text-text-secondary uppercase tracking-wider">
                            {results.length} match
                            {results.length === 1 ? "" : "es"}
                        </p>
                        <ul className="space-y-2">
                            {results.map(r => (
                                <li key={`${r.session_id}-${r.message_index}`}>
                                    <Link
                                        href={`/sessions/${encodeURIComponent(r.session_id)}?q=${encodeURIComponent(urlQ)}&msg=${r.message_index}`}
                                        className="block bg-raised hover:bg-surface border border-border hover:border-accent rounded-lg p-4 transition-colors"
                                    >
                                        <div className="flex items-baseline justify-between gap-4 mb-1.5 text-xs text-text-secondary">
                                            <span className="font-medium text-text-primary truncate">
                                                {r.project_name}
                                            </span>
                                            <span className="shrink-0 font-mono">
                                                {formatDateTime(
                                                    r.timestamp ??
                                                        r.session_first_timestamp
                                                )}
                                            </span>
                                        </div>
                                        <p className="text-sm font-mono text-text-primary break-words whitespace-pre-wrap">
                                            {r.snippet.map((seg, i) =>
                                                seg.match ? (
                                                    <mark
                                                        key={`${i}-${seg.text}`}
                                                        className="bg-amber-400/40 text-inherit rounded-sm px-0.5"
                                                    >
                                                        {seg.text}
                                                    </mark>
                                                ) : (
                                                    <span
                                                        key={`${i}-${seg.text}`}
                                                    >
                                                        {seg.text}
                                                    </span>
                                                )
                                            )}
                                        </p>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </main>
        </div>
    );
}

// useSearchParams() needs a Suspense boundary for the page to prerender
export default function SearchPage() {
    return (
        <Suspense>
            <SearchContent />
        </Suspense>
    );
}
