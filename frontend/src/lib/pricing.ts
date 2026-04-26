/**
 * Model pricing (per million tokens).
 * TS copy of backend/src/pricing.py — keep in sync.
 */

interface ModelPricing {
    input: number;
    output: number;
    cache_write: number;
    cache_read: number;
}

export const MODEL_PRICING: Record<string, ModelPricing> = {
    "claude-opus-4-6": {
        input: 5.0,
        output: 25.0,
        cache_write: 6.25,
        cache_read: 0.5,
    },
    "claude-opus-4-5": {
        input: 5.0,
        output: 25.0,
        cache_write: 6.25,
        cache_read: 0.5,
    },
    "claude-opus-4-5-20251101": {
        input: 5.0,
        output: 25.0,
        cache_write: 6.25,
        cache_read: 0.5,
    },
    "claude-opus-4-1": {
        input: 15.0,
        output: 75.0,
        cache_write: 18.75,
        cache_read: 1.5,
    },
    "claude-opus-4": {
        input: 15.0,
        output: 75.0,
        cache_write: 18.75,
        cache_read: 1.5,
    },
    "claude-sonnet-4-5": {
        input: 3.0,
        output: 15.0,
        cache_write: 3.75,
        cache_read: 0.3,
    },
    "claude-sonnet-4-5-20250929": {
        input: 3.0,
        output: 15.0,
        cache_write: 3.75,
        cache_read: 0.3,
    },
    "claude-sonnet-4": {
        input: 3.0,
        output: 15.0,
        cache_write: 3.75,
        cache_read: 0.3,
    },
    "claude-sonnet-4-20250514": {
        input: 3.0,
        output: 15.0,
        cache_write: 3.75,
        cache_read: 0.3,
    },
    "claude-sonnet-3-7": {
        input: 3.0,
        output: 15.0,
        cache_write: 3.75,
        cache_read: 0.3,
    },
    "claude-3-5-sonnet-20241022": {
        input: 3.0,
        output: 15.0,
        cache_write: 3.75,
        cache_read: 0.3,
    },
    "claude-haiku-4-5": {
        input: 1.0,
        output: 5.0,
        cache_write: 1.25,
        cache_read: 0.1,
    },
    "claude-haiku-4-5-20251001": {
        input: 1.0,
        output: 5.0,
        cache_write: 1.25,
        cache_read: 0.1,
    },
    "claude-3-5-haiku-20241022": {
        input: 0.8,
        output: 4.0,
        cache_write: 1.0,
        cache_read: 0.08,
    },
    "claude-haiku-3-5": {
        input: 0.8,
        output: 4.0,
        cache_write: 1.0,
        cache_read: 0.08,
    },
    "claude-haiku-3": {
        input: 0.25,
        output: 1.25,
        cache_write: 0.3,
        cache_read: 0.03,
    },
    "claude-opus-3": {
        input: 15.0,
        output: 75.0,
        cache_write: 18.75,
        cache_read: 1.5,
    },
};

const DEFAULT_MODEL = "claude-sonnet-4-5";

export function estimateCost(
    inputTokens: number,
    outputTokens: number,
    cacheCreation: number,
    cacheRead: number,
    model: string
): number {
    const pricing = MODEL_PRICING[model] ?? MODEL_PRICING[DEFAULT_MODEL];
    return (
        (inputTokens / 1e6) * pricing.input +
        (outputTokens / 1e6) * pricing.output +
        (cacheCreation / 1e6) * pricing.cache_write +
        (cacheRead / 1e6) * pricing.cache_read
    );
}
