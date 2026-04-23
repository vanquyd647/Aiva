"""Schema models for web search and citation payloads."""

from pydantic import BaseModel, Field


class SearchResultOut(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2000)
    snippet: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=255)


class SearchWebOut(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    provider: str = Field(default="duckduckgo")
    results: list[SearchResultOut]
