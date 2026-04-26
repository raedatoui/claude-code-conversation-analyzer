"use client";

import { useApp } from "@/context/AppContext";

export default function ThemeToggle() {
    const { theme, toggleTheme } = useApp();

    return (
        <button
            type="button"
            onClick={toggleTheme}
            className="bg-raised border border-border rounded-md px-3 py-1.5 text-text-secondary hover:text-text-primary cursor-pointer transition-colors"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
            {theme === "dark" ? "\u2600" : "\u263D"}
        </button>
    );
}
