from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.config import Configuration
from models.database import Subscription


class DatabaseService:
    def __init__(self, config: Configuration) -> None:
        self._config = config

    def _create_engine(self):
        return create_async_engine(
            f"sqlite+aiosqlite:///{Path(self._config.database_path / 'tracker.db')}", echo=True
        )

    def initialize(self):
        if Path(self._config.database_path / "tracker.db").is_file():
            return

        SQLModel.metadata.create_all(
            create_engine(
                f"sqlite:///{Path(self._config.database_path / 'tracker.db')}", echo=True
            )
        )

    def session(self):
        return AsyncSession(self._create_engine())

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
