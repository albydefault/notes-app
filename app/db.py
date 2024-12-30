# db.py
import sqlite3
from pathlib import Path
import logging
from contextlib import contextmanager
from typing import Dict, Any, List
import uuid
from datetime import datetime
from typing import Optional

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT DEFAULT 'Untitled Notes',
                    summary TEXT,
                    status TEXT CHECK(status IN ('pending', 'scanning', 'processing', 'completed', 'error'))
                        DEFAULT 'pending'
                )
            """)
            
            # Create Files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT CHECK(file_type IN ('original', 'scanned', 'transcription', 'exposition', 'questions'))
                        NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES Sessions(id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
    
    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Sessions (id) VALUES (?)",
                (session_id,)
            )
            conn.commit()
        return session_id
    
    def add_file(self, session_id: str, filename: str, file_path: str, file_type: str) -> int:
        """Add a file record to the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Files (session_id, filename, file_path, file_type)
                VALUES (?, ?, ?, ?)
            """, (session_id, filename, file_path, file_type))
            conn.commit()
            return cursor.lastrowid
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Update session information."""
        valid_fields = {'title', 'summary', 'status'}
        update_fields = {k: v for k, v in updates.items() if k in valid_fields}
        
        if not update_fields:
            return
            
        fields = ', '.join(f'{k} = ?' for k in update_fields.keys())
        values = list(update_fields.values())
        values.append(session_id)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE Sessions SET {fields} WHERE id = ?",
                values
            )
            conn.commit()
    
    def get_session_files(self, session_id: str, file_type: str = None) -> List[Dict[str, Any]]:
        """Get all files for a session, optionally filtered by type."""
        query = "SELECT * FROM Files WHERE session_id = ?"
        params = [session_id]
        
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information including its files."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Sessions WHERE id = ?", (session_id,))
            session = cursor.fetchone()
            
            if not session:
                return None
                
            # Get all files for this session
            cursor.execute("SELECT * FROM Files WHERE session_id = ?", (session_id,))
            files = cursor.fetchall()
            
            return {
                **dict(session),
                'files': [dict(f) for f in files]
            }

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions, ordered by creation date."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, created_at, status, summary 
                FROM Sessions 
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session information including all files."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get session info
            cursor.execute("""
                SELECT id, title, created_at, status, summary
                FROM Sessions 
                WHERE id = ?
            """, (session_id,))
            session = cursor.fetchone()
            
            if not session:
                return None
                
            # Get associated files
            cursor.execute("""
                SELECT id, filename, file_path, file_type, created_at
                FROM Files 
                WHERE session_id = ?
                ORDER BY created_at ASC
            """, (session_id,))
            files = cursor.fetchall()
            
            session_dict = dict(session)
            session_dict['files'] = [dict(f) for f in files]
            return session_dict

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its files."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0