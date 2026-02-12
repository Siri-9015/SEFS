"""
Database Module.
Handles SQLite interactions for file records, embeddings, and clusters.
"""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import List, Optional

from core.models import FileRecord, Cluster


DB_FILE = "sefs.db"


class Database:
    """
    Manages the SQLite database connection and schema.
    """

    def __init__(self, root: Path):
        self.db_path = root / DB_FILE
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # -------------------------
    # Schema
    # -------------------------
    def _init_schema(self):
        """Initialize the database schema if it doesn't exist."""
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            filename TEXT,
            extension TEXT,
            last_modified REAL,
            content_hash TEXT,
            cluster_id TEXT,
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            content_hash TEXT PRIMARY KEY,
            vector TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY,
            name TEXT,
            keywords TEXT,
            centroid TEXT,
            updated_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS cluster_files (
            cluster_id TEXT,
            file_id TEXT,
            PRIMARY KEY(cluster_id, file_id)
        )
        """)

        self.conn.commit()

    # -------------------------
    # File Records
    # -------------------------
    def upsert_file(self, record: FileRecord):
        """Insert or update a file record."""
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO files(id, path, filename, extension, last_modified, content_hash, cluster_id, created_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            path=excluded.path,
            filename=excluded.filename,
            extension=excluded.extension,
            last_modified=excluded.last_modified,
            content_hash=excluded.content_hash,
            cluster_id=excluded.cluster_id
        """, (
            record.id,
            str(record.path),
            record.filename,
            record.extension,
            record.last_modified,
            record.content_hash,
            record.cluster_id,
            record.created_at.isoformat()
        ))
        self.conn.commit()

    def get_file_by_path(self, path: Path) -> Optional[FileRecord]:
        """Retrieve a file record by its path."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM files WHERE path=?", (str(path),))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_file(row)

    def delete_file(self, file_id: str):
        """Delete a file record and its association with clusters."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM files WHERE id=?", (file_id,))
        cur.execute("DELETE FROM cluster_files WHERE file_id=?", (file_id,))
        self.conn.commit()

    def list_files(self) -> List[FileRecord]:
        """List all file records."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM files")
        return [self._row_to_file(r) for r in cur.fetchall()]

    # -------------------------
    # Embeddings
    # -------------------------
    def store_embedding(self, content_hash: str, vector: List[float]):
        """Store an embedding vector for a given content hash."""
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO embeddings(content_hash, vector)
        VALUES (?,?)
        """, (content_hash, json.dumps(vector)))
        self.conn.commit()

    def get_embedding(self, content_hash: str) -> Optional[List[float]]:
        """Retrieve an embedding vector by content hash."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT vector FROM embeddings WHERE content_hash=?", (content_hash,))
        row = cur.fetchone()
        if not row:
            return None
        return json.loads(row["vector"])

    # -------------------------
    # Clusters
    # -------------------------
    def upsert_cluster(self, cluster: Cluster):
        """Insert or update a cluster."""
        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO clusters(id, name, keywords, centroid, updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            keywords=excluded.keywords,
            centroid=excluded.centroid,
            updated_at=excluded.updated_at
        """, (
            cluster.id,
            cluster.name,
            json.dumps(cluster.keywords),
            json.dumps(cluster.centroid) if cluster.centroid else None,
            cluster.updated_at.isoformat()
        ))

        cur.execute("DELETE FROM cluster_files WHERE cluster_id=?",
                    (cluster.id,))
        for fid in cluster.file_ids:
            cur.execute(
                "INSERT INTO cluster_files(cluster_id, file_id) VALUES(?,?)", (cluster.id, fid))

        self.conn.commit()

    def list_clusters(self) -> List[Cluster]:
        """List all clusters with their associated file IDs."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM clusters")
        rows = cur.fetchall()

        clusters: List[Cluster] = []
        for r in rows:
            cur.execute(
                "SELECT file_id FROM cluster_files WHERE cluster_id=?", (r["id"],))
            file_ids = [f["file_id"] for f in cur.fetchall()]

            clusters.append(Cluster(
                id=r["id"],
                name=r["name"],
                keywords=json.loads(r["keywords"]),
                centroid=json.loads(r["centroid"]) if r["centroid"] else None,
                file_ids=file_ids
            ))

        return clusters

    # -------------------------
    # Helpers
    # -------------------------
    def _row_to_file(self, row) -> FileRecord:
        return FileRecord(
            id=row["id"],
            path=Path(row["path"]),
            filename=row["filename"],
            extension=row["extension"],
            last_modified=row["last_modified"],
            content_hash=row["content_hash"],
            cluster_id=row["cluster_id"],
        )
