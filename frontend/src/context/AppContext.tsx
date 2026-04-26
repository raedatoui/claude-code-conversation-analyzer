"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
} from "react";
import type { AnalysisData, SortDirection, SortKey } from "@/lib/types";

interface AppContextValue {
    data: AnalysisData | null;
    loading: boolean;
    error: string | null;
    search: string;
    setSearch: (search: string) => void;
    sortKey: SortKey;
    setSortKey: (key: SortKey) => void;
    sortDirection: SortDirection;
    setSortDirection: (dir: SortDirection) => void;
    toggleSortDirection: () => void;
    theme: "dark" | "light";
    setTheme: (theme: "dark" | "light") => void;
    toggleTheme: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

function getInitialTheme(): "dark" | "light" {
    if (typeof window === "undefined") return "dark";
    const stored = localStorage.getItem("rating-app-theme");
    if (stored === "light" || stored === "dark") return stored;
    return "dark";
}

function applyTheme(theme: "dark" | "light") {
    if (typeof document === "undefined") return;
    const html = document.documentElement;
    if (theme === "light") {
        html.classList.add("light");
    } else {
        html.classList.remove("light");
    }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
    const [data, setData] = useState<AnalysisData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [sortKey, setSortKey] = useState<SortKey>("cost");
    const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
    const [theme, setThemeState] = useState<"dark" | "light">("dark");

    useEffect(() => {
        const initial = getInitialTheme();
        setThemeState(initial);
        applyTheme(initial);
    }, []);

    useEffect(() => {
        let cancelled = false;

        async function fetchData() {
            try {
                const response = await fetch("/api/data");
                if (!response.ok) {
                    throw new Error(
                        `Failed to load data: ${response.status} ${response.statusText}`
                    );
                }
                const json: AnalysisData = await response.json();
                if (!cancelled) {
                    setData(json);
                    setLoading(false);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(
                        err instanceof Error
                            ? err.message
                            : "Failed to load analysis data"
                    );
                    setLoading(false);
                }
            }
        }

        fetchData();
        return () => {
            cancelled = true;
        };
    }, []);

    const setTheme = useCallback((value: "dark" | "light") => {
        setThemeState(value);
        applyTheme(value);
        localStorage.setItem("rating-app-theme", value);
    }, []);

    const toggleTheme = useCallback(() => {
        setTheme(theme === "dark" ? "light" : "dark");
    }, [theme, setTheme]);

    const toggleSortDirection = useCallback(() => {
        setSortDirection(d => (d === "asc" ? "desc" : "asc"));
    }, []);

    return (
        <AppContext.Provider
            value={{
                data,
                loading,
                error,
                search,
                setSearch,
                sortKey,
                setSortKey,
                sortDirection,
                setSortDirection,
                toggleSortDirection,
                theme,
                setTheme,
                toggleTheme,
            }}
        >
            {children}
        </AppContext.Provider>
    );
}

export function useApp(): AppContextValue {
    const context = useContext(AppContext);
    if (!context) {
        throw new Error("useApp must be used within an AppProvider");
    }
    return context;
}
