"use client";

import { useState } from "react";
import { MESSAGE_LABEL_COLORS } from "@/lib/constants";
import type { ConversationMessage } from "@/lib/types";

const INITIAL_DISPLAY = 20;
const LOAD_MORE_COUNT = 20;

export default function MessageList({
    messages,
}: {
    messages: ConversationMessage[];
}) {
    const [displayCount, setDisplayCount] = useState(INITIAL_DISPLAY);

    if (!messages || messages.length === 0) {
        return (
            <div className="text-xs text-text-secondary italic py-2">
                No messages available.
            </div>
        );
    }

    const visible = messages.slice(0, displayCount);

    return (
        <div className="space-y-1.5">
            {visible.map((msg, idx) => {
                const labelColors =
                    MESSAGE_LABEL_COLORS[msg.message_label] ??
                    MESSAGE_LABEL_COLORS.META;
                const key = `${idx}-${msg.message_label}-${msg.timestamp ?? ""}`;
                return (
                    <div key={key} className="flex items-start gap-2 text-sm">
                        <span
                            className={`shrink-0 mt-0.5 min-w-[5.5rem] text-center px-1.5 py-0.5 rounded text-xs font-medium ${labelColors.bg} ${labelColors.text}`}
                        >
                            {msg.message_label}
                        </span>
                        <span
                            className={`font-mono whitespace-pre-wrap break-words ${msg.is_meta ? "text-text-secondary italic" : "text-text-primary"}`}
                        >
                            {msg.content}
                        </span>
                    </div>
                );
            })}
            {displayCount < messages.length && (
                <button
                    type="button"
                    onClick={() => setDisplayCount(c => c + LOAD_MORE_COUNT)}
                    className="text-sm text-accent hover:text-accent-hover cursor-pointer transition-colors"
                >
                    Show more ({messages.length - displayCount} remaining)
                </button>
            )}
        </div>
    );
}
