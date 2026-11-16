"""
Model pricing and cost calculation utilities.

Anthropic's official pricing (per million tokens).
Source: https://platform.claude.com/docs/en/about-claude/pricing#model-pricing
"""

# Using 5m cache prices as default since JSONL doesn't distinguish cache expiry
PRICING: dict[str, dict[str, float | bool]] = {
    # Claude Fable 5.x
    'claude-fable-5-2': {
        'input': 8.00,
        'cache_write': 10.00,
        'cache_read': 0.20,
        'output': 40.00,
    },
    'claude-fable-5-1': {
        'input': 10.00,
        'cache_write': 12.50,
        'cache_read': 0.25,
        'output': 50.00,
    },
    'claude-fable-5': {
        'input': 10.00,
        'cache_write': 12.50,
        'cache_read': 1.00,
        'output': 50.00,
    },
    # Claude Opus 5.x
    'claude-opus-5-5': {
        'input': 4.00,
        'cache_write': 5.00,
        'cache_read': 0.20,
        'output': 20.00,
    },
    'claude-opus-5': {
        'input': 5.00,
        'cache_write': 6.25,
        'cache_read': 0.50,
        'output': 25.00,
    },
    # Claude Opus 4.x
    'claude-opus-4-8': {
        'input': 5.00,
        'cache_write': 6.25,
        'cache_read': 0.50,
        'output': 25.00,
    },
    'claude-opus-4-7': {
        'input': 5.00,
        'cache_write': 6.25,
        'cache_read': 0.50,
        'output': 25.00,
    },
    'claude-opus-4-6': {
        'input': 5.00,
        'cache_write': 6.25,
        'cache_read': 0.50,
        'output': 25.00,
    },
    'claude-opus-4-5': {
        'input': 5.00,
        'cache_write': 6.25,
        'cache_read': 0.50,
        'output': 25.00,
    },
    'claude-opus-4-5-20251101': {
        'input': 5.00,
        'cache_write': 6.25,
        'cache_read': 0.50,
        'output': 25.00,
    },
    'claude-opus-4-1-20250805': {
        'input': 15.00,
        'cache_write': 18.75,
        'cache_read': 1.50,
        'output': 75.00,
    },
    'claude-opus-4-1': {
        'input': 15.00,
        'cache_write': 18.75,
        'cache_read': 1.50,
        'output': 75.00,
    },
    'claude-opus-4': {
        'input': 15.00,
        'cache_write': 18.75,
        'cache_read': 1.50,
        'output': 75.00,
    },
    # Claude Sonnet 5.x
    'claude-sonnet-5-5': {
        'input': 2.00,
        'cache_write': 2.50,
        'cache_read': 0.10,
        'output': 10.00,
    },
    'claude-sonnet-5': {
        'input': 2.00,
        'cache_write': 2.50,
        'cache_read': 0.20,
        'output': 10.00,
    },
    # Claude Sonnet 4.x
    'claude-sonnet-4-6': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
    },
    'claude-sonnet-4-5': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
    },
    'claude-sonnet-4-5-20250929': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
    },
    'claude-sonnet-4': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
    },
    'claude-sonnet-4-20250514': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
    },
    'claude-sonnet-3-7': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
    },
    'claude-3-5-sonnet-20241022': {
        'input': 3.00,
        'cache_write': 3.75,
        'cache_read': 0.30,
        'output': 15.00,
        'deprecated': True,
    },
    # Claude Haiku 5.x
    # Rates for prompts up to 100K tokens. Requests with longer prompts are billed at 5x these
    # rates (0.50 / 0.625 / 0.05 / 2.50), which this flat table does not model.
    'claude-haiku-5-5': {
        'input': 0.10,
        'cache_write': 0.125,
        'cache_read': 0.01,
        'output': 0.50,
    },
    # Claude Haiku 4.x and 3.x
    'claude-haiku-4-5': {
        'input': 1.00,
        'cache_write': 1.25,
        'cache_read': 0.10,
        'output': 5.00,
    },
    'claude-haiku-4-5-20251001': {
        'input': 1.00,
        'cache_write': 1.25,
        'cache_read': 0.10,
        'output': 5.00,
    },
    'claude-3-5-haiku-20241022': {
        'input': 0.80,
        'cache_write': 1.00,
        'cache_read': 0.08,
        'output': 4.00,
    },
    'claude-haiku-3-5': {
        'input': 0.80,
        'cache_write': 1.00,
        'cache_read': 0.08,
        'output': 4.00,
    },
    'claude-haiku-3': {
        'input': 0.25,
        'cache_write': 0.30,
        'cache_read': 0.03,
        'output': 1.25,
    },
    # Claude Opus 3 (deprecated)
    'claude-opus-3': {
        'input': 15.00,
        'cache_write': 18.75,
        'cache_read': 1.50,
        'output': 75.00,
        'deprecated': True,
    },
}


def calculate_cost(tokens: dict[str, int], model: str) -> float:
    """Calculate cost for a given token usage and model.

    Args:
        tokens: Dict with keys:
            - input_tokens: Number of input tokens
            - output_tokens: Number of output tokens
            - cache_creation_input_tokens: Number of cache creation tokens
            - cache_read_input_tokens: Number of cache read tokens
        model: Model name

    Returns:
        Total cost in USD, or 0.0 if pricing not found
    """
    if model not in PRICING:
        return 0.0

    pricing = PRICING[model]

    input_tokens = tokens.get('input_tokens', 0)
    output_tokens = tokens.get('output_tokens', 0)
    cache_creation_tokens = tokens.get('cache_creation_input_tokens', 0)
    cache_read_tokens = tokens.get('cache_read_input_tokens', 0)

    input_cost = (input_tokens / 1_000_000) * float(pricing['input'])
    cache_write_cost = (cache_creation_tokens / 1_000_000) * float(pricing['cache_write'])
    cache_read_cost = (cache_read_tokens / 1_000_000) * float(pricing['cache_read'])
    output_cost = (output_tokens / 1_000_000) * float(pricing['output'])

    return input_cost + cache_write_cost + cache_read_cost + output_cost
