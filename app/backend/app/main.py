import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.loader import ConfigLoader, ConfigError
from app.routes.sources import router as sources_router

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load configuration on startup."""
    try:
        loader = ConfigLoader(CONFIG_DIR)
        config = loader.load()
        app.state.config = config
        logger.info(
            "Configuration loaded: %d sources, %d endpoints, %d routes",
            len(config.sources),
            len(config.endpoints),
            len(config.routes),
        )
    except ConfigError as exc:
        logger.error("Configuration failed to load:\n%s", exc)
        raise
    yield


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    app = FastAPI(title="AI Lab", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(sources_router, prefix="/api")

    return app


app = create_app()
