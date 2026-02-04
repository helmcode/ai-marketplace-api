import asyncio
import json
from typing import Dict, Set, Optional, Callable, Any
from uuid import UUID
from dataclasses import dataclass, field
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import paramiko
from io import StringIO


@dataclass
class WebSocketConnection:
    """Represents an active WebSocket connection."""
    websocket: WebSocket
    user_id: UUID
    resource_id: UUID
    resource_type: str  # "terminal", "install", "tui"
    connected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    read_task: Optional[asyncio.Task] = field(default=None)


class WebSocketManager:
    """
    Manages WebSocket connections for terminal sessions.

    Supports:
    - Interactive terminal sessions (box shell access)
    - Installation output streaming
    - Agent TUI interaction
    """

    def __init__(self):
        # Active connections: {resource_id: {connection_id: WebSocketConnection}}
        self._connections: Dict[str, Dict[str, WebSocketConnection]] = {}
        # SSH channels for terminal sessions: {connection_id: paramiko.Channel}
        self._ssh_channels: Dict[str, paramiko.Channel] = {}
        self._ssh_clients: Dict[str, paramiko.SSHClient] = {}
        self._lock = asyncio.Lock()

    def _connection_key(self, resource_type: str, resource_id: UUID) -> str:
        """Generate a unique key for a resource."""
        return f"{resource_type}:{resource_id}"

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID,
        resource_id: UUID,
        resource_type: str,
        metadata: Optional[dict] = None
    ) -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        connection_id = f"{user_id}:{resource_id}:{datetime.utcnow().timestamp()}"
        connection = WebSocketConnection(
            websocket=websocket,
            user_id=user_id,
            resource_id=resource_id,
            resource_type=resource_type,
            metadata=metadata or {}
        )

        resource_key = self._connection_key(resource_type, resource_id)

        async with self._lock:
            if resource_key not in self._connections:
                self._connections[resource_key] = {}
            self._connections[resource_key][connection_id] = connection

        return connection_id

    async def disconnect(self, connection_id: str, resource_type: str, resource_id: UUID):
        """Remove a WebSocket connection and cleanup resources."""
        resource_key = self._connection_key(resource_type, resource_id)

        async with self._lock:
            # Cancel read task if exists
            if resource_key in self._connections:
                if connection_id in self._connections[resource_key]:
                    conn = self._connections[resource_key][connection_id]
                    if conn.read_task and not conn.read_task.done():
                        conn.read_task.cancel()
                        try:
                            await conn.read_task
                        except asyncio.CancelledError:
                            pass

            # Close SSH channel if exists
            if connection_id in self._ssh_channels:
                try:
                    self._ssh_channels[connection_id].close()
                except Exception:
                    pass
                del self._ssh_channels[connection_id]

            # Close SSH client if exists
            if connection_id in self._ssh_clients:
                try:
                    self._ssh_clients[connection_id].close()
                except Exception:
                    pass
                del self._ssh_clients[connection_id]

            # Remove connection
            if resource_key in self._connections:
                if connection_id in self._connections[resource_key]:
                    del self._connections[resource_key][connection_id]
                if not self._connections[resource_key]:
                    del self._connections[resource_key]

    async def send_message(self, connection_id: str, resource_type: str, resource_id: UUID, message: dict):
        """Send a message to a specific connection."""
        resource_key = self._connection_key(resource_type, resource_id)

        async with self._lock:
            if resource_key in self._connections:
                if connection_id in self._connections[resource_key]:
                    conn = self._connections[resource_key][connection_id]
                    try:
                        await conn.websocket.send_json(message)
                    except Exception:
                        pass

    async def broadcast(self, resource_type: str, resource_id: UUID, message: dict):
        """Broadcast a message to all connections for a resource."""
        resource_key = self._connection_key(resource_type, resource_id)

        async with self._lock:
            if resource_key in self._connections:
                for conn in list(self._connections[resource_key].values()):
                    try:
                        await conn.websocket.send_json(message)
                    except Exception:
                        pass

    async def start_terminal_session(
        self,
        connection_id: str,
        host: str,
        username: str,
        private_key: str,
        resource_type: str,
        resource_id: UUID,
        initial_command: Optional[str] = None
    ):
        """Start an interactive SSH terminal session."""
        resource_key = self._connection_key(resource_type, resource_id)

        # Get the websocket connection
        if resource_key not in self._connections or connection_id not in self._connections[resource_key]:
            return

        conn = self._connections[resource_key][connection_id]

        try:
            # Create SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Try to load key (supports RSA, Ed25519, ECDSA)
            key_file = StringIO(private_key)
            pkey = None
            for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
                try:
                    key_file.seek(0)
                    pkey = key_class.from_private_key(key_file)
                    break
                except Exception:
                    continue

            if pkey is None:
                raise Exception("Could not load SSH private key")

            # Run connection in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.connect(
                    hostname=host,
                    username=username,
                    pkey=pkey,
                    timeout=30
                )
            )

            # Create interactive channel
            channel = client.invoke_shell(term='xterm-256color', width=120, height=40)
            channel.settimeout(0.1)

            async with self._lock:
                self._ssh_clients[connection_id] = client
                self._ssh_channels[connection_id] = channel

            # Send connected message
            await conn.websocket.send_json({
                "type": "connected",
                "message": "Terminal session started"
            })

            # If there's an initial command, send it
            if initial_command:
                await asyncio.sleep(1.0)  # Wait for shell to be ready and for client to send resize
                channel.send(initial_command + "\n")

            # Start reading output in a background task (non-blocking)
            read_task = asyncio.create_task(
                self._read_terminal_output(connection_id, channel, conn.websocket)
            )
            conn.read_task = read_task

        except Exception as e:
            await conn.websocket.send_json({
                "type": "error",
                "message": f"Failed to connect: {str(e)}"
            })
            await self.disconnect(connection_id, resource_type, resource_id)

    async def _read_terminal_output(
        self,
        connection_id: str,
        channel: paramiko.Channel,
        websocket: WebSocket
    ):
        """Read and forward terminal output to WebSocket."""
        loop = asyncio.get_event_loop()

        try:
            while True:
                # Check if connection still exists
                if connection_id not in self._ssh_channels:
                    break

                # Read from channel in executor
                def read_data():
                    try:
                        if channel.recv_ready():
                            return channel.recv(4096)
                        return None
                    except Exception:
                        return None

                data = await loop.run_in_executor(None, read_data)

                if data:
                    try:
                        await websocket.send_json({
                            "type": "output",
                            "data": data.decode('utf-8', errors='replace')
                        })
                    except Exception:
                        break
                else:
                    await asyncio.sleep(0.05)

                # Check if channel is closed
                if channel.closed:
                    break

        except Exception:
            pass

    async def send_terminal_input(
        self,
        connection_id: str,
        data: str
    ):
        """Send input to an active terminal session."""
        async with self._lock:
            if connection_id in self._ssh_channels:
                channel = self._ssh_channels[connection_id]
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: channel.send(data))
                except Exception:
                    pass

    async def resize_terminal(
        self,
        connection_id: str,
        width: int,
        height: int
    ):
        """Resize the terminal window."""
        async with self._lock:
            if connection_id in self._ssh_channels:
                channel = self._ssh_channels[connection_id]
                try:
                    channel.resize_pty(width=width, height=height)
                except Exception:
                    pass

    def get_active_connections(self, resource_type: str, resource_id: UUID) -> int:
        """Get count of active connections for a resource."""
        resource_key = self._connection_key(resource_type, resource_id)
        return len(self._connections.get(resource_key, {}))


# Global instance
websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return websocket_manager
