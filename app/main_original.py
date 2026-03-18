"""
app_web.py — Bellart ERP
Servidor FastAPI com todas as rotas da aplicação.
Melhorias aplicadas:
  - Conexão DB inicializada UMA vez via lifespan (não a cada request)
  - Rota /api/print_qrs duplicada removida
  - Todos os imports no topo do arquivo
  - Lógica de ml_mode centralizada em resolve_ml_platform_id (importada do db)
  - Tratamento de erros com HTTPException nas rotas principais
  - Função auxiliar _get_db() para obter a conexão já inicializada
"""

import io
import math
import os
import re
import shutil
import sys
import threading
import time
import unicodedata
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime

import segno
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from calc import get_material_details, platform_financials, store_financials
from db import (
    BASE_DIR,
    delete_composition,
    delete_material,
    delete_product,
    delete_venda,
    ensure_initialized,
    fetch_materials,
    fetch_products,
    fetch_vendas,
    get_composition,
    get_or_create_qr,
    get_platform_id,
    get_price_by_ids,
    get_prices,
    get_qr_by_code,
    get_qr_for_product,
    get_taxes,
    insert_material,
    insert_product,
    insert_venda,
    resolve_ml_platform_id,
    update_composition,
    update_material,
    update_product,
    upsert_composition,
    upsert_price,
    upsert_tax,
    verify_login,
    change_password,
)

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def get_resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def _get_db():
    """Retorna a conexão já inicializada. Use em todas as rotas."""
    return ensure_initialized()


def _clean_component(s: str) -> str:
    if not s:
        return "item"
    norm = unicodedata.normalize("NFKD", s)
    s2 = "".join(ch for ch in norm if not unicodedata.combining(ch))
    s2 = s2.replace(" ", "_")
    s2 = re.sub(r"[^A-Za-z0-9_\-]+", "", s2)
    return s2 or "item"


# ---------------------------------------------------------------------------
# Lifespan — inicialização única do banco
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_initialized()  # init_db + seed_initial rodados uma única vez
    yield


UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(lifespan=lifespan)
app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=get_resource_path("web")), name="static")
app.mount("/brand", StaticFiles(directory=get_resource_path("static")), name="brand")


# ---------------------------------------------------------------------------
# Rotas base
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(get_resource_path("web/index.html"))


@app.post("/api/exit")
def api_exit():
    def _exit():
        time.sleep(0.2)
        os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

@app.post("/api/login")
def api_login(data: dict = Body(...)):
    conn = _get_db()
    u = verify_login(conn, str(data.get("username", "")).strip(), str(data.get("password", "")))
    if not u:
        return {"error": "login_invalido"}
    return {"ok": True, "user": {"id": u["id"], "username": u["username"]}}


@app.post("/api/users/password")
def api_change_password(data: dict = Body(...)):
    conn = _get_db()
    ok = change_password(
        conn,
        str(data.get("username", "")).strip(),
        str(data.get("old", "")),
        str(data.get("new", "")),
    )
    if not ok:
        return {"error": "senha_invalida"}
    return {"ok": True}


# ---------------------------------------------------------------------------
# Upload de foto
# ---------------------------------------------------------------------------

@app.post("/api/products/{pid}/photo")
def api_upload_photo(pid: int, data: bytes = Body(...)):
    dest = os.path.join(UPLOAD_DIR, f"{pid}.png")
    with open(dest, "wb") as f:
        f.write(data)
    return {"ok": True, "path": f"/static/uploads/{pid}.png"}


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------

@app.get("/api/produtos")
def api_produtos():
    conn = _get_db()
    rows = fetch_products(conn)
    return [{"id": r[0], "nome": r[1], "sku": r[2]} for r in rows]


@app.post("/api/products")
def api_add_product(data: dict = Body(...)):
    conn = _get_db()
    nome = data.get("nome", "").strip()
    sku = data.get("sku", "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="nome vazio")
    pid = insert_product(conn, nome, sku)
    return {"id": pid}


@app.put("/api/products/{pid}")
def api_update_product(pid: int, data: dict = Body(...)):
    conn = _get_db()
    update_product(conn, pid, data.get("nome", "").strip(), data.get("sku", "").strip())
    return {"ok": True}


@app.delete("/api/products/{pid}")
def api_delete_product(pid: int):
    conn = _get_db()
    delete_product(conn, pid)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Preços
# ---------------------------------------------------------------------------

@app.get("/api/prices/{pid}")
def api_get_prices(pid: int):
    conn = _get_db()
    return get_prices(conn, pid)


@app.post("/api/prices/{pid}")
def api_set_price(pid: int, data: dict = Body(...)):
    conn = _get_db()
    plataforma = data.get("plataforma")
    preco = float(data.get("preco", 0))
    upsert_price(conn, pid, plataforma, preco)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Plataformas
# ---------------------------------------------------------------------------

@app.get("/api/platforms")
def api_platforms():
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
    return [{"id": r[0], "nome": r[1]} for r in cur.fetchall() if r[1] != "Mercado Livre"]


# ---------------------------------------------------------------------------
# Taxas
# ---------------------------------------------------------------------------

@app.get("/api/taxes")
def api_taxes():
    conn = _get_db()
    return get_taxes(conn)


@app.post("/api/taxes/{plataforma}")
def api_upsert_tax(plataforma: str, data: dict = Body(...)):
    conn = _get_db()
    upsert_tax(
        conn,
        plataforma,
        float(data.get("percentual", 0)),
        float(data.get("fixo", 0)),
        float(data.get("imposto", 0)),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Materiais
# ---------------------------------------------------------------------------

@app.get("/api/materias")
def api_materias():
    conn = _get_db()
    rows = fetch_materials(conn)
    return [{"id": r[0], "nome": r[1], "unidade": r[2], "estoque": r[3], "custo": r[4]} for r in rows]


@app.post("/api/materias")
def api_add_materia(data: dict = Body(...)):
    conn = _get_db()
    mid = insert_material(conn, data.get("nome", ""), data.get("unidade", ""), data.get("estoque", 0), data.get("custo", 0))
    return {"id": mid}


@app.put("/api/materias/{mid}")
def api_update_materia(mid: int, data: dict = Body(...)):
    conn = _get_db()
    update_material(conn, mid, data.get("nome", ""), data.get("unidade", ""), data.get("estoque", 0), data.get("custo", 0))
    return {"ok": True}


@app.delete("/api/materias/{mid}")
def api_delete_materia(mid: int):
    conn = _get_db()
    delete_material(conn, mid)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Composição
# ---------------------------------------------------------------------------

@app.get("/api/composicao/{pid}")
def api_get_composicao(pid: int):
    conn = _get_db()
    rows = get_composition(conn, pid)
    return [{"id": r[0], "materia": r[1], "unidade": r[2], "qtd": r[3], "custo_medio": r[4]} for r in rows]


@app.post("/api/composicao")
def api_add_composicao(data: dict = Body(...)):
    conn = _get_db()
    upsert_composition(conn, int(data.get("produto_id")), int(data.get("materia_id")), float(data.get("quantidade", 0)))
    return {"ok": True}


@app.put("/api/composicao/{cid}")
def api_update_composicao(cid: int, data: dict = Body(...)):
    conn = _get_db()
    update_composition(conn, cid, float(data.get("quantidade", 0)))
    return {"ok": True}


@app.delete("/api/composicao/{cid}")
def api_delete_composicao(cid: int):
    conn = _get_db()
    delete_composition(conn, cid)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

@app.get("/api/relatorios/{pid}")
def api_relatorios(pid: int):
    conn = _get_db()
    rows = platform_financials(conn, pid)
    mats = get_material_details(conn, pid)
    return [
        {
            "plataforma": r[0],
            "bruto": r[1],
            "taxa": r[2],
            "fixo": r[3],
            "imposto": r[4],
            "custo_total": r[5],
            "custo_mats": r[6],
            "impostos_total": r[8],
            "receita": r[9],
            "lucro_total": r[10],
            "lucro_mats": r[11],
            "margem": r[12],
            "materiais": mats,
        }
        for r in rows
    ]


@app.get("/api/reports/store")
def api_reports_store(start: str = None, end: str = None):
    conn = _get_db()
    return store_financials(conn, start_date=start, end_date=end)


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------

@app.get("/api/vendas/{pid}")
def api_get_vendas(pid: int):
    conn = _get_db()
    rows = fetch_vendas(conn, pid)
    out = []
    for r in rows:
        produto_nome = r[6] if len(r) >= 8 else None
        ml_mode = r[7] if len(r) >= 8 else (r[6] if len(r) == 7 else None)
        out.append({
            "id": r[0],
            "plataforma": r[1],
            "quantidade": r[2],
            "preco": r[3],
            "data": r[4],
            "via_qr": int(r[5] or 0),
            "produto_nome": produto_nome,
            "ml_mode": ml_mode,
        })
    return out


@app.get("/api/vendas_qr/{pid}")
def api_get_vendas_qr(pid: int):
    conn = _get_db()
    rows = fetch_vendas(conn, pid)
    return [
        {"id": r[0], "plataforma": r[1], "quantidade": r[2], "preco": r[3], "data": r[4]}
        for r in rows
        if int(r[5] or 0) == 1
    ]


@app.post("/api/vendas")
def api_add_venda(data: dict = Body(...)):
    conn = _get_db()
    produto_id = int(data.get("produto_id"))
    plataforma_id = int(data.get("plataforma_id"))
    quantidade = int(data.get("quantidade", 1))
    ml_mode = data.get("ml_mode") or None
    data_str = data.get("data") or time.strftime("%Y-%m-%d")

    real_plat_id = resolve_ml_platform_id(conn, plataforma_id, ml_mode)
    preco = get_price_by_ids(conn, produto_id, real_plat_id)
    vid = insert_venda(conn, produto_id, real_plat_id, quantidade, preco, data_str, 0, ml_mode)
    return {"id": vid}


@app.delete("/api/vendas/{vid}")
def api_delete_venda(vid: int):
    conn = _get_db()
    delete_venda(conn, vid)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Vendas em lote
# ---------------------------------------------------------------------------

@app.post("/api/vendas/batch")
def api_vendas_batch(items: list = Body(...)):
    conn = _get_db()
    count = 0
    for item in items:
        pid = item.get("produto_id")
        plid = item.get("plataforma_id")
        q = int(item.get("quantidade", 1))
        dt = item.get("data") or time.strftime("%Y-%m-%d")
        ml_mode = item.get("ml_mode") or None
        if pid and plid:
            real_plid = resolve_ml_platform_id(conn, int(plid), ml_mode)
            preco = get_price_by_ids(conn, int(pid), real_plid)
            insert_venda(conn, int(pid), real_plid, q, preco, dt, 1, ml_mode)
            count += 1
    return {"ok": True, "count": count}


# ---------------------------------------------------------------------------
# QR Codes
# ---------------------------------------------------------------------------

@app.get("/api/qr/lookup")
def api_qr_lookup(code: str):
    conn = _get_db()
    clean_code = "".join(ch for ch in code if ch.isalnum()).strip()
    m = get_qr_by_code(conn, clean_code)
    if not m:
        raise HTTPException(status_code=404, detail="Código não encontrado")

    cur = conn.cursor()
    cur.execute("SELECT nome FROM produtos WHERE id=?", (m["produto_id"],))
    rp = cur.fetchone()
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (m["plataforma_id"],))
    rpl = cur.fetchone()

    plat_nome = rpl[0] if rpl else "?"
    ml_mode = m.get("ml_mode")
    real_plat_id = resolve_ml_platform_id(conn, m["plataforma_id"], ml_mode)

    if ml_mode == "premium":
        plat_nome = "Mercado Livre Premium"
    elif ml_mode == "classico":
        plat_nome = "Mercado Livre Clássico"

    return {
        "produto_id": m["produto_id"],
        "plataforma_id": real_plat_id,
        "produto_nome": rp[0] if rp else "?",
        "plataforma_nome": plat_nome,
        "ml_mode": ml_mode,
    }


@app.post("/api/qr/register")
def api_register_sale_by_qr(data: dict = Body(...)):
    conn = _get_db()
    raw = str(data.get("code", ""))
    code = "".join(ch for ch in raw if ch.isalnum()).strip()
    quantidade = int(data.get("quantidade", 1))
    data_str = data.get("data") or time.strftime("%Y-%m-%d")

    m = get_qr_by_code(conn, code)
    if not m:
        # Tentar por produto_id + plataforma_id explícitos
        pid = data.get("produto_id")
        plid = data.get("plataforma_id")
        try:
            pid = int(pid) if pid is not None else None
            plid = int(plid) if plid is not None else None
        except (ValueError, TypeError):
            pid = plid = None
        if pid and plid:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM produtos WHERE id=?", (pid,))
            cur2 = conn.cursor()
            cur2.execute("SELECT 1 FROM plataformas WHERE id=?", (plid,))
            if cur.fetchone() and cur2.fetchone():
                m = {"produto_id": pid, "plataforma_id": plid, "ml_mode": None}

    if not m:
        raise HTTPException(status_code=404, detail="codigo_invalido")

    ml_mode = m.get("ml_mode")
    real_plid = resolve_ml_platform_id(conn, m["plataforma_id"], ml_mode)
    preco = get_price_by_ids(conn, m["produto_id"], real_plid)
    vid = insert_venda(conn, m["produto_id"], real_plid, quantidade, preco, data_str, 1, ml_mode)
    return {"id": vid, "produto_id": m["produto_id"]}


@app.post("/api/qr/generate_all_global")
def api_generate_all_qrs_global():
    try:
        conn = _get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM produtos WHERE ativo=1")
        products = cur.fetchall()
        cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
        plats = cur.fetchall()

        count = 0
        for (prod_id,) in products:
            for plat_id, plat_nome in plats:
                lower = (plat_nome or "").lower()
                if lower == "mercado livre":
                    get_or_create_qr(conn, prod_id, plat_id, force=False, ml_mode="classico")
                    get_or_create_qr(conn, prod_id, plat_id, force=False, ml_mode="premium")
                    count += 2
                else:
                    get_or_create_qr(conn, prod_id, plat_id, force=False)
                    count += 1
        return {"ok": True, "count": count}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@app.post("/api/qr/{pid}")
def api_generate_qr(pid: int, force: int = 0):
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
    plats = cur.fetchall()

    out = []
    for plat_id, plat_nome in plats:
        lower = (plat_nome or "").lower()
        if lower == "mercado livre":
            c1 = get_or_create_qr(conn, pid, plat_id, force=bool(force), ml_mode="classico")
            out.append({"plataforma": "Mercado Livre Clássico", "code": c1, "ml_mode": "classico"})
            c2 = get_or_create_qr(conn, pid, plat_id, force=bool(force), ml_mode="premium")
            out.append({"plataforma": "Mercado Livre Premium", "code": c2, "ml_mode": "premium"})
        else:
            c = get_or_create_qr(conn, pid, plat_id, force=bool(force))
            out.append({"plataforma": plat_nome, "code": c, "ml_mode": None})
    return out


@app.get("/api/qr/{pid}")
def api_get_qr(pid: int):
    conn = _get_db()
    return get_qr_for_product(conn, pid)


@app.delete("/api/qr/{pid}")
def api_delete_all_qr(pid: int):
    conn = _get_db()
    conn.cursor().execute("DELETE FROM qr_codes WHERE produto_id=?", (pid,))
    conn.commit()
    return {"ok": True}


@app.delete("/api/qr/{pid}/{plat_id}")
def api_delete_qr(pid: int, plat_id: int, ml_mode: str = None):
    conn = _get_db()
    cur = conn.cursor()
    if ml_mode:
        cur.execute(
            "DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?",
            (pid, plat_id, ml_mode),
        )
    else:
        cur.execute(
            "DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')",
            (pid, plat_id),
        )
    conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# QR PNG
# ---------------------------------------------------------------------------

def _build_qr_png(code: str, size: int) -> bytes:
    size = max(128, min(int(size), 2048))
    qr = segno.make(code, error="h")
    scale = 1
    for s in range(2, 50):
        w, h = qr.symbol_size(scale=s, border=2)
        if max(w, h) >= size:
            scale = s
            break
    else:
        scale = 50
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


@app.get("/api/qr/png/{pid}/{plat_id}")
def api_qr_png(pid: int, plat_id: int, size: int = 512, ml_mode: str = None):
    conn = _get_db()
    rows = get_qr_for_product(conn, pid)
    code = None
    plataforma_nome = "plataforma"

    cur = conn.cursor()
    cur.execute("SELECT nome, sku FROM produtos WHERE id=?", (pid,))
    rprod = cur.fetchone()
    produto_sku = (rprod[1] or "").strip() or (rprod[0] if rprod else "produto")

    cur.execute("SELECT nome FROM plataformas WHERE id=?", (plat_id,))
    rplat = cur.fetchone()
    if rplat:
        plataforma_nome = rplat[0]

    for r in rows:
        if r.get("plataforma_id") == plat_id:
            if ml_mode and r.get("ml_mode") != ml_mode:
                continue
            if not ml_mode and r.get("ml_mode"):
                continue
            code = r.get("code")
            if r.get("plataforma"):
                plataforma_nome = r["plataforma"]
            break

    if not code:
        raise HTTPException(status_code=404, detail="codigo_inexistente")

    img = _build_qr_png(code, size)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"qr-{_clean_component(plataforma_nome)}-{_clean_component(produto_sku)}-{stamp}.png"
    return Response(content=img, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/qr/png/save/{pid}/{plat_id}")
def api_qr_png_save(pid: int, plat_id: int, size: int = 512, ml_mode: str = None):
    conn = _get_db()
    rows = get_qr_for_product(conn, pid)
    code = None
    plataforma_nome = "plataforma"

    cur = conn.cursor()
    cur.execute("SELECT nome, sku FROM produtos WHERE id=?", (pid,))
    rprod = cur.fetchone()
    produto_sku = (rprod[1] or "").strip() or (rprod[0] if rprod else "produto")

    for r in rows:
        if r.get("plataforma_id") == plat_id:
            if ml_mode and r.get("ml_mode") != ml_mode:
                continue
            if not ml_mode and r.get("ml_mode"):
                continue
            code = r.get("code")
            if r.get("plataforma"):
                plataforma_nome = r["plataforma"]
            break

    if not code:
        return {"ok": False, "error": "codigo_inexistente"}

    qr = segno.make(code, error="h")
    uploads_dir = os.path.join(os.path.dirname(__file__), "web", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    base = f"qr-{_clean_component(plataforma_nome)}-{_clean_component(produto_sku)}"
    fname = f"{base}.png"
    path = os.path.join(uploads_dir, fname)
    i = 1
    while os.path.exists(path):
        fname = f"{base}-{i}.png"
        path = os.path.join(uploads_dir, fname)
        i += 1

    scale = 10
    for s in range(2, 50):
        w, h = qr.symbol_size(scale=s, border=2)
        if max(w, h) >= max(128, min(int(size), 2048)):
            scale = s
            break

    qr.save(path, kind="png", scale=scale, border=2)
    return {"ok": True, "path": path, "filename": fname}


# ---------------------------------------------------------------------------
# Impressão de QR em PDF
# ---------------------------------------------------------------------------

def _render_qr_pdf(data: list) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(10 * cm, 15 * cm))

    for item in data:
        prod_name = item.get("nome", "Produto")
        codes = item.get("codes", [])
        if not codes:
            continue

        font_size = 12 if len(prod_name) > 20 else 14
        c.setFont("Helvetica-Bold", font_size)
        c.drawCentredString(5 * cm, 14 * cm, prod_name)

        num_qrs = len(codes)
        cols = 1 if num_qrs <= 2 else 2
        rows = math.ceil(num_qrs / cols)
        start_y = 13.5 * cm
        available_h = 12.5 * cm
        cell_w = (10 * cm) / cols
        cell_h = available_h / rows
        max_qr_size = min(cell_w * 0.7, cell_h * 0.6, 5 * cm)

        for i, code_obj in enumerate(codes):
            row = i // cols
            col = i % cols
            cx = col * cell_w + cell_w / 2
            cy = start_y - (row * cell_h) - cell_h / 2

            label = code_obj.get("label", "")
            c.setFont("Helvetica", 10)
            c.drawCentredString(cx, cy - max_qr_size / 2 - 0.4 * cm, label)

            qr_content = code_obj.get("code", "")
            if qr_content:
                qr = segno.make(qr_content)
                img_buf = io.BytesIO()
                qr.save(img_buf, kind="png", scale=5, border=0)
                img_buf.seek(0)
                img = ImageReader(img_buf)
                c.drawImage(img, cx - max_qr_size / 2, cy - max_qr_size / 2, width=max_qr_size, height=max_qr_size, mask="auto")

        c.showPage()

    c.save()
    return buf.getvalue()


@app.post("/api/print_qrs")
def api_print_qrs(data: list = Body(...)):
    pdf_content = _render_qr_pdf(data)
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="etiquetas_qr.pdf"'},
    )


# ---------------------------------------------------------------------------
# Exportação CSV
# ---------------------------------------------------------------------------

def _to_csv(headers: list[str], rows: list[list]) -> str:
    lines = [",".join(f'"{h.replace(chr(34), chr(34)*2)}"' for h in headers)]
    for row in rows:
        lines.append(",".join(f'"{str(c).replace(chr(34), chr(34)*2)}"' for c in row))
    return "\n".join(lines)


@app.get("/api/export/rel/{pid}")
def api_export_rel(pid: int):
    conn = _get_db()
    rows = platform_financials(conn, pid)
    headers = ["Plataforma", "Bruto", "Taxa", "Imposto", "Fixo", "Impostos Total", "Receita", "Lucro c/ Mats", "Margem"]
    data_rows = [
        [r[0], f"{r[1]:.2f}", f"{r[2]*100:.2f}", f"{r[4]*100:.2f}", f"{r[3]:.2f}", f"{r[8]:.2f}", f"{r[9]:.2f}", f"{r[11]:.2f}", f"{r[12]*100:.2f}"]
        for r in rows
    ]
    csv = _to_csv(headers, data_rows)
    return Response(content=csv, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="relatorios.csv"'})


@app.get("/api/export/vendas/{pid}")
def api_export_vendas(pid: int):
    conn = _get_db()
    rows = fetch_vendas(conn, pid)
    headers = ["Plataforma", "Quantidade", "Preço", "Data"]
    data_rows = [[r[1], r[2], f"{r[3]:.2f}", r[4]] for r in rows]
    csv = _to_csv(headers, data_rows)
    return Response(content=csv, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="vendas.csv"'})


# ---------------------------------------------------------------------------
# Backup e Restore
# ---------------------------------------------------------------------------

def _build_backup_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        db_path = os.path.join(BASE_DIR, "bellart.db")
        if os.path.exists(db_path):
            z.write(db_path, arcname="bellart.db")
        if os.path.isdir(UPLOAD_DIR):
            for root, _, files in os.walk(UPLOAD_DIR):
                for fname in files:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, UPLOAD_DIR)
                    z.write(full, arcname=os.path.join("uploads", rel))
    return buf.getvalue()


@app.get("/api/backup")
def api_backup():
    content = _build_backup_zip()
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="bellart-backup.zip"'},
    )


@app.post("/api/backup/save")
def api_backup_save(dest: str = "backups"):
    content = _build_backup_zip()
    if (dest or "").lower() == "downloads":
        target_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    else:
        target_dir = os.path.join(BASE_DIR, "backups")
    os.makedirs(target_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    full_path = os.path.join(target_dir, f"bellart-backup-{ts}.zip")
    with open(full_path, "wb") as f:
        f.write(content)
    return {"ok": True, "path": full_path}


@app.post("/api/restore")
def api_restore(data: bytes = Body(...)):
    try:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, "r") as z:
            names = z.namelist()
            if "bellart.db" in names:
                db_target = os.path.join(BASE_DIR, "bellart.db")
                with z.open("bellart.db") as src, open(db_target, "wb") as dst:
                    dst.write(src.read())
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            for name in names:
                if name.startswith("uploads/") and not name.endswith("/"):
                    rel = name[len("uploads/"):].replace("\\", "/").strip("/")
                    dest = os.path.join(UPLOAD_DIR, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(name) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Info de rede
# ---------------------------------------------------------------------------

@app.get("/api/network_info")
def api_network_info():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return {"ip": ip, "port": 8765}
