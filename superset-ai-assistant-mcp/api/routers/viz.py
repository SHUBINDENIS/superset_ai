"""
Thin FastAPI router for US13-US15 preview / recommend / share flows.

These endpoints intentionally wrap the existing ``US13To15VizService``
without changing its business logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_user, get_viz_service
from api.schemas import (
    DatabaseListResponse,
    DatabaseResponse,
    DatasetListResponse,
    DatasetMetadataResponse,
    DatasetResponse,
    PreviewRequest,
    PreviewResponse,
    RecommendVizRequest,
    RecommendVizResponse,
    ShareWidgetRequest,
    ShareWidgetResponse,
)

router = APIRouter(prefix="/api/viz", tags=["viz"])


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )


@router.get("/databases", response_model=DatabaseListResponse)
def list_databases(
    _current_user: Dict[str, Any] = Depends(get_current_user),
    svc=Depends(get_viz_service),
) -> DatabaseListResponse:
    try:
        databases = svc.list_databases()
    except Exception as exc:
        raise _service_error(exc) from exc

    return DatabaseListResponse(
        databases=[DatabaseResponse(**item) for item in databases],
    )


@router.get("/datasets", response_model=DatasetListResponse)
def list_datasets(
    limit: int = Query(default=300, ge=1, le=1000),
    _current_user: Dict[str, Any] = Depends(get_current_user),
    svc=Depends(get_viz_service),
) -> DatasetListResponse:
    try:
        datasets = svc.list_datasets(limit=limit)
    except Exception as exc:
        raise _service_error(exc) from exc

    return DatasetListResponse(
        datasets=[DatasetResponse(**item) for item in datasets],
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetMetadataResponse)
def get_dataset_metadata(
    dataset_id: int,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    svc=Depends(get_viz_service),
) -> DatasetMetadataResponse:
    try:
        metadata = svc.get_dataset_metadata(dataset_id=dataset_id)
    except Exception as exc:
        raise _service_error(exc) from exc
    return DatasetMetadataResponse(**metadata)


@router.post("/preview", response_model=PreviewResponse)
def preview_sql(
    body: PreviewRequest,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    svc=Depends(get_viz_service),
) -> PreviewResponse:
    try:
        preview = svc.preview_sql(
            database_id=body.database_id,
            sql=body.sql,
            schema=body.schema_name,
            preview_limit=body.preview_limit,
        )
    except Exception as exc:
        raise _service_error(exc) from exc

    preview_payload = dict(preview)
    if body.dataset_id is not None:
        preview_payload["dataset_id"] = body.dataset_id
    return PreviewResponse(**preview_payload)


@router.post("/recommend", response_model=RecommendVizResponse)
def recommend_viz(
    body: RecommendVizRequest,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    svc=Depends(get_viz_service),
) -> RecommendVizResponse:
    try:
        recommendation = svc.recommend_viz_types(
            rows=body.rows,
            columns=[column.model_dump() for column in body.columns],
            metric_column=body.metric_column,
            dimension_column=body.dimension_column,
            time_column=body.time_column,
        )
    except Exception as exc:
        raise _service_error(exc) from exc

    return RecommendVizResponse(**recommendation)


@router.post("/share/widget", response_model=ShareWidgetResponse)
def create_widget_with_share(
    body: ShareWidgetRequest,
    _current_user: Dict[str, Any] = Depends(get_current_user),
    svc=Depends(get_viz_service),
) -> ShareWidgetResponse:
    try:
        result = svc.create_dashboard_widget_with_share(
            dataset_id=body.dataset_id,
            dashboard_title=body.dashboard_title,
            slice_name=body.slice_name,
            viz_type=body.viz_type,
            metric_column=body.metric_column,
            dimension_column=body.dimension_column,
            time_column=body.time_column,
            row_limit=body.row_limit,
            description=body.description,
        )
    except Exception as exc:
        raise _service_error(exc) from exc

    return ShareWidgetResponse(**result)
