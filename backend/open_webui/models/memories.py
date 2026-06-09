import time
import uuid
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from open_webui.internal.db import Base, get_async_db_context
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Float, JSON, String, Text

####################
# Memory DB Schema
# What was learned at cost should not need to be paid
# for again. Let the memory hold.
####################


class Memory(Base):
    __tablename__ = 'memory'

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String)
    content = Column(Text)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)

    # IMLM extensions — new columns with safe defaults so existing rows are unaffected
    node_type = Column(String, nullable=False, default='fact', server_default='fact')
    entity_name = Column(String, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0, server_default='1.0')
    source_chat_id = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default='1')
    meta = Column(JSON, nullable=True)


class MemoryModel(BaseModel):
    id: str
    user_id: str
    content: str
    updated_at: int
    created_at: int
    node_type: str = 'fact'
    entity_name: Optional[str] = None
    confidence: float = 1.0
    source_chat_id: Optional[str] = None
    is_active: bool = True
    meta: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class MemoriesTable:
    async def insert_new_memory(
        self,
        user_id: str,
        content: str,
        node_type: str = 'fact',
        entity_name: Optional[str] = None,
        confidence: float = 1.0,
        source_chat_id: Optional[str] = None,
        meta: Optional[dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[MemoryModel]:
        async with get_async_db_context(db) as db:
            id = str(uuid.uuid4())
            now = int(time.time())
            memory = MemoryModel(
                id=id,
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
            result = Memory(**memory.model_dump())
            db.add(result)
            await db.commit()
            await db.refresh(result)
            return MemoryModel.model_validate(result) if result else None

    async def get_memories_by_user_id_and_type(
        self,
        user_id: str,
        node_type: str,
        active_only: bool = True,
        db: Optional[AsyncSession] = None,
    ) -> list[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                q = select(Memory).filter_by(user_id=user_id, node_type=node_type)
                if active_only:
                    q = q.where(Memory.is_active == True)  # noqa: E712
                result = await db.execute(q)
                memories = result.scalars().all()
                return [MemoryModel.model_validate(m) for m in memories]
            except Exception:
                return []

    async def deactivate_memory_by_id(
        self,
        id: str,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[MemoryModel]:
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
        db: Optional[AsyncSession] = None,
    ) -> Optional[MemoryModel]:
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

    async def get_memories(self, db: Optional[AsyncSession] = None) -> list[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(select(Memory))
                memories = result.scalars().all()
                return [MemoryModel.model_validate(memory) for memory in memories]
            except Exception:
                return None

    async def get_memories_by_user_id(self, user_id: str, db: Optional[AsyncSession] = None) -> list[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(select(Memory).filter_by(user_id=user_id))
                memories = result.scalars().all()
                return [MemoryModel.model_validate(memory) for memory in memories]
            except Exception:
                return None

    async def get_memory_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[MemoryModel]:
        async with get_async_db_context(db) as db:
            try:
                memory = await db.get(Memory, id)
                return MemoryModel.model_validate(memory) if memory else None
            except Exception:
                return None

    async def delete_memory_by_id(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            try:
                await db.execute(delete(Memory).filter_by(id=id))
                await db.commit()

                return True

            except Exception:
                return False

    async def delete_memories_by_user_id(self, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            try:
                await db.execute(delete(Memory).filter_by(user_id=user_id))
                await db.commit()

                return True
            except Exception:
                return False

    async def delete_memory_by_id_and_user_id(self, id: str, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            try:
                memory = await db.get(Memory, id)
                if not memory or memory.user_id != user_id:
                    return None

                # Delete the memory
                await db.delete(memory)
                await db.commit()

                return True
            except Exception:
                return False


Memories = MemoriesTable()
