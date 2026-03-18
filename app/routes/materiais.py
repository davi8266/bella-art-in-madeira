from fastapi import APIRouter, Body
from app.db import (
    ensure_initialized, fetch_materials, insert_material,
    update_material, delete_material, get_composition,
    upsert_composition, update_composition, delete_composition,
)

router = APIRouter(prefix="/api", tags=["materiais"])


def _db():
    return ensure_initialized()


@router.get("/materias")
def api_materias():
    return [{"id": r[0], "nome": r[1], "unidade": r[2], "estoque": r[3], "custo": r[4]}
            for r in fetch_materials(_db())]


@router.post("/materias")
def api_add_materia(data: dict = Body(...)):
    mid = insert_material(_db(), data.get("nome", ""), data.get("unidade", ""),
                          data.get("estoque", 0), data.get("custo", 0))
    return {"id": mid}


@router.put("/materias/{mid}")
def api_update_materia(mid: int, data: dict = Body(...)):
    update_material(_db(), mid, data.get("nome", ""), data.get("unidade", ""),
                    data.get("estoque", 0), data.get("custo", 0))
    return {"ok": True}


@router.delete("/materias/{mid}")
def api_delete_materia(mid: int):
    delete_material(_db(), mid)
    return {"ok": True}


@router.get("/composicao/{pid}")
def api_get_composicao(pid: int):
    return [{"id": r[0], "materia": r[1], "unidade": r[2], "qtd": r[3], "custo_medio": r[4]}
            for r in get_composition(_db(), pid)]


@router.post("/composicao")
def api_add_composicao(data: dict = Body(...)):
    upsert_composition(_db(), int(data["produto_id"]), int(data["materia_id"]),
                       float(data.get("quantidade", 0)))
    return {"ok": True}


@router.put("/composicao/{cid}")
def api_update_composicao(cid: int, data: dict = Body(...)):
    update_composition(_db(), cid, float(data.get("quantidade", 0)))
    return {"ok": True}


@router.delete("/composicao/{cid}")
def api_delete_composicao(cid: int):
    delete_composition(_db(), cid)
    return {"ok": True}
