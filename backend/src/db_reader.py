"""
Reader for the cclog SQLite database (claude-code-log-cache.db).

Reads existing cclog tables (projects, sessions, messages) without modifying them.
Provides model-level token grouping for accurate multi-model cost calculation.
"""

import json
import sqlite3
import zlib
from pathlib import Path
from typing import Any


class CCLogDBReader:
    """Reads the cclog SQLite database."""

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise FileNotFoundError(f'cclog database not found: {db_path}')
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def read_all_projects(self) -> list[dict[str, Any]]:
        """Read all projects from cclog DB."""
        cursor = self.conn.execute('SELECT * FROM projects')
        return [dict(row) for row in cursor.fetchall()]

    def read_sessions(self, project_id: int) -> list[dict[str, Any]]:
        """Read all sessions for a given project."""
        cursor = self.conn.execute('SELECT * FROM sessions WHERE project_id = ?', (project_id,))
        return [dict(row) for row in cursor.fetchall()]

    def read_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Read all messages for a given session, ordered by timestamp."""
        cursor = self.conn.execute(
            'SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC',
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def decompress_content(self, blob: bytes) -> dict[str, Any]:
        """Decompress a zlib-compressed content blob to JSON dict."""
        try:
            decompressed = zlib.decompress(blob)
            result: dict[str, Any] = json.loads(decompressed)
            return result
        except Exception:
            return {}

    def extract_model_token_groups(self, session_id: str) -> dict[str, dict[str, int]]:
        """Extract per-model token totals for a session.

        For each message in the session:
        1. Decompress content blob
        2. Extract model from content JSON
        3. Deduplicate by _request_id (keep LAST per request_id for complete output_tokens)
        4. Group tokens by model

        Returns:
            Dict mapping model name to token counts:
            { 'claude-sonnet-4-5': { 'input_tokens': N, 'output_tokens': N,
              'cache_creation_input_tokens': N, 'cache_read_input_tokens': N } }
        """
        messages = self.read_messages(session_id)

        # Deduplicate by _request_id (keep last occurrence for complete output_tokens)
        deduped: dict[str, dict[str, Any]] = {}
        no_request_id: list[dict[str, Any]] = []

        for msg in messages:
            request_id = msg.get('_request_id')
            if request_id:
                deduped[request_id] = msg  # overwrites, keeping last
            else:
                no_request_id.append(msg)

        all_messages = list(deduped.values()) + no_request_id

        # Group tokens by model
        model_groups: dict[str, dict[str, int]] = {}

        for msg in all_messages:
            content_blob = msg.get('content')
            if not content_blob or not isinstance(content_blob, bytes):
                continue

            content = self.decompress_content(content_blob)
            if not content:
                continue

            # Extract model — try message-level content, then nested message object
            model = content.get('model')
            if not model:
                nested_msg = content.get('message', {})
                if isinstance(nested_msg, dict):
                    model = nested_msg.get('model')

            if not model:
                model = 'unknown'

            # Extract token counts from the DB columns (more reliable than blob)
            input_tokens = msg.get('input_tokens') or 0
            output_tokens = msg.get('output_tokens') or 0
            cache_creation_tokens = msg.get('cache_creation_tokens') or 0
            cache_read_tokens = msg.get('cache_read_tokens') or 0

            if model not in model_groups:
                model_groups[model] = {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cache_creation_input_tokens': 0,
                    'cache_read_input_tokens': 0,
                }

            model_groups[model]['input_tokens'] += input_tokens
            model_groups[model]['output_tokens'] += output_tokens
            model_groups[model]['cache_creation_input_tokens'] += cache_creation_tokens
            model_groups[model]['cache_read_input_tokens'] += cache_read_tokens

        return model_groups

    def read_messages_for_quality_analysis(self, session_id: str) -> list[dict[str, Any]]:
        """Read and decompress messages into the format expected by quality analysis functions.

        Returns messages in the same format as the legacy JSONL loader so that
        analyzer.py functions (analyze_cache_read_abuse, analyze_conversation_length, etc.)
        can consume them directly.
        """
        raw_messages = self.read_messages(session_id)
        formatted: list[dict[str, Any]] = []

        for msg in raw_messages:
            content_blob = msg.get('content')
            content: dict[str, Any] = {}
            if content_blob and isinstance(content_blob, bytes):
                content = self.decompress_content(content_blob)

            msg_type = msg.get('type', '')
            timestamp = msg.get('timestamp', '')

            # Build a message dict compatible with analyzer functions
            formatted_msg: dict[str, Any] = {
                'type': msg_type,
                'timestamp': timestamp,
                'sessionId': session_id,
                'requestId': msg.get('_request_id'),
                'isMeta': bool(msg.get('_is_meta')),
                'parentUuid': msg.get('_parent_uuid'),
            }

            if msg_type == 'assistant':
                # Analyzer functions expect usage nested under message.usage
                usage = {
                    'input_tokens': msg.get('input_tokens') or 0,
                    'output_tokens': msg.get('output_tokens') or 0,
                    'cache_creation_input_tokens': msg.get('cache_creation_tokens') or 0,
                    'cache_read_input_tokens': msg.get('cache_read_tokens') or 0,
                }
                model = content.get('model') or content.get('message', {}).get('model')
                formatted_msg['message'] = {
                    'usage': usage,
                    'model': model,
                    'content': content.get('content', content.get('message', {}).get('content', '')),
                }
            else:
                # User message — extract text content
                msg_content = content.get('content', content.get('message', {}).get('content', ''))
                formatted_msg['message'] = {'content': msg_content}

            formatted.append(formatted_msg)

        return formatted

    def read_user_text_content(self, session_id: str) -> list[dict[str, Any]]:
        """Read messages and extract text content for user prompts.

        Returns a list of dicts with 'type', 'content' (text), 'timestamp', 'is_meta', 'parent_uuid'.
        """
        raw_messages = self.read_messages(session_id)
        result: list[dict[str, Any]] = []

        for msg in raw_messages:
            msg_type = msg.get('type', '')
            content_blob = msg.get('content')
            content: dict[str, Any] = {}
            if content_blob and isinstance(content_blob, bytes):
                content = self.decompress_content(content_blob)

            # Extract text content
            raw_content = content.get('content', content.get('message', {}).get('content', ''))
            text = self._extract_text(raw_content)

            result.append(
                {
                    'type': msg_type,
                    'content': text,
                    'timestamp': msg.get('timestamp', ''),
                    'is_meta': bool(msg.get('_is_meta')),
                    'parent_uuid': msg.get('_parent_uuid'),
                    'message_label': self._determine_label(msg_type, bool(msg.get('_is_meta')), text, raw_content),
                }
            )

        return result

    def _extract_text(self, content: Any) -> str:
        """Extract plain text from message content."""
        if not content:
            return ''
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                block_type = item.get('type')
                if block_type == 'text':
                    parts.append(item.get('text', ''))
                elif block_type == 'thinking':
                    thinking = item.get('thinking', '')
                    if thinking:
                        parts.append(f'[Thinking] {thinking}')
                elif block_type == 'tool_use':
                    tool_name = item.get('name', 'Unknown')
                    tool_input = item.get('input', {})
                    input_str = ', '.join(f'{k}={v}' for k, v in tool_input.items())
                    parts.append(f'[Tool: {tool_name}({input_str})]')
                elif block_type == 'tool_result':
                    result_content = item.get('content', '')
                    parts.append(str(result_content) if not isinstance(result_content, str) else result_content)
            return '\n'.join(parts) if parts else ''
        return str(content)

    def _determine_label(self, msg_type: str, is_meta: bool, text: str, raw_content: Any) -> str:
        """Determine display label for a message."""
        if msg_type == 'assistant':
            return 'ASSISTANT'
        if is_meta:
            return 'META'
        if '<command-name>' in text or '<command-message>' in text:
            return 'COMMAND'
        if '<local-command-stdout>' in text or '<local-command-stderr>' in text:
            return 'COMMAND_OUTPUT'
        if isinstance(raw_content, list):
            for item in raw_content:
                if isinstance(item, dict) and item.get('type') == 'tool_result':
                    return 'TOOL_RESULT'
        return 'USER'

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
