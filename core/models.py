"""
Core data models for the SEFS (Semantic Entropy File System).
Includes definitions for FileRecord, Cluster, and EmbeddingCache.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import uuid


# -----------------------------
# File Metadata Representation
# -----------------------------
@dataclass
class FileRecord:
    """
    Represents a file in the system with its metadata and semantic information.
    """
    id: str
    path: Path
    filename: str
    extension: str
    last_modified: float
    content_hash: str
    cluster_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def create(path: Path, content_hash: str, last_modified: float) -> "FileRecord":
        """Factory method to create a new FileRecord."""
        return FileRecord(
            id=str(uuid.uuid4()),
            path=path,
            filename=path.name,
            extension=path.suffix.lower(),
            last_modified=last_modified,
            content_hash=content_hash,
        )


# -----------------------------
# Semantic Cluster Representation
# -----------------------------
@dataclass
class Cluster:
    """
    Represents a semantic cluster of files with a calculated centroid.
    """
    id: str
    name: str
    keywords: List[str]
    file_ids: List[str] = field(default_factory=list)
    centroid: Optional[List[float]] = None
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def create(name: str, keywords: List[str]) -> "Cluster":
        """Factory method to create a new Cluster."""
        return Cluster(
            id=str(uuid.uuid4()),
            name=name,
            keywords=keywords,
        )


# -----------------------------
# Embedding Cache
# -----------------------------
@dataclass
class EmbeddingCache:
    """
    Keeps embeddings in memory to avoid recomputation.
    key = content_hash
    value = embedding vector
    """
    embeddings: Dict[str, List[float]] = field(default_factory=dict)

    def has(self, content_hash: str) -> bool:
        """Check if an embedding exists in the cache."""
        return content_hash in self.embeddings

    def get(self, content_hash: str) -> Optional[List[float]]:
        """Retrieve an embedding from the cache."""
        return self.embeddings.get(content_hash)

    def set(self, content_hash: str, vector: List[float]) -> None:
        """Store an embedding in the cache."""
        self.embeddings[content_hash] = vector

    def remove(self, content_hash: str) -> None:
        """Remove an embedding from the cache."""
        if content_hash in self.embeddings:
            del self.embeddings[content_hash]
