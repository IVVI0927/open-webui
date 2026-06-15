from __future__ import annotations

import time
import uuid

from open_webui.internal.db import Base, get_async_db_context
from open_webui.models.memories import Memory
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryConflict(Base):
    __tablename__ = 'memory_conflict'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    node_a_id = Column(String, ForeignKey(Memory.id, ondelete='CASCADE'), nullable=False)
    node_b_id = Column(String, ForeignKey(Memory.id, ondelete='CASCADE'), nullable=False)
    conflict_type = Column(String, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    resolution = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    resolved_at = Column(BigInteger, nullable=True)


class MemoryConflictModel(BaseModel):
    id: str
    user_id: str
    node_a_id: str
    node_b_id: str
    conflict_type: str
    resolved: bool = False
    resolution: str | None = None
    created_at: int
    resolved_at: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryConflictsTable:
    async def insert_conflict(
        self,
        user_id: str,
        node_a_id: str,
        node_b_id: str,
        conflict_type: str,
        db: AsyncSession | None = None,
    ) -> MemoryConflictModel | None:
        async with get_async_db_context(db) as db:
            conflict = MemoryConflict(
                id=str(uuid.uuid4()),
                user_id=user_id,
                node_a_id=node_a_id,
                node_b_id=node_b_id,
                conflict_type=conflict_type,
                resolved=False,
                created_at=int(time.time()),
            )
            db.add(conflict)
            await db.commit()
            await db.refresh(conflict)
            return MemoryConflictModel.model_validate(conflict)

    async def get_unresolved_conflicts(
        self,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> list[MemoryConflictModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(MemoryConflict).where(
                    MemoryConflict.user_id == user_id,
                    MemoryConflict.resolved.is_(False),
                )
            )
            return [MemoryConflictModel.model_validate(conflict) for conflict in result.scalars().all()]

    async def resolve_conflict(
        self,
        conflict_id: str,
        user_id: str,
        resolution: str,
        db: AsyncSession | None = None,
    ) -> MemoryConflictModel | None:
        async with get_async_db_context(db) as db:
            conflict = await db.get(MemoryConflict, conflict_id)
            if not conflict or conflict.user_id != user_id:
                return None

            conflict.resolved = True
            conflict.resolution = resolution
            conflict.resolved_at = int(time.time())
            await db.commit()
            await db.refresh(conflict)
            return MemoryConflictModel.model_validate(conflict)


MemoryConflicts = MemoryConflictsTable()
