"""This file contains the LangGraph Agent/workflow and interactions with the LLM."""

import asyncio
from typing import AsyncGenerator, Optional, cast, TypedDict
from urllib.parse import quote_plus

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ToolMessage,
    convert_to_openai_messages,
)
from langchain.agents import create_agent

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)

from langgraph.types import (
    RetryPolicy,
    StateSnapshot,
)
from psycopg import (
    AsyncConnection,
    sql,
)
from psycopg.rows import (
    DictRow,
    dict_row,
)
from psycopg_pool import AsyncConnectionPool

from app.core.config import (
    Environment,
    settings,
)
from app.core.langgraph.tools import tools

from app.core.logging import logger
from app.core.metrics import llm_inference_duration_seconds
from app.core.observability import langfuse_callback_handler
from app.core.prompts import load_system_prompt
from app.services.llm.registry import LLMRegistry

from app.schemas import ResearchOutput, AnalysisOutput, StrategyOutput, CritiqueOutput


from app.services.llm import llm_service
from app.services.memory import memory_service
from app.utils import (
    dump_messages,
    extract_text_content,
    prepare_messages,
    process_llm_response,
)

PostgresConnPool = AsyncConnectionPool[AsyncConnection[DictRow]]


class GraphState(TypedDict):
    """State definition for the LangGraph Agent/Workflow."""
    user_query: str

    research: ResearchOutput | None
    analysis: AnalysisOutput | None
    strategy: StrategyOutput | None
    critique: CritiqueOutput | None

    final_output: dict | None



class LangGraphAgent:
    """Manages the LangGraph Agent/workflow and interactions with the LLM.

    This class handles the creation and management of the LangGraph workflow,
    including LLM interactions, database connections, and response processing.
    """

    def __init__(self):
        """Initialize the LangGraph Agent with necessary components."""
        # Use the LLM service with tools bound
        self.llm_service = llm_service
        self._connection_pool: Optional[PostgresConnPool] = None
        self._graph: Optional[CompiledStateGraph] = None
        logger.info(
            "langgraph_agent_initialized",
            model=settings.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    
    async def _get_connection_pool(self) -> Optional[PostgresConnPool]:
        """Get a PostgreSQL connection pool using environment-specific settings.

        Returns:
            AsyncConnectionPool or None when the pool fails to initialise in
            production (the app keeps running in a degraded mode).
        """
        if self._connection_pool is None:
            try:
                # Configure pool size based on environment
                max_size = settings.POSTGRES_POOL_SIZE

                connection_url = (
                    "postgresql://"
                    f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
                    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
                )

                self._connection_pool = AsyncConnectionPool(
                    connection_url,
                    open=False,
                    max_size=max_size,
                    kwargs={
                        "autocommit": True,
                        "connect_timeout": 5,
                        "prepare_threshold": None,
                        "row_factory": dict_row,
                    },
                )

                await self._connection_pool.open()
                logger.info("connection_pool_created", max_size=max_size, environment=settings.ENVIRONMENT.value)
            except Exception as e:
                logger.error("connection_pool_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # In production, we might want to degrade gracefully
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_connection_pool", environment=settings.ENVIRONMENT.value)
                    return None
                raise e
        return self._connection_pool

 


    async def research_node(self,state: GraphState) -> dict:

        research_agent = create_agent(
            model=LLMRegistry.get_model("research_agent"),
            tools=[
                tavily_search,
                news_search,
                competitor_search,
                market_research,
            ],
            response_format=ResearchOutput,
        )

        # llm = LLMRegistry.get_model("research_agent")

        # structured_llm = llm.with_structured_output(
        #     ResearchOutput
        # )

        # result = await self.llm_service.invoke_with_timeout(
        #     structured_llm,
        #     f"""
        #     Conduct market research.

        #     Query:
        #     {state["user_query"]}
        #     """,
        # )

        # return {
        #     "research": result
        # }

        result = await research_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": state["user_query"],
                    }
                ]
            }
        )

        return {
            "research": result["structured_response"]
        }




    async def analysis_node(self,state: GraphState) -> dict:

        llm = LLMRegistry.get_model("analyst_agent")

        structured_llm = llm.with_structured_output(
            AnalysisOutput
        )

        result = await self.llm_service.invoke_with_timeout(
            structured_llm,
            f"""
            Analyze the research.

            Research:
            {state["research"].model_dump_json()}
            """,
        )

        return {
            "analysis": result
        }

    
    async def strategy_node(self,state: GraphState) -> dict:

        llm = LLMRegistry.get_model("strategy_agent")

        structured_llm = llm.with_structured_output(
            StrategyOutput
        )

        result = await self.llm_service.invoke_with_timeout(
            structured_llm,
            f"""
            Create product strategy.

            Analysis:
            {state["analysis"].model_dump_json()}
            """,
        )

        return {
            "strategy": result
        }
    

    async def critique_node(self, state: GraphState) -> dict:

        llm = LLMRegistry.get_model("critic_agent")

        structured_llm = llm.with_structured_output(
            CritiqueOutput
        )

        result = await self.llm_service.invoke_with_timeout(
            structured_llm,
            f"""
            Review the strategy.

            Strategy:
            {state["strategy"].model_dump_json()}
            """,
        )

        return {
            "critique": result,
            "final_output": {
                "research": state["research"],
                "analysis": state["analysis"],
                "strategy": state["strategy"],
                "critique": result,
            },
        }


    
    async def create_graph(self)-> Optional[CompiledStateGraph]:
        """Create and configure the LangGraph workflow.

        Returns:
            Optional[CompiledStateGraph]: The configured LangGraph instance or None if init fails
        """

        if self._graph is None:
            try:

                graph = StateGraph(GraphState)

                graph.add_node("research",self.research_node)
                graph.add_node("analysis",self.analysis_node)
                graph.add_node("strategy",self.strategy_node)
                graph.add_node("critique",self.critique_node)

                graph.add_edge(START,"research")
                graph.add_edge("research","analysis")
                graph.add_edge("analysis","strategy")
                graph.add_edge("strategy","critique")
                graph.add_edge("critique",END)

                # Get connection pool (may be None in production if DB unavailable)
                connection_pool = await self._get_connection_pool()
                if connection_pool:
                    checkpointer = AsyncPostgresSaver(connection_pool)
                    await checkpointer.setup()
                else:
                    # In production, proceed without checkpointer if needed
                    checkpointer = None
                    if settings.ENVIRONMENT != Environment.PRODUCTION:
                        raise Exception("Connection pool initialization failed")

                # Compile graph
                self._graph = graph.compile(
                        checkpointer=checkpointer, name=f"{settings.PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})"
                    )

                logger.info(
                    "graph_created",
                    graph_name=f"{settings.PROJECT_NAME} Agent",
                    environment=settings.ENVIRONMENT.value,
                    has_checkpointer=checkpointer is not None,
                )
            except Exception as e:
                logger.error("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # In production, we don't want to crash the app
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_graph")
                    return None
                raise e

        return self._graph


    
    
    async def _get_graph(self) -> CompiledStateGraph:
        """Return the compiled graph, creating it on first access.

        Raises:
            RuntimeError: When ``create_graph()`` swallowed an init failure
                (production-only path) and returned ``None``. Callers can
                rely on the return being non-``None``.
        """
        if self._graph is None:
            self._graph = await self.create_graph()
        if self._graph is None:
            raise RuntimeError("graph initialization failed")
        return self._graph


    
    async def run(self,query: str,session_id: str, user_id: Optional[str] = None, email: Optional[str] = None):

        graph = await self._get_graph()

        # config = {
        #     "configurable": {
        #         "thread_id": thread_id
        #     },
        #     "callbacks": [
        #         langfuse_callback_handler
        #     ]
        # }

        callbacks: list[BaseCallbackHandler] = [langfuse_callback_handler] if settings.LANGFUSE_TRACING_ENABLED else []
        config: RunnableConfig = {
            "configurable": {"thread_id": session_id},
            "callbacks": callbacks,
            "metadata": {
                "user_id": user_id,
                "email":email,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }

        result = await graph.ainvoke(
            {
                "user_query": query
            },
            config=config,
        )

        # return result["final_output"]
        return {
    "research": result["research"],
    "analysis": result["analysis"],
    "strategy": result["strategy"],
    "critique": result["critique"],
}







