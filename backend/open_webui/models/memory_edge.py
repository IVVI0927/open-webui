import time
import uuid
from typing import Optional

from sqlalchemy import BigInteger, Column, ForeignKey, JSON, String, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from open_webui.internal.db import Base, get_async_db_context


class MemoryEdge(Base):
    __tablename__ = 'memory_edge'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    source_node_id = Column(String, ForeignKey('memory.id', ondelete='CASCADE'), nullable=False)
    target_node_id = Column(String, ForeignKey('memory.id', ondelete='CASCADE'), nullable=False)
    relation = Column(String, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    meta = Column(JSON, nullable=True)


class MemoryEdgeModel(BaseModel):
    id: str
    user_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    created_at: int
    meta: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class MemoryEdgesTable:
    async def insert_edge(
        self,
        user_id: str,
        source_node_id: str,
        target_node_id: str,
        relation: str,
        meta: Optional[dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[MemoryEdgeModel]:
        async with get_async_db_context(db) as db:
            edge = MemoryEdge(
                id=str(uuid.uuid4()),
                user_id=user_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                relation=relation,
                created_at=int(time.time()),
                meta=meta,
            )
            db.add(edge)
            await db.commit()
            await db.refresh(edge)
            return MemoryEdgeModel.model_validate(edge)

    async def get_edges_by_user_id(
        self,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> list[MemoryEdgeModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(select(MemoryEdge).filter_by(user_id=user_id))
                return [MemoryEdgeModel.model_validate(e) for e in result.scalars().all()]
            except Exception:
                return []

    async def get_edges_for_node(
        self,
        node_id: str,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> list[MemoryEdgeModel]:
        async with get_async_db_context(db) as db:
            try:
                result = await db.execute(
                    select(MemoryEdge).where(
                        MemoryEdge.user_id == user_id,
                        (MemoryEdge.source_node_id == node_id) | (MemoryEdge.target_node_id == node_id),
                    )
                )
                return [MemoryEdgeModel.model_validate(e) for e in result.scalars().all()]
            except Exception:
                return []

    async def delete_edges_for_node(
        self,
        node_id: str,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        async with get_async_db_context(db) as db:
            try:
                await db.execute(
                    delete(MemoryEdge).where(
                        MemoryEdge.user_id == user_id,
                        (MemoryEdge.source_node_id == node_id) | (MemoryEdge.target_node_id == node_id),
                    )
                )
                await db.commit()
                return True
            except Exception:
                return False


MemoryEdges = MemoryEdgesTable()
