"""
Writes fallback data for projects that cclog doesn't discover.

Uses the legacy ConversationDataLoader to find projects not in the cclog DB,
then writes their data into fallback_* tables in the same SQLite database.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .data_loader import ConversationDataLoader
from .pricing import calculate_cost


class FallbackWriter:
    """Discovers and writes fallback projects not covered by cclog."""

    def __init__(self, db_path: Path, claude_projects_path: Path) -> None:
        self.db_path = db_path
        self.claude_projects_path = claude_projects_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute('PRAGMA journal_mode=WAL')
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create fallback tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS fallback_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                dir_name TEXT NOT NULL,
                total_conversations INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                earliest_timestamp TEXT,
                latest_timestamp TEXT,
                last_updated TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fallback_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES fallback_projects(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL,
                title TEXT,
                first_timestamp TEXT,
                last_timestamp TEXT,
                duration_minutes REAL,
                message_count INTEGER DEFAULT 0,
                cwd TEXT,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                total_cache_creation_tokens INTEGER DEFAULT 0,
                total_cache_read_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                UNIQUE(project_id, session_id)
            );

            CREATE TABLE IF NOT EXISTS fallback_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                project_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                message_label TEXT,
                timestamp TEXT,
                content TEXT NOT NULL,
                is_meta INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def discover_and_write_fallback_projects(self, cclog_project_paths: set[str]) -> None:
        """Find projects not in cclog and write them to fallback tables.

        Args:
            cclog_project_paths: Set of project_path values from cclog's projects table.
        """
        loader = ConversationDataLoader(self.claude_projects_path)
        all_projects = loader.load_all_conversations()

        fallback_count = 0

        for dir_name, project_group in all_projects.items():
            # Check if this project is already in cclog by matching cwd_path
            project_path = project_group.path
            if project_path and project_path in cclog_project_paths:
                continue

            # Also check by dir_name pattern matching against cclog paths
            if any(dir_name in p for p in cclog_project_paths):
                continue

            # This is a fallback project — write it
            self._write_project(dir_name, project_group)
            fallback_count += 1

        self.conn.commit()
        print(f'Wrote {fallback_count} fallback projects')

    def _write_project(self, dir_name: str, project_group: Any) -> None:
        """Write a single fallback project and its sessions/messages."""
        display_name = project_group.clean_name
        project_path = project_group.path or dir_name

        # Calculate date range
        earliest = None
        latest = None
        total_cost = 0.0

        for conv in project_group.conversations:
            if conv.start_time:
                ts = conv.start_time.isoformat()
                if earliest is None or ts < earliest:
                    earliest = ts
                if latest is None or ts > latest:
                    latest = ts

        # Insert or update project
        self.conn.execute(
            """INSERT OR REPLACE INTO fallback_projects
               (project_path, display_name, dir_name, total_conversations,
                total_cost, earliest_timestamp, latest_timestamp, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_path,
                display_name,
                dir_name,
                len(project_group.conversations),
                0.0,  # will update after computing session costs
                earliest,
                latest,
                datetime.now().isoformat(),
            ),
        )

        # Get the project ID
        fb_project_id = self.conn.execute(
            'SELECT id FROM fallback_projects WHERE project_path = ?',
            (project_path,),
        ).fetchone()[0]

        # Clear existing sessions and messages for this project
        self.conn.execute('DELETE FROM fallback_messages WHERE project_id = ?', (fb_project_id,))
        self.conn.execute('DELETE FROM fallback_sessions WHERE project_id = ?', (fb_project_id,))

        # Write sessions
        for conv in project_group.conversations:
            input_tokens = conv.cached_input_tokens or 0
            output_tokens = conv.cached_output_tokens or 0
            cache_creation = conv.cached_cache_creation_tokens or 0
            cache_read = conv.cached_cache_read_tokens or 0

            # Calculate cost using default model
            session_cost = calculate_cost(
                {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'cache_creation_input_tokens': cache_creation,
                    'cache_read_input_tokens': cache_read,
                },
                'claude-sonnet-4-5',
            )
            total_cost += session_cost

            self.conn.execute(
                """INSERT OR REPLACE INTO fallback_sessions
                   (project_id, session_id, title, first_timestamp, last_timestamp,
                    duration_minutes, message_count, cwd,
                    total_input_tokens, total_output_tokens,
                    total_cache_creation_tokens, total_cache_read_tokens, total_cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fb_project_id,
                    conv.session_id,
                    conv.title,
                    conv.start_time.isoformat() if conv.start_time else None,
                    conv.end_time.isoformat() if conv.end_time else None,
                    conv.duration_minutes,
                    len(conv.messages),
                    conv.cwd_path,
                    input_tokens,
                    output_tokens,
                    cache_creation,
                    cache_read,
                    session_cost,
                ),
            )

            # Write messages (full content, no truncation)
            for msg in conv.messages:
                self.conn.execute(
                    """INSERT INTO fallback_messages
                       (session_id, project_id, type, message_label, timestamp, content, is_meta)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        conv.session_id,
                        fb_project_id,
                        msg.type,
                        msg.message_label,
                        msg.timestamp,
                        msg.content,
                        1 if msg.is_meta else 0,
                    ),
                )

        # Update project total cost
        self.conn.execute(
            'UPDATE fallback_projects SET total_cost = ? WHERE id = ?',
            (total_cost, fb_project_id),
        )

    def close(self) -> None:
        """Commit and close the database connection."""
        self.conn.commit()
        self.conn.close()
