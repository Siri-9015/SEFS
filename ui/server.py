"""
UI Server.
FastAPI server needed to serve the web interface and WebSocket graph data.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db.database import Database


app = FastAPI()
clients: List[WebSocket] = []
db: Database | None = None
root_path: Path | None = None


# --------------------------------------------------
# Startup Hook
# --------------------------------------------------
def configure(database: Database, root: Path):
    """Configure the global database connection and root path."""
    global db, root_path
    db = database
    root_path = root


# --------------------------------------------------
# Static UI
# --------------------------------------------------
app.mount("/static", StaticFiles(directory="ui"), name="static")


@app.get("/")
async def index():
    """Serve the main index page."""
    return FileResponse("ui/index.html")


# --------------------------------------------------
# WebSocket Graph Stream
# --------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Handle WebSocket connections for real-time graph updates."""
    await ws.accept()
    clients.append(ws)

    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        clients.remove(ws)


# --------------------------------------------------
# Graph Builder
# --------------------------------------------------
def build_graph() -> Dict:
    """Build the graph representation of files and clusters."""
    files = db.list_files()
    clusters = db.list_clusters()

    nodes = []
    links = []

    cluster_nodes = {c.id: f"cluster-{c.id}" for c in clusters}

    for c in clusters:
        nodes.append({
            "id": cluster_nodes[c.id],
            "label": c.name,
            "type": "cluster"
        })

    for f in files:
        nodes.append({
            "id": f.id,
            "label": f.filename,
            "type": "file",
            "path": str(f.path)
        })

        if f.cluster_id in cluster_nodes:
            links.append({
                "source": f.id,
                "target": cluster_nodes[f.cluster_id]
            })

    return {"nodes": nodes, "links": links}


# --------------------------------------------------
# Broadcast Updates
# --------------------------------------------------
async def broadcast_update():
    """Broadcast the current graph to all connected clients."""
    if not clients:
        return

    graph = build_graph()

    for ws in clients[:]:
        try:
            await ws.send_json(graph)
        except Exception:
            clients.remove(ws)
