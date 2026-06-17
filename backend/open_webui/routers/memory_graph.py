from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.memories import Memories, MemoryModel
from open_webui.models.memory_conflict import MemoryConflictModel, MemoryConflicts
from open_webui.models.memory_edge import MemoryEdgeModel, MemoryEdges
from open_webui.retrieval.vector.async_client import ASYNC_VECTOR_DB_CLIENT
from open_webui.utils.access_control import has_permission
from open_webui.utils.auth import get_verified_user
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

router = APIRouter()


def _require_memories(request: Request) -> None:
    if not request.app.state.config.ENABLE_MEMORIES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


async def _require_permission(user, request: Request) -> None:
    if not await has_permission(user.id, 'features.memories', request.app.state.config.USER_PERMISSIONS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


async def _require_owned_nodes(
    node_ids: tuple[str, ...],
    user_id: str,
    db: AsyncSession,
) -> None:
    for node_id in node_ids:
        node = await Memories.get_memory_by_id(node_id, db=db)
        if not node or node.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Memory node {node_id} not found',
            )


class CreateNodeForm(BaseModel):
    content: str = Field(min_length=1)
    node_type: str = Field(default='fact', min_length=1)
    entity_name: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_chat_id: str | None = None
    meta: dict | None = None


@router.get('/nodes', response_model=list[MemoryModel])
async def list_nodes(
    request: Request,
    node_type: str | None = None,
    active_only: bool = True,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    if node_type:
        return await Memories.get_memories_by_user_id_and_type(
            user.id,
            node_type,
            active_only=active_only,
            db=db,
        )

    memories = await Memories.get_memories_by_user_id(user.id, db=db) or []
    return [memory for memory in memories if memory.is_active] if active_only else memories


@router.get('/nodes/{node_id}', response_model=MemoryModel)
async def get_node(
    node_id: str,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    memory = await Memories.get_memory_by_id(node_id, db=db)
    if not memory or memory.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return memory


@router.post('/nodes', response_model=MemoryModel)
async def create_node(
    form_data: CreateNodeForm,
    request: Request,
    user=Depends(get_verified_user),
):
    _require_memories(request)
    await _require_permission(user, request)

    memory = await Memories.insert_new_memory(
        user_id=user.id,
        content=form_data.content,
        node_type=form_data.node_type,
        entity_name=form_data.entity_name,
        confidence=form_data.confidence,
        source_chat_id=form_data.source_chat_id,
        meta=form_data.meta,
    )
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to create memory node',
        )

    try:
        vector = await request.app.state.EMBEDDING_FUNCTION(memory.content, user=user)
        await ASYNC_VECTOR_DB_CLIENT.upsert(
            collection_name=f'user-memory-{user.id}',
            items=[
                {
                    'id': memory.id,
                    'text': memory.content,
                    'vector': vector,
                    'metadata': {
                        'created_at': memory.created_at,
                        'node_type': memory.node_type,
                        'confidence': memory.confidence,
                    },
                }
            ],
        )
    except Exception:
        log.exception('Failed to embed IMLM node %s', memory.id)

    return memory


@router.patch('/nodes/{node_id}/deactivate', response_model=MemoryModel)
async def deactivate_node(
    node_id: str,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    memory = await Memories.deactivate_memory_by_id(node_id, user.id, db=db)
    if not memory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    try:
        await ASYNC_VECTOR_DB_CLIENT.delete(
            collection_name=f'user-memory-{user.id}',
            ids=[node_id],
        )
    except Exception:
        log.exception('Failed to remove deactivated IMLM node %s from vector storage', node_id)

    return memory


class CreateEdgeForm(BaseModel):
    source_node_id: str
    target_node_id: str
    relation: str = Field(min_length=1)
    meta: dict | None = None


@router.get('/edges', response_model=list[MemoryEdgeModel])
async def list_edges(
    request: Request,
    node_id: str | None = None,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    if node_id:
        await _require_owned_nodes((node_id,), user.id, db)
        return await MemoryEdges.get_edges_for_node(node_id, user.id, db=db)
    return await MemoryEdges.get_edges_by_user_id(user.id, db=db)


@router.post('/edges', response_model=MemoryEdgeModel)
async def create_edge(
    form_data: CreateEdgeForm,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)
    await _require_owned_nodes(
        (form_data.source_node_id, form_data.target_node_id),
        user.id,
        db,
    )

    edge = await MemoryEdges.insert_edge(
        user_id=user.id,
        source_node_id=form_data.source_node_id,
        target_node_id=form_data.target_node_id,
        relation=form_data.relation,
        meta=form_data.meta,
        db=db,
    )
    if not edge:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to create memory edge',
        )
    return edge


@router.delete('/edges/{edge_id}', response_model=bool)
async def delete_edge(
    edge_id: str,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    deleted = await MemoryEdges.delete_edge_by_id(edge_id, user.id, db=db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return True


class CreateConflictForm(BaseModel):
    node_a_id: str
    node_b_id: str
    conflict_type: Literal['contradiction', 'supersede', 'duplicate']


class ResolveConflictForm(BaseModel):
    resolution: Literal['keep_a', 'keep_b', 'keep_both', 'merge']


@router.get('/conflicts', response_model=list[MemoryConflictModel])
async def list_conflicts(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)
    return await MemoryConflicts.get_unresolved_conflicts(user.id, db=db)


@router.post('/conflicts', response_model=MemoryConflictModel)
async def create_conflict(
    form_data: CreateConflictForm,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)
    await _require_owned_nodes(
        (form_data.node_a_id, form_data.node_b_id),
        user.id,
        db,
    )

    conflict = await MemoryConflicts.insert_conflict(
        user_id=user.id,
        node_a_id=form_data.node_a_id,
        node_b_id=form_data.node_b_id,
        conflict_type=form_data.conflict_type,
        db=db,
    )
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to record memory conflict',
        )
    return conflict


@router.post('/conflicts/{conflict_id}/resolve', response_model=MemoryConflictModel)
async def resolve_conflict(
    conflict_id: str,
    form_data: ResolveConflictForm,
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    conflict = await MemoryConflicts.resolve_conflict(
        conflict_id,
        user.id,
        form_data.resolution,
        db=db,
    )
    if not conflict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return conflict


@router.get('/health')
async def memory_health(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    _require_memories(request)
    await _require_permission(user, request)

    memories = await Memories.get_memories_by_user_id(user.id, db=db) or []
    active = [memory for memory in memories if memory.is_active]
    type_counts: dict[str, int] = {}
    for memory in active:
        type_counts[memory.node_type] = type_counts.get(memory.node_type, 0) + 1

    edges = await MemoryEdges.get_edges_by_user_id(user.id, db=db)
    conflicts = await MemoryConflicts.get_unresolved_conflicts(user.id, db=db)

    return {
        'total_nodes': len(memories),
        'active_nodes': len(active),
        'inactive_nodes': len(memories) - len(active),
        'nodes_by_type': type_counts,
        'total_edges': len(edges),
        'unresolved_conflicts': len(conflicts),
    }
