"""
Verify that all required modules can be imported.
"""
import sys

try:
    from core.engine import SemanticEngine  # noqa: F401
    from db.database import Database  # noqa: F401
    from ui.server import app  # noqa: F401
    # Explicitly use imports to silence linter warnings
    _ = SemanticEngine
    _ = Database
    _ = app
    print('Imports successful')
except ImportError as e:
    print(f'Import failed: {e}')
    sys.exit(1)
