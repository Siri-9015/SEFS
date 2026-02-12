"""
Folder Monitor.
Uses watchdog to monitor the file system for changes and triggers the SemanticEngine.
"""
from __future__ import annotations

import logging
import time
import threading
from pathlib import Path
from typing import Dict

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent,
    FileMovedEvent, FileDeletedEvent
)

from core.engine import SemanticEngine
from core.fs_adapter import FileSystemAdapter


DEBOUNCE_SECONDS = 1.5
SUPPORTED_EXT = {".txt", ".pdf"}


class DebounceCache:
    """Prevents rapid duplicate processing during save operations"""

    def __init__(self):
        self._last_event: Dict[Path, float] = {}

    def should_process(self, path: Path) -> bool:
        """Check if enough time has passed since the last event for this path."""
        now = time.time()
        last = self._last_event.get(path)

        if last and (now - last) < DEBOUNCE_SECONDS:
            return False

        self._last_event[path] = now
        return True


class SEFSEventHandler(FileSystemEventHandler):
    """
    Handles file system events and triggers semantic processing.
    """

    def __init__(self, engine: SemanticEngine, fs: FileSystemAdapter, root: Path):
        self.engine = engine
        self.fs = fs
        self.root = root
        self.debounce = DebounceCache()

    # ------------------------------------------
    # Event Handlers
    # ------------------------------------------
    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        self._handle(Path(event.src_path))

    def on_modified(self, event: FileModifiedEvent):
        if event.is_directory:
            return
        self._handle(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent):
        if event.is_directory:
            return
        self._handle(Path(event.dest_path))

    def on_deleted(self, event: FileDeletedEvent):
        # deletion handled later by DB cleanup logic
        pass

    # ------------------------------------------
    # Core Logic
    # ------------------------------------------
    def _handle(self, path: Path):
        if path.suffix.lower() not in SUPPORTED_EXT:
            return

        if not self.debounce.should_process(path):
            return

        try:
            record, cluster = self.engine.process_file(path)

            if cluster:
                new_path = self.fs.move_to_cluster(path, cluster.name)
                if new_path != path:
                    # re-trigger record update with new path
                    record.path = new_path
                    self.engine.db.upsert_file(record)

        except Exception:
            logging.exception(f"Error processing file {path}")
            # In a real app, we'd log this properly


class FolderMonitor:
    """
    Manages the watchdog observer and event handler.
    """

    def __init__(self, root: Path, engine: SemanticEngine, fs: FileSystemAdapter):
        self.root = root
        self.engine = engine
        self.fs = fs
        self.observer = Observer()

    def start(self):
        """Start the file system observer."""
        handler = SEFSEventHandler(self.engine, self.fs, self.root)
        self.observer.schedule(handler, str(self.root), recursive=True)
        self.observer.start()

        thread = threading.Thread(target=self._keep_alive, daemon=True)
        thread.start()

    def _keep_alive(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stop the observer."""
        self.observer.stop()
        self.observer.join()
