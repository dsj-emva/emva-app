from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Emva API")


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health", operation_id="getHealth")
def health() -> Health:
    return Health(status="ok")
