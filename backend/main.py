from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

from backend.config import settings
from backend.database import engine, Base

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing database tables if not exist...")
    # In production, we use migrations, but for ease of setup/local run, we can create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully.")
    yield
    # Shutdown actions
    logger.info("Cleaning up connections...")
    await engine.dispose()
    logger.info("Shutdown sequence complete.")

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Ready AI Research Assistant API Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS setup
origins = [org.strip() for org in settings.ALLOWED_ORIGINS.split(",") if org]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
