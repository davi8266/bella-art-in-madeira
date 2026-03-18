import time
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from app.db import (
    ensure_initialized, fetch_vendas, insert_venda, delete_venda,
    get_price_by_ids, resolve_ml_platform_id,
)

router = APIRouter(prefix="/api", tags=["vendas"])


def _db():
    return ensure_initialized()


@router.get("/vendas/{pid}")
def api_get_vendas(pid: int):
    rows = fetch_vendas(_db(), pid)
    out = []
    for r in rows:
        produto_nome = r[6] if len(r) >= 8 else None
        ml_mode = r[7] if len(r) >= 8 else (r[6] if len(r) == 7 else None)
        out.append({"id": r[0], "plataforma": r[1], "quantidade": r[2],
                    "preco": r[3], "data": r[4], "via_qr": int(r[5] or 0),
                    "produto_nome": produto_nome, "ml_mode": ml_mode})
    return out


@router.get("/vendas_qr/{pid}")
def api_get_vendas_qr(pid: int):
    rows = fetch_vendas(_db(), pid)
    return [{"id": r[0], "plataforma": r[1], "quantidade": r[2], "preco": r[3], "data": r[4]}
            for r in rows if int(r[5] or 0) == 1]


@router.post("/vendas")
def api_add_venda(data: dict = Body(...)):
    conn = _db()
    produto_id = int(data["produto_id"])
    plataforma_id = int(data["plataforma_id"])
    quantidade = int(data.get("quantidade", 1))
    ml_mode = data.get("ml_mode") or None
    data_str = data.get("data") or time.strftime("%Y-%m-%d")
    real_plat_id = resolve_ml_platform_id(conn, plataforma_id, ml_mode)
    preco = get_price_by_ids(conn, produto_id, real_plat_id)
    return {"id": insert_venda(conn, produto_id, real_plat_id, quantidade, preco, data_str, 0, ml_mode)}


@router.delete("/vendas/{vid}")
def api_delete_venda(vid: int):
    delete_venda(_db(), vid)
    return {"ok": True}


@router.post("/vendas/batch")
def api_vendas_batch(items: list = Body(...)):
    conn = _db()
    count = 0
    for item in items:
        pid = item.get("produto_id")
        plid = item.get("plataforma_id")
        if pid and plid:
            ml_mode = item.get("ml_mode") or None
            real_plid = resolve_ml_platform_id(conn, int(plid), ml_mode)
            preco = get_price_by_ids(conn, int(pid), real_plid)
            dt = item.get("data") or time.strftime("%Y-%m-%d")
            insert_venda(conn, int(pid), real_plid, int(item.get("quantidade", 1)), preco, dt, 1, ml_mode)
            count += 1
    return {"ok": True, "count": count}


def _to_csv(headers, rows) -> str:
    q = lambda s: '"' + str(s).replace('"', '""') + '"'
    lines = [",".join(q(h) for h in headers)]
    lines += [",".join(q(c) for c in row) for row in rows]
    return "\n".join(lines)


@router.get("/export/vendas/{pid}")
def api_export_vendas(pid: int):
    rows = fetch_vendas(_db(), pid)
    headers = ["Plataforma", "Quantidade", "Preço", "Data"]
    data = [[r[1], r[2], f"{r[3]:.2f}", r[4]] for r in rows]
    return Response(_to_csv(headers, data), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="vendas.csv"'})
