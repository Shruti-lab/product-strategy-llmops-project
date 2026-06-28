from app.schemas.graph import QueryRequest
from app.services.dependencies import db_dependency
from fastapi import APIRouter, HTTPException

from app.core.langgraph.graph import LangGraphAgent
from app.schemas import  QueryRequest, WorkflowResponse

from app.services.dependencies import db_dependency

router = APIRouter(prefix="/strategy", tags=["Strategy"])

graph = LangGraphAgent()


@router.post("/query",
    response_model=WorkflowResponse,
)
async def generate_strategy(request: QueryRequest, session: db_dependency):
    """
    Execute the Product Strategy LangGraph workflow.
    """

    try:
        result = await agent.run(
        query=request.query,
        session_id=session.id,
        user_id=str(session.user_id),
        email=session.email,
    )

        return WorkflowResponse(
            success=True,
            **result,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )