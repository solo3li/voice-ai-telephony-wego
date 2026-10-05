"""Local SQLite Storage Manager for GSM Dongle Gateway.

Persists call records, SMS messages, USSD transaction history,
and device configurations offline-first with synchronization flags.
"""
import os
import sys
import tempfile
import sqlite3
import logging
from typing import List, Dict, Any, Optional

try:
    from controllers.app_paths import get_writable_file_path
except ImportError:
    try:
        from app_paths import get_writable_file_path
    except ImportError:
        def get_writable_file_path(name: str) -> str:
            return os.path.join(tempfile.gettempdir(), name)

logger = logging.getLogger(__name__)

DB_PATH = get_writable_file_path("gateway_local.db")


class StorageManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Obtain a SQLite connection with timeout and automatic read-only / permission recovery."""
        if self._memory_conn is not None:
            return self._memory_conn

        try:
            if self.db_path != ":memory:":
                parent = os.path.dirname(os.path.abspath(self.db_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            return conn
        except (sqlite3.OperationalError, PermissionError, OSError) as e:
            logger.error(f"Cannot access primary SQLite at '{self.db_path}': {e}. Trying fallback location.")
            # Fallback 1: user temp directory
            fallback_path = os.path.join(tempfile.gettempdir(), "gateway_local_fallback.db")
            try:
                conn = sqlite3.connect(fallback_path, timeout=10.0)
                conn.row_factory = sqlite3.Row
                self.db_path = fallback_path
                logger.info(f"Switched StorageManager to fallback path: {fallback_path}")
                return conn
            except Exception as e2:
                logger.error(f"Fallback path also failed: {e2}. Switching to in-memory SQLite.")
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self.db_path = ":memory:"
                return self._memory_conn

    def _init_db(self):
        """Create necessary tables if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS call_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        caller_phone TEXT NOT NULL,
                        destination_phone TEXT,
                        direction TEXT DEFAULT 'inbound',
                        duration INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'completed',
                        room_name TEXT,
                        dongle_port TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        synced INTEGER DEFAULT 0
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sms_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phone_number TEXT NOT NULL,
                        message_text TEXT NOT NULL,
                        direction TEXT DEFAULT 'inbound',
                        dongle_port TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_read INTEGER DEFAULT 0
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ussd_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ussd_code TEXT NOT NULL,
                        response_text TEXT NOT NULL,
                        dongle_port TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS dongle_devices (
                        port TEXT PRIMARY KEY,
                        alias TEXT,
                        operator_name TEXT,
                        sim_number TEXT,
                        is_enabled INTEGER DEFAULT 1,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except sqlite3.OperationalError as e:
            if "readonly" in str(e).lower() or "locked" in str(e).lower():
                logger.warning(f"Database at '{self.db_path}' is readonly: {e}. Switching to in-memory fallback.")
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
                self.db_path = ":memory:"
                self._init_db()
            else:
                logger.error(f"Error initializing DB: {e}")

    def _execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute write query with automatic recovery on readonly database."""
        for attempt in range(2):
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.lastrowid if cursor.lastrowid is not None else (cursor.rowcount or 1)
            except sqlite3.OperationalError as e:
                err_str = str(e).lower()
                if "readonly" in err_str or "locked" in err_str or "attempt to write a readonly database" in err_str:
                    logger.warning(f"Read-only SQLite error caught: {e}. Switching to in-memory mode and retrying.")
                    self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
                    self._memory_conn.row_factory = sqlite3.Row
                    self.db_path = ":memory:"
                    self._init_db()
                    continue
                logger.error(f"SQLite operational error on write: {e}")
                return 0
            except Exception as e:
                logger.error(f"SQLite unexpected error on write: {e}")
                return 0
        return 0

    # --- Call Logs ---
    def add_call_log(
        self,
        caller_phone: str,
        destination_phone: str = "",
        direction: str = "inbound",
        duration: int = 0,
        status: str = "completed",
        room_name: str = "",
        dongle_port: str = "SIMULATED",
        synced: bool = False
    ) -> int:
        sql = """
            INSERT INTO call_logs (caller_phone, destination_phone, direction, duration, status, room_name, dongle_port, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (caller_phone, destination_phone, direction, duration, status, room_name, dongle_port, 1 if synced else 0)
        return self._execute_write(sql, params)

    def get_recent_calls(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, caller_phone, destination_phone, direction, duration, status, room_name, dongle_port, created_at, synced
                    FROM call_logs
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Error fetching recent calls: {e}")
            return []

    def get_total_calls_today(self) -> int:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as total FROM call_logs
                    WHERE date(created_at) = date('now')
                """)
                row = cursor.fetchone()
                return row["total"] if row else 0
        except Exception as e:
            logger.warning(f"Error fetching total calls today: {e}")
            return 0

    # --- SMS Messages ---
    def add_sms(
        self,
        phone_number: str,
        message_text: str,
        direction: str = "inbound",
        dongle_port: str = "SIMULATED"
    ) -> int:
        sql = """
            INSERT INTO sms_messages (phone_number, message_text, direction, dongle_port, is_read)
            VALUES (?, ?, ?, ?, 1)
        """
        return self._execute_write(sql, (phone_number, message_text, direction, dongle_port))

    def get_sms_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, phone_number, message_text, direction, dongle_port, created_at, is_read
                    FROM sms_messages
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Error fetching SMS messages: {e}")
            return []

    # --- USSD History ---
    def add_ussd_record(self, ussd_code: str, response_text: str, dongle_port: str = "SIMULATED") -> int:
        sql = """
            INSERT INTO ussd_history (ussd_code, response_text, dongle_port)
            VALUES (?, ?, ?)
        """
        return self._execute_write(sql, (ussd_code, response_text, dongle_port))

    def get_recent_ussd(self, limit: int = 15) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, ussd_code, response_text, dongle_port, created_at
                    FROM ussd_history
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Error fetching USSD records: {e}")
            return []

    # --- Dongle Devices ---
    def upsert_dongle(
        self,
        port: str,
        alias: str = "",
        operator_name: str = "",
        sim_number: str = "",
        is_enabled: bool = True
    ):
        sql = """
            INSERT INTO dongle_devices (port, alias, operator_name, sim_number, is_enabled, last_seen)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(port) DO UPDATE SET
                alias = excluded.alias,
                operator_name = excluded.operator_name,
                sim_number = excluded.sim_number,
                is_enabled = excluded.is_enabled,
                last_seen = CURRENT_TIMESTAMP
        """
        params = (port, alias, operator_name, sim_number, 1 if is_enabled else 0)
        self._execute_write(sql, params)

    def get_all_dongles(self) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM dongle_devices ORDER BY last_seen DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Error fetching dongles: {e}")
            return []
