from app.core.langgraph.tools.tavily import tavily_search
from langchain_core.tools import tool

@tool
async def market_research(product: str) -> str:
    """
    Gather market insights for the given product.

    Use this tool whenever market research is required. 
    Returns web information about market insights of product like market size, trends,
    segments, growth.

    """

    query = f"""
    Research the market for {product}.

    Include:

    - market size
    - trends
    - customer segments
    - adoption
    - growth
    - opportunities
    """

    return await tavily_search(query)