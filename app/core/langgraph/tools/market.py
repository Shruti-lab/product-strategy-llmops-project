from app.core.langgraph.tools.tavily import tavily_search


async def market_research(product: str) -> str:
    """
    Gather market insights.
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