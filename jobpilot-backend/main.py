import uvicorn

from src.config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
