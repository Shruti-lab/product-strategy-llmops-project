from typing import Any
import json


from app.models import User, UserSession
from app.schemas.graph import QueryRequest
from app.services.dependencies import db_dependency
from fastapi import APIRouter, HTTPException, Request, Depends

from app.core.langgraph.graph import LangGraphAgent
from app.schemas import  QueryRequest, WorkflowResponse
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.config import settings
from app.services.user_db import get_current_user

from app.services.dependencies import db_dependency

router: Any = APIRouter()

agent  = LangGraphAgent()


@router.post("/query",response_model=WorkflowResponse,)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def generate_strategy(request: Request, body: QueryRequest, current_user:User = Depends(get_current_user), db: db_dependency):
    """
    Execute the Product Strategy LangGraph workflow.
    """

    try:
        # logger.info(f"This is entire session: {session}")
        # logger.info(
        #     "chat_request_received",
        #     session_id=session.session_id,
        #     message_length=len(body.query),
        # )
        user_session = UserSession(
            user_id=current_user.id,
            user_message=body.query,
        )
        db.add(user_session)
        db.commit()
        db.refresh(user_session)

        logger.info(
            "chat_request_received",
            message_length=len(body.query),
        )

        # print(type(session.session_id))
        # print(f'This is session id in llm.py {session.session_id}')

        result = await agent.run(
        query=body.query,
        session_id=str(user_session.id),
        user_id=str(current_user.id),
        email=current_user.email,
        )
        logger.info("chat_request_processed", session_id=user_session.id)

        user_session.agent_message = json.dumps(result)

        db.commit()

        return WorkflowResponse(
            success=True,
            session_id=user_session.id,
            **result,
        )

    except Exception as e:
        logger.exception("chat_request_failed", error=str(e))
        raise HTTPException(status_code=500,detail=str(e))



@router.get("/{session_id}")
def get_session(session_id: int,current_user: User = Depends(get_current_user),db: db_dependency = Depends()):
    chat = (
    db.query(UserSession).filter(
          UserSession.id == session_id,
          UserSession.user_id == current_user.id,
      )
      .first()
    )
    if chat is None:
        HTTPException(404, "Session not found")
    
    return {
    "id": chat.id,
    "user_message": chat.user_message,
    "agent_message": json.loads(chat.agent_message),
    "created_at": chat.created_at,
    }