"""
Augments the cclog SQLite database with cost and quality analysis tables.

Writes NEW tables (session_costs, session_quality) into the cclog DB.
cclog itself doesn't know about these tables and won't touch them.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class DBAugmenter:
    """Writes analysis results into the cclog database as new tables."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute('PRAGMA journal_mode=WAL')
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create augmented tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS session_costs (
                session_id TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                total_cost REAL NOT NULL,
                cost_per_message REAL DEFAULT 0.0,
                primary_model TEXT,
                model_breakdown TEXT,
                computed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_quality (
                session_id TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL,
                overall_score REAL,
                grade TEXT,
                query_specificity_score REAL,
                context_utilization_score REAL,
                prompt_efficiency_score REAL,
                vague_queries_count INTEGER,
                specific_queries_count INTEGER,
                redundant_requests_count INTEGER,
                cache_read_millions REAL,
                cache_read_severity TEXT,
                cache_score REAL,
                length_severity TEXT,
                length_score REAL,
                message_count INTEGER,
                compaction_count INTEGER DEFAULT 0,
                should_have_compacted INTEGER DEFAULT 0,
                compaction_events TEXT,
                token_progression TEXT,
                computed_at TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS user_prompts_fts USING fts5(
                content,
                session_id UNINDEXED,
                project_id UNINDEXED,
                message_index UNINDEXED,
                timestamp UNINDEXED,
                tokenize = 'unicode61 remove_diacritics 2'
            );
        """)
        self.conn.commit()

    def clear_user_prompts_fts(self) -> None:
        """Wipe the FTS index so a pipeline re-run doesn't duplicate rows."""
        self.conn.execute('DELETE FROM user_prompts_fts')
        self.conn.commit()

    def write_user_prompt(
        self,
        session_id: str,
        project_id: int,
        message_index: int,
        timestamp: str,
        content: str,
    ) -> None:
        """Insert a user prompt into the FTS index."""
        self.conn.execute(
            """INSERT INTO user_prompts_fts
               (content, session_id, project_id, message_index, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (content, session_id, project_id, message_index, timestamp),
        )

    def write_session_cost(self, session_id: str, project_id: int, cost_data: dict[str, Any]) -> None:
        """Write or replace cost data for a session."""
        self.conn.execute(
            """INSERT OR REPLACE INTO session_costs
               (session_id, project_id, total_cost, cost_per_message, primary_model, model_breakdown, computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                project_id,
                cost_data['total_cost'],
                cost_data.get('cost_per_message', 0.0),
                cost_data.get('primary_model'),
                json.dumps(cost_data.get('model_breakdown', {})),
                datetime.now().isoformat(),
            ),
        )

    def write_session_quality(self, session_id: str, project_id: int, quality_data: dict[str, Any]) -> None:
        """Write or replace quality data for a session."""
        self.conn.execute(
            """INSERT OR REPLACE INTO session_quality
               (session_id, project_id, overall_score, grade,
                query_specificity_score, context_utilization_score, prompt_efficiency_score,
                vague_queries_count, specific_queries_count, redundant_requests_count,
                cache_read_millions, cache_read_severity, cache_score,
                length_severity, length_score, message_count,
                compaction_count, should_have_compacted, compaction_events, token_progression,
                computed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                project_id,
                quality_data.get('overall_score'),
                quality_data.get('grade'),
                quality_data.get('query_specificity_score'),
                quality_data.get('context_utilization_score'),
                quality_data.get('prompt_efficiency_score'),
                quality_data.get('vague_queries_count'),
                quality_data.get('specific_queries_count'),
                quality_data.get('redundant_requests_count'),
                quality_data.get('cache_read_millions'),
                quality_data.get('cache_read_severity'),
                quality_data.get('cache_score'),
                quality_data.get('length_severity'),
                quality_data.get('length_score'),
                quality_data.get('message_count'),
                quality_data.get('compaction_count', 0),
                1 if quality_data.get('should_have_compacted') else 0,
                json.dumps(quality_data.get('compaction_events', [])),
                json.dumps(quality_data.get('token_progression', [])),
                datetime.now().isoformat(),
            ),
        )

    def commit(self) -> None:
        """Commit pending writes."""
        self.conn.commit()

    def close(self) -> None:
        """Commit and close the database connection."""
        self.conn.commit()
        self.conn.close()
