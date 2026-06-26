from __future__ import annotations

from pathlib import Path
import logging
import uvicorn

from db.database import Database
from core.engine import SemanticEngine
from core.fs_adapter import FileSystemAdapter
from core.monitor import FolderMonitor
from ui.server import app, configure


ROOT = Path("semantic_root").resolve()


def main():
    """Run the SEFS application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    ROOT.mkdir(exist_ok=True)

    db = Database(ROOT)
    engine = SemanticEngine(db)
    fs = FileSystemAdapter(ROOT)
    monitor = FolderMonitor(ROOT, engine, fs)

    configure(db, ROOT)

    monitor.start()

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
