#!/usr/bin/env python3
"""
Main script for the modular Conversation Rating Analyzer.

New pipeline: reads cclog DB → computes costs → computes quality → fallback → outputs.
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from .analyzer import (
    analyze_cache_read_abuse,
    analyze_compaction_events,
    analyze_context_utilization,
    analyze_conversation_length,
    analyze_prompt_efficiency,
    analyze_query_specificity,
    calculate_overall_score,
)
from .conversation_types import (
    AnalysisReport,
    ConversationAnalysis,
    ConversationMessage,
    ConversationSession,
    CostMetrics,
    ProjectGroup,
    ProjectMetrics,
    QualityMetrics,
    UserPrompt,
)
from .db_augmenter import DBAugmenter
from .db_reader import CCLogDBReader
from .fallback_writer import FallbackWriter
from .pricing import calculate_cost


def main() -> int:
    """Main entry point for the conversation analyzer."""
    parser = argparse.ArgumentParser(
        description='Analyze Claude conversations with cost and rating metrics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--cclog-db',
        type=Path,
        default=Path.home() / '.claude' / 'projects' / 'claude-code-log-cache.db',
        help='Path to cclog SQLite database (default: ~/.claude/projects/claude-code-log-cache.db)',
    )

    parser.add_argument(
        '--claude-projects',
        type=Path,
        default=Path.home() / '.claude' / 'projects',
        help='Path to Claude projects directory (default: ~/.claude/projects)',
    )


    parser.add_argument(
        '--project-filter',
        type=str,
        help='Filter to specific project name (supports partial matching)',
    )

    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Validate arguments
    if not args.cclog_db.exists():
        print(f'Error: cclog database not found: {args.cclog_db}')
        return 1

    try:
        # Step 1: Read cclog DB
        print('=' * 60)
        print('STEP 1: Reading cclog database')
        print('=' * 60)

        reader = CCLogDBReader(args.cclog_db)
        cclog_projects = reader.read_all_projects()
        print(f'Found {len(cclog_projects)} projects in cclog DB')

        # Step 2: Compute costs → write session_costs table
        print('=' * 60)
        print('STEP 2: Computing costs')
        print('=' * 60)

        augmenter = DBAugmenter(args.cclog_db)
        total_sessions = 0

        for project in cclog_projects:
            sessions = reader.read_sessions(project['id'])
            for session in sessions:
                session_id = session['session_id']
                model_groups = reader.extract_model_token_groups(session_id)

                total_cost = 0.0
                model_breakdown: dict[str, dict[str, Any]] = {}
                primary_model = 'unknown'
                max_tokens = 0

                for model, tokens in model_groups.items():
                    cost = calculate_cost(tokens, model)
                    total_cost += cost
                    model_breakdown[model] = {'cost': cost, **tokens}
                    model_total = tokens.get('input_tokens', 0) + tokens.get('output_tokens', 0)
                    if model_total > max_tokens:
                        max_tokens = model_total
                        primary_model = model

                message_count = session.get('message_count') or 1
                augmenter.write_session_cost(
                    session_id,
                    project['id'],
                    {
                        'total_cost': total_cost,
                        'cost_per_message': total_cost / max(message_count, 1),
                        'primary_model': primary_model,
                        'model_breakdown': model_breakdown,
                    },
                )
                total_sessions += 1

        augmenter.commit()
        print(f'Computed costs for {total_sessions} sessions')

        # Step 3: Compute quality → write session_quality table
        # Also populate user_prompts_fts (full-text search index over user prompts).
        print('=' * 60)
        print('STEP 3: Computing quality metrics + FTS index')
        print('=' * 60)

        augmenter.clear_user_prompts_fts()
        prompt_count = 0

        quality_count = 0
        for project in cclog_projects:
            sessions = reader.read_sessions(project['id'])
            for session in sessions:
                session_id = session['session_id']
                messages = reader.read_messages_for_quality_analysis(session_id)

                # Index user prompts for full-text search. Iterate the same
                # timestamp-ordered message list the frontend renders so
                # message_index aligns with SessionMessageList's render index.
                labeled = reader.read_user_text_content(session_id)
                for idx, m in enumerate(labeled):
                    if m.get('message_label') != 'USER':
                        continue
                    text = (m.get('content') or '').strip()
                    if not text:
                        continue
                    augmenter.write_user_prompt(
                        session_id,
                        project['id'],
                        idx,
                        m.get('timestamp') or '',
                        text,
                    )
                    prompt_count += 1

                if not messages:
                    continue

                try:
                    length_analysis = analyze_conversation_length(messages)
                    cache_analysis = analyze_cache_read_abuse(messages)
                    compaction_analysis = analyze_compaction_events(messages)
                    query_specificity = analyze_query_specificity(messages)
                    context_utilization = analyze_context_utilization(messages)
                    prompt_efficiency = analyze_prompt_efficiency(messages)

                    overall_score, grade = calculate_overall_score(
                        cache_analysis,
                        length_analysis,
                        query_specificity,
                        context_utilization,
                        prompt_efficiency,
                    )

                    augmenter.write_session_quality(
                        session_id,
                        project['id'],
                        {
                            'overall_score': overall_score,
                            'grade': grade,
                            'query_specificity_score': query_specificity['score'],
                            'context_utilization_score': context_utilization['score'],
                            'prompt_efficiency_score': prompt_efficiency['score'],
                            'vague_queries_count': query_specificity['vague_queries'],
                            'specific_queries_count': query_specificity['specific_queries'],
                            'redundant_requests_count': context_utilization['redundant_requests'],
                            'cache_read_millions': cache_analysis['total_cache_read_millions'],
                            'cache_read_severity': cache_analysis['severity'],
                            'cache_score': cache_analysis['score'],
                            'length_severity': length_analysis['severity'],
                            'length_score': length_analysis['score'],
                            'message_count': length_analysis['message_count'],
                            'compaction_count': compaction_analysis['compaction_count'],
                            'should_have_compacted': compaction_analysis['should_have_compacted'],
                            'compaction_events': compaction_analysis['compaction_events'],
                            'token_progression': compaction_analysis['token_progression'],
                        },
                    )
                    quality_count += 1
                except Exception as e:
                    if args.verbose:
                        print(f'  Warning: quality analysis failed for {session_id}: {e}')

        augmenter.commit()
        print(f'Computed quality for {quality_count} sessions')
        print(f'Indexed {prompt_count} user prompts for full-text search')

        # Step 4: Fallback projects
        print('=' * 60)
        print('STEP 4: Processing fallback projects')
        print('=' * 60)

        cclog_paths = {p['project_path'] for p in cclog_projects}
        fallback = FallbackWriter(args.cclog_db, args.claude_projects)
        fallback.discover_and_write_fallback_projects(cclog_paths)
        fallback.close()

        # Step 5: Build AnalysisReport for legacy outputs
        print('=' * 60)
        print('STEP 5: Generating outputs')
        print('=' * 60)

        analysis_report = _build_analysis_report(reader, augmenter, args.project_filter, args.verbose)

        reader.close()
        augmenter.close()

        print('Analysis complete:')
        print(f'  - Total projects: {len(analysis_report.projects)}')
        print(f'  - Total conversations: {analysis_report.total_conversations}')
        print(f'  - Total cost: ${analysis_report.total_cost:.2f}')

        print('=' * 60)
        print('ANALYSIS COMPLETE')
        print('=' * 60)

        overall_metrics = analysis_report.overall_metrics
        print(f'Successfully analyzed {overall_metrics["total_conversations"]} conversations across {overall_metrics["total_projects"]} projects')
        print(f'Total cost: ${overall_metrics["total_cost"]:.2f}')
        print(f'Average score: {overall_metrics["average_score"]:.1f}')

        return 0

    except Exception as e:
        print(f'Error: {e}')
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def _build_analysis_report(reader: CCLogDBReader, augmenter: DBAugmenter, project_filter: str | None, verbose: bool) -> AnalysisReport:
    """Build an AnalysisReport from the augmented DB for backward compat with exporters."""
    # Re-open a read connection for the augmented tables
    import json
    import sqlite3

    conn = sqlite3.connect(str(reader.db_path))
    conn.row_factory = sqlite3.Row

    # Read all projects
    projects_raw = [dict(r) for r in conn.execute('SELECT * FROM projects').fetchall()]

    # Read all session costs and quality keyed by session_id
    costs_by_session: dict[str, dict[str, Any]] = {}
    for row in conn.execute('SELECT * FROM session_costs').fetchall():
        costs_by_session[row['session_id']] = dict(row)

    quality_by_session: dict[str, dict[str, Any]] = {}
    for row in conn.execute('SELECT * FROM session_quality').fetchall():
        quality_by_session[row['session_id']] = dict(row)

    # Build project groups
    project_groups: list[ProjectGroup] = []

    for proj in projects_raw:
        project_id = proj['id']
        project_path = proj['project_path']

        # Extract project name from path
        path_parts = Path(project_path).parts
        project_name = path_parts[-1] if path_parts else project_path

        # Apply filter
        if project_filter and project_filter.lower() not in project_name.lower():
            continue

        sessions_raw = [dict(r) for r in conn.execute('SELECT * FROM sessions WHERE project_id = ?', (project_id,)).fetchall()]

        conversations: list[ConversationSession] = []
        total_cost = 0.0
        total_tokens = 0
        total_input = 0
        total_output = 0
        total_cache_creation = 0
        total_cache_read = 0
        scores: list[float] = []

        for session in sessions_raw:
            session_id = session['session_id']
            cost_row = costs_by_session.get(session_id, {})
            quality_row = quality_by_session.get(session_id, {})

            # Build cost metrics
            session_cost = cost_row.get('total_cost', 0.0)
            total_cost += session_cost
            s_input = session.get('total_input_tokens') or 0
            s_output = session.get('total_output_tokens') or 0
            s_cache_creation = session.get('total_cache_creation_tokens') or 0
            s_cache_read = session.get('total_cache_read_tokens') or 0
            total_input += s_input
            total_output += s_output
            total_cache_creation += s_cache_creation
            total_cache_read += s_cache_read
            total_tokens += s_input + s_output

            message_count = session.get('message_count') or 1

            cost_metrics = CostMetrics(
                total_cost=session_cost,
                cost_per_message=cost_row.get('cost_per_message', 0.0),
                total_tokens=s_input + s_output,
                average_tokens_per_message=(s_input + s_output) / max(message_count, 1),
                input_tokens=s_input,
                output_tokens=s_output,
                primary_model=cost_row.get('primary_model', 'unknown'),
                model_breakdown=json.loads(cost_row.get('model_breakdown', '{}')) if cost_row.get('model_breakdown') else {},
                cache_creation_tokens=s_cache_creation,
                cache_read_tokens=s_cache_read,
            )

            # Build quality metrics (nullable)
            if quality_row:
                overall_score = quality_row.get('overall_score', 0.0) or 0.0
                scores.append(overall_score)
                quality_metrics = QualityMetrics(
                    overall_score=overall_score,
                    grade=quality_row.get('grade', 'F'),
                    query_specificity_score=quality_row.get('query_specificity_score', 0.0) or 0.0,
                    context_utilization_score=quality_row.get('context_utilization_score', 0.0) or 0.0,
                    prompt_efficiency_score=quality_row.get('prompt_efficiency_score', 0.0) or 0.0,
                    vague_queries_count=quality_row.get('vague_queries_count', 0) or 0,
                    specific_queries_count=quality_row.get('specific_queries_count', 0) or 0,
                    redundant_requests_count=quality_row.get('redundant_requests_count', 0) or 0,
                    cache_read_millions=quality_row.get('cache_read_millions'),
                    cache_read_severity=quality_row.get('cache_read_severity'),
                    cache_score=quality_row.get('cache_score'),
                    length_severity=quality_row.get('length_severity'),
                    length_score=quality_row.get('length_score'),
                    message_count=quality_row.get('message_count'),
                )
                compaction_events = json.loads(quality_row.get('compaction_events') or '[]')
                token_progression = json.loads(quality_row.get('token_progression') or '[]')
                compaction_count = quality_row.get('compaction_count', 0) or 0
                should_have_compacted = bool(quality_row.get('should_have_compacted'))
            else:
                quality_metrics = QualityMetrics(
                    overall_score=50.0,
                    grade='C',
                    query_specificity_score=50.0,
                    context_utilization_score=50.0,
                    prompt_efficiency_score=50.0,
                    vague_queries_count=0,
                    specific_queries_count=0,
                    redundant_requests_count=0,
                )
                compaction_events = []
                token_progression = []
                compaction_count = 0
                should_have_compacted = False

            # Build messages and user prompts from DB
            msg_data = reader.read_user_text_content(session_id)
            conv_messages = [
                ConversationMessage(
                    type=m['type'],
                    content=m['content'],
                    timestamp=m['timestamp'],
                    session_id=session_id,
                    is_meta=m['is_meta'],
                    parent_uuid=m.get('parent_uuid'),
                    message_label=m.get('message_label'),
                )
                for m in msg_data
            ]

            user_prompts = [
                UserPrompt(content=m['content'], timestamp=m['timestamp']) for m in msg_data if m['type'] == 'user' and not m['is_meta'] and m.get('parent_uuid') is None and m['content'].strip()
            ]

            # Parse timestamps
            start_time = None
            end_time = None
            if session.get('first_timestamp'):
                try:
                    start_time = datetime.fromisoformat(session['first_timestamp'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            if session.get('last_timestamp'):
                try:
                    end_time = datetime.fromisoformat(session['last_timestamp'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass

            analysis = ConversationAnalysis(
                cost_metrics=cost_metrics,
                quality_metrics=quality_metrics,
                conversation_length=message_count,
                issues=[],
                analysis_timestamp=datetime.now().isoformat(),
                compaction_count=compaction_count,
                compaction_events=compaction_events,
                token_progression=token_progression,
                should_have_compacted=should_have_compacted,
            )

            conversations.append(
                ConversationSession(
                    session_id=session_id,
                    messages=conv_messages,
                    user_prompts=user_prompts,
                    start_time=start_time,
                    end_time=end_time,
                    analysis=analysis,
                    cwd_path=session.get('cwd'),
                    cached_input_tokens=s_input,
                    cached_output_tokens=s_output,
                    cached_cache_creation_tokens=s_cache_creation,
                    cached_cache_read_tokens=s_cache_read,
                )
            )

        # Sort by start_time descending
        conversations.sort(
            key=lambda c: (c.start_time.replace(tzinfo=None) if c.start_time else datetime.min),
            reverse=True,
        )

        avg_score = sum(scores) / len(scores) if scores else 0.0
        start_times = [c.start_time for c in conversations if c.start_time]
        date_range = (min(start_times), max(start_times)) if start_times else (None, None)

        project_groups.append(
            ProjectGroup(
                name=project_name,
                conversations=conversations,
                metrics=ProjectMetrics(
                    total_conversations=len(conversations),
                    total_cost=total_cost,
                    total_tokens=total_tokens,
                    total_input_tokens=total_input,
                    total_output_tokens=total_output,
                    total_cache_creation_tokens=total_cache_creation,
                    total_cache_read_tokens=total_cache_read,
                    average_score=avg_score,
                    total_issues=0,
                    conversation_date_range=date_range,
                ),
                path=project_path,
            )
        )

    # Also include fallback projects
    try:
        fb_projects = [dict(r) for r in conn.execute('SELECT * FROM fallback_projects').fetchall()]
    except sqlite3.OperationalError:
        fb_projects = []

    for fb_proj in fb_projects:
        fb_name = fb_proj['display_name']
        if project_filter and project_filter.lower() not in fb_name.lower():
            continue

        fb_id = fb_proj['id']
        try:
            fb_sessions = [dict(r) for r in conn.execute('SELECT * FROM fallback_sessions WHERE project_id = ?', (fb_id,)).fetchall()]
        except sqlite3.OperationalError:
            fb_sessions = []

        fb_conversations: list[ConversationSession] = []
        fb_total_cost = 0.0
        fb_total_tokens = 0
        fb_total_input = 0
        fb_total_output = 0
        fb_total_cache_creation = 0
        fb_total_cache_read = 0

        for fb_session in fb_sessions:
            s_input = fb_session.get('total_input_tokens') or 0
            s_output = fb_session.get('total_output_tokens') or 0
            s_cache_creation = fb_session.get('total_cache_creation_tokens') or 0
            s_cache_read = fb_session.get('total_cache_read_tokens') or 0
            s_cost = fb_session.get('total_cost') or 0.0
            fb_total_cost += s_cost
            fb_total_input += s_input
            fb_total_output += s_output
            fb_total_cache_creation += s_cache_creation
            fb_total_cache_read += s_cache_read
            fb_total_tokens += s_input + s_output

            msg_count = fb_session.get('message_count') or 1

            cost_metrics = CostMetrics(
                total_cost=s_cost,
                cost_per_message=s_cost / max(msg_count, 1),
                total_tokens=s_input + s_output,
                average_tokens_per_message=(s_input + s_output) / max(msg_count, 1),
                input_tokens=s_input,
                output_tokens=s_output,
                primary_model='unknown',
                model_breakdown={},
                cache_creation_tokens=s_cache_creation,
                cache_read_tokens=s_cache_read,
            )

            quality_metrics = QualityMetrics(
                overall_score=50.0,
                grade='C',
                query_specificity_score=50.0,
                context_utilization_score=50.0,
                prompt_efficiency_score=50.0,
                vague_queries_count=0,
                specific_queries_count=0,
                redundant_requests_count=0,
            )

            # Read fallback messages
            try:
                fb_msgs = [
                    dict(r)
                    for r in conn.execute(
                        'SELECT * FROM fallback_messages WHERE session_id = ? AND project_id = ?',
                        (fb_session['session_id'], fb_id),
                    ).fetchall()
                ]
            except sqlite3.OperationalError:
                fb_msgs = []

            conv_messages = [
                ConversationMessage(
                    type=m['type'],
                    content=m['content'],
                    timestamp=m.get('timestamp'),
                    session_id=fb_session['session_id'],
                    is_meta=bool(m.get('is_meta')),
                    message_label=m.get('message_label'),
                )
                for m in fb_msgs
            ]

            user_prompts = [UserPrompt(content=m['content'], timestamp=m.get('timestamp')) for m in fb_msgs if m['type'] == 'user' and not m.get('is_meta') and m['content'].strip()]

            start_time = None
            end_time = None
            if fb_session.get('first_timestamp'):
                try:
                    start_time = datetime.fromisoformat(fb_session['first_timestamp'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
            if fb_session.get('last_timestamp'):
                try:
                    end_time = datetime.fromisoformat(fb_session['last_timestamp'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass

            analysis = ConversationAnalysis(
                cost_metrics=cost_metrics,
                quality_metrics=quality_metrics,
                conversation_length=msg_count,
                issues=['Fallback project (no cclog data)'],
                analysis_timestamp=datetime.now().isoformat(),
            )

            fb_conversations.append(
                ConversationSession(
                    session_id=fb_session['session_id'],
                    messages=conv_messages,
                    user_prompts=user_prompts,
                    start_time=start_time,
                    end_time=end_time,
                    analysis=analysis,
                    cwd_path=fb_session.get('cwd'),
                    cached_input_tokens=s_input,
                    cached_output_tokens=s_output,
                    cached_cache_creation_tokens=s_cache_creation,
                    cached_cache_read_tokens=s_cache_read,
                )
            )

        fb_conversations.sort(
            key=lambda c: (c.start_time.replace(tzinfo=None) if c.start_time else datetime.min),
            reverse=True,
        )

        start_times = [c.start_time for c in fb_conversations if c.start_time]
        date_range = (min(start_times), max(start_times)) if start_times else (None, None)

        project_groups.append(
            ProjectGroup(
                name=fb_name,
                conversations=fb_conversations,
                metrics=ProjectMetrics(
                    total_conversations=len(fb_conversations),
                    total_cost=fb_total_cost,
                    total_tokens=fb_total_tokens,
                    total_input_tokens=fb_total_input,
                    total_output_tokens=fb_total_output,
                    total_cache_creation_tokens=fb_total_cache_creation,
                    total_cache_read_tokens=fb_total_cache_read,
                    average_score=50.0,
                    total_issues=0,
                    conversation_date_range=date_range,
                ),
                path=fb_proj.get('project_path'),
            )
        )

    conn.close()

    total_conversations = sum(p.metrics.total_conversations for p in project_groups)
    total_cost = sum(p.metrics.total_cost for p in project_groups)
    total_tokens = sum(p.metrics.total_tokens for p in project_groups)

    return AnalysisReport(
        projects=project_groups,
        total_conversations=total_conversations,
        total_cost=total_cost,
        total_tokens=total_tokens,
        analysis_timestamp=datetime.now().isoformat(),
    )


if __name__ == '__main__':
    exit(main())
