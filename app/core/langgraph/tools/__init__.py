"""LangGraph tools for enhanced language model capabilities.

This package contains custom tools that can be used with LangGraph to extend
the capabilities of language models. Currently includes tools for web search
and other external integrations.
"""

from langchain_core.tools.base import BaseTool

from .market import market_research
from .competitor import competitor_research

research_tools: list[BaseTool] = [market_research, competitor_research]

"""
from langchain_core.tools.base import BaseTool

from .market import market_research
from .competitor import competitor_research
from .pricing import pricing_research
from .customer import customer_research

research_tools: list[BaseTool] = [
    market_research,
    competitor_research,
]

strategy_tools: list[BaseTool] = [
    pricing_research,
    customer_research,
]

all_tools: list[BaseTool] = [
    *research_tools,
    *strategy_tools,
]
"""