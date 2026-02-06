# AI Agent Marketplace - Backend

FastAPI backend for the AI Agent Marketplace. Manages user authentication, box (VPS) provisioning, agent installation, billing, and real-time terminal access.

## Features

- **Box Management** - Create, monitor, and delete isolated VPS instances on DigitalOcean
- **Agent Catalog** - Browse and install AI agents (Claude Code, OpenClaw) into boxes
- **Web Terminal** - Real-time WebSocket terminal proxy for agent interaction via SSH
- **Stripe Billing** - Subscription-based billing with checkout, webhooks, and customer portal
- **Auth0 JWT** - Secure authentication with automatic user provisioning

## Tech Stack

- **Python 3.12** / **FastAPI** / **Uvicorn**
- **SQLAlchemy 2.0** + **Alembic** (PostgreSQL)
- **Paramiko** (SSH client for VPS operations and terminal proxy)
- **Stripe SDK** (subscriptions, webhooks, customer portal)
- **Auth0** (JWT validation)
- **DigitalOcean API** via httpx

## Project Structure

```
backend/
├── alembic/                  # Database migrations
│   └── versions/
├── app/
│   ├── api/                  # API endpoints
│   │   ├── agents.py         # Agent catalog (public)
│   │   ├── billing.py        # Stripe checkout, webhooks, portal
│   │   ├── boxes.py          # Box CRUD + provisioning
│   │   ├── box_agents.py     # Install/manage agents in boxes
│   │   ├── terminal.py       # WebSocket terminal proxy
│   │   └── users.py          # User profile + SSH keys
│   ├── core/                 # Security, exceptions
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic (DO API, provisioning, SSH)
│   ├── config.py             # Settings from environment
│   ├── database.py           # Engine + session
│   └── main.py               # App entry point
├── scripts/
│   └── seed.py               # Seed agent catalog
├── requirements.txt
└── .env.example
```

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- A DigitalOcean account with an API token
- An Auth0 tenant (SPA + API)
- A Stripe account with products configured

### Installation

```bash
# Clone the repository
git clone https://github.com/helmcode/ai-marketplace-api.git
cd ai-marketplace-api

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Database Setup

```bash
# Run migrations
alembic upgrade head

# Seed agent catalog
python scripts/seed.py
```

### Running

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production (systemd recommended)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Environment Variables

Copy `.env.example` and fill in your values:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `AUTH0_DOMAIN` | Auth0 tenant domain |
| `AUTH0_AUDIENCE` | Auth0 API audience |
| `AUTH0_CLIENT_ID` | Auth0 application client ID |
| `DIGITALOCEAN_TOKEN` | DigitalOcean API token |
| `DIGITALOCEAN_SYSTEM_SSH_KEY_ID` | Pre-configured SSH key ID in DO |
| `SYSTEM_SSH_PRIVATE_KEY_PATH` | Path to system SSH private key |
| `ENCRYPTION_KEY` | 32-byte base64-encoded encryption key |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_PRICE_MAP` | JSON mapping tier names to Stripe price IDs |
| `FRONTEND_URL` | Frontend URL for Stripe redirects |
| `CORS_ORIGINS` | Comma-separated allowed origins |

## API Endpoints

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agents` | List available agents |
| GET | `/api/agents/{slug}` | Agent details |
| GET | `/api/tiers` | List box tiers and pricing |

### Authenticated (JWT)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Current user profile |
| PUT | `/api/users/me` | Update profile (SSH key) |
| GET | `/api/boxes` | List user's boxes |
| GET | `/api/boxes/{id}` | Box details |
| DELETE | `/api/boxes/{id}` | Delete box |
| POST | `/api/boxes/{id}/sync-ssh` | Sync SSH key to box |
| POST | `/api/billing/checkout-session` | Create Stripe checkout |
| POST | `/api/billing/customer-portal` | Open billing portal |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/billing/webhook` | Stripe webhook handler |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/tui/{box_agent_id}` | Agent TUI session |
| `/ws/install-tui/{box_agent_id}` | Install + TUI combined |

## Stripe Setup

1. Create products in Stripe Dashboard with monthly recurring prices:
   - **Box - Basic** ($16/mo)
   - **Box - Medium** ($28/mo)
   - **Box - Pro** ($52/mo)

2. Create a webhook endpoint pointing to `/api/billing/webhook` with events:
   - `checkout.session.completed`
   - `invoice.payment_failed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`

3. Enable the Customer Portal in Stripe Dashboard (Settings > Billing > Customer portal)

4. Add the keys to your `.env`

## SSH Architecture

The platform uses a **single system SSH key** for backend access to all boxes:

1. A system Ed25519 key is pre-configured in DigitalOcean
2. The backend uses this key to manage all boxes (provisioning, agent installation, terminal proxy)
3. Users can optionally add their own SSH public key for direct access

## Billing Flow

```
User selects tier → Backend creates Stripe Checkout Session →
User pays on Stripe → Webhook fires → Backend creates Box + Subscription →
Box provisioned on DigitalOcean → User redirected to dashboard
```

On cancellation, a 3-day grace period applies before the box is destroyed. Subscription reuse with proration is supported when creating a new box.

## License

MIT
