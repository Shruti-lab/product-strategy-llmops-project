from langchain_tavily import TavilySearch

search = TavilySearch(
    max_results=5,
    topic="general",
    include_answer=True,
    include_raw_content=True,
)


async def tavily_search(query: str) -> str:
    """
    Performs deep web search and returns raw page content.
    """

    result = await search.ainvoke(query)

    return str(result)