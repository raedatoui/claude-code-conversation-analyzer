"""
Type definitions for conversation analysis system.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ConversationMessage:
    """Individual message in a conversation."""

    type: str  # "user" or "assistant"
    content: str
    timestamp: str | None = None
    session_id: str | None = None
    is_meta: bool = False
    parent_uuid: str | None = None
    request_id: str | None = None  # For assistant messages (used in token deduplication)
    message_label: str | None = None  # Display label: "USER", "ASSISTANT", "META", "TOOL_RESULT", etc.


@dataclass
class UserPrompt:
    """User prompt with metadata."""

    content: str
    timestamp: str | None = None
    token_count: int | None = None


@dataclass
class CostMetrics:
    """Cost-related metrics."""

    total_cost: float  # Calculated from token counts and model pricing
    cost_per_message: float
    total_tokens: int
    average_tokens_per_message: float
    input_tokens: int
    output_tokens: int
    primary_model: str
    model_breakdown: dict[str, dict[str, float | int]]
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class QualityMetrics:
    """Quality assessment metrics including cache and length analysis."""

    overall_score: float
    grade: str
    query_specificity_score: float
    context_utilization_score: float
    prompt_efficiency_score: float
    vague_queries_count: int
    specific_queries_count: int
    redundant_requests_count: int
    # Cache analysis
    cache_read_millions: float | None = None
    cache_read_severity: str | None = None
    cache_score: float | None = None
    # Length analysis
    length_severity: str | None = None
    length_score: float | None = None
    message_count: int | None = None


@dataclass
class ConversationAnalysis:
    """Analysis results for a conversation."""

    cost_metrics: CostMetrics
    quality_metrics: QualityMetrics
    conversation_length: int
    issues: list[str]
    analysis_timestamp: str
    # Compaction data
    compaction_count: int | None = None
    compaction_events: list[dict[str, Any]] | None = None
    token_progression: list[dict[str, Any]] | None = None
    should_have_compacted: bool | None = None
    messages_per_compaction: float | None = None


@dataclass
class ConversationSession:
    """Complete conversation session with analysis."""

    session_id: str
    messages: list[ConversationMessage]
    user_prompts: list[UserPrompt]
    start_time: datetime | None = None
    end_time: datetime | None = None
    parent_jsonl_file: Path | None = None
    analysis: ConversationAnalysis | None = None
    cwd_path: str | None = None
    # Cached token counts from cache/index.json (pre-aggregated)
    cached_input_tokens: int | None = None
    cached_output_tokens: int | None = None
    cached_cache_creation_tokens: int | None = None
    cached_cache_read_tokens: int | None = None

    @property
    def title(self) -> str:
        """Generate a title for the conversation."""
        if self.user_prompts:
            first_prompt = self.user_prompts[0].content
            # Truncate and clean up
            title = first_prompt[:100] + ('...' if len(first_prompt) > 100 else '')
            # Remove newlines and extra spaces
            title = ' '.join(title.split())
            return title
        return f'Session {self.session_id[:8]}'

    @property
    def duration_minutes(self) -> float | None:
        """Calculate conversation duration in minutes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return None


@dataclass
class ProjectMetrics:
    """Aggregated metrics for a project."""

    total_conversations: int
    total_cost: float  # Calculated from tokens
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    total_cache_creation_tokens: int
    total_cache_read_tokens: int
    average_score: float
    total_issues: int
    conversation_date_range: tuple[datetime | None, datetime | None]


@dataclass
class ProjectGroup:
    """Group of conversations by project."""

    name: str
    conversations: list[ConversationSession]
    metrics: ProjectMetrics
    path: str | None = None

    @property
    def clean_name(self) -> str:
        """Get a cleaned version of the project name for display."""
        # Since we now extract real project names from cwd paths,
        # just return the project name directly
        return self.name


@dataclass
class AnalysisReport:
    """Complete analysis report for all conversations."""

    projects: list[ProjectGroup]
    total_conversations: int
    total_cost: float
    total_tokens: int
    analysis_timestamp: str

    @property
    def overall_metrics(self) -> dict[str, int | float]:
        """Get overall metrics across all projects."""
        if not self.projects:
            return {
                'total_projects': 0,
                'total_conversations': 0,
                'total_cost': 0.0,
                'average_score': 0.0,
                'total_tokens': 0,
            }

        return {
            'total_projects': len(self.projects),
            'total_conversations': sum(p.metrics.total_conversations for p in self.projects),
            'total_cost': sum(p.metrics.total_cost for p in self.projects),
            'average_score': sum(p.metrics.average_score for p in self.projects) / len(self.projects),
            'total_tokens': sum(p.metrics.total_tokens for p in self.projects),
        }
