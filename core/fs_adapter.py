"""
FileSystem Adapter.
Provides safe, atomic file operations for the SEFS system.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


class FileSystemAdapter:
    """
    Handles all OS-level file operations safely.
    All operations must be atomic and recoverable.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _ensure_inside_root(self, path: Path):
        path = path.resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError(f"Unsafe path outside root: {path}")

    def ensure_folder(self, folder: Path) -> Path:
        """Ensure a directory exists within the root."""
        folder = folder.resolve()
        self._ensure_inside_root(folder)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # --------------------------------------------------
    # Atomic Move
    # --------------------------------------------------
    def atomic_move(self, src: Path, dst: Path) -> Path:
        """
        Move file atomically using temp file strategy.
        Prevents corruption if crash occurs mid-move.
        """
        src = src.resolve()
        dst = dst.resolve()

        self._ensure_inside_root(src)
        self._ensure_inside_root(dst)

        if not src.exists():
            raise FileNotFoundError(src)

        self.ensure_folder(dst.parent)

        # If same location, skip
        if src == dst:
            return dst

        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(dst.parent))
        os.close(tmp_fd)
        tmp_path = Path(tmp_path)

        try:
            # Copy to temp
            shutil.copy2(src, tmp_path)

            # Replace destination atomically
            os.replace(tmp_path, dst)

            # Remove original
            src.unlink(missing_ok=True)

        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

        return dst

    # --------------------------------------------------
    # Safe Rename
    # --------------------------------------------------
    def atomic_rename(self, path: Path, new_name: str) -> Path:
        """Safely rename a file within the root."""
        path = path.resolve()
        self._ensure_inside_root(path)

        new_path = path.with_name(new_name)
        self._ensure_inside_root(new_path)

        os.replace(path, new_path)
        return new_path

    # --------------------------------------------------
    # Folder Removal (only empty)
    # --------------------------------------------------
    def remove_folder_if_empty(self, folder: Path):
        """Remove a directory if it is empty."""
        folder = folder.resolve()
        self._ensure_inside_root(folder)

        if folder.exists() and folder.is_dir():
            try:
                folder.rmdir()
            except OSError:
                pass  # Not empty, ignore

    # --------------------------------------------------
    # Cluster Folder Path
    # --------------------------------------------------
    def cluster_folder(self, name: str) -> Path:
        """
        Sanitize folder names and return cluster directory.
        """
        safe = "".join(c for c in name if c.isalnum()
                       or c in (" ", "_", "-")).strip()
        safe = safe or "Uncategorized"
        return self.root / safe

    # --------------------------------------------------
    # Move file into cluster folder
    # --------------------------------------------------
    def move_to_cluster(self, file_path: Path, cluster_name: str) -> Path:
        """Move a file to the appropriate cluster directory."""
        folder = self.cluster_folder(cluster_name)
        self.ensure_folder(folder)

        destination = folder / file_path.name
        return self.atomic_move(file_path, destination)
