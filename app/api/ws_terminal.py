from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from uuid import UUID
import json
import time

from app.database import SessionLocal
from app.models import Box, BoxAgent, BoxStatus, BoxAgentStatus, AgentCatalog, User
from app.core.security import verify_jwt
from app.services.websocket_manager import get_websocket_manager
from app.config import get_settings

router = APIRouter(tags=["websocket"])

def _get_system_ssh_private_key() -> str:
    """Read the system SSH private key from file."""
    settings = get_settings()
    with open(settings.system_ssh_private_key_path, 'r') as f:
        return f.read()


async def _authenticate_websocket(token: str) -> tuple:
    """Authenticate WebSocket connection and return user info."""
    try:
        payload = await verify_jwt(token)
        auth0_id = payload.get("sub")
        if not auth0_id:
            return None, None
        return auth0_id, payload
    except Exception:
        return None, None


@router.websocket("/ws/terminal/{box_id}")
async def terminal_websocket(
    websocket: WebSocket,
    box_id: UUID,
    token: str = Query(...)
):
    """
    WebSocket endpoint for interactive box terminal.

    Protocol:
    - Client sends: {"type": "input", "data": "ls -la\n"}
    - Client sends: {"type": "resize", "cols": 120, "rows": 40}
    - Server sends: {"type": "output", "data": "..."}
    - Server sends: {"type": "connected", "message": "..."}
    - Server sends: {"type": "error", "message": "..."}
    """
    # Authenticate
    auth0_id, payload = await _authenticate_websocket(token)
    if not auth0_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Use a short-lived DB session for initial validation only
    db = SessionLocal()
    try:
        # Get box
        box = db.query(Box).filter(Box.id == box_id).first()
        if not box:
            await websocket.close(code=4004, reason="Box not found")
            return

        # Get user
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user or box.user_id != user.id:
            await websocket.close(code=4003, reason="Forbidden")
            return

        if box.status != BoxStatus.RUNNING.value:
            await websocket.close(code=4000, reason="Box is not running")
            return

        if not box.ip_address:
            await websocket.close(code=4000, reason="Box does not have an IP address")
            return

        # Extract values we need before closing the session
        user_id = user.id
        ip_address = box.ip_address
        private_key = _get_system_ssh_private_key()
    finally:
        db.close()

    # Connect (DB session is now closed)
    manager = get_websocket_manager()
    connection_id = await manager.connect(
        websocket=websocket,
        user_id=user_id,
        resource_id=box_id,
        resource_type="terminal"
    )

    try:
        # Start terminal session
        await manager.start_terminal_session(
            connection_id=connection_id,
            host=ip_address,
            username="root",
            private_key=private_key,
            resource_type="terminal",
            resource_id=box_id
        )

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "input":
                    await manager.send_terminal_input(
                        connection_id=connection_id,
                        data=message.get("data", "")
                    )
                elif message.get("type") == "resize":
                    await manager.resize_terminal(
                        connection_id=connection_id,
                        width=message.get("cols", 120),
                        height=message.get("rows", 40)
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception:
                break

    finally:
        await manager.disconnect(connection_id, "terminal", box_id)


@router.websocket("/ws/tui/{box_agent_id}")
async def tui_websocket(
    websocket: WebSocket,
    box_agent_id: UUID,
    token: str = Query(...)
):
    """
    WebSocket endpoint for agent TUI interaction.

    Opens a terminal session and automatically runs the agent's TUI command.
    """
    # Authenticate
    auth0_id, payload = await _authenticate_websocket(token)
    if not auth0_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Use a short-lived DB session for initial validation only
    db = SessionLocal()
    try:
        # Get box agent
        box_agent = db.query(BoxAgent).filter(BoxAgent.id == box_agent_id).first()
        if not box_agent:
            await websocket.close(code=4004, reason="Agent not found")
            return

        # Get box
        box = db.query(Box).filter(Box.id == box_agent.box_id).first()
        if not box:
            await websocket.close(code=4004, reason="Box not found")
            return

        # Get user
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user or box.user_id != user.id:
            await websocket.close(code=4003, reason="Forbidden")
            return

        if box.status != BoxStatus.RUNNING.value:
            await websocket.close(code=4000, reason="Box is not running")
            return

        if not box.ip_address:
            await websocket.close(code=4000, reason="Box does not have an IP address")
            return

        # Get agent for TUI command
        agent = db.query(AgentCatalog).filter(AgentCatalog.id == box_agent.agent_id).first()
        tui_command = agent.tui_command if agent and agent.tui_command else "openclaw tui"

        # Build secure command: add PATH and ensure session closes when TUI exits/fails
        # The trailing `; exit $?` ensures the shell ALWAYS closes after TUI exits/fails
        secure_tui_command = f'export PATH="$HOME/.local/bin:$PATH" && {tui_command}; exit $?'

        # Extract values we need before closing the session
        user_id = user.id
        ip_address = box.ip_address
        private_key = _get_system_ssh_private_key()
    finally:
        db.close()

    # Connect (DB session is now closed)
    manager = get_websocket_manager()
    connection_id = await manager.connect(
        websocket=websocket,
        user_id=user_id,
        resource_id=box_agent_id,
        resource_type="tui"
    )

    try:
        # Start terminal session with secure TUI command
        await manager.start_terminal_session(
            connection_id=connection_id,
            host=ip_address,
            username="root",
            private_key=private_key,
            resource_type="tui",
            resource_id=box_agent_id,
            initial_command=secure_tui_command
        )

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "input":
                    await manager.send_terminal_input(
                        connection_id=connection_id,
                        data=message.get("data", "")
                    )
                elif message.get("type") == "resize":
                    await manager.resize_terminal(
                        connection_id=connection_id,
                        width=message.get("cols", 120),
                        height=message.get("rows", 40)
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception:
                break

    finally:
        await manager.disconnect(connection_id, "tui", box_agent_id)


@router.websocket("/ws/install-tui/{box_agent_id}")
async def install_tui_websocket(
    websocket: WebSocket,
    box_agent_id: UUID,
    token: str = Query(...)
):
    """
    WebSocket endpoint for agent installation followed by TUI interaction.

    Executes: {install_command} && exec {tui_command} || exit 1

    This combines installation and TUI in a single session:
    - User sees installation output
    - If successful, automatically transitions to TUI
    - When user exits TUI (or install fails), session closes
    - Agent status is updated based on outcome
    """
    # Authenticate
    auth0_id, payload = await _authenticate_websocket(token)
    if not auth0_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Use a short-lived DB session for initial validation only
    db = SessionLocal()
    try:
        # Get box agent
        box_agent = db.query(BoxAgent).filter(BoxAgent.id == box_agent_id).first()
        if not box_agent:
            await websocket.close(code=4004, reason="Agent not found")
            return

        # Get box
        box = db.query(Box).filter(Box.id == box_agent.box_id).first()
        if not box:
            await websocket.close(code=4004, reason="Box not found")
            return

        # Get user
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user or box.user_id != user.id:
            await websocket.close(code=4003, reason="Forbidden")
            return

        if box.status != BoxStatus.RUNNING.value:
            await websocket.close(code=4000, reason="Box is not running")
            return

        if not box.ip_address:
            await websocket.close(code=4000, reason="Box does not have an IP address")
            return

        # Get agent catalog for install and TUI commands
        agent = db.query(AgentCatalog).filter(AgentCatalog.id == box_agent.agent_id).first()
        if not agent:
            await websocket.close(code=4004, reason="Agent catalog not found")
            return

        install_command = agent.install_command
        tui_command = agent.tui_command or "claude"

        if not install_command:
            await websocket.close(code=4000, reason="Agent has no install command")
            return

        # Update agent status to installing
        box_agent.status = BoxAgentStatus.INSTALLING.value
        box_agent.status_message = "Starting installation..."
        db.commit()

        # Extract values we need before closing the session
        user_id = user.id
        box_id = box.id
        ip_address = box.ip_address
        private_key = _get_system_ssh_private_key()
    finally:
        db.close()

    # Build combined command that always exits when done
    # 1. Run install command
    # 2. Add ~/.local/bin to PATH (where many CLI tools install)
    # 3. Run TUI command
    # 4. Exit with the TUI's exit code (or error code if command not found)
    # The trailing `; exit $?` ensures the shell ALWAYS closes after TUI exits/fails
    combined_command = f'({install_command}) && export PATH="$HOME/.local/bin:$PATH" && {tui_command}; exit $?'

    # Connect (DB session is now closed)
    manager = get_websocket_manager()
    connection_id = await manager.connect(
        websocket=websocket,
        user_id=user_id,
        resource_id=box_agent_id,
        resource_type="install-tui"
    )

    session_start = time.time()

    try:
        # Start terminal session with combined install + TUI command
        await manager.start_terminal_session(
            connection_id=connection_id,
            host=ip_address,
            username="root",
            private_key=private_key,
            resource_type="install-tui",
            resource_id=box_agent_id,
            initial_command=combined_command
        )

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "input":
                    await manager.send_terminal_input(
                        connection_id=connection_id,
                        data=message.get("data", "")
                    )
                elif message.get("type") == "resize":
                    await manager.resize_terminal(
                        connection_id=connection_id,
                        width=message.get("cols", 120),
                        height=message.get("rows", 40)
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception:
                break

    finally:
        await manager.disconnect(connection_id, "install-tui", box_agent_id)

        # Update agent status based on session duration
        # If session lasted > 30 seconds, likely TUI was reached (install succeeded)
        session_duration = time.time() - session_start

        db = SessionLocal()
        try:
            box_agent = db.query(BoxAgent).filter(BoxAgent.id == box_agent_id).first()
            if box_agent:
                if session_duration > 30:
                    # Session lasted a while, assume install succeeded and user used TUI
                    box_agent.status = BoxAgentStatus.RUNNING.value
                    box_agent.status_message = "Agent installed and configured"
                else:
                    # Session was very short, likely install failed
                    box_agent.status = BoxAgentStatus.FAILED.value
                    box_agent.status_message = "Installation may have failed (session ended quickly)"
                db.commit()
        finally:
            db.close()


@router.websocket("/ws/install/{box_agent_id}")
async def install_websocket(
    websocket: WebSocket,
    box_agent_id: UUID,
    token: str = Query(...)
):
    """
    WebSocket endpoint for streaming agent installation output.

    This is a read-only stream that shows installation progress.
    """
    # Authenticate
    auth0_id, payload = await _authenticate_websocket(token)
    if not auth0_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Use a short-lived DB session for initial validation only
    db = SessionLocal()
    try:
        # Get box agent
        box_agent = db.query(BoxAgent).filter(BoxAgent.id == box_agent_id).first()
        if not box_agent:
            await websocket.close(code=4004, reason="Agent not found")
            return

        # Get box
        box = db.query(Box).filter(Box.id == box_agent.box_id).first()
        if not box:
            await websocket.close(code=4004, reason="Box not found")
            return

        # Get user
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user or box.user_id != user.id:
            await websocket.close(code=4003, reason="Forbidden")
            return

        # Extract values we need before closing the session
        user_id = user.id
        install_log = box_agent.install_log
        agent_status = box_agent.status
        status_message = box_agent.status_message
    finally:
        db.close()

    # Connect (DB session is now closed)
    manager = get_websocket_manager()
    connection_id = await manager.connect(
        websocket=websocket,
        user_id=user_id,
        resource_id=box_agent_id,
        resource_type="install"
    )

    try:
        await websocket.accept()

        # Send current log if available
        if install_log:
            await websocket.send_json({
                "type": "output",
                "data": install_log
            })

        # Send current status
        await websocket.send_json({
            "type": "status",
            "status": agent_status,
            "message": status_message
        })

        # Keep connection open for updates
        # In a production system, you'd want to implement proper pub/sub
        # For now, we just keep the connection alive and let the client poll
        while True:
            try:
                # Wait for client messages (ping/pong or disconnect)
                await websocket.receive_text()
            except WebSocketDisconnect:
                break

    finally:
        await manager.disconnect(connection_id, "install", box_agent_id)
