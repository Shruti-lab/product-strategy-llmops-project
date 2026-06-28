from app.core.langgraph.tools.tavily import tavily_search


async def competitor_research(product: str) -> str:
    """
    Gather competitor information.
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