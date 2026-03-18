import io
import math
import time

import segno
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.db import (
    ensure_initialized, get_or_create_qr, get_qr_by_code, get_qr_for_product,
    insert_venda, get_price_by_ids, resolve_ml_platform_id,
)
from app.utils import clean_component

router = APIRouter(prefix="/api", tags=["qr"])


def _db():
    return ensure_initialized()


@router.get("/qr/lookup")
def api_qr_lookup(code: str):
    conn = _db()
    clean = "".join(ch for ch in code if ch.isalnum()).strip()
    m = get_qr_by_code(conn, clean)
    if not m:
        raise HTTPException(status_code=404, detail="Código não encontrado")
    cur = conn.cursor()
    cur.execute("SELECT nome FROM produtos WHERE id=?", (m["produto_id"],))
    rp = cur.fetchone()
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (m["plataforma_id"],))
    rpl = cur.fetchone()
    ml_mode = m.get("ml_mode")
    real_plat_id = resolve_ml_platform_id(conn, m["plataforma_id"], ml_mode)
    plat_nome = ("Mercado Livre Premium" if ml_mode == "premium"
                 else "Mercado Livre Clássico" if ml_mode == "classico"
                 else (rpl[0] if rpl else "?"))
    return {"produto_id": m["produto_id"], "plataforma_id": real_plat_id,
            "produto_nome": rp[0] if rp else "?", "plataforma_nome": plat_nome, "ml_mode": ml_mode}


@router.post("/qr/register")
def api_register_sale_by_qr(data: dict = Body(...)):
    conn = _db()
    code = "".join(ch for ch in str(data.get("code", "")) if ch.isalnum()).strip()
    quantidade = int(data.get("quantidade", 1))
    data_str = data.get("data") or time.strftime("%Y-%m-%d")
    m = get_qr_by_code(conn, code)
    if not m:
        try:
            pid = int(data["produto_id"]); plid = int(data["plataforma_id"])
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM produtos WHERE id=?", (pid,))
            cur2 = conn.cursor()
            cur2.execute("SELECT 1 FROM plataformas WHERE id=?", (plid,))
            if cur.fetchone() and cur2.fetchone():
                m = {"produto_id": pid, "plataforma_id": plid, "ml_mode": None}
        except Exception:
            pass
    if not m:
        raise HTTPException(status_code=404, detail="codigo_invalido")
    ml_mode = m.get("ml_mode")
    real_plid = resolve_ml_platform_id(conn, m["plataforma_id"], ml_mode)
    preco = get_price_by_ids(conn, m["produto_id"], real_plid)
    vid = insert_venda(conn, m["produto_id"], real_plid, quantidade, preco, data_str, 1, ml_mode)
    return {"id": vid, "produto_id": m["produto_id"]}


@router.post("/qr/generate_all_global")
def api_generate_all_qrs_global():
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM produtos WHERE ativo=1")
        products = cur.fetchall()
        cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
        plats = cur.fetchall()
        count = 0
        for (prod_id,) in products:
            for plat_id, plat_nome in plats:
                if plat_nome.lower() == "mercado livre":
                    get_or_create_qr(conn, prod_id, plat_id, ml_mode="classico")
                    get_or_create_qr(conn, prod_id, plat_id, ml_mode="premium")
                    count += 2
                else:
                    get_or_create_qr(conn, prod_id, plat_id)
                    count += 1
        return {"ok": True, "count": count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/qr/{pid}")
def api_generate_qr(pid: int, force: int = 0):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
    out = []
    for plat_id, plat_nome in cur.fetchall():
        if plat_nome.lower() == "mercado livre":
            c1 = get_or_create_qr(conn, pid, plat_id, force=bool(force), ml_mode="classico")
            c2 = get_or_create_qr(conn, pid, plat_id, force=bool(force), ml_mode="premium")
            out += [{"plataforma": "Mercado Livre Clássico", "code": c1, "ml_mode": "classico"},
                     {"plataforma": "Mercado Livre Premium",  "code": c2, "ml_mode": "premium"}]
        else:
            c = get_or_create_qr(conn, pid, plat_id, force=bool(force))
            out.append({"plataforma": plat_nome, "code": c, "ml_mode": None})
    return out


@router.get("/qr/{pid}")
def api_get_qr(pid: int):
    return get_qr_for_product(_db(), pid)


@router.delete("/qr/{pid}")
def api_delete_all_qr(pid: int):
    conn = _db()
    conn.cursor().execute("DELETE FROM qr_codes WHERE produto_id=?", (pid,))
    conn.commit()
    return {"ok": True}


@router.delete("/qr/{pid}/{plat_id}")
def api_delete_qr(pid: int, plat_id: int, ml_mode: str = None):
    conn = _db()
    cur = conn.cursor()
    if ml_mode:
        cur.execute("DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?",
                    (pid, plat_id, ml_mode))
    else:
        cur.execute("DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')",
                    (pid, plat_id))
    conn.commit()
    return {"ok": True}


def _build_qr_png(code: str, size: int) -> bytes:
    size = max(128, min(int(size), 2048))
    qr = segno.make(code, error="h")
    scale = next((s for s in range(2, 50) if max(qr.symbol_size(scale=s, border=2)) >= size), 50)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


@router.get("/qr/png/{pid}/{plat_id}")
def api_qr_png(pid: int, plat_id: int, size: int = 512, ml_mode: str = None):
    from datetime import datetime
    conn = _db()
    rows = get_qr_for_product(conn, pid)
    cur = conn.cursor()
    cur.execute("SELECT nome, sku FROM produtos WHERE id=?", (pid,))
    rprod = cur.fetchone()
    produto_sku = (rprod[1] or "").strip() or (rprod[0] if rprod else "produto")
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (plat_id,))
    rplat = cur.fetchone()
    plataforma_nome = rplat[0] if rplat else "plataforma"
    code = next((r["code"] for r in rows if r.get("plataforma_id") == plat_id
                 and r.get("ml_mode") == ml_mode), None)
    if not code:
        raise HTTPException(status_code=404, detail="codigo_inexistente")
    img = _build_qr_png(code, size)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"qr-{clean_component(plataforma_nome)}-{clean_component(produto_sku)}-{stamp}.png"
    return Response(img, media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _render_qr_pdf(data: list) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(10 * cm, 15 * cm))
    for item in data:
        prod_name = item.get("nome", "Produto")
        codes = item.get("codes", [])
        if not codes:
            continue
        c.setFont("Helvetica-Bold", 12 if len(prod_name) > 20 else 14)
        c.drawCentredString(5 * cm, 14 * cm, prod_name)
        cols = 1 if len(codes) <= 2 else 2
        rows = math.ceil(len(codes) / cols)
        cell_w = (10 * cm) / cols
        cell_h = (12.5 * cm) / rows
        max_qr = min(cell_w * 0.7, cell_h * 0.6, 5 * cm)
        for i, obj in enumerate(codes):
            cx = (i % cols) * cell_w + cell_w / 2
            cy = 13.5 * cm - (i // cols) * cell_h - cell_h / 2
            c.setFont("Helvetica", 10)
            c.drawCentredString(cx, cy - max_qr / 2 - 0.4 * cm, obj.get("label", ""))
            if obj.get("code"):
                qr = segno.make(obj["code"])
                ib = io.BytesIO()
                qr.save(ib, kind="png", scale=5, border=0)
                ib.seek(0)
                c.drawImage(ImageReader(ib), cx - max_qr / 2, cy - max_qr / 2,
                            width=max_qr, height=max_qr, mask="auto")
        c.showPage()
    c.save()
    return buf.getvalue()


@router.post("/print_qrs")
def api_print_qrs(data: list = Body(...)):
    return Response(_render_qr_pdf(data), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="etiquetas_qr.pdf"'})
