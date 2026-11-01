from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import router
from app.core.database import Base, engine
from app import models  # noqa: F401

@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ERP Procure-to-Pay Management & Reconciliation System", version="1.0.0",
              description="A local, fictional procure-to-pay workflow simulation.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "Authorization"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.include_router(router)
