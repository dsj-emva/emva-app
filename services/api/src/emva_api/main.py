from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emva_api import mapping_api, training_api, uploads
from emva_api.clock import Clock, SystemClock
from emva_api.object_store import ObjectStore
from emva_api.settings import Settings


class Health(BaseModel):
    status: Literal["ok"]


def create_app(settings: Settings, clock: Clock) -> FastAPI:
    engine = create_engine(settings.database_url)
    store = ObjectStore(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        store.ensure_bucket()
        yield
        engine.dispose()

    app = FastAPI(title="Emva API", lifespan=lifespan)
    app.state.sessions = sessionmaker(engine, expire_on_commit=False)
    app.state.store = store
    app.state.clock = clock

    @app.get("/health", operation_id="getHealth")
    def health() -> Health:
        return Health(status="ok")

    app.include_router(uploads.router)
    app.include_router(mapping_api.router)
    app.include_router(training_api.router)
    return app


app = create_app(Settings.from_environment(), SystemClock())
