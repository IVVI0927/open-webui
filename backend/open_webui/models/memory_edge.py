from __future__ import annotations

import time
import uuid

from open_webui.internal.db import Base, get_async_db_context
from open_webui.models.memories import Memory
from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, BigInteger, Column, ForeignKey, String, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryEdge(Base):
    __tablename__ = 'memory_edge'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    source_node_id = Column(String, ForeignKey(Memory.id, ondelete='CASCADE'), nullable=False)
    target_node_id = Column(String, ForeignKey(Memory.id, ondelete='CASCADE'), nullable=False)
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
    meta: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryEdgesTable:
    async def insert_edge(
        self,
        user_id: str,
        source_node_id: str,
        target_node_id: str,
        relation: str,
        meta: dict | None = None,
        db: AsyncSession | None = None,
    ) -> MemoryEdgeModel | None:
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
        db: AsyncSession | None = None,
    ) -> list[MemoryEdgeModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(MemoryEdge).filter_by(user_id=user_id))
            return [MemoryEdgeModel.model_validate(edge) for edge in result.scalars().all()]

    async def get_edges_for_node(
        self,
        node_id: str,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> list[MemoryEdgeModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(MemoryEdge).where(
                    MemoryEdge.user_id == user_id,
                    or_(
                        MemoryEdge.source_node_id == node_id,
                        MemoryEdge.target_node_id == node_id,
                    ),
                )
            )
            return [MemoryEdgeModel.model_validate(edge) for edge in result.scalars().all()]

    async def delete_edge_by_id(
        self,
        edge_id: str,
        user_id: str,
        db: AsyncSession | None = None,
    ) -> bool:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                delete(MemoryEdge).where(
                    MemoryEdge.id == edge_id,
                    MemoryEdge.user_id == user_id,
                )
            )
            await db.commit()
            return bool(result.rowcount)


MemoryEdges = MemoryEdgesTable()
