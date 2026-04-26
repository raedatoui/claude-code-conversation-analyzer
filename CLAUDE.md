# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository analyzes Claude Code conversation quality and cost efficiency. It has two parts:

1. **Backend** (Python) — Reads cclog data, computes costs and quality scores, writes results to a SQLite database
2. **Frontend** (Next.js) — Interactive dashboard that reads from the database via API routes

### Related Projects

API tools for analyzing Claude Code usage, costs, and analytics live in `../claude-dashboard/api/`.
See `../claude-dashboard/api/CLAUDE.md` for documentation.

## Development Commands

**IMPORTANT**: Never run `make` commands directly. The user should run these commands themselves. Always provide the exact command for the user to run, but do not execute it yourself.

### Backend Setup (Python)
All `make` commands run from `backend/`:
```bash
cd backend
make install-dev          # Install package with dev dependencies (ruff, mypy)
```

### Code Quality
```bash
cd backend
make fmt                  # Format code with ruff (required before commits)
make lint                 # Lint code with ruff
make lint-fix             # Auto-fix linting issues
make type-check           # Type check with mypy (strict mode enabled)
make check                # Run both lint and type-check
```

**Important**: The Python side uses:
- **uv** for dependency management (automatically manages virtual environments)
- **ruff** with single quotes (`'`) and 200-char line length (see `backend/ruff.toml`)
- **mypy** in strict mode with Python 3.13 (see `backend/pyproject.toml`)
- Always format code before committing

### Frontend Development
```bash
cd frontend
pnpm install              # Install dependencies
pnpm dev                  # Start dev server (localhost:3000)
pnpm build                # Production build
pnpm lint                 # Check with biome
pnpm lint:fix             # Auto-fix lint issues
pnpm format               # Format with biome
```

**Important**: The frontend uses:
- **pnpm** as package manager
- **Biome 2.1.2** for linting + formatting (4-space indent, 80-char line width)
- **TypeScript** in strict mode

### Running the Analysis Pipeline

All commands run from `backend/`:

#### Full Automated Pipeline (Recommended)
```bash
cd backend

# Run complete pipeline: setup -> update -> clean -> generate -> analyze
make all

# What it does:
# 1. setup-cclog          - Clone claude-code-log fork (prompts for location first time)
# 2. update-cclog         - Pull latest from origin (daaain/claude-code-log)
# 3. clean-cclog-output   - Delete old full-transcripts.json and HTML files from ~/.claude/projects
# 4. generate-cclog-data  - Generate fresh conversation data (writes to cclog SQLite DB)
# 5. conversations-analysis - Augment DB with cost and quality metrics
```

**First-time setup**: On first run, `make all` (or `make setup-cclog`) will prompt you to choose where to clone claude-code-log:
1. `~/work/claude-code-log` (recommended, next to `collab/`)
2. `~/.cache/claude-code-log` (cache directory)
3. Custom path

Your choice is saved in `backend/.cclog-config` (gitignored). To change location, delete it and run `make setup-cclog`.

#### Individual Pipeline Steps
For debugging or partial updates:
```bash
cd backend
make setup-cclog           # Clone/verify claude-code-log exists
make update-cclog          # Pull latest from origin
make clean-cclog-output    # Delete old output files (HTML, full-transcripts.json)
make generate-cclog-data   # Generate full-transcripts.json files
make conversations-analysis # Run analysis only (skip data generation)
```

#### Manual Analysis (Advanced)
```bash
cd backend

uv run python -m src.app \
  --cclog-db ~/.claude/projects/claude-code-log-cache.db \
  --claude-projects ~/.claude/projects \
  --project-filter "permissions" \
  --verbose
```

**Note**: `make all` handles the full pipeline from scratch. Individual targets are for debugging.

## Architecture

### Data Flow

1. **claude-code-log** (external tool) — Generates `full-transcripts.json` and populates a SQLite DB (`claude-code-log-cache.db`) in `~/.claude/projects`

2. **CCLogDBReader** (`db_reader.py`) — Reads projects, sessions, and messages from the cclog SQLite DB

3. **Pricing** (`pricing.py`) — Calculates per-session costs using model-specific token pricing

4. **Analyzer** (`analyzer.py`) — Core quality analysis engine
   - Analyzes conversation quality (cache usage, length, query specificity)
   - Detects compaction events (cache drops >10k tokens)

5. **DBAugmenter** (`db_augmenter.py`) — Writes computed cost and quality metrics back to the SQLite DB (`session_costs`, `session_quality` tables)

6. **FallbackWriter** (`fallback_writer.py`) — Discovers projects in `~/.claude/projects` that don't have cclog data and writes them as fallback entries

7. **Frontend** (`frontend/`) — Next.js dashboard that reads from the augmented DB via API routes

### Cost Calculation Logic

Costs are computed per-session by grouping tokens by model:
- Each model's token counts (input, output, cache_creation, cache_read) are priced using `MODEL_PRICING` in `pricing.py`
- Per-session costs and model breakdowns are stored in the `session_costs` table

### Conversation Quality Scoring

The analyzer weights multiple factors (see `calculate_overall_score` in `analyzer.py`):
- **Cache Usage** (40%) — Primary cost driver; tracks cache read tokens vs thresholds
- **Conversation Length** (30%) — Message count vs length thresholds
- **Query Specificity** (15%) — Detects vague queries vs specific ones
- **Context Utilization** (10%) — Redundancy and token efficiency
- **Prompt Efficiency** (5%) — Input token optimization

**Violations**: Conversations with excessive cache usage (>30M tokens) OR excessive length (>500 messages) are capped at score 30 (grade F).

### Data Sources

**Primary**: cclog SQLite database (`claude-code-log-cache.db`)
- Generated by claude-code-log (`make generate-cclog-data`)
- Contains projects, sessions, messages with accurate token counts

**Fallback**: Legacy project data from `~/.claude/projects`
- `cache/index.json` — Conversation metadata
- JSONL/JSON cache files — Full conversation messages
- Used for projects without cclog data

## File Organization

### Backend (Python)
```
backend/
├── Makefile                 # Build/task automation (cclog + analysis pipeline)
├── pyproject.toml           # Python project metadata (hatchling)
├── ruff.toml                # Ruff formatter/linter config
├── .cclog-config            # Local path to claude-code-log clone (gitignored)
├── src/
│   ├── app.py               # Main entry point and pipeline orchestrator
│   ├── analyzer.py          # Core quality analysis logic (scoring, metrics)
│   ├── conversation_types.py # Type definitions (dataclasses)
│   ├── db_reader.py         # Reads from cclog SQLite DB
│   ├── db_augmenter.py      # Writes cost/quality tables to SQLite DB
│   ├── pricing.py           # Model-specific token pricing
│   ├── fallback_writer.py   # Discovers and writes non-cclog projects
│   └── data_loader.py       # Legacy loader (used by fallback_writer)
└── output/                  # Gitignored except README
```

### Frontend Directory Structure
```
frontend/
├── biome.json               # Linter/formatter config (Biome 2.1.2)
├── next.config.ts           # Next.js config
├── package.json             # Dependencies (Next.js 16, React 19, Recharts)
├── postcss.config.mjs       # Tailwind CSS v4
├── tsconfig.json            # TypeScript strict mode, @/* path alias
└── src/
    ├── app/
    │   ├── globals.css      # Theme (purple accent, dark/light via CSS vars)
    │   ├── layout.tsx       # Root layout: Geist fonts, AppProvider
    │   ├── page.tsx         # Overview: project grid with search/sort
    │   ├── api/             # API routes (reads from SQLite DB)
    │   ├── projects/[id]/
    │   │   └── page.tsx     # Project detail: conversation list
    │   └── sessions/        # Session detail pages
    ├── components/
    │   ├── ConversationCard.tsx  # Expandable card with metrics, chart, messages
    │   ├── Header.tsx           # Sticky header with metrics + theme toggle
    │   ├── ProjectCard.tsx      # Project card with grade distribution
    │   ├── SessionMessageList.tsx # Message transcript viewer
    │   └── TokenChart.tsx       # Recharts line chart + compaction markers
    ├── context/
    │   └── AppContext.tsx        # Global state: data, search, sort, theme
    └── lib/
        ├── types.ts             # TS interfaces
        ├── pricing.ts           # Client-side pricing utils
        └── utils.ts             # Formatting, filtering, sorting helpers
```

## Common Tasks

### Modifying Quality Metrics

1. Update analysis functions in `backend/src/analyzer.py` (e.g., `analyze_cache_read_abuse`, `analyze_query_specificity`)
2. Update `calculate_overall_score` to adjust weights
3. Update `QualityMetrics` dataclass in `backend/src/conversation_types.py` if adding new fields

### Adding a New Model to Pricing

Update `MODEL_PRICING` dict in `backend/src/pricing.py`:
```python
MODEL_PRICING = {
    'claude-new-model-20251231': {
        'input': 3.00,
        'output': 15.00,
        'cache_creation': 3.75,
        'cache_read': 0.30,
    },
    # ... existing models
}
```

## Important Patterns

### Error Handling

The codebase uses defensive programming:
- Try/except around file reads with fallbacks
- Warnings printed to console, not raised
- Graceful degradation when data unavailable

### Type Safety

- Uses Python 3.13 type hints throughout
- Dataclasses for structured data (`backend/src/conversation_types.py`)
- mypy strict mode enabled
- Use `Path` objects for file paths, not strings

### Frontend (Next.js)

**Stack**: Next.js 16, React 19, Tailwind CSS v4, Recharts, Biome 2.1.2, TypeScript strict

**Key patterns**:
- Single `AppContext` for all app-wide state (data, search, sort, theme)
- CSS custom properties for dark/light theme (`globals.css` with `@theme inline` block)
- Geist fonts (sans + mono) via `next/font/google`
- Path alias `@/*` → `./src/*`
- Purple accent color (`#7c3aed` dark / `#6d28d9` light)
- API routes read directly from the cclog SQLite DB

**Recharts SSR handling**: `TokenChart.tsx` dynamically imports recharts via `useEffect` + `import("recharts")` to avoid server-side rendering issues.
