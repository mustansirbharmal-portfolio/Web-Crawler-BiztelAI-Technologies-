from uvicorn.workers import UvicornWorker

class FastAPIWorker(UvicornWorker):
    """Worker that integrates FastAPI with Gunicorn via Uvicorn."""
    CONFIG_KWARGS = {
        "log_level": "info",
        "reload": True
    }