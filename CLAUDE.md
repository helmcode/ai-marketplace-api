# AI Agent Marketplace - Backend

FastAPI backend for the AI Agent Marketplace.

## Tech Stack

- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Authentication**: Auth0 JWT validation
- **Database**: PostgreSQL
- **SSH Client**: Paramiko (for VPS file operations)
- **HTTP Client**: httpx (for Digital Ocean API)

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
│
└── app/
    ├── __init__.py
    ├── main.py                     # FastAPI app, CORS, routers
    ├── config.py                   # Settings from env vars
    ├── database.py                 # SQLAlchemy engine + session
    │
    ├── models/                     # SQLAlchemy models
    │   ├── __init__.py
    │   ├── base.py                 # Base model class
    │   ├── user.py
    │   ├── agent_catalog.py
    │   ├── deployment.py
    │   └── subscription.py
    │
    ├── schemas/                    # Pydantic schemas
    │   ├── __init__.py
    │   ├── user.py
    │   ├── agent.py
    │   └── deployment.py
    │
    ├── api/                        # API endpoints
    │   ├── __init__.py
    │   ├── deps.py                 # Shared dependencies
    │   ├── auth.py                 # Auth0 JWT validation
    │   ├── users.py                # User endpoints
    │   ├── agents.py               # Agent catalog endpoints
    │   ├── deployments.py          # Deployment CRUD
    │   ├── files.py                # Agent file operations (Phase 2)
    │   └── billing.py              # Stripe webhooks (Phase 3)
    │
    ├── services/                   # Business logic
    │   ├── __init__.py
    │   ├── digitalocean.py         # DO API wrapper
    │   ├── provisioning.py         # VPS setup scripts
    │   └── ssh.py                  # SSH client for file ops
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
    auth0_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    ssh_public_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    deployments = relationship("Deployment", back_populates="user")
```

### AgentCatalog

```python
class AgentCatalog(Base):
    __tablename__ = "agent_catalog"

    id = Column(UUID, primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)
    icon_url = Column(String)
    config_schema = Column(JSON)  # JSON Schema for config form
    snapshot_id = Column(String)  # Digital Ocean snapshot ID
    droplet_size = Column(String, default="s-1vcpu-2gb")
    base_price = Column(Integer)  # Price in cents
    created_at = Column(DateTime, default=datetime.utcnow)

    deployments = relationship("Deployment", back_populates="agent")
```

### Deployment

```python
class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID, ForeignKey("agent_catalog.id"), nullable=False)
    droplet_id = Column(String)  # Digital Ocean droplet ID
    ip_address = Column(String)
    ssh_user = Column(String, default="root")
    status = Column(String, default="pending")  # pending, provisioning, running, stopped, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="deployments")
    agent = relationship("AgentCatalog", back_populates="deployments")
    config = relationship("DeploymentConfig", back_populates="deployment")
```

### DeploymentConfig

```python
class DeploymentConfig(Base):
    __tablename__ = "deployment_config"

    id = Column(UUID, primary_key=True, default=uuid4)
    deployment_id = Column(UUID, ForeignKey("deployments.id"), nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text)  # Encrypted for sensitive values
    is_secret = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    deployment = relationship("Deployment", back_populates="config")
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
     Get agent details including config_schema
```

### Users (Protected)

```
GET  /api/users/me
     Get current user profile

PUT  /api/users/me
     Update user profile (SSH key)
     Body: { "ssh_public_key": "ssh-rsa AAAA..." }
```

### Deployments (Protected)

```
GET  /api/deployments
     List user's deployments

POST /api/deployments
     Create new deployment
     Body: {
       "agent_slug": "openclaw",
       "config": {
         "provider": "anthropic",
         "api_key": "sk-ant-...",
         "model": "claude-sonnet-4-5",
         "agent_name": "My Agent"
       }
     }

GET  /api/deployments/{id}
     Get deployment details

DELETE /api/deployments/{id}
       Delete deployment (destroys VPS)
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
        snapshot_id: str,
        ssh_keys: list[str],
        size: str = "s-1vcpu-2gb",
        region: str = "nyc1"
    ) -> dict:
        """Create a new droplet from snapshot."""
        response = await self.client.post("/droplets", json={
            "name": name,
            "region": region,
            "size": size,
            "image": snapshot_id,
            "ssh_keys": ssh_keys,
            "monitoring": True,
            "tags": ["ai-marketplace"]
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

    async def add_ssh_key(self, name: str, public_key: str) -> dict:
        """Add SSH key to account."""
        response = await self.client.post("/account/keys", json={
            "name": name,
            "public_key": public_key
        })
        return response.json()
```

## Provisioning Flow

### Service: `services/provisioning.py`

```python
async def provision_deployment(deployment: Deployment, config: dict):
    """
    Provision a new deployment:
    1. Add user's SSH key to Digital Ocean
    2. Create droplet from snapshot
    3. Wait for droplet to be active
    4. Apply user configuration via SSH
    """

    # 1. Add SSH key
    ssh_key = await do_service.add_ssh_key(
        name=f"user-{deployment.user_id}",
        public_key=deployment.user.ssh_public_key
    )

    # 2. Create droplet
    droplet = await do_service.create_droplet(
        name=f"agent-{deployment.id}",
        snapshot_id=deployment.agent.snapshot_id,
        ssh_keys=[ssh_key["ssh_key"]["id"]],
        size=deployment.agent.droplet_size
    )

    # 3. Wait for active status
    ip_address = await wait_for_droplet_active(droplet["droplet"]["id"])

    # 4. Apply configuration
    await apply_agent_config(ip_address, config)

    return ip_address
```

### Config Application Script

```python
async def apply_agent_config(ip: str, config: dict):
    """Apply user configuration to the agent via SSH."""

    # Generate openclaw.json
    openclaw_config = {
        "auth": {
            "profiles": {
                f"{config['provider']}:api-key": {
                    "provider": config["provider"],
                    "mode": "api-key"
                }
            }
        },
        "agents": {
            "defaults": {
                "model": {
                    "primary": f"{config['provider']}/{config['model']}"
                }
            }
        },
        "gateway": {
            "port": 54321,
            "mode": "local"
        }
    }

    # Generate IDENTITY.md
    identity_content = f"""# Identity

Name: {config.get('agent_name', 'Claw')}
Creature: AI Assistant
Vibe: Helpful and efficient
Emoji: 🦞
"""

    # Write files via SSH
    ssh = SSHClient(ip, "root")
    await ssh.write_file("~/.openclaw/openclaw.json", json.dumps(openclaw_config))
    await ssh.write_file("~/.openclaw/workspace/IDENTITY.md", identity_content)

    # Set API key as environment variable
    env_line = f'{config["provider"].upper()}_API_KEY={config["api_key"]}'
    await ssh.append_file("~/.bashrc", f'export {env_line}')

    # Restart openclaw daemon
    await ssh.execute("openclaw daemon restart")
```

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
