"use client";

import { useEffect, useState } from "react";
import { MESSAGE_LABEL_COLORS } from "@/lib/constants";
import type { ConversationMessage } from "@/lib/types";

function HighlightedText({
    text,
    searchTerm,
}: {
    text: string;
    searchTerm: string;
}) {
    if (!searchTerm.trim()) {
        return <>{text}</>;
    }

    const escaped = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const parts = text.split(new RegExp(`(${escaped})`, "gi"));

    return (
        <>
            {parts.map((part, i) => {
                const isMatch = part.toLowerCase() === searchTerm.toLowerCase();
                return isMatch ? (
                    <mark
                        key={`${i}-${part}`}
                        className="bg-amber-400/40 text-inherit rounded-sm px-0.5"
                    >
                        {part}
                    </mark>
                ) : (
                    <span key={`${i}-${part}`}>{part}</span>
                );
            })}
        </>
    );
}

export default function SessionMessageList({
    messages,
    searchTerm = "",
    originalIndices,
    scrollToIndex = null,
}: {
    messages: ConversationMessage[];
    searchTerm?: string;
    // Position of each message in the parent's unfiltered list. When provided,
    // used as the DOM anchor so deep links survive filtering/sorting.
    originalIndices?: number[];
    // Index (within the parent's unfiltered list) to scroll to on mount.
    scrollToIndex?: number | null;
}) {
    const [flashIndex, setFlashIndex] = useState<number | null>(null);

    useEffect(() => {
        if (scrollToIndex == null) return;
        const el = document.getElementById(`msg-${scrollToIndex}`);
        if (!el) return;
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        setFlashIndex(scrollToIndex);
        const t = setTimeout(() => setFlashIndex(null), 2500);
        return () => clearTimeout(t);
    }, [scrollToIndex]);

    if (!messages || messages.length === 0) {
        return (
            <div className="text-xs text-text-secondary italic py-2">
                No messages available.
            </div>
        );
    }

    return (
        <div className="space-y-1.5">
            {messages.map((msg, idx) => {
                const labelColors =
                    MESSAGE_LABEL_COLORS[msg.message_label] ??
                    MESSAGE_LABEL_COLORS.META;
                const anchorIdx = originalIndices?.[idx] ?? idx;
                const key = `${anchorIdx}-${msg.message_label}-${msg.timestamp ?? ""}`;
                const flashing = flashIndex === anchorIdx;
                return (
                    <div
                        key={key}
                        id={`msg-${anchorIdx}`}
                        className={`flex items-start gap-2 text-sm rounded transition-all ${flashing ? "ring-2 ring-amber-400 bg-amber-400/5 p-1 -m-1" : ""}`}
                    >
                        <span
                            className={`shrink-0 mt-0.5 min-w-[5.5rem] text-center px-1.5 py-0.5 rounded text-xs font-medium ${labelColors.bg} ${labelColors.text}`}
                        >
                            {msg.message_label}
                        </span>
                        <span
                            className={`font-mono whitespace-pre-wrap break-words ${msg.is_meta ? "text-text-secondary italic" : "text-text-primary"}`}
                        >
                            <HighlightedText
                                text={msg.content}
                                searchTerm={searchTerm}
                            />
                        </span>
                    </div>
                );
            })}
        </div>
    );
}
