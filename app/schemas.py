"""Pydantic response models — these define the API's response contract and
populate the OpenAPI docs at /docs."""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class OperationResponse(BaseModel):
    """Standard envelope for successful write operations.

    ``warnings`` carries non-blocking data problems the user should still see
    (rendered ORANGE in the UI), e.g. duplicate wells or ignored columns.
    """

    status: str = Field(default="success", examples=["success"])
    message: str = Field(examples=["dbesp: replaced 12 rows by key 'well'."])
    warnings: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    # `detail` is a single message for simple errors, or a list of messages when
    # several blocking validations fail at once.
    detail: str | list[str] = Field(examples=["File must be a .xlsx file."])
