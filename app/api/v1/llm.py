from app.models.user import User
from app.schemas.graph import QueryRequest
from app.services.dependencies import db_dependency
from fastapi import APIRouter, HTTPException, Request, Depends

from app.core.langgraph.graph import LangGraphAgent
from app.schemas import  QueryRequest, WorkflowResponse
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.config import settings
from app.services.user_db import get_current_session

from app.services.dependencies import db_dependency

router = APIRouter(prefix="/strategy", tags=["Strategy"])

agent = LangGraphAgent()


@router.post("/query",response_model=WorkflowResponse,)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def generate_strategy(request: Request, body: QueryRequest, session:User = Depends(get_current_session)):
    """
    Execute the Product Strategy LangGraph workflow.
    """

    try:
        logger.info(
            "chat_request_received",
            session_id=session.session_id,
            message_length=len(body.query),
        )
        print(type(session.session_id))
        print(f'This is session id in llm.py {session.session_id}')

        result = await agent.run(
        query=body.query,
        session_id=session.session_id,
        user_id=str(session.session_id),
        email=session.email,
        )
        logger.info("chat_request_processed", session_id=session.id)

        return WorkflowResponse(
            success=True,
            **result,
        )

    except Exception as e:
        logger.exception("chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500,detail=str(e))