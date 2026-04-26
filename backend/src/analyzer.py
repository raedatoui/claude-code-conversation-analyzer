"""
Analyzer module that adds conversation cost and quality analysis to loaded data.

This module uses hardcoded Anthropic pricing to calculate costs from token usage.
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from .conversation_types import (
    AnalysisReport,
    ConversationAnalysis,
    ConversationSession,
    CostMetrics,
    ProjectGroup,
    ProjectMetrics,
    QualityMetrics,
)
from .pricing import calculate_cost

# ---------- Benchmarks ----------
BENCHMARKS = {
    'optimal_input_tokens_per_message': 200,
    'max_efficient_input_tokens': 1000,
    'reasonable_total_tokens': 10000,
    'expensive_total_tokens': 25000,
    'very_expensive_total_tokens': 50000,
    'extreme_total_tokens': 100000,
}

# Conversation length thresholds
CONVERSATION_LENGTH_THRESHOLDS = {
    'reasonable': 100,
    'long': 300,
    'very_long': 500,
    'extreme': 800,
    'unacceptable': 1000,
}

# Cache read token thresholds (millions)
CACHE_READ_THRESHOLDS = {
    'normal': 5_000_000,
    'elevated': 15_000_000,
    'high': 30_000_000,
    'extreme': 50_000_000,
    'abusive': 70_000_000,
}

VAGUE_PATTERNS = [
    'fix the bug',
    'fix the bugs',
    "what's wrong",
    'check all',
    'entire project',
    'everything',
    'all files',
    'scan the repo',
    'look at this',
    'help with this',
    'find all',
    'search entire',
    'debug this',
    'fix the test',
    'i have errors',
]
SPECIFIC_HINTS = ['in file', 'exactly', 'line ', 'at path', 'in directory', 'glob ', 'grep ']


# ---------- Helper Functions ----------
def safe_get(d: dict[str, Any], keys: list[str], default=None):
    """Safely get nested dict values."""
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def analyze_conversation_length(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze conversation length to detect overly long conversations."""
    conversation_length = len(messages)

    if conversation_length < CONVERSATION_LENGTH_THRESHOLDS['reasonable']:
        severity = 'excellent'
        score = 100
    elif conversation_length < CONVERSATION_LENGTH_THRESHOLDS['long']:
        severity = 'good'
        score = 85
    elif conversation_length < CONVERSATION_LENGTH_THRESHOLDS['very_long']:
        severity = 'acceptable'
        score = 70
    elif conversation_length < CONVERSATION_LENGTH_THRESHOLDS['extreme']:
        severity = 'concerning'
        score = 40
    elif conversation_length < CONVERSATION_LENGTH_THRESHOLDS['unacceptable']:
        severity = 'critical'
        score = 20
    else:
        severity = 'unacceptable'
        score = 5

    return {
        'score': score,
        'severity': severity,
        'message_count': conversation_length,
        'is_violation': conversation_length >= CONVERSATION_LENGTH_THRESHOLDS['very_long'],
    }


def analyze_cache_read_abuse(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze cache read token usage - THE PRIMARY COST DRIVER."""
    total_cache_read_tokens = 0

    for msg in messages:
        if msg.get('type') == 'assistant':
            usage = msg.get('message', {}).get('usage', {})
            if not usage:
                usage = msg.get('usage', {})
            cache_read = int(usage.get('cache_read_input_tokens', 0) or 0)
            total_cache_read_tokens += cache_read

    if total_cache_read_tokens < CACHE_READ_THRESHOLDS['normal']:
        severity = 'excellent'
        score = 100
    elif total_cache_read_tokens < CACHE_READ_THRESHOLDS['elevated']:
        severity = 'good'
        score = 85
    elif total_cache_read_tokens < CACHE_READ_THRESHOLDS['high']:
        severity = 'elevated'
        score = 60
    elif total_cache_read_tokens < CACHE_READ_THRESHOLDS['extreme']:
        severity = 'high'
        score = 30
    elif total_cache_read_tokens < CACHE_READ_THRESHOLDS['abusive']:
        severity = 'extreme'
        score = 10
    else:
        severity = 'abusive'
        score = 5

    return {
        'score': score,
        'severity': severity,
        'total_cache_read_tokens': total_cache_read_tokens,
        'total_cache_read_millions': round(total_cache_read_tokens / 1_000_000, 2),
        'is_violation': total_cache_read_tokens >= CACHE_READ_THRESHOLDS['high'],
    }


def analyze_compaction_events(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze cache token progression to detect compaction events."""
    token_progression = []
    compaction_events = []
    prev_cache_read = 0
    message_index = 0

    for msg in messages:
        if msg.get('type') == 'assistant':
            usage = msg.get('message', {}).get('usage', {})
            if not usage:
                usage = msg.get('usage', {})

            cache_read = int(usage.get('cache_read_input_tokens', 0) or 0)
            cache_creation = int(usage.get('cache_creation_input_tokens', 0) or 0)
            input_tokens = int(usage.get('input_tokens', 0) or 0)
            output_tokens = int(usage.get('output_tokens', 0) or 0)
            timestamp = msg.get('timestamp', '')

            token_drop = prev_cache_read - cache_read
            is_compaction = token_drop > 10_000

            if is_compaction:
                compaction_events.append(
                    {
                        'message_index': message_index,
                        'timestamp': timestamp,
                        'cache_read_before': prev_cache_read,
                        'cache_read_after': cache_read,
                        'token_drop': token_drop,
                    }
                )

            token_progression.append(
                {
                    'message_index': message_index,
                    'timestamp': timestamp,
                    'cache_read_tokens': cache_read,
                    'cache_creation_tokens': cache_creation,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'is_compaction_event': is_compaction,
                    'token_drop': token_drop if is_compaction else 0,
                }
            )

            prev_cache_read = cache_read
            message_index += 1

    compaction_count = len(compaction_events)
    total_messages = len(token_progression)
    max_cache_read = max([tp['cache_read_tokens'] for tp in token_progression]) if token_progression else 0
    should_have_compacted = max_cache_read > 50_000_000 and compaction_count == 0

    if compaction_count > 0 and total_messages > 0:
        messages_per_compaction = total_messages / compaction_count
    else:
        messages_per_compaction = total_messages if total_messages > 0 else 0

    return {
        'compaction_count': compaction_count,
        'compaction_events': compaction_events,
        'token_progression': token_progression,
        'should_have_compacted': should_have_compacted,
        'messages_per_compaction': round(messages_per_compaction, 1),
    }


def analyze_query_specificity(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze query specificity."""
    user_messages = [(i, msg) for i, msg in enumerate(messages, 1) if msg.get('type') == 'user']
    vague_count = specific_count = 0

    for idx, msg in user_messages:
        content = safe_get(msg, ['message', 'content'], '')
        if isinstance(content, str):
            content_lower = content.lower()
            if any(pat in content_lower for pat in VAGUE_PATTERNS):
                vague_count += 1
            if any(hint in content_lower for hint in SPECIFIC_HINTS):
                specific_count += 1

    total = max(len(user_messages), 1)
    vague_ratio = vague_count / total
    specific_ratio = specific_count / total

    score = max(0, min(100, 100 - 40 * vague_ratio + 15 * specific_ratio))
    status = 'excellent' if score >= 85 else 'good' if score >= 70 else 'needs_improvement' if score >= 55 else 'poor'

    return {
        'score': round(score, 1),
        'status': status,
        'vague_queries': vague_count,
        'specific_queries': specific_count,
        'specificity_score': round(score, 1),
    }


def analyze_context_utilization(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze how efficiently context is being used."""
    total_tokens = 0
    redundant_msgs = 0
    seen_content = set()

    for msg in messages:
        if msg.get('type') == 'user':
            content = safe_get(msg, ['message', 'content'], '')
            if isinstance(content, str):
                content_hash = hash(content.lower().strip())
                if content_hash in seen_content:
                    redundant_msgs += 1
                else:
                    seen_content.add(content_hash)
        elif msg.get('type') == 'assistant':
            usage = safe_get(msg, ['message', 'usage'], {})
            total_tokens += int(usage.get('input_tokens', 0) or 0)
            total_tokens += int(usage.get('output_tokens', 0) or 0)

    conversation_length = len(messages)
    avg_tokens_per_message = total_tokens / max(conversation_length, 1)
    redundancy_ratio = redundant_msgs / max(len([m for m in messages if m.get('type') == 'user']), 1)

    score = max(0, min(100, 100 - (redundancy_ratio * 50) - max(0, (avg_tokens_per_message - 2000) / 100)))
    status = 'excellent' if score >= 85 else 'good' if score >= 70 else 'needs_improvement' if score >= 55 else 'poor'

    return {
        'score': round(score, 1),
        'status': status,
        'avg_tokens_per_message': round(avg_tokens_per_message, 1),
        'redundant_requests': redundant_msgs,
        'utilization_score': round(score, 1),
    }


def analyze_prompt_efficiency(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze input token efficiency and prompt quality."""
    user_messages = [msg for msg in messages if msg.get('type') == 'user']
    if not user_messages:
        return {'score': 100, 'status': 'excellent', 'efficiency_score': 100.0}

    input_tokens = []
    verbose_prompts = 0
    optimal_prompts = 0

    for msg in user_messages:
        content = safe_get(msg, ['message', 'content'], '')
        if isinstance(content, str):
            estimated_tokens = len(content) // 4
            input_tokens.append(estimated_tokens)

            if estimated_tokens > BENCHMARKS['max_efficient_input_tokens']:
                verbose_prompts += 1
            elif estimated_tokens <= BENCHMARKS['optimal_input_tokens_per_message']:
                optimal_prompts += 1

    avg_tokens = statistics.mean(input_tokens) if input_tokens else 0
    verbose_ratio = verbose_prompts / len(user_messages)
    optimal_ratio = optimal_prompts / len(user_messages)

    score = max(
        0,
        min(100, 100 - (verbose_ratio * 40) + (optimal_ratio * 20) - max(0, (avg_tokens - 300) / 20)),
    )
    status = 'excellent' if score >= 85 else 'good' if score >= 70 else 'needs_improvement' if score >= 55 else 'poor'

    return {'score': round(score, 1), 'status': status, 'efficiency_score': round(score, 1)}


def calculate_overall_score(
    cache_analysis: dict[str, Any],
    length_analysis: dict[str, Any],
    query_specificity: dict[str, Any],
    context_utilization: dict[str, Any],
    prompt_efficiency: dict[str, Any],
) -> tuple[float, str]:
    """Calculate weighted overall score focused on quality and efficiency."""
    # Extract scores
    cache_score = cache_analysis['score']
    length_score = length_analysis['score']
    query_score = query_specificity['score']
    context_score = context_utilization['score']
    prompt_score = prompt_efficiency['score']

    # Weighted calculation (cache and length are primary drivers)
    weights = {
        'cache': 0.40,
        'length': 0.30,
        'query': 0.15,
        'context': 0.10,
        'prompt': 0.05,
    }

    overall = weights['cache'] * cache_score + weights['length'] * length_score + weights['query'] * query_score + weights['context'] * context_score + weights['prompt'] * prompt_score

    # Apply violations (hard caps on score)
    if cache_analysis['is_violation'] or length_analysis['is_violation']:
        overall = min(overall, 30)
        grade = 'F'
    else:
        grade = 'A' if overall >= 90 else 'B' if overall >= 80 else 'C' if overall >= 70 else 'D' if overall >= 60 else 'F'

    return round(overall, 1), grade


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL file and return messages."""
    msgs = []
    try:
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    msgs.append(json.loads(s))
                except Exception:
                    pass
    except Exception:
        pass
    return msgs


def read_cache_json(path: Path) -> list[dict[str, Any]]:
    """Read cache/*.json file and return messages in JSONL-compatible format.

    Cache JSON files are structured as:
    {
        "_no_timestamp": [...],
        "2025-08-22T15:01:07.199Z": [message1, message2, ...],
        "2025-08-22T15:01:10.686Z": [message3, ...]
    }

    We flatten all messages from timestamp keys and return them chronologically.
    """
    msgs = []
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        # Collect all messages from timestamp keys (skip _no_timestamp)
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if isinstance(value, list):
                for msg in value:
                    if isinstance(msg, dict):
                        msgs.append(msg)

        # Sort by timestamp to maintain chronological order
        msgs.sort(key=lambda m: m.get('timestamp', ''))

    except Exception as e:
        print(f'Warning: Error reading cache JSON {path}: {e}')

    return msgs


class ConversationAnalyzer:
    """Analyzes conversations with cost calculation and quality rating.

    Uses LiteLLM pricing fetcher to calculate costs from token usage.
    """

    def __init__(self, claude_projects_path: Path):
        self.claude_projects_path = claude_projects_path

    def analyze_projects(self, projects: dict[str, ProjectGroup]) -> AnalysisReport:
        """Analyze all projects with conversation analysis."""
        print('Starting project analysis...')

        # Analyze each project
        analyzed_projects = []
        for project_name, project in projects.items():
            analyzed_project = self._analyze_project(project)
            analyzed_projects.append(analyzed_project)

        # Create analysis report
        total_conversations = sum(p.metrics.total_conversations for p in analyzed_projects)
        total_cost = sum(p.metrics.total_cost for p in analyzed_projects)
        total_tokens = sum(p.metrics.total_tokens for p in analyzed_projects)

        return AnalysisReport(
            projects=analyzed_projects,
            total_conversations=total_conversations,
            total_cost=total_cost,
            total_tokens=total_tokens,
            analysis_timestamp=datetime.now().isoformat(),
        )

    def _analyze_project(self, project: ProjectGroup) -> ProjectGroup:
        """Analyze a single project."""
        print(f'Analyzing project: {project.name}')

        # Analyze each conversation in the project
        analyzed_conversations = []
        total_tokens = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_creation_tokens = 0
        total_cache_read_tokens = 0
        total_cost = 0.0
        scores = []
        total_issues = 0

        for conversation in project.conversations:
            analyzed_conversation = self._analyze_conversation(conversation)
            analyzed_conversations.append(analyzed_conversation)

            if analyzed_conversation.analysis:
                total_tokens += analyzed_conversation.analysis.cost_metrics.total_tokens
                total_input_tokens += analyzed_conversation.analysis.cost_metrics.input_tokens
                total_output_tokens += analyzed_conversation.analysis.cost_metrics.output_tokens
                total_cache_creation_tokens += analyzed_conversation.analysis.cost_metrics.cache_creation_tokens
                total_cache_read_tokens += analyzed_conversation.analysis.cost_metrics.cache_read_tokens
                # Sum calculated costs (each conversation sums tokens correctly)
                total_cost += analyzed_conversation.analysis.cost_metrics.total_cost
                scores.append(analyzed_conversation.analysis.quality_metrics.overall_score)
                total_issues += len(analyzed_conversation.analysis.issues)

        # Calculate project metrics
        average_score = sum(scores) / len(scores) if scores else 0.0

        # Update project metrics
        project.metrics = ProjectMetrics(
            total_conversations=len(analyzed_conversations),
            total_cost=total_cost,
            total_tokens=total_tokens,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_cache_creation_tokens=total_cache_creation_tokens,
            total_cache_read_tokens=total_cache_read_tokens,
            average_score=average_score,
            total_issues=total_issues,
            conversation_date_range=project.metrics.conversation_date_range,
        )

        # Update conversations
        project.conversations = analyzed_conversations

        return project

    def _find_cache_json_for_session(self, session_id: str) -> Path | None:
        """Find the cache/*.json file for a given session ID.

        Searches in all project directories for cache/{session_id}.json
        """
        if not self.claude_projects_path:
            return None

        # Search through all project directories
        for project_dir in self.claude_projects_path.iterdir():
            if not project_dir.is_dir():
                continue

            cache_dir = project_dir / 'cache'
            if not cache_dir.exists():
                continue

            cache_json = cache_dir / f'{session_id}.json'
            if cache_json.exists():
                return cache_json

        return None

    def _analyze_conversation(self, conversation: ConversationSession) -> ConversationSession:
        """Analyze a single conversation using token-based cost calculation."""
        messages = []

        # Try to load messages from JSONL file first
        if conversation.parent_jsonl_file and conversation.parent_jsonl_file.exists():
            messages = read_jsonl(conversation.parent_jsonl_file)

        # If no JSONL, try to load from cache/*.json file
        if not messages:
            cache_json_path = self._find_cache_json_for_session(conversation.session_id)
            if cache_json_path and cache_json_path.exists():
                messages = read_cache_json(cache_json_path)

        # If still no messages, fall back to cache/index.json data
        if not messages:
            if conversation.cached_input_tokens is not None and conversation.cached_output_tokens is not None:
                conversation.analysis = self._create_analysis_from_cache(conversation)
            return conversation

        try:
            # Get analysis metrics
            length_analysis = analyze_conversation_length(messages)
            cache_analysis = analyze_cache_read_abuse(messages)
            compaction_analysis = analyze_compaction_events(messages)
            query_specificity = analyze_query_specificity(messages)
            context_utilization = analyze_context_utilization(messages)
            prompt_efficiency = analyze_prompt_efficiency(messages)

            # Calculate cost per message using message deduplication:
            # 1. Deduplicate messages by message ID + request ID
            #    Keep the LAST occurrence (streaming completion) for complete token counts
            # 2. Pass RAW usage values to cost calculator (no delta computation)
            # 3. Sum costs across unique messages
            #
            # JSONL contains streaming updates: first message has partial output tokens,
            # last message has complete output tokens. Must keep LAST occurrence!

            # First pass: collect all messages and identify last occurrence of each ID
            message_map = {}  # hash -> message (keeps last occurrence)

            for msg in messages:
                # Extract message data
                msg_data = msg.get('message', {}) if 'message' in msg else msg

                # Build unique hash: messageId:requestId
                message_id = msg_data.get('id') if isinstance(msg_data, dict) else None
                request_id = msg.get('requestId')

                if message_id and request_id:
                    unique_hash = f'{message_id}:{request_id}'
                    # Overwrite with latest message (keeps LAST occurrence)
                    message_map[unique_hash] = msg
                else:
                    # Messages without IDs (user messages) - keep all
                    message_map[id(msg)] = msg

            # Second pass: calculate cost from deduplicated messages
            input_tokens = 0
            output_tokens = 0
            cache_creation_tokens = 0
            cache_read_tokens = 0
            calculated_cost = 0.0
            models_found = set()

            for msg in message_map.values():
                # Extract message data
                msg_data = msg.get('message', {}) if 'message' in msg else msg

                # Extract usage (handles both JSONL and cache JSON formats)
                usage = msg_data.get('usage', {}) if isinstance(msg_data, dict) else {}
                if not usage:
                    usage = msg.get('usage', {})

                if not usage:
                    continue

                # Get RAW token values from this message (no delta computation)
                msg_input = usage.get('input_tokens', 0)
                msg_output = usage.get('output_tokens', 0)
                msg_cache_creation = usage.get('cache_creation_input_tokens', 0)
                msg_cache_read = usage.get('cache_read_input_tokens', 0)

                # Sum tokens (for display)
                input_tokens += msg_input
                output_tokens += msg_output
                cache_creation_tokens = max(cache_creation_tokens, msg_cache_creation)
                cache_read_tokens = max(cache_read_tokens, msg_cache_read)

                # Extract model name
                model = msg_data.get('model') if isinstance(msg_data, dict) else None
                if not model:
                    model = msg.get('model')
                if model:
                    models_found.add(model)

                # Calculate cost using RAW token values
                if model and usage:
                    # Pass raw usage values to pricing calculator
                    msg_cost = calculate_cost(usage, model)
                    calculated_cost += msg_cost

            # Determine primary model (use most complete model name)
            primary_model = 'unknown'
            if models_found:
                # Prefer longer model names
                # (e.g., "claude-sonnet-4-20250514" over "claude-sonnet-4")
                primary_model = max(models_found, key=len)

            message_count = len([m for m in messages if m.get('type') in ['user', 'assistant']])

            # Use calculated cost from token counts
            cost_per_message = calculated_cost / max(message_count, 1)

            cost_metrics = CostMetrics(
                total_cost=calculated_cost,
                cost_per_message=cost_per_message,
                total_tokens=input_tokens + output_tokens,
                average_tokens_per_message=(input_tokens + output_tokens) / max(message_count, 1),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                primary_model=primary_model,
                model_breakdown={},
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
            )

            # Calculate overall score
            overall_score, grade = calculate_overall_score(
                cache_analysis=cache_analysis,
                length_analysis=length_analysis,
                query_specificity=query_specificity,
                context_utilization=context_utilization,
                prompt_efficiency=prompt_efficiency,
            )

            # Create quality metrics with cache and length data
            quality_metrics = QualityMetrics(
                overall_score=overall_score,
                grade=grade,
                query_specificity_score=query_specificity['score'],
                context_utilization_score=context_utilization['score'],
                prompt_efficiency_score=prompt_efficiency['score'],
                vague_queries_count=query_specificity['vague_queries'],
                specific_queries_count=query_specificity['specific_queries'],
                redundant_requests_count=context_utilization['redundant_requests'],
                cache_read_millions=cache_analysis['total_cache_read_millions'],
                cache_read_severity=cache_analysis['severity'],
                cache_score=cache_analysis['score'],
                length_severity=length_analysis['severity'],
                length_score=length_analysis['score'],
                message_count=length_analysis['message_count'],
            )

            # Create analysis
            conversation.analysis = ConversationAnalysis(
                cost_metrics=cost_metrics,
                quality_metrics=quality_metrics,
                conversation_length=len(messages),
                issues=[],
                analysis_timestamp=datetime.now().isoformat(),
                compaction_count=compaction_analysis['compaction_count'],
                compaction_events=compaction_analysis['compaction_events'],
                token_progression=compaction_analysis['token_progression'],
                should_have_compacted=compaction_analysis['should_have_compacted'],
                messages_per_compaction=compaction_analysis['messages_per_compaction'],
            )

        except Exception as e:
            print(f'Warning: Error analyzing {conversation.parent_jsonl_file}: {e}')
            if conversation.cached_input_tokens is not None and conversation.cached_output_tokens is not None:
                conversation.analysis = self._create_analysis_from_cache(conversation)

        return conversation

    def _create_analysis_from_cache(self, conversation: ConversationSession) -> ConversationAnalysis:
        """Create a basic analysis from cached token counts when JSONL is not available."""
        input_tokens = conversation.cached_input_tokens or 0
        output_tokens = conversation.cached_output_tokens or 0
        cache_read_tokens = conversation.cached_cache_read_tokens or 0
        cache_creation_tokens = conversation.cached_cache_creation_tokens or 0
        total_tokens = input_tokens + output_tokens

        # Estimate message count from timestamps if available
        message_count = 1
        if conversation.start_time and conversation.end_time:
            duration_minutes = (conversation.end_time - conversation.start_time).total_seconds() / 60
            message_count = max(1, int(duration_minutes / 2))

        # Calculate cost using hardcoded pricing
        # Use a default Claude model since we don't have the actual model name
        calculated_cost = calculate_cost(
            {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cache_creation_input_tokens': cache_creation_tokens,
                'cache_read_input_tokens': cache_read_tokens,
            },
            'claude-sonnet-4-20250514',  # Use a default Claude model
        )

        cost_metrics = CostMetrics(
            total_cost=calculated_cost,
            cost_per_message=calculated_cost / message_count,
            total_tokens=total_tokens,
            average_tokens_per_message=total_tokens / message_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            primary_model='unknown',
            model_breakdown={},
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
        )

        quality_metrics = QualityMetrics(
            overall_score=50.0,
            grade=self._score_to_grade(50.0),
            query_specificity_score=50.0,
            context_utilization_score=50.0,
            prompt_efficiency_score=50.0,
            vague_queries_count=0,
            specific_queries_count=0,
            redundant_requests_count=0,
            cache_read_millions=cache_read_tokens / 1_000_000 if cache_read_tokens else None,
            cache_read_severity=None,
            cache_score=50.0,
            length_severity=None,
            length_score=50.0,
            message_count=message_count,
        )

        return ConversationAnalysis(
            cost_metrics=cost_metrics,
            quality_metrics=quality_metrics,
            conversation_length=message_count,
            issues=['Cache-only conversation'],
            analysis_timestamp=datetime.now().isoformat(),
        )

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
