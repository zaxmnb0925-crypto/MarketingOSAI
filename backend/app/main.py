import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.brands import router as brand_router
from app.api.content import router as content_router
from app.api.credits import router as credit_router
from app.api.subscriptions import (
    router as subscription_router,
)
from app.api.platform_admin_billing import (
    router as platform_admin_billing_router,
)
from app.api.social_accounts import router as social_account_router
from app.api.oauth_connections import router as oauth_connection_router
from app.api.usage import router as usage_router
from app.api.publications import router as publication_router
from app.core.config import settings
from app.core.request_context import (
    RequestContextMiddleware,
    get_request_id,
)
from app.core.database import check_database
from app.core.redis_client import check_redis


app = FastAPI(
    title="MarketingOS AI API",
    version=settings.app_version,
    docs_url=(
        "/docs"
        if settings.api_docs_enabled
        else None
    ),
    redoc_url=(
        "/redoc"
        if settings.api_docs_enabled
        else None
    ),
    openapi_url=(
        "/openapi.json"
        if settings.api_docs_enabled
        else None
    ),
)

app.add_middleware(
    RequestContextMiddleware
)


app.include_router(auth_router)
app.include_router(brand_router)
app.include_router(content_router)
app.include_router(credit_router)
app.include_router(subscription_router)
app.include_router(platform_admin_billing_router)
app.include_router(social_account_router)
app.include_router(oauth_connection_router)
app.include_router(usage_router)
app.include_router(publication_router)


@app.get("/")
async def root():
    return {
        "name": "MarketingOS AI API",
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/api/health")
async def health():
    database = False
    redis = False

    try:
        database = await check_database()
    except Exception:
        logging.warning(
            "health_dependency_check_failed "
            "request_id=%s",
            get_request_id(),
        )
        database = False

    try:
        redis = await check_redis()
    except Exception:
        logging.warning(
            "health_dependency_check_failed "
            "request_id=%s",
            get_request_id(),
        )
        redis = False

    healthy = database and redis

    payload = {
        "status": (
            "healthy"
            if healthy
            else "degraded"
        ),
        "version": settings.app_version,
        "services": {
            "api": True,
            "database": database,
            "redis": redis,
        },
    }

    if healthy:
        return payload

    return JSONResponse(
        status_code=503,
        content=payload,
    )
