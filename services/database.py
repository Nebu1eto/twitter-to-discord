from pathlib import Path
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.config import Configuration
from models.database import Subscription


class DatabaseService:
    _async_engine: AsyncEngine | None
    _sync_engine: Engine | None

    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._async_engine = None
        self._sync_engine = None

    def _get_database_path(self):
        return Path(self._config.database_path) / "tracker.db"

    def _get_async_engine(self):
        if self._async_engine is None:
            self._async_engine = create_async_engine(
                f"sqlite+aiosqlite:///{self._get_database_path()}?check_same_thread=false",
                echo=True,
            )

        return self._async_engine

    def _get_sync_engine(self):
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                f"sqlite:///{self._get_database_path()}?check_same_thread=false",
                echo=True,
            )

        return self._sync_engine

    def initialize(self):
        if not self._get_database_path().is_file():
            return

        SQLModel.metadata.create_all(self._get_sync_engine())

    def session(self):
        return AsyncSession(self._get_async_engine())

    async def subscriptions(self, channel_id: str | None = None):
        async with self.session() as session:
            stmt = select(Subscription)
            if channel_id is not None:
                stmt = stmt.where(Subscription.channel_id == channel_id)

            results = await session.exec(stmt)
            return results.all()

    async def get_one_subscription(self, subscription_id: UUID):
        async with self.session() as session:
            return await session.get_one(Subscription, subscription_id)
