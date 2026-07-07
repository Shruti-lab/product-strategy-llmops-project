"""This file contains the graph schema for the application."""
# schemas/research.py

from pydantic import BaseModel, Field

# Research agent output schema
class ResearchOutput(BaseModel):
    market_size: str
    competitors: list[str]
    customer_pain_points: list[str]
    trends: list[str]


# SWOT analysis
# Analysis agent output schema
class AnalysisOutput(BaseModel):
    opportunities: list[str]
    risks: list[str]
    strengths: list[str]
    weaknesses: list[str]


# Strategy agent output schema
class StrategicGoal(BaseModel):
    goal: str = Field(description="Strategic objective")
    rationale: str = Field(description="Why this goal matters")


class Initiative(BaseModel):
    title: str = Field(description="Initiative name")
    description: str = Field(description="Initiative details")
    expected_impact: str = Field(description="Expected business impact")
    priority: str = Field(description="High, Medium or Low")


class StrategyOutput(BaseModel):
    executive_summary: str

    strategic_goals: list[StrategicGoal]

    initiatives: list[Initiative]

    success_metrics: list[str]

    risks: list[str]



# Critique agent output schema
class CritiqueOutput(BaseModel):
    overall_score: int = Field(
        ge=1,
        le=10,
        description="Overall strategy score"
    )

    strengths: list[str]

    weaknesses: list[str]

    missing_considerations: list[str]

    recommendations: list[str]

    final_verdict: str


class QueryRequest(BaseModel):
    query: str


class WorkflowResponse(BaseModel):
    success: bool
    session_id: int

    research: ResearchOutput
    analysis: AnalysisOutput
    strategy: StrategyOutput
    critique: CritiqueOutput