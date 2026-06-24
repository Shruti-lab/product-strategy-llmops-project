"""LLM model registry with pre-initialized instances."""

from typing import List,Any, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain.chat_models import init_chat_model
from pydantic import SecretStr

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger

_TOKEN_LIMIT: Dict[str, Any] = {"max_completion_tokens": settings.MAX_TOKENS}
_API_KEY = SecretStr(settings.GROQ_API_KEY)



class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    MODELS = {
        "research": init_chat_model("groq:llama-3.3-70b-versatile",temperature=0),

        "analyst": init_chat_model("groq:llama-3.3-70b-versatile",temperature=0),

        "planner": init_chat_model("groq:llama-3.3-70b-versatile",temperature=0.2),

        "critic": init_chat_model("groq:llama-3.3-70b-versatile",temperature=0),
    }

    @classmethod
    def get_model(cls,agent_name):
        try:
            return cls.MODELS[agent_name]
        except KeyError:
            raise ValueError(
                f"Unknown agent '{agent_name}'. "
                f"Available: {list(cls.MODELS.keys())}"
            )