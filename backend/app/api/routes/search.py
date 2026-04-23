"""Search routes for web result retrieval and citations."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.search import SearchWebOut
from app.services.governance import record_usage_event
from app.services.web_search import search_web

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/web", response_model=SearchWebOut)
def web_search(
    q: str = Query(min_length=2, max_length=400),
    limit: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = q.strip()
    results = search_web(query=query, limit=limit)

    record_usage_event(
        db,
        user_id=current_user.id,
        metric="web_search_queries",
        quantity=1,
        source="search",
        metadata={
            "query": query[:160],
            "results": len(results),
        },
    )

    return SearchWebOut(
        query=query,
        provider="duckduckgo",
        results=results,
    )
