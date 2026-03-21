"""
app/main.py — Bellart ERP
Monta o servidor FastAPI incluindo todos os routers.
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db import BASE_DIR, ensure_initialized
from app.routes import produtos, materiais, financeiro, vendas, qr, sistema

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Token secreto gerado pelo Electron e passado via variável de ambiente.
# Se não estiver definido (ex: execução manual via run.py sem Electron), acesso é livre.
_SECRET = os.environ.get("BELLART_SECRET", "")


def get_resource(relative: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_initialized()
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def require_secret(request: Request, call_next):
    """Bloqueia requisições que não venham do Electron (sem o token secreto)."""
    if _SECRET and request.headers.get("X-Bellart-Secret") != _SECRET:
        return HTMLResponse(
            "<h2 style='font-family:sans-serif;text-align:center;margin-top:20%'>"
            "Acesso restrito ao aplicativo Bellart.</h2>",
            status_code=403,
        )
    return await call_next(request)

app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static",  StaticFiles(directory=get_resource("frontend/web")),    name="static")
app.mount("/brand",   StaticFiles(directory=get_resource("frontend/static")), name="brand")

for router in [produtos.router, materiais.router, financeiro.router,
               vendas.router, qr.router, sistema.router]:
    app.include_router(router)


@app.get("/")
def index():
    return FileResponse(get_resource("frontend/web/index.html"))
