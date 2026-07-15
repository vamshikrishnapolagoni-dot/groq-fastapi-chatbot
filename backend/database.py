from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from backend.config import settings
import logging

logger = logging.getLogger("database")

# Create Async Engine
# SQLAlchemy async engine requires the driver in connection string (e.g. postgresql+asyncpg://...)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True to log queries
    pool_pre_ping=True
)

# Create Async Session Maker
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Dependency to get session in routers
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
