"""Long-term memory storage for per-user context recall."""

from __future__ import annotations

import time
import uuid

from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, BigInteger, Boolean, Column, Float, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession


class Memory(Base):  # user memory store
    """Stores user-created memory entries linked to a vector collection."""

    __tablename__ = 'memory'

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)
    content = Column(Text)  # free-form text learned from conversation
    updated_at = Column(BigInteger)  # epoch seconds
    created_at = Column(BigInteger)  # epoch seconds
    node_type = Column(String, nullable=False, default='fact', server_default='fact')
    entity_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0, server_default='1.0')
    source_chat_id = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default='1')
    meta = Column(JSON, nullable=True)


class MemoryModel(BaseModel):
    """Pydantic mirror of the Memory table row."""

    id: str
    user_id: str
    content: str
    updated_at: int  # timestamp in epoch
    created_at: int  # timestamp in epoch
    node_type: str = 'fact'
    entity_name: str | None = None
    confidence: float = 1.0
    source_chat_id: str | None = None
    is_active: bool = True
    meta: dict | None = None
    model_config = ConfigDict(from_attributes=True)  # allows ORM mapping


class MemoriesTable:
    async def insert_new_memory(
        self,
        user_id: str,
        content: str,
        node_type: str = 'fact',
        entity_name: str | None = None,
        confidence: float = 1.0,
        source_chat_id: str | None = None,
        meta: dict | None = None,
        db: AsyncSession | None = None,
    ) -> MemoryModel | None:
        """Persist a new memory entry and return the created model."""
        async with get_async_db_context(db) as db:
            now = int(time.time())
            record = Memory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                content=content,
                created_at=now,
                updated_at=now,
                node_type=node_type,
                entity_name=entity_name,
                confidence=confidence,
                source_chat_id=source_chat_id,
                is_active=True,
                meta=meta,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return MemoryModel.model_validate(record) if record else None

    async def get_memories_by_user_id_and_type(
        self,
        user_id: str,
        node_type: str,
        active_only: bool = True,
        db: AsyncSession | None = None,
    ) -> list[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                query = select(Memory).filter_by(user_id=user_id, node_type=node_type)
                if active_only:
                    query = query.where(Memory.is_active.is_(True))
                result = await db.execute(query)
                return [MemoryModel.model_validate(memory) for memory in result.scalars().all()]
            except Exception:
                return []

    async def deactivate_memory_by_id(
        self,
        id: str,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> MemoryModel | None:
        async with get_async_db_context(db) as db:
            try:
                memory = await db.get(Memory, id)
                if not memory or memory.user_id != user_id:
                    return None

                memory.is_active = False
                memory.updated_at = int(time.time())
                await db.commit()
                await db.refresh(memory)
                return MemoryModel.model_validate(memory)
            except Exception:
                return None

    async def update_memory_by_id_and_user_id(
        self,
        id: str,
        user_id: str,
        content: str,
        db: AsyncSession | None = None,
    ) -> MemoryModel | None:
        async with get_async_db_context(db) as db:
            try:
                memory = await db.get(Memory, id)
                if not memory or memory.user_id != user_id:
                    return None

                memory.content = content
                memory.updated_at = int(time.time())

                await db.commit()
                await db.refresh(memory)
                return MemoryModel.model_validate(memory)
            except Exception:
                return None

    async def get_memories(self, db: AsyncSession | None = None) -> list[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(select(Memory))
                memories = result.scalars().all()
                return [MemoryModel.model_validate(memory) for memory in memories]
            except Exception:
                return None

    async def get_memories_by_user_id(self, user_id: str, db: AsyncSession | None = None) -> list[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(select(Memory).filter_by(user_id=user_id))
                memories = result.scalars().all()
                return [MemoryModel.model_validate(memory) for memory in memories]
            except Exception:
                return None

    async def get_memory_by_id(self, id: str, db: AsyncSession | None = None) -> MemoryModel | None:
        async with get_async_db_context(db) as db:
            try:
                memory = await db.get(Memory, id)
                return MemoryModel.model_validate(memory) if memory else None
            except Exception:
                return None

    async def delete_memory_by_id(self, id: str, db: AsyncSession | None = None) -> bool:
        async with get_async_db_context(db) as db:
            try:
                await db.execute(delete(Memory).filter_by(id=id))
                await db.commit()

                return True

            except Exception:
                return False

    async def delete_memories_by_user_id(self, user_id: str, db: AsyncSession | None = None) -> bool:
        async with get_async_db_context(db) as db:
            try:
                await db.execute(delete(Memory).filter_by(user_id=user_id))
                await db.commit()

                return True
            except Exception:
                return False

    async def delete_memory_by_id_and_user_id(self, id: str, user_id: str, db: AsyncSession | None = None) -> bool:
        async with get_async_db_context(db) as db:
            try:
                memory = await db.get(Memory, id)
                if not memory or memory.user_id != user_id:
                    return False

                await db.delete(memory)
                await db.commit()
                return True
            except Exception:
                return False


Memories = MemoriesTable()  # user memory registry
