from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import users, agents, deployments

settings = get_settings()

app = FastAPI(
    title="AI Agent Marketplace API",
    description="API for deploying and managing AI agents",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(deployments.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "AI Agent Marketplace API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
