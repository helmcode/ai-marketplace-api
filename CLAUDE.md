# AI Agent Marketplace - Backend

FastAPI backend for the AI Agent Marketplace.

## Tech Stack

- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Authentication**: Auth0 JWT validation
- **Database**: PostgreSQL
- **SSH Client**: Paramiko (for VPS operations and Web Terminal)
- **HTTP Client**: httpx (for Digital Ocean API)
- **WebSocket**: For real-time terminal communication

## Project Structure

```
backend/
├── CLAUDE.md
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
├── alembic.ini
│
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_box_model.py
│
└── app/
    ├── __init__.py
    ├── main.py                     # FastAPI app, CORS, routers
    ├── config.py                   # Settings from env vars
    ├── database.py                 # SQLAlchemy engine + session
    │
    ├── models/                     # SQLAlchemy models
    │   ├── __init__.py
    │   ├── user.py
    │   ├── agent_catalog.py
    │   ├── box.py                  # Box (VPS) model with tiers
    │   └── box_agent.py            # Agent installations in boxes
    │
    ├── schemas/                    # Pydantic schemas
    │   ├── __init__.py
    │   ├── user.py
    │   ├── agent.py
    │   ├── box.py
    │   └── box_agent.py
    │
    ├── api/                        # API endpoints
    │   ├── __init__.py
    │   ├── deps.py                 # Shared dependencies
    │   ├── auth.py                 # Auth0 JWT validation
    │   ├── users.py                # User endpoints
    │   ├── agents.py               # Agent catalog endpoints
    │   ├── boxes.py                # Box CRUD + provisioning
    │   ├── box_agents.py           # Install/manage agents in boxes
    │   ├── terminal.py             # WebSocket terminal proxy
    │   ├── files.py                # Agent file operations (Phase 2)
    │   └── billing.py              # Stripe webhooks (Phase 3)
    │
    ├── services/                   # Business logic
    │   ├── __init__.py
    │   ├── digitalocean.py         # DO API wrapper
    │   ├── provisioning.py         # Box setup scripts
    │   └── ssh.py                  # SSH client for commands/terminal
    │
    └── core/
        ├── __init__.py
        ├── security.py             # JWT utilities
        └── exceptions.py           # Custom exceptions
```

## Database Models

### User

```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid4)
    auth0_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    ssh_public_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    boxes = relationship("Box", back_populates="user", cascade="all, delete-orphan")
```

### Box

```python
class BoxTier(str, enum.Enum):
    BASIC = "basic"    # 1 vCPU, 2GB RAM, $12/mo
    MEDIUM = "medium"  # 2 vCPU, 4GB RAM, $24/mo
    PRO = "pro"        # 4 vCPU, 8GB RAM, $48/mo

class BoxStatus(str, enum.Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"

class Box(Base):
    __tablename__ = "boxes"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    tier = Column(String(20), nullable=False, default=BoxTier.BASIC.value)

    # Digital Ocean resources
    droplet_id = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    region = Column(String(20), default="nyc1")

    # Status
    status = Column(String(20), default=BoxStatus.PENDING.value)
    status_message = Column(Text, nullable=True)

    # System SSH (for backend operations, not user access)
    system_ssh_key_id = Column(String(50), nullable=True)
    system_private_key = Column(Text, nullable=True)  # Encrypted

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="boxes")
    agents = relationship("BoxAgent", back_populates="box", cascade="all, delete-orphan")
```

### AgentCatalog

```python
class AgentCatalog(Base):
    __tablename__ = "agent_catalog"

    id = Column(UUID, primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    long_description = Column(Text)
    icon_url = Column(String(500))
    config_schema = Column(JSON)  # JSON Schema for config form

    # Installation
    install_script_url = Column(String(500))  # e.g., https://openclaw.ai/install.sh
    install_command = Column(Text)            # e.g., curl -fsSL ... | bash
    tui_command = Column(String(200))         # e.g., openclaw tui, claude

    base_price = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### BoxAgent

```python
class BoxAgentStatus(str, enum.Enum):
    PENDING = "pending"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"

class BoxAgent(Base):
    __tablename__ = "box_agents"

    id = Column(UUID, primary_key=True, default=uuid4)
    box_id = Column(UUID, ForeignKey("boxes.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID, nullable=False, index=True)  # Reference to agent_catalog

    instance_name = Column(String(100), nullable=False)
    install_script_url = Column(String(500), nullable=True)
    install_log = Column(Text, nullable=True)

    status = Column(String(20), default=BoxAgentStatus.PENDING.value)
    status_message = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    box = relationship("Box", back_populates="agents")
```

## API Endpoints

### Authentication

All endpoints except agent catalog require Auth0 JWT.

```python
# Dependency for protected routes
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = verify_jwt(token)
    user = get_or_create_user(db, payload)
    return user
```

### Agents (Public)

```
GET  /api/agents
     List all available agents

GET  /api/agents/{slug}
     Get agent details including config_schema, install_command, tui_command
```

### Users (Protected)

```
GET  /api/users/me
     Get current user profile

PUT  /api/users/me
     Update user profile (SSH key)
     Body: { "ssh_public_key": "ssh-rsa AAAA..." }
```

### Boxes (Protected)

```
GET  /api/boxes
     List user's boxes

POST /api/boxes
     Create new box (provisions VPS)
     Body: {
       "name": "My Dev Box",
       "tier": "basic",   # basic | medium | pro
       "region": "nyc1"
     }

GET  /api/boxes/{id}
     Get box details with installed agents

DELETE /api/boxes/{id}
       Delete box (destroys VPS)
```

### Box Agents (Protected)

```
GET  /api/boxes/{box_id}/agents
     List agents installed in a box

POST /api/boxes/{box_id}/agents
     Install an agent in a box
     Body: {
       "agent_slug": "openclaw",
       "instance_name": "My OpenClaw"
     }

GET  /api/boxes/{box_id}/agents/{agent_id}
     Get agent installation details

PUT  /api/boxes/{box_id}/agents/{agent_id}/config
     Update agent configuration
     Body: { "config": { ... } }

DELETE /api/boxes/{box_id}/agents/{agent_id}
       Uninstall agent from box
```

### WebSocket Endpoints (Protected)

```
WS  /ws/tui/{box_agent_id}
    Agent TUI interaction
    - Executes the agent's tui_command (e.g., "claude", "openclaw tui")
    - Session closes when user exits the TUI

WS  /ws/install-tui/{box_agent_id}
    Combined install + TUI flow
    - Runs install_command, then automatically launches tui_command
    - Session closes when user exits the TUI
    - Used during initial agent setup

WS  /ws/terminal/{box_id}
    Full terminal access (restricted)
    - Interactive shell session to box
    - Only for authenticated box owners
```

## Digital Ocean Integration

### Service: `services/digitalocean.py`

```python
class DigitalOceanService:
    def __init__(self, api_token: str):
        self.client = httpx.AsyncClient(
            base_url="https://api.digitalocean.com/v2",
            headers={"Authorization": f"Bearer {api_token}"}
        )

    async def create_droplet(
        self,
        name: str,
        ssh_keys: list[str],
        size: str = "s-1vcpu-2gb",
        region: str = "nyc1",
        image: str = "ubuntu-24-04-x64"
    ) -> dict:
        """Create a new droplet with Ubuntu 24.04."""
        response = await self.client.post("/droplets", json={
            "name": name,
            "region": region,
            "size": size,
            "image": image,
            "ssh_keys": ssh_keys,
            "monitoring": True,
            "tags": ["ai-marketplace", "box"]
        })
        return response.json()

    async def get_droplet(self, droplet_id: str) -> dict:
        """Get droplet details."""
        response = await self.client.get(f"/droplets/{droplet_id}")
        return response.json()

    async def delete_droplet(self, droplet_id: str) -> bool:
        """Delete a droplet."""
        response = await self.client.delete(f"/droplets/{droplet_id}")
        return response.status_code == 204

    async def create_ssh_key(self, name: str, public_key: str) -> dict:
        """Add SSH key to account."""
        response = await self.client.post("/account/keys", json={
            "name": name,
            "public_key": public_key
        })
        return response.json()
```

## Box Provisioning Flow

### Service: `services/box_provisioning.py`

Uses a **single system SSH key** pre-configured in DigitalOcean. No per-box SSH keys are created.

```python
async def provision_box(box: Box, user_ssh_public_key: Optional[str] = None):
    """
    Provision a new Box (VPS):
    1. Use pre-configured system SSH key from DO
    2. Create droplet with Ubuntu 24.04
    3. Wait for droplet to be active
    4. Add user's SSH key via SSH (if provided)
    """

    # Use the pre-configured system SSH key in DigitalOcean
    system_key_id = int(settings.digitalocean_system_ssh_key_id)

    # Create droplet with system SSH key only
    droplet = await do_service.create_droplet(
        name=f"box-{box.id}",
        ssh_key_ids=[system_key_id],
        size=tier_specs["do_size"],
        region=box.region,
        image="ubuntu-24-04-x64"
    )

    # Wait for active status
    ip_address = await wait_for_droplet_active(droplet["droplet"]["id"])

    # Update box record
    box.droplet_id = droplet["droplet"]["id"]
    box.ip_address = ip_address
    box.system_ssh_key_id = str(system_key_id)
    box.status = BoxStatus.RUNNING

    # Add user's SSH key to box via SSH if provided
    if user_ssh_public_key:
        await _add_user_ssh_key_to_box(box, user_ssh_public_key)
        box.user_ssh_synced = '1'

    return box
```

## Agent Installation Flow

Installation happens via WebSocket (`/ws/install-tui/`) for real-time output:

```python
# Combined install + TUI command
combined_command = f'({install_command}) && export PATH="$HOME/.local/bin:$PATH" && {tui_command}; exit $?'
```

The flow:
1. User selects agent to install → creates BoxAgent record
2. Frontend connects to `/ws/install-tui/{box_agent_id}`
3. Backend runs combined command (install + TUI)
4. User configures agent in TUI
5. When user exits TUI, session closes automatically

## WebSocket Terminal Architecture

The backend uses `WebSocketManager` to handle terminal sessions:

- **SSH Connection**: Uses system SSH key (Ed25519/RSA/ECDSA supported)
- **Interactive Shell**: `paramiko.Channel` with PTY for full terminal emulation
- **Bidirectional Proxy**: Forwards data between WebSocket and SSH channel
- **Auto-cleanup**: Sessions close when user exits TUI or disconnects

Terminal sessions are **restricted by design** - they only run the agent's configured commands.
For full shell access, users must SSH from their own machine using their synced SSH key.

## Auth0 JWT Validation

### Core: `core/security.py`

```python
from jose import jwt, JWTError
from functools import lru_cache
import httpx

@lru_cache()
def get_jwks():
    """Fetch Auth0 JWKS (cached)."""
    response = httpx.get(f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json")
    return response.json()

def verify_jwt(token: str) -> dict:
    """Verify Auth0 JWT token."""
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = find_rsa_key(jwks, unverified_header["kid"])

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.AUTH0_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/"
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=str(e))
```

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ai_marketplace

# Auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.yourdomain.com
AUTH0_CLIENT_ID=your-client-id

# Digital Ocean
DIGITALOCEAN_TOKEN=your-do-token
DIGITALOCEAN_SYSTEM_SSH_KEY_ID=12345678  # ID of pre-configured SSH key in DO
SYSTEM_SSH_PRIVATE_KEY_PATH=/path/to/.ssh/id_ed25519  # Path to private key on server

# Encryption (for sensitive config values)
ENCRYPTION_KEY=your-32-byte-key

# Stripe (Phase 3)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000

# Create new migration
alembic revision --autogenerate -m "description"
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test
pytest tests/test_deployments.py -v
```

## Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t ai-marketplace-api .

# Run
docker run -p 8000:8000 --env-file .env ai-marketplace-api
```
