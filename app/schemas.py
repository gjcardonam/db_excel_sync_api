"""Pydantic response models — these define the API's response contract and
populate the OpenAPI docs at /docs."""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class OperationResponse(BaseModel):
    """Standard envelope for successful write operations."""

    status: str = Field(default="success", examples=["success"])
    message: str = Field(examples=["dbesp: replaced 12 rows by key 'well'."])


class ErrorResponse(BaseModel):
    detail: str = Field(examples=["File must be .xlsx"])
