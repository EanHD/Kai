"""SQLite storage implementation for metadata and session persistence."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SQLiteStore:
    """Manages SQLite database connections and operations."""

    def __init__(self, db_path: str):
        """Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Get database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema if not exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # User Profiles
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    preferences TEXT,
                    encryption_key_hash TEXT NOT NULL
                )
            """)

            # Conversation Sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    total_cost REAL DEFAULT 0.0,
                    cost_limit REAL DEFAULT 1.0,
                    message_count INTEGER DEFAULT 0,
                    active_tools TEXT,
                    CONSTRAINT positive_cost CHECK (total_cost >= 0)
                )
            """)

            # Messages (combines Query + Response)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES conversations(session_id),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role TEXT CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    complexity_level TEXT CHECK(
                        complexity_level IN ('simple', 'moderate', 'complex')
                    ),
                    emotional_tone TEXT,
                    routing_decision TEXT,
                    mode TEXT CHECK(mode IN ('concise', 'expert', 'advisor')),
                    source_citations TEXT,
                    tool_results TEXT,
                    confidence REAL,
                    token_count INTEGER,
                    cost REAL DEFAULT 0.0
                )
            """)

            # Tool Invocations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_invocations (
                    invocation_id TEXT PRIMARY KEY,
                    query_message_id TEXT NOT NULL REFERENCES messages(message_id),
                    tool_name TEXT NOT NULL CHECK(
                        tool_name IN ('web_search', 'rag', 'code_exec', 'sentiment')
                    ),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    parameters TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    execution_time_ms INTEGER NOT NULL,
                    status TEXT CHECK(
                        status IN ('pending', 'running', 'success', 'failed', 'timeout')
                    ),
                    fallback_used BOOLEAN DEFAULT 0
                )
            """)

            # Model Configurations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_configs (
                    model_id TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    context_window INTEGER NOT NULL,
                    cost_per_1k_input REAL NOT NULL,
                    cost_per_1k_output REAL NOT NULL,
                    routing_priority INTEGER NOT NULL,
                    is_local BOOLEAN NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    last_health_check TIMESTAMP
                )
            """)

            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_query ON tool_invocations(query_message_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_active "
                "ON model_configs(active, routing_priority)"
            )

            logger.info(f"Database schema initialized at {self.db_path}")

    # User operations
    def create_user(
        self, user_id: str, encryption_key_hash: str, preferences: dict | None = None
    ) -> None:
        """Create a new user profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (user_id, encryption_key_hash, preferences)
                VALUES (?, ?, ?)
                """,
                (user_id, encryption_key_hash, json.dumps(preferences) if preferences else None),
            )

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Retrieve user profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_user_preferences(self, user_id: str, preferences: dict) -> None:
        """Update user preferences."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET preferences = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (json.dumps(preferences), user_id),
            )

    def store_user_profile(self, user_id: str, profile_data: dict[str, Any]) -> None:
        """Store complete user profile with schedules and goals.

        Args:
            user_id: User identifier
            profile_data: Dict containing preferences, schedules, goals from UserProfile.to_dict()
        """
        # Ensure user exists
        if not self.get_user(user_id):
            # Create user if doesn't exist
            self.create_user(
                user_id=user_id,
                encryption_key_hash=profile_data.get("encryption_key_hash", ""),
                preferences=profile_data.get("preferences", {}),
            )
        else:
            # Update existing user preferences
            self.update_user_preferences(user_id, profile_data.get("preferences", {}))

        logger.info(f"Stored user profile for {user_id}")

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        """Retrieve complete user profile.

        Args:
            user_id: User identifier

        Returns:
            User profile dict compatible with UserProfile.from_dict() or None
        """
        user_data = self.get_user(user_id)
        if not user_data:
            return None

        # Parse preferences JSON
        if user_data.get("preferences"):
            try:
                user_data["preferences"] = json.loads(user_data["preferences"])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse preferences for user {user_id}")
                user_data["preferences"] = {}
        else:
            user_data["preferences"] = {}

        return user_data

    # Conversation operations
    def create_conversation(self, session_id: str, user_id: str, cost_limit: float = 1.0) -> None:
        """Create a new conversation session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversations (session_id, user_id, cost_limit)
                VALUES (?, ?, ?)
                """,
                (session_id, user_id, cost_limit),
            )

    def get_conversation(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve conversation session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def end_conversation(self, session_id: str) -> None:
        """Mark conversation as ended."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE conversations
                SET ended_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (session_id,),
            )

    def update_conversation_cost(self, session_id: str, cost_increment: float) -> None:
        """Add cost to conversation total."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE conversations
                SET total_cost = total_cost + ?,
                    message_count = message_count + 1
                WHERE session_id = ?
                """,
                (cost_increment, session_id),
            )

    # Message operations
    def save_message(self, message_data: dict[str, Any]) -> None:
        """Save a message (user query or assistant response)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Remove fields that don't belong in messages table
            message_data = message_data.copy()  # Don't modify original
            message_data.pop("query_message_id", None)  # This belongs in tool_invocations

            # Convert JSON fields
            for field in ["emotional_tone", "source_citations", "tool_results"]:
                if field in message_data and message_data[field] is not None:
                    message_data[field] = json.dumps(message_data[field])

            # Build dynamic INSERT based on provided fields
            fields = list(message_data.keys())
            placeholders = ", ".join(["?"] * len(fields))
            field_names = ", ".join(fields)

            cursor.execute(
                f"INSERT INTO messages ({field_names}) VALUES ({placeholders})",
                tuple(message_data[f] for f in fields),
            )

    def get_messages(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """Retrieve messages for a conversation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_old_conversations(self, cutoff_date: str) -> list[dict[str, Any]]:
        """Get conversations older than cutoff date.

        Args:
            cutoff_date: ISO format date string

        Returns:
            List of conversation dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE started_at < ?", (cutoff_date,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_messages(self, session_id: str) -> int:
        """Delete all messages for a session.

        Args:
            session_id: Session to delete messages from

        Returns:
            Number of messages deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount

    def delete_conversation(self, session_id: str) -> None:
        """Delete a conversation session.

        Args:
            session_id: Session to delete
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            conn.commit()

    # Tool invocation operations
    def save_tool_invocation(self, invocation_data: dict[str, Any]) -> None:
        """Save tool invocation record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Convert JSON fields
            for field in ["parameters", "result"]:
                if field in invocation_data and invocation_data[field] is not None:
                    invocation_data[field] = json.dumps(invocation_data[field])

            fields = list(invocation_data.keys())
            placeholders = ", ".join(["?"] * len(fields))
            field_names = ", ".join(fields)

            cursor.execute(
                f"INSERT INTO tool_invocations ({field_names}) VALUES ({placeholders})",
                tuple(invocation_data[f] for f in fields),
            )

    def get_tool_invocations(self, query_message_id: str) -> list[dict[str, Any]]:
        """Get all tool invocations for a query."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tool_invocations WHERE query_message_id = ?",
                (query_message_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # Model configuration operations
    def save_model_config(self, config: dict[str, Any]) -> None:
        """Save or update model configuration."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Convert capabilities array to JSON
            if "capabilities" in config and isinstance(config["capabilities"], list):
                config["capabilities"] = json.dumps(config["capabilities"])

            fields = list(config.keys())
            placeholders = ", ".join(["?"] * len(fields))
            field_names = ", ".join(fields)

            # Use INSERT OR REPLACE for upsert
            cursor.execute(
                f"INSERT OR REPLACE INTO model_configs ({field_names}) VALUES ({placeholders})",
                tuple(config[f] for f in fields),
            )

    def get_active_models(self) -> list[dict[str, Any]]:
        """Get all active models ordered by routing priority."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM model_configs
                WHERE active = 1
                ORDER BY routing_priority DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_model_config(self, model_id: str) -> dict[str, Any] | None:
        """Get specific model configuration."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_configs WHERE model_id = ?", (model_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def store_model_config(self, config: dict[str, Any]) -> None:
        """Store or update model configuration.

        Args:
            config: Model config dict from ModelConfig.to_dict()
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO model_configs (
                    model_id, model_name, provider, capabilities,
                    context_window, cost_per_1k_input, cost_per_1k_output,
                    routing_priority, is_local, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config["model_id"],
                    config["model_name"],
                    config["provider"],
                    json.dumps(config["capabilities"]),
                    config["context_window"],
                    config["cost_per_1k_input"],
                    config["cost_per_1k_output"],
                    config["routing_priority"],
                    config["is_local"],
                    config.get("active", True),
                ),
            )
            logger.info(f"Stored model config: {config['model_id']}")
