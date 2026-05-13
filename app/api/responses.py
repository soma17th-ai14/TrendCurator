"""API 응답 공통 모델."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str


def error_response(code: str, message: str) -> ErrorResponse:
    return ErrorResponse(code=code, message=message)
