from fastapi import APIRouter, Body, HTTPException
from app.db import ensure_initialized, fetch_products, insert_product, update_product, delete_product, get_prices, upsert_price

router = APIRouter(prefix="/api", tags=["produtos"])


def _db():
    return ensure_initialized()


@router.get("/produtos")
def api_produtos():
    return [{"id": r[0], "nome": r[1], "sku": r[2]} for r in fetch_products(_db())]


@router.post("/products")
def api_add_product(data: dict = Body(...)):
    nome = data.get("nome", "").strip()
    sku = data.get("sku", "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="nome vazio")
    return {"id": insert_product(_db(), nome, sku)}


@router.put("/products/{pid}")
def api_update_product(pid: int, data: dict = Body(...)):
    update_product(_db(), pid, data.get("nome", "").strip(), data.get("sku", "").strip())
    return {"ok": True}


@router.delete("/products/{pid}")
def api_delete_product(pid: int):
    delete_product(_db(), pid)
    return {"ok": True}


@router.get("/prices/{pid}")
def api_get_prices(pid: int):
    return get_prices(_db(), pid)


@router.post("/prices/{pid}")
def api_set_price(pid: int, data: dict = Body(...)):
    upsert_price(_db(), pid, data.get("plataforma"), float(data.get("preco", 0)))
    return {"ok": True}


@router.get("/platforms")
def api_platforms():
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
    return [{"id": r[0], "nome": r[1]} for r in cur.fetchall() if r[1] != "Mercado Livre"]
