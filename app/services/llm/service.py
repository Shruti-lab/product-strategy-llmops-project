"""LLM service with retries, circular fallback, and optional structured output."""

import asyncio
import logging
from typing import TypeVar
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.registry import LLMRegistry

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Service for managing LLM calls with retries and circular fallback.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        reraise=True,
    )

    async def invoke(self,llm,messages,):
        return await llm.ainvoke(messages)

    async def invoke_with_timeout(self,llm,messages,):
        return await asyncio.wait_for(
            self.invoke(llm, messages),
            timeout=settings.LLM_TOTAL_TIMEOUT,
        )


llm_service = LLMService()