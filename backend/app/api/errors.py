"""
IMANI Business OS

Module:
    API Error Handling

Author:
    OpenAI + Your Team

Purpose:
    Centralised exception handlers for consistent
    error responses across the entire API.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("imani.errors")
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def register_error_handlers(app: FastAPI) -> None:
    """Register all custom error handlers on the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic/FastAPI validation errors."""
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in error.get("loc", [])),
                    "message": error.get("msg", "Invalid value"),
                    "type": error.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "Validation failed",
                "details": errors,
            },
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors (internal)."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "Validation failed",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        """Handle database integrity violations (duplicates, FK errors)."""
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "error": "Resource conflict",
                "detail": str(exc.orig) if exc.orig else "Database integrity error",
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        """Handle unexpected database errors."""
        logger.exception("Unhandled database error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Database error",
                "detail": "An unexpected database error occurred",
            },
        )

    @app.exception_handler(JWTError)
    async def jwt_error_handler(
        request: Request, exc: JWTError
    ) -> JSONResponse:
        """Handle JWT validation errors."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": "Invalid or expired token",
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unhandled exceptions."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc) if app.debug else "An unexpected error occurred",
            },
        )
