from app.core.langgraph.tools.tavily import tavily_search
from langchain_core.tools import tool

@tool
async def competitor_research(product: str) -> str:
    """
    Research competing products in the market.

    Use this tool whenever competitor analysis is required.
    Returns recent web information about competitors, pricing,
    positioning, strengths, weaknesses, and product launches.
    """

    query = f"""
    Identify major competitors for {product}.

    Include:
    - competitors
    - pricing
    - strengths
    - weaknesses
    - positioning
    - recent launches
    """

    return await tavily_search(query)