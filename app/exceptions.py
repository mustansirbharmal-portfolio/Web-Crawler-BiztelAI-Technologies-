from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

class CrawlerException(Exception):
    """Base exception class for the crawler application."""
    def __init__(self, detail: str, status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)

class URLFetchError(CrawlerException):
    """Raised when a URL cannot be fetched."""
    def __init__(self, url: str, detail: str = None):
        message = f"Failed to fetch URL: {url}"
        if detail:
            message += f" - {detail}"
        super().__init__(message, status_code=400)

def add_exception_handlers(app: FastAPI):
    """Add exception handlers to the FastAPI application."""
    
    @app.exception_handler(CrawlerException)
    async def crawler_exception_handler(request: Request, exc: CrawlerException):
        logger.error(f"CrawlerException: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"ValidationError: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )
        
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )
