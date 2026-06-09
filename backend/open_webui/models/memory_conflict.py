import time
import uuid
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from open_webui.internal.db import Base, get_async_db_context


class MemoryConflict(Base):
    __tablename__ = 'memory_conflict'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    node_a_id = Column(String, ForeignKey('memory.id', ondelete='CASCADE'), nullable=False)
    node_b_id = Column(String, ForeignKey('memory.id', ondelete='CASCADE'), nullable=False)
    conflict_type = Column(String, nullable=False)  # contradiction | supersede | duplicate
    resolved = Column(Boolean, nullable=False, default=False)
    resolution = Column(String, nullable=True)  # keep_a | keep_b | keep_both | merge
    created_at = Column(BigInteger, nullable=False)
    resolved_at = Column(BigInteger, nullable=True)


class MemoryConflictModel(BaseModel):
    id: str
    user_id: str
    node_a_id: str
    node_b_id: str
    conflict_type: str
    resolved: bool = False
    resolution: Optional[str] = None
    created_at: int
    resolved_at: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class MemoryConflictsTable:
    async def insert_conflict(
        self,
        user_id: str,
        node_a_id: str,
        node_b_id: str,
        conflict_type: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[MemoryConflictModel]:
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
        db: Optional[AsyncSession] = None,
    ) -> list[MemoryConflictModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(
                    select(MemoryConflict).where(
                        MemoryConflict.user_id == user_id,
                        MemoryConflict.resolved == False,  # noqa: E712
                    )
                )
                return [MemoryConflictModel.model_validate(c) for c in result.scalars().all()]
            except Exception:
                return []

    async def resolve_conflict(
        self,
        conflict_id: str,
        user_id: str,
        resolution: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[MemoryConflictModel]:
        async with get_async_db_context(db) as db:
            try:
                conflict = await db.get(MemoryConflict, conflict_id)
                if not conflict or conflict.user_id != user_id:
                    return None
                conflict.resolved = True
                conflict.resolution = resolution
                conflict.resolved_at = int(time.time())
                await db.commit()
                await db.refresh(conflict)
                return MemoryConflictModel.model_validate(conflict)
            except Exception:
                return None


MemoryConflicts = MemoryConflictsTable()
