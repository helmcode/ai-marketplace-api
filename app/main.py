from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import users, agents, tiers, boxes, box_agents, ws_terminal

settings = get_settings()

app = FastAPI(
    title="AI Agent Marketplace API",
    description="API for deploying and managing AI agents on boxes",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routers
app.include_router(users.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(tiers.router, prefix="/api")
app.include_router(boxes.router, prefix="/api")
app.include_router(box_agents.router, prefix="/api")

# WebSocket routers
app.include_router(ws_terminal.router)


@app.get("/")
async def root():
    return {"message": "AI Agent Marketplace API", "version": "0.2.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
