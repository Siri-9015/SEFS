# Semantic Entropy File System (SEFS)

SEFS is a semantic file system that automatically organizes your files based on their content using embeddings and clustering.

## Features

- **Semantic Clustering**: Automatically groups files into clusters based on content similarity.
- **Auto-Tagging**: Generates keywords for clusters.
- **Debounced Monitoring**: Watches for file changes and processes them efficiently.
- **Web UI**: Visualizes the file clusters and relationships in a graph.

## Structure

- `core/`: Core logic for semantic engine, file system adapter, and monitoring.
- `db/`: Database interactions (SQLite).
- `ui/`: Web server and UI assets.
- `main.py`: Entry point for the application.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: You may need to create a requirements.txt file with `fastapi`, `uvicorn`, `watchdog`, `sentence-transformers`, `pypdf`)*

## Usage

1. Run the application:
   ```bash
   python main.py
   ```
2. The system will start monitoring the `semantic_root` directory.
3. Open `http://127.0.0.1:8000` to view the visualization.

## Development

- Run from the root directory to ensure imports work correctly.
