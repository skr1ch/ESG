"""FastAPI entry point. Vercel finds `app` here with no configuration.

Run locally:  uvicorn app.main:app --reload
Routes only translate HTTP to app.views; all logic lives in app.core.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import views

app = FastAPI(title="Nimbus climate exposure register", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/", response_class=HTMLResponse)
def overview() -> HTMLResponse:
    return HTMLResponse(views.render_overview())


@app.get("/plants/{plant_id}", response_class=HTMLResponse)
def plant(plant_id: str) -> HTMLResponse:
    html = views.render_plant(plant_id)
    if html is None:
        return HTMLResponse(views.render_not_found(f"Plant '{plant_id[:12]}'"), status_code=404)
    return HTMLResponse(html)


@app.get("/carbon", response_class=HTMLResponse)
def carbon(price: str | None = None, horizon: str = "2040") -> HTMLResponse:
    return HTMLResponse(views.render_carbon(price, horizon))


@app.get("/method", response_class=HTMLResponse)
def method() -> HTMLResponse:
    return HTMLResponse(views.render_method())


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse(views.health())


@app.exception_handler(StarletteHTTPException)
async def not_found(request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return HTMLResponse(views.render_not_found(), status_code=404)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
