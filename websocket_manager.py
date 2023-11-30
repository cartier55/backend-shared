from fastapi import Depends, HTTPException, status, Query, APIRouter, Body, Response, Request, File, UploadFile, WebSocket, WebSocketDisconnect
from logger import coach_logger
from typing import Optional, Union, List, Dict
import json


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        # await websocket.accept()
        coach_logger.log_info("[+] New connection established.")
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        if len(self.active_connections) > 0:
            coach_logger.log_info(f"[+] Broadcasting message to {len(self.active_connections)} connections.")
            message_text = json.dumps(message)  # Convert the message dict to a JSON string
            for connection in self.active_connections:
                await connection.send_text(message_text)

manager = ConnectionManager()
