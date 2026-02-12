
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Dict, Tuple
import math
import re

from sentence_transformers import SentenceTransformer
from pypdf import PdfReader

from core.models import FileRecord, Cluster, EmbeddingCache
from db.database import Database


SUPPORTED_EXT = {".txt", ".pdf"}
SIM_THRESHOLD = 0.55
KEYWORD_COUNT = 3


class SemanticEngine:
    """
    Core engine for processing files, generating embeddings, and managing clusters.
    """

    def __init__(self, db: Database):
        self.db = db
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.cache = EmbeddingCache()

    # --------------------------------------------------
    # PUBLIC ENTRY
    # --------------------------------------------------
    def process_file(self, path: Path) -> Tuple[FileRecord, Cluster]:
        """
        Process a single file: extract text, generate embedding, and assign to a cluster.
        """
        if path.suffix.lower() not in SUPPORTED_EXT:
            raise ValueError("Unsupported file")

        text = self._extract_text(path)
        content_hash = self._hash(text)

        existing = self.db.get_file_by_path(path)
        if existing and existing.content_hash == content_hash:
            return existing, self._get_cluster(existing.cluster_id)

        embedding = self._get_embedding(content_hash, text)
        record = FileRecord.create(path, content_hash, path.stat().st_mtime)

        cluster = self._assign_cluster(record, embedding, text)

        record.cluster_id = cluster.id
        self.db.upsert_file(record)

        return record, cluster

    # --------------------------------------------------
    # TEXT EXTRACTION
    # --------------------------------------------------
    def _extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".txt":
            return path.read_text(errors="ignore")

        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        return ""

    # --------------------------------------------------
    # EMBEDDINGS
    # --------------------------------------------------
    def _get_embedding(self, content_hash: str, text: str) -> List[float]:
        if self.cache.has(content_hash):
            return self.cache.get(content_hash)

        stored = self.db.get_embedding(content_hash)
        if stored:
            self.cache.set(content_hash, stored)
            return stored

        vector = self.model.encode(text[:4000]).tolist()
        self.db.store_embedding(content_hash, vector)
        self.cache.set(content_hash, vector)
        return vector

    # --------------------------------------------------
    # CLUSTERING
    # --------------------------------------------------
    def _assign_cluster(self, record: FileRecord, embedding: List[float], text: str) -> Cluster:
        clusters = self.db.list_clusters()

        best_cluster = None
        best_score = 0.0

        for cluster in clusters:
            if not cluster.centroid:
                continue
            score = self._cosine(cluster.centroid, embedding)
            if score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster and best_score >= SIM_THRESHOLD:
            best_cluster.file_ids.append(record.id)
            best_cluster.centroid = self._recompute_centroid(best_cluster)
            self.db.upsert_cluster(best_cluster)
            return best_cluster

        # create new cluster
        keywords = self._extract_keywords(text)
        new_cluster = Cluster.create(" ".join(keywords).title(), keywords)
        new_cluster.file_ids.append(record.id)
        new_cluster.centroid = embedding

        self.db.upsert_cluster(new_cluster)
        return new_cluster

    # --------------------------------------------------
    # UTILITIES
    # --------------------------------------------------
    def _recompute_centroid(self, cluster: Cluster) -> List[float]:
        vectors = []
        for fid in cluster.file_ids:
            f = next((x for x in self.db.list_files() if x.id == fid), None)
            if not f:
                continue
            vec = self.db.get_embedding(f.content_hash)
            if vec:
                vectors.append(vec)

        if not vectors:
            return cluster.centroid

        dim = len(vectors[0])
        centroid = [0.0] * dim

        for v in vectors:
            for i in range(dim):
                centroid[i] += v[i]

        for i in range(dim):
            centroid[i] /= len(vectors)

        return centroid

    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[a-zA-Z]{4,}", text.lower())
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1

        ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in ranked[:KEYWORD_COUNT]] or ["general"]

    def _cosine(self, a: List[float], b: List[float]) -> float:
        dot = sum(x*y for x, y in zip(a, b))
        na = math.sqrt(sum(x*x for x in a))
        nb = math.sqrt(sum(x*x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode(errors="ignore")).hexdigest()

    def _get_cluster(self, cluster_id: str | None) -> Cluster | None:
        if not cluster_id:
            return None
        return next((c for c in self.db.list_clusters() if c.id == cluster_id), None)
