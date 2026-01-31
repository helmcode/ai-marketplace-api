import paramiko
import asyncio
from typing import Optional
from io import StringIO


class SSHService:
    """Service for executing commands and managing files on remote servers via SSH."""

    def __init__(
        self,
        host: str,
        username: str = "root",
        port: int = 22,
        private_key: Optional[str] = None,
        private_key_path: Optional[str] = None
    ):
        self.host = host
        self.username = username
        self.port = port
        self.private_key = private_key
        self.private_key_path = private_key_path

    def _get_client(self) -> paramiko.SSHClient:
        """Create and configure SSH client."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": self.host,
            "username": self.username,
            "port": self.port,
            "timeout": 30
        }

        if self.private_key:
            key_file = StringIO(self.private_key)
            pkey = paramiko.RSAKey.from_private_key(key_file)
            connect_kwargs["pkey"] = pkey
        elif self.private_key_path:
            connect_kwargs["key_filename"] = self.private_key_path

        client.connect(**connect_kwargs)
        return client

    async def execute(self, command: str, timeout: int = 60) -> tuple[str, str, int]:
        """Execute a command on the remote server."""
        def _execute():
            client = self._get_client()
            try:
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                exit_code = stdout.channel.recv_exit_status()
                return (
                    stdout.read().decode("utf-8"),
                    stderr.read().decode("utf-8"),
                    exit_code
                )
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _execute)

    async def read_file(self, remote_path: str) -> str:
        """Read a file from the remote server."""
        def _read():
            client = self._get_client()
            try:
                sftp = client.open_sftp()
                try:
                    with sftp.file(remote_path, "r") as f:
                        return f.read().decode("utf-8")
                finally:
                    sftp.close()
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read)

    async def write_file(self, remote_path: str, content: str) -> None:
        """Write content to a file on the remote server."""
        def _write():
            client = self._get_client()
            try:
                sftp = client.open_sftp()
                try:
                    with sftp.file(remote_path, "w") as f:
                        f.write(content)
                finally:
                    sftp.close()
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write)

    async def append_file(self, remote_path: str, content: str) -> None:
        """Append content to a file on the remote server."""
        def _append():
            client = self._get_client()
            try:
                sftp = client.open_sftp()
                try:
                    with sftp.file(remote_path, "a") as f:
                        f.write(content)
                finally:
                    sftp.close()
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _append)

    async def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote server."""
        def _exists():
            client = self._get_client()
            try:
                sftp = client.open_sftp()
                try:
                    sftp.stat(remote_path)
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    sftp.close()
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _exists)

    async def mkdir(self, remote_path: str) -> None:
        """Create a directory on the remote server."""
        await self.execute(f"mkdir -p {remote_path}")
