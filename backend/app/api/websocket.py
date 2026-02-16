"""WebSocket endpoint for real-time job progress updates."""

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# In-memory pub/sub mechanism
_subscribers: dict[str, list[WebSocket]] = {}


def subscribe(job_id: str, websocket: WebSocket) -> None:
    """Subscribe a WebSocket to updates for a specific job."""
    if job_id not in _subscribers:
        _subscribers[job_id] = []
    _subscribers[job_id].append(websocket)


def unsubscribe(job_id: str, websocket: WebSocket) -> None:
    """Unsubscribe a WebSocket from updates for a specific job."""
    if job_id in _subscribers:
        _subscribers[job_id] = [ws for ws in _subscribers[job_id] if ws != websocket]
        # Clean up empty lists
        if not _subscribers[job_id]:
            del _subscribers[job_id]


async def notify_progress(
    job_id: str, status: str, progress: int, error: str | None = None
) -> None:
    """Notify all subscribers of progress updates for a specific job."""
    if job_id not in _subscribers:
        return

    message: dict[str, Any] = {
        "status": status,
        "progress": progress,
        "error": error,
    }

    # Send to all subscribers and collect dead connections
    dead_connections: list[WebSocket] = []
    for websocket in _subscribers[job_id]:
        try:
            await websocket.send_json(message)
        except Exception:
            # Connection is dead, mark for removal
            dead_connections.append(websocket)

    # Clean up dead connections
    for websocket in dead_connections:
        unsubscribe(job_id, websocket)


@router.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for real-time job progress updates.

    Args:
        websocket: The WebSocket connection
        job_id: The job ID to subscribe to

    The endpoint sends JSON messages in the format:
    {"status": "...", "progress": 0-100, "error": null}
    """
    await websocket.accept()
    subscribe(job_id, websocket)

    try:
        # Keep connection alive until client disconnects or job completes
        while True:
            # Wait for messages from client (ping/pong to keep connection alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(job_id, websocket)
