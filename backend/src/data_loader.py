"""
Data loader module for JSONL conversation files.
Handles loading, parsing, and grouping conversation data.
"""

import json
from datetime import datetime
from pathlib import Path

from .conversation_types import ConversationMessage, ConversationSession, ProjectGroup, UserPrompt


class ConversationDataLoader:
    """Loads and processes JSONL conversation files."""

    def __init__(self, claude_projects_path: Path):
        self.claude_projects_path = claude_projects_path
        self.projects: dict[str, ProjectGroup] = {}

    def load_all_conversations(self) -> dict[str, ProjectGroup]:
        """Load all conversations from the Claude projects directory."""
        print(f'Loading conversations from {self.claude_projects_path}')

        if not self.claude_projects_path.exists():
            raise FileNotFoundError(f'Claude projects directory not found: {self.claude_projects_path}')

        self.projects = {}

        # Scan project directories
        for project_dir in self.claude_projects_path.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                project_conversations = self._load_project_conversations(project_dir)
                if project_conversations:
                    self.projects[project_dir.name] = self._create_project_group(project_dir.name, project_conversations)

        print(f'Loaded {len(self.projects)} projects with {self._total_conversation_count()} total conversations')

        return self.projects

    def _load_project_conversations(self, project_dir: Path) -> list[ConversationSession]:
        """Load all conversations from a single project directory.

        Uses cache/index.json as source of truth if available, falls back to scanning JSONL files.
        """
        conversations = []
        sessions_found = set()

        # Try to load from cache/index.json first (canonical source)
        cache_index_path = project_dir / 'cache' / 'index.json'
        if cache_index_path.exists():
            try:
                conversations_from_cache = self._load_conversations_from_cache(project_dir, cache_index_path)
                conversations.extend(conversations_from_cache)
                sessions_found.update(c.session_id for c in conversations_from_cache)
            except Exception as e:
                print(f'Warning: Error loading cache from {cache_index_path}: {e}')

        # Also scan JSONL files directly for any sessions not in cache
        for jsonl_file in project_dir.glob('*.jsonl'):
            try:
                messages_in_file = self._read_jsonl_file(jsonl_file)
                session_conversations = self._extract_sessions_from_messages(messages_in_file, jsonl_file, project_dir)

                for conversation in session_conversations:
                    if conversation.session_id not in sessions_found:
                        conversations.append(conversation)
                        sessions_found.add(conversation.session_id)

            except Exception as e:
                print(f'Warning: Error processing {jsonl_file}: {e}')
                continue

        return conversations

    def _load_conversations_from_cache(self, project_dir: Path, cache_index_path: Path) -> list[ConversationSession]:
        """Load conversations from cache/index.json file.

        For each session in the cache, try to load the actual JSONL file if it exists,
        otherwise create a minimal ConversationSession from cache metadata.
        """
        conversations = []

        with cache_index_path.open('r', encoding='utf-8') as f:
            cache_data = json.load(f)

        sessions = cache_data.get('sessions', {})

        for session_id, session_info in sessions.items():
            # Try to find the corresponding JSONL file
            jsonl_filename = f'{session_id}.jsonl'
            jsonl_path = project_dir / jsonl_filename

            if jsonl_path.exists():
                # Load from JSONL for full message data
                try:
                    messages_in_file = self._read_jsonl_file(jsonl_path)
                    session_conversations = self._extract_sessions_from_messages(messages_in_file, jsonl_path, project_dir)

                    # Attach cached token counts to the conversation
                    for conv in session_conversations:
                        if conv.session_id == session_id:
                            conv.cached_input_tokens = session_info.get('total_input_tokens')
                            conv.cached_output_tokens = session_info.get('total_output_tokens')
                            conv.cached_cache_creation_tokens = session_info.get('total_cache_creation_tokens')
                            conv.cached_cache_read_tokens = session_info.get('total_cache_read_tokens')

                    conversations.extend(session_conversations)
                except Exception as e:
                    print(f'Warning: Error loading {jsonl_path}: {e}')
                    # Fall back to cache data
                    conversation = self._create_conversation_from_cache(session_info, project_dir)
                    if conversation:
                        conversations.append(conversation)
            else:
                # JSONL doesn't exist, create from cache metadata only
                conversation = self._create_conversation_from_cache(session_info, project_dir)
                if conversation:
                    conversations.append(conversation)

        return conversations

    def _create_conversation_from_cache(self, session_info: dict, project_dir: Path) -> ConversationSession | None:
        """Create a ConversationSession from cache metadata when JSONL is missing."""
        try:
            session_id = session_info.get('session_id')
            if not session_id:
                return None

            # Parse timestamps
            first_timestamp = session_info.get('first_timestamp')
            last_timestamp = session_info.get('last_timestamp')
            start_time = None
            end_time = None

            if first_timestamp:
                try:
                    start_time = datetime.fromisoformat(first_timestamp.replace('Z', '+00:00'))
                except:
                    pass

            if last_timestamp:
                try:
                    end_time = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
                except:
                    pass

            # Create a minimal user prompt from first_user_message
            first_message = session_info.get('first_user_message', '')
            user_prompts = []
            if first_message:
                user_prompts.append(UserPrompt(content=first_message, timestamp=first_timestamp))

            # Create session with minimal data and cached token counts
            return ConversationSession(
                session_id=session_id,
                messages=[],  # No detailed messages available
                user_prompts=user_prompts,
                start_time=start_time,
                end_time=end_time,
                parent_jsonl_file=None,
                cwd_path=session_info.get('cwd'),
                cached_input_tokens=session_info.get('total_input_tokens'),
                cached_output_tokens=session_info.get('total_output_tokens'),
                cached_cache_creation_tokens=session_info.get('total_cache_creation_tokens'),
                cached_cache_read_tokens=session_info.get('total_cache_read_tokens'),
            )

        except Exception as e:
            print(f'Warning: Error creating conversation from cache: {e}')
            return None

    def _extract_sessions_from_messages(self, messages_data: list[dict], jsonl_file: Path, project_dir: Path) -> list[ConversationSession]:
        """Extract all sessions from a list of message data."""
        sessions_by_id = {}
        session_cwds = {}  # Track cwd for each session

        # Group messages by session ID and capture cwd
        for msg_data in messages_data:
            session_id = msg_data.get('sessionId')
            if not session_id:
                continue

            # Capture the cwd field for project path extraction
            cwd = msg_data.get('cwd')
            if cwd and session_id not in session_cwds:
                session_cwds[session_id] = cwd

            message = self._parse_message(msg_data)
            if not message:
                continue

            if session_id not in sessions_by_id:
                sessions_by_id[session_id] = []
            sessions_by_id[session_id].append(message)

        # Create ConversationSession objects
        conversations = []
        for session_id, messages in sessions_by_id.items():
            cwd_path = session_cwds.get(session_id)
            conversation = self._create_conversation_session(session_id, messages, jsonl_file, cwd_path)
            conversations.append(conversation)

        return conversations

    def _read_jsonl_file(self, file_path: Path) -> list[dict]:
        """Read and parse a JSONL file."""
        messages = []

        try:
            with file_path.open('r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            messages.append(message)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f'Error reading {file_path}: {e}')

        return messages

    def _parse_message(self, msg_data: dict) -> ConversationMessage | None:
        """Parse a message from JSONL data."""
        try:
            msg_type = msg_data.get('type', '')
            if not msg_type:
                return None

            # Extract content based on message structure
            content = ''
            if 'message' in msg_data and isinstance(msg_data['message'], dict):
                raw_content = msg_data['message'].get('content', '')
            elif 'content' in msg_data:
                raw_content = msg_data.get('content', '')
            else:
                return None

            # Handle different content types
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                # Handle complex content structures - extract only user-generated content
                content_parts = []
                for part in raw_content:
                    if isinstance(part, dict):
                        # Skip tool results - only include actual user text content
                        if part.get('type') == 'tool_result':
                            continue
                        if 'text' in part:
                            content_parts.append(str(part['text']))
                    elif isinstance(part, str):
                        content_parts.append(part)
                content = '\n'.join(content_parts)
            else:
                # Convert other types to string
                content = str(raw_content)

            if not content.strip():
                return None

            is_meta = msg_data.get('isMeta', False)

            # Determine message label
            if msg_type == 'assistant':
                message_label = 'ASSISTANT'
            elif is_meta:
                message_label = 'META'
            elif msg_type == 'user':
                message_label = 'USER'
            else:
                message_label = msg_type.upper()

            return ConversationMessage(
                type=msg_type,
                content=content.strip(),
                timestamp=msg_data.get('timestamp'),
                session_id=msg_data.get('sessionId'),
                is_meta=is_meta,
                message_label=message_label,
            )

        except Exception as e:
            print(f'Warning: Error parsing message: {e}')
            return None

    def _create_conversation_session(
        self,
        session_id: str,
        messages: list[ConversationMessage],
        parent_jsonl: Path | None,
        cwd_path: str | None = None,
    ) -> ConversationSession:
        """Create a ConversationSession from messages."""

        # Extract user prompts
        user_prompts = []
        for msg in messages:
            if msg.type == 'user' and msg.content.strip():
                # Only filter out truly empty content or system reminders
                content = msg.content.strip()
                if content and not content.startswith('<system-reminder>') and not content.startswith('<command-message>'):
                    user_prompts.append(UserPrompt(content=msg.content, timestamp=msg.timestamp))

        # Calculate start/end times
        timestamps = [msg.timestamp for msg in messages if msg.timestamp]
        start_time = None
        end_time = None

        if timestamps:
            try:
                datetime_objects = []
                for ts in timestamps:
                    # Handle different timestamp formats
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        datetime_objects.append(dt)
                    except:
                        continue

                if datetime_objects:
                    start_time = min(datetime_objects)
                    end_time = max(datetime_objects)
            except Exception as e:
                print(f'Warning: Error parsing timestamps for session {session_id}: {e}')

        return ConversationSession(
            session_id=session_id,
            messages=messages,
            user_prompts=user_prompts,
            start_time=start_time,
            end_time=end_time,
            parent_jsonl_file=parent_jsonl,
            cwd_path=cwd_path,
        )

    def _create_project_group(self, project_name: str, conversations: list[ConversationSession]) -> ProjectGroup:
        """Create a ProjectGroup with placeholder metrics."""
        from .conversation_types import ProjectMetrics  # Import here to avoid circular imports

        # Extract real project name and path from cwd paths
        real_project_name, project_path = self._extract_project_info_from_conversations(conversations)

        # Sort conversations by start time (most recent first)
        # Normalize timezone-aware datetimes to naive for comparison
        conversations.sort(
            key=lambda c: (c.start_time.replace(tzinfo=None) if c.start_time else datetime.min),
            reverse=True,
        )

        # Calculate basic metrics (will be enhanced by analyzer)
        start_times = [c.start_time for c in conversations if c.start_time]
        date_range = (min(start_times), max(start_times)) if start_times else (None, None)

        metrics = ProjectMetrics(
            total_conversations=len(conversations),
            total_cost=0.0,  # Will be filled by analyzer
            total_tokens=0,  # Will be filled by analyzer
            total_input_tokens=0,  # Will be filled by analyzer
            total_output_tokens=0,  # Will be filled by analyzer
            total_cache_creation_tokens=0,  # Will be filled by analyzer
            total_cache_read_tokens=0,  # Will be filled by analyzer
            average_score=0.0,  # Will be filled by analyzer
            total_issues=0,  # Will be filled by analyzer
            conversation_date_range=date_range,
        )

        return ProjectGroup(
            name=real_project_name or project_name,
            conversations=conversations,
            metrics=metrics,
            path=project_path,
        )

    def _extract_project_info_from_conversations(self, conversations: list[ConversationSession]) -> tuple[str | None, str | None]:
        """Extract the real project name and path from conversation cwd paths.

        Returns:
            tuple: (project_name, project_path)
        """
        cwd_paths = [c.cwd_path for c in conversations if c.cwd_path]

        if not cwd_paths:
            return None, None

        # Use the most common cwd path
        from collections import Counter

        most_common_cwd = Counter(cwd_paths).most_common(1)[0][0]

        # Extract project name from path like "/Users/ratoui/work/ows/ows-product-review"
        path_parts = Path(most_common_cwd).parts

        # Get the last meaningful segments (typically the last 1-2 parts)
        project_name = None
        if len(path_parts) >= 2:
            # For paths like /Users/ratoui/work/ows/ows-product-review
            # Take the last part: ows-product-review
            project_name = path_parts[-1]
        else:
            project_name = path_parts[-1] if path_parts else None

        return project_name, most_common_cwd

    def _total_conversation_count(self) -> int:
        """Get total conversation count across all projects."""
        return sum(len(project.conversations) for project in self.projects.values())
