"""HR Docs API (FastAPI). Chạy sau Kong; token do Keycloak phát; quyết định phân quyền do OPA (hoặc Casbin) trả về.

Tài liệu OpenAPI tự sinh: /api/docs (Swagger UI) và /api/openapi.json.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config
from .authz import get_engine
from .authz.casbin_engine import working_hours
from .db import ensure_indexes, get_db
from .errors import HttpError
from .request_log import request_log_middleware
from .routers import admin, auth, departments, documents, employees
from .security import bearer_scheme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        ensure_indexes(get_db())
    except Exception as exc:
        logging.getLogger("hrdocs").warning("MongoDB not ready at startup: %s", exc)
    logging.getLogger("hrdocs").info("policy engine: %s", config.POLICY_ENGINE)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="HR Docs API",
    version="2.0.0",
    description="API quản lý hồ sơ/tài liệu nội bộ. Xác thực: Keycloak (OIDC). Gateway: Kong. "
    "Phân quyền: OPA (RBAC + ABAC R1–R6). Log: Loki + Grafana.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.middleware("http")(request_log_middleware)

for r in (auth.router, documents.router, employees.router, departments.router, admin.router):
    # bearer_scheme chỉ để Swagger hiện nút Authorize; kiểm token thật nằm ở security.current_principal
    app.include_router(r, dependencies=[Depends(bearer_scheme)])


@app.exception_handler(HttpError)
async def http_error(_req: Request, exc: HttpError):
    return JSONResponse({"error": exc.message}, status_code=exc.status)


@app.exception_handler(StarletteHTTPException)
async def starlette_error(_req: Request, exc: StarletteHTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_req: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {"loc": [], "msg": "invalid request"}
    return JSONResponse({"error": f"{'.'.join(map(str, first['loc']))}: {first['msg']}"}, status_code=400)


@app.get("/api/health", tags=["health"])
def health():
    # working_hours chỉ để script kiểm thử biết kỳ vọng R3; quyết định thật vẫn do policy engine tính.
    return {"status": "ok", "policy_engine": get_engine().name, "working_hours": working_hours(time.time_ns())}
