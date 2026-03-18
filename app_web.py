from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
import threading
import time
import os
import sys
import re
import unicodedata
from db import BASE_DIR, get_conn, init_db, seed_initial, fetch_products, get_taxes, upsert_tax, get_prices, upsert_price, fetch_materials, insert_material, update_material, delete_material, get_composition, upsert_composition, update_composition, delete_composition, insert_product, update_product, delete_product, get_platform_id, insert_venda, fetch_vendas, get_price_by_ids, get_or_create_qr, get_qr_by_code, get_qr_for_product, delete_venda
from db import verify_login, change_password
from calc import platform_financials, get_material_details, store_financials

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

def ensure_db():
    conn = get_conn()
    init_db(conn)
    seed_initial(conn)
    return conn

UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
app.mount('/static/uploads', StaticFiles(directory=UPLOAD_DIR), name='uploads')
app.mount('/static', StaticFiles(directory=get_resource_path('web')), name='static')
app.mount('/brand', StaticFiles(directory=get_resource_path('static')), name='brand')

@app.get('/')
def index():
    return FileResponse(get_resource_path('web/index.html'))

@app.post('/api/exit')
def api_exit():
    def _exit():
        time.sleep(0.2)
        os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    return {'ok': True}

@app.post('/api/login')
def api_login(data: dict = Body(...)):
    conn = ensure_db()
    u = verify_login(conn, str(data.get('username','')).strip(), str(data.get('password','')))
    if not u:
        return {'error': 'login_invalido'}
    return {'ok': True, 'user': {'id': u['id'], 'username': u['username']}}

@app.post('/api/users/password')
def api_change_password(data: dict = Body(...)):
    conn = ensure_db()
    ok = change_password(conn, str(data.get('username','')).strip(), str(data.get('old','')), str(data.get('new','')))
    if not ok:
        return {'error': 'senha_invalida'}
    return {'ok': True}

@app.post('/api/products/{pid}/photo')
def api_upload_photo(pid: int, data: bytes = Body(...)):
    # salva como PNG no diretório persistente
    dest = os.path.join(UPLOAD_DIR, f"{pid}.png")
    with open(dest, 'wb') as f:
        f.write(data)
    return {'ok': True, 'path': f"/static/uploads/{pid}.png"}

@app.get('/api/produtos')
def api_produtos():
    conn = ensure_db()
    rows = fetch_products(conn)
    return [{'id': r[0], 'nome': r[1], 'sku': r[2]} for r in rows]

@app.get('/api/relatorios/{pid}')
def api_relatorios(pid: int):
    conn = ensure_db()
    rows = platform_financials(conn, pid)
    mats = get_material_details(conn, pid)
    return [
        {
            'plataforma': r[0],
            'bruto': r[1],
            'taxa': r[2],
            'fixo': r[3],
            'imposto': r[4],
            'custo_total': r[5],
            'custo_mats': r[6],
            'impostos_total': r[8],
            'receita': r[9],
            'lucro_total': r[10],
            'lucro_mats': r[11],
            'margem': r[12],
            'materiais': mats
        }
        for r in rows
    ]

@app.get('/api/reports/store')
def api_reports_store(start: str = None, end: str = None):
    conn = ensure_db()
    return store_financials(conn, start_date=start, end_date=end)

@app.get('/api/taxes')
def api_taxes():
    conn = ensure_db()
    return get_taxes(conn)

@app.post('/api/taxes/{plataforma}')
def api_upsert_tax(plataforma: str, data: dict = Body(...)):
    conn = ensure_db()
    p = float(data.get('percentual', 0))
    f = float(data.get('fixo', 0))
    i = float(data.get('imposto', 0))
    upsert_tax(conn, plataforma, p, f, i)
    return {'ok': True}

# Produtos
@app.post('/api/products')
def api_add_product(data: dict = Body(...)):
    conn = ensure_db()
    nome = data.get('nome','').strip()
    sku = data.get('sku','').strip()
    if not nome:
        return {'error':'nome vazio'}
    pid = insert_product(conn, nome, sku)
    return {'id': pid}

@app.put('/api/products/{pid}')
def api_update_product(pid: int, data: dict = Body(...)):
    conn = ensure_db()
    update_product(conn, pid, data.get('nome','').strip(), data.get('sku','').strip())
    return {'ok': True}

@app.delete('/api/products/{pid}')
def api_delete_product(pid: int):
    conn = ensure_db()
    delete_product(conn, pid)
    return {'ok': True}

@app.get('/api/prices/{pid}')
def api_get_prices(pid: int):
    conn = ensure_db()
    return get_prices(conn, pid)

@app.post('/api/prices/{pid}')
def api_set_price(pid: int, data: dict = Body(...)):
    conn = ensure_db()
    plataforma = data.get('plataforma')
    preco = float(data.get('preco', 0))
    upsert_price(conn, pid, plataforma, preco)
    return {'ok': True}

@app.get('/api/platforms')
def api_platforms():
    conn = ensure_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
    return [{'id': r[0], 'nome': r[1]} for r in cur.fetchall() if r[1] != 'Mercado Livre']

# Materiais
@app.get('/api/materias')
def api_materias():
    conn = ensure_db()
    rows = fetch_materials(conn)
    return [{'id': r[0], 'nome': r[1], 'unidade': r[2], 'estoque': r[3], 'custo': r[4]} for r in rows]

@app.post('/api/materias')
def api_add_materia(data: dict = Body(...)):
    conn = ensure_db()
    mid = insert_material(conn, data.get('nome',''), data.get('unidade',''), data.get('estoque',0), data.get('custo',0))
    return {'id': mid}

@app.put('/api/materias/{mid}')
def api_update_materia(mid: int, data: dict = Body(...)):
    conn = ensure_db()
    update_material(conn, mid, data.get('nome',''), data.get('unidade',''), data.get('estoque',0), data.get('custo',0))
    return {'ok': True}

@app.delete('/api/materias/{mid}')
def api_delete_materia(mid: int):
    conn = ensure_db()
    delete_material(conn, mid)
    return {'ok': True}

# Composição
@app.get('/api/composicao/{pid}')
def api_get_composicao(pid: int):
    conn = ensure_db()
    rows = get_composition(conn, pid)
    return [{'id': r[0], 'materia': r[1], 'unidade': r[2], 'qtd': r[3], 'custo_medio': r[4]} for r in rows]

@app.post('/api/composicao')
def api_add_composicao(data: dict = Body(...)):
    conn = ensure_db()
    upsert_composition(conn, int(data.get('produto_id')), int(data.get('materia_id')), float(data.get('quantidade',0)))
    return {'ok': True}

@app.put('/api/composicao/{cid}')
def api_update_composicao(cid: int, data: dict = Body(...)):
    conn = ensure_db()
    update_composition(conn, cid, float(data.get('quantidade',0)))
    return {'ok': True}

@app.delete('/api/composicao/{cid}')
def api_delete_composicao(cid: int):
    conn = ensure_db()
    delete_composition(conn, cid)
    return {'ok': True}

# Vendas
@app.get('/api/vendas/{pid}')
def api_get_vendas(pid: int):
    conn = ensure_db()
    rows = fetch_vendas(conn, pid)
    out = []
    for r in rows:
        if len(r) == 7:
            produto_nome = None
            ml_mode = r[6]
        elif len(r) >= 8:
            produto_nome = r[6]
            ml_mode = r[7]
        else:
            produto_nome = None
            ml_mode = None
        out.append({
            'id': r[0],
            'plataforma': r[1],
            'quantidade': r[2],
            'preco': r[3],
            'data': r[4],
            'via_qr': int(r[5] or 0),
            'produto_nome': produto_nome,
            'ml_mode': ml_mode
        })
    return out

@app.get('/api/vendas_qr/{pid}')
def api_get_vendas_qr(pid: int):
    conn = ensure_db()
    rows = fetch_vendas(conn, pid)
    rows_qr = [r for r in rows if (len(r) >= 6 and int(r[5] or 0) == 1)]
    return [{'id': r[0], 'plataforma': r[1], 'quantidade': r[2], 'preco': r[3], 'data': r[4]} for r in rows_qr]

@app.post('/api/vendas')
def api_add_venda(data: dict = Body(...)):
    conn = ensure_db()
    produto_id = int(data.get('produto_id'))
    plataforma_id = int(data.get('plataforma_id'))
    quantidade = int(data.get('quantidade', 1))
    ml_mode = data.get('ml_mode') or None
    preco = get_price_by_ids(conn, produto_id, plataforma_id)
    data_str = data.get('data') or time.strftime('%Y-%m-%d')
    vid = insert_venda(conn, produto_id, plataforma_id, quantidade, preco, data_str, 0, ml_mode)
    return {'id': vid}

@app.delete('/api/vendas/{vid}')
def api_delete_venda(vid: int):
    conn = ensure_db()
    delete_venda(conn, vid)
    return {'ok': True}

# QR Codes
@app.get('/api/qr/lookup')
def api_qr_lookup(code: str):
    conn = ensure_db()
    m = get_qr_by_code(conn, code)
    if not m:
        return {'error': 'Código não encontrado'}
    cur = conn.cursor()
    cur.execute("SELECT nome FROM produtos WHERE id=?", (m['produto_id'],))
    rp = cur.fetchone()
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (m['plataforma_id'],))
    rpl = cur.fetchone()
    plat_nome = rpl[0] if rpl else '?'
    
    # Resolver ID específico se for ML estratificado
    ml_mode = m.get('ml_mode') if isinstance(m, dict) else None
    real_plat_id = m['plataforma_id']
    
    if plat_nome == 'Mercado Livre' and ml_mode:
        if ml_mode == 'premium':
            plat_nome = 'Mercado Livre Premium'
            pid_prem = get_platform_id(conn, 'Mercado Livre Premium')
            if pid_prem: real_plat_id = pid_prem
        elif ml_mode == 'classico':
            plat_nome = 'Mercado Livre Clássico'
            pid_class = get_platform_id(conn, 'Mercado Livre Clássico')
            if pid_class: real_plat_id = pid_class
            
    return {
        'produto_id': m['produto_id'],
        'plataforma_id': real_plat_id,
        'produto_nome': rp[0] if rp else '?',
        'plataforma_nome': plat_nome,
        'ml_mode': ml_mode
    }

@app.post('/api/vendas/batch')
def api_vendas_batch(items: list = Body(...)):
    conn = ensure_db()
    count = 0
    for item in items:
        pid = item.get('produto_id')
        plid = item.get('plataforma_id')
        q = int(item.get('quantidade', 1))
        dt = item.get('data') or time.strftime('%Y-%m-%d')
        ml_mode = item.get('ml_mode') or None
        
        # Resolver plataforma correta se tiver ml_mode
        if ml_mode:
            if ml_mode == 'premium':
                pp = get_platform_id(conn, 'Mercado Livre Premium')
                if pp: plid = pp
            elif ml_mode == 'classico':
                pc = get_platform_id(conn, 'Mercado Livre Clássico')
                if pc: plid = pc
                
        if pid and plid:
            preco = get_price_by_ids(conn, pid, plid)
            insert_venda(conn, pid, plid, q, preco, dt, 1, ml_mode)
            count += 1
    return {'ok': True, 'count': count}

@app.post('/api/qr/register')
def api_register_sale_by_qr(data: dict = Body(...)):
    conn = ensure_db()
    raw = str(data.get('code',''))
    code = ''.join(ch for ch in raw if ch.isalnum()).strip()
    quantidade = int(data.get('quantidade', 1))
    data_str = data.get('data') or time.strftime('%Y-%m-%d')
    m = get_qr_by_code(conn, code)
    if not m:
        pid = data.get('produto_id')
        plid = data.get('plataforma_id')
        try:
            pid = int(pid) if pid is not None else None
            plid = int(plid) if plid is not None else None
        except Exception:
            pid = None; plid = None
        if pid and plid:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM produtos WHERE id=?", (pid,))
            okp = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM plataformas WHERE id=?", (plid,))
            okpl = cur.fetchone() is not None
            if okp and okpl:
                m = {'produto_id': pid, 'plataforma_id': plid}
        if not m:
            return {'error': 'codigo_invalido'}
            
    # Ajustar plataforma se ml_mode presente
    ml_mode = m.get('ml_mode') if isinstance(m, dict) else None
    real_plid = m['plataforma_id']
    if ml_mode:
        if ml_mode == 'premium':
            pp = get_platform_id(conn, 'Mercado Livre Premium')
            if pp: real_plid = pp
        elif ml_mode == 'classico':
            pc = get_platform_id(conn, 'Mercado Livre Clássico')
            if pc: real_plid = pc

    preco = get_price_by_ids(conn, m['produto_id'], real_plid)
    vid = insert_venda(conn, m['produto_id'], real_plid, quantidade, preco, data_str, 1, ml_mode)
    return {'id': vid, 'produto_id': m['produto_id']}

@app.post('/api/qr/generate_all_global')
def api_generate_all_qrs_global():
    try:
        conn = ensure_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM produtos WHERE ativo=1")
        products = cur.fetchall()
        
        cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
        plats = cur.fetchall()
        
        count = 0
        for prod in products:
            pid = prod[0]
            for plat_id, plat_nome in plats:
                lower = (plat_nome or '').lower()
                if lower == 'mercado livre':
                    get_or_create_qr(conn, pid, plat_id, force=False, ml_mode='classico')
                    get_or_create_qr(conn, pid, plat_id, force=False, ml_mode='premium')
                    count += 2
                    continue
                
                get_or_create_qr(conn, pid, plat_id, force=False)
                count += 1
                
        return {'ok': True, 'count': count}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

@app.post('/api/qr/{pid}')
def api_generate_qr(pid: int, force: int = 0):
    conn = ensure_db()
    # Gerar para todas as plataformas
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM plataformas ORDER BY nome")
    plats = cur.fetchall()
    out = []
    for plat_id, plat_nome in plats:
        lower = (plat_nome or '').lower()
        if lower == 'mercado livre':
            # Gerar ML Clássico e Premium
            c1 = get_or_create_qr(conn, pid, plat_id, force=bool(force), ml_mode='classico')
            out.append({'plataforma': 'Mercado Livre Clássico', 'code': c1, 'ml_mode': 'classico'})
            c2 = get_or_create_qr(conn, pid, plat_id, force=bool(force), ml_mode='premium')
            out.append({'plataforma': 'Mercado Livre Premium', 'code': c2, 'ml_mode': 'premium'})
        else:
            c = get_or_create_qr(conn, pid, plat_id, force=bool(force))
            out.append({'plataforma': plat_nome, 'code': c, 'ml_mode': None})
    return out

@app.post('/api/print_qrs')
def api_print_qrs(data: list = Body(...)):
    import io
    import segno
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    import math

    buf = io.BytesIO()
    # Tamanho 10x15 cm
    c = canvas.Canvas(buf, pagesize=(10*cm, 15*cm))
    
    for item in data:
        prod_name = item.get('nome', 'Produto')
        codes = item.get('codes', []) # Expects list of {label: str, code: str}
        
        if not codes:
            continue
        
        # Draw Product Name
        c.setFont("Helvetica-Bold", 14)
        # Quebra de linha simples se nome for muito longo
        if len(prod_name) > 20:
            c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(5*cm, 14*cm, prod_name)
        
        num_qrs = len(codes)
        
        # Layout Grid dinâmico
        # Se <= 2: 1 coluna (vertical), bem espaçados
        # Se > 2: 2 colunas
        cols = 1 if num_qrs <= 2 else 2
        rows = math.ceil(num_qrs / cols)
        
        start_y = 13.5 * cm
        available_h = 12.5 * cm
        
        cell_w = (10 * cm) / cols
        cell_h = available_h / rows
        
        # Tamanho máximo do QR para caber na célula com margem
        max_qr_size = min(cell_w * 0.7, cell_h * 0.6)
        # Limita tamanho máximo absoluto para não ficar gigante se for só 1
        if max_qr_size > 5*cm: max_qr_size = 5*cm
        
        for i, code_obj in enumerate(codes):
            row = i // cols
            col = i % cols
            
            # Centro da célula
            cx = col * cell_w + cell_w/2
            cy = start_y - (row * cell_h) - cell_h/2
            
            # Label
            label = code_obj.get('label', '')
            c.setFont("Helvetica", 10)
            text_y = cy - max_qr_size/2 - 0.4*cm
            c.drawCentredString(cx, text_y, label)
            
            # QR Code
            qr_content = code_obj.get('code', '')
            if qr_content:
                qr = segno.make(qr_content)
                img_buf = io.BytesIO()
                qr.save(img_buf, kind='png', scale=5, border=0)
                img_buf.seek(0)
                
                img = ImageReader(img_buf)
                c.drawImage(img, cx - max_qr_size/2, cy - max_qr_size/2, width=max_qr_size, height=max_qr_size, mask='auto')
        
        c.showPage()
    
    c.save()
    pdf_content = buf.getvalue()
    return Response(content=pdf_content, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="etiquetas_qr.pdf"'})

@app.get('/api/qr/{pid}')
def api_get_qr(pid: int):
    conn = ensure_db()
    return get_qr_for_product(conn, pid)

@app.delete('/api/qr/{pid}')
def api_delete_all_qr(pid: int):
    conn = ensure_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM qr_codes WHERE produto_id=?", (pid,))
    conn.commit()
    return {'ok': True}

@app.delete('/api/qr/{pid}/{plat_id}')
def api_delete_qr(pid: int, plat_id: int, ml_mode: str = None):
    conn = ensure_db()
    cur = conn.cursor()
    if ml_mode:
        cur.execute("DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND ml_mode=?", (pid, plat_id, ml_mode))
    else:
        cur.execute("DELETE FROM qr_codes WHERE produto_id=? AND plataforma_id=? AND (ml_mode IS NULL OR ml_mode='')", (pid, plat_id))
    conn.commit()
    return {'ok': True}

@app.get('/api/qr/png/{pid}/{plat_id}')
def api_qr_png(pid: int, plat_id: int, size: int = 512, ml_mode: str = None):
    # busca código do QR no banco
    conn = ensure_db()
    rows = get_qr_for_product(conn, pid)
    code = None
    plataforma_nome = 'plataforma'
    produto_nome = 'produto'
    # obter nomes para filename
    cur = conn.cursor()
    cur.execute("SELECT nome, sku FROM produtos WHERE id=?", (pid,))
    rprod = cur.fetchone()
    produto_sku = None
    if rprod:
        produto_nome = rprod[0]
        produto_sku = (rprod[1] or '').strip() or produto_nome
    cur.execute("SELECT nome FROM plataformas WHERE id=?", (plat_id,))
    rplat = cur.fetchone()
    if rplat:
        plataforma_nome = rplat[0]
    for r in rows:
        if r.get('plataforma_id') == plat_id:
            if ml_mode and r.get('ml_mode') != ml_mode:
                continue
            if not ml_mode and r.get('ml_mode'):
                continue
            code = r.get('code')
            if r.get('plataforma'):
                plataforma_nome = r.get('plataforma')
            break
    if not code:
        return {'error': 'codigo_inexistente'}
    # gerar PNG localmente (offline)
    import io
    import segno
    size = max(128, min(int(size or 512), 2048))
    qr = segno.make(code, error='h')
    # calcular scale aproximado para atingir o tamanho desejado
    scale = 1
    try:
        for s in range(2, 50):
            w, h = qr.symbol_size(scale=s, border=2)
            if max(w, h) >= size:
                scale = s
                break
        else:
            scale = 50
    except Exception:
        scale = 10
    buf = io.BytesIO()
    qr.save(buf, kind='png', scale=scale, border=2)
    img = buf.getvalue()
    from datetime import datetime
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    plat_safe = _clean_component(plataforma_nome)
    sku_safe = _clean_component(produto_sku or produto_nome)
    fname = f"qr-{plat_safe}-{sku_safe}-{stamp}.png"
    return Response(content=img, media_type='image/png', headers={'Content-Disposition': f'attachment; filename="{fname}"'})

@app.get('/api/qr/png/save/{pid}/{plat_id}')
def api_qr_png_save(pid: int, plat_id: int, size: int = 512, ml_mode: str = None):
    # gera e salva PNG em web/uploads para uso em app desktop
    conn = ensure_db()
    rows = get_qr_for_product(conn, pid)
    code = None
    plataforma_nome = 'plataforma'
    produto_nome = 'produto'
    for r in rows:
        if r.get('plataforma_id') == plat_id:
            if ml_mode and r.get('ml_mode') != ml_mode:
                continue
            if not ml_mode and r.get('ml_mode'):
                continue
            code = r.get('code')
            if r.get('plataforma'):
                plataforma_nome = r.get('plataforma')
            break
    # obter SKU do produto para usar no arquivo
    cur = conn.cursor()
    cur.execute("SELECT nome, sku FROM produtos WHERE id=?", (pid,))
    rprod = cur.fetchone()
    produto_sku = 'produto'
    if rprod:
        produto_sku = (rprod[1] or '').strip() or rprod[0]
        produto_nome = rprod[0]
    if not code:
        return {'ok': False, 'error': 'codigo_inexistente'}
    import os, segno
    size = max(128, min(int(size or 512), 2048))
    qr = segno.make(code, error='h')
    scale = 10
    uploads_dir = os.path.join(os.path.dirname(__file__), 'web', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    plat_safe = _clean_component(plataforma_nome)
    sku_safe = _clean_component(produto_sku or produto_nome)
    base = f"qr-{plat_safe}-{sku_safe}"
    fname = f"{base}.png"
    path = os.path.join(uploads_dir, fname)
    i = 1
    # garante nome único adicionando contador incremental
    while os.path.exists(path):
        fname = f"{base}-{i}.png"
        path = os.path.join(uploads_dir, fname)
        i += 1
    # ajustar scale grosseiramente para tamanho desejado
    for s in range(2, 50):
        w, h = qr.symbol_size(scale=s, border=2)
        if max(w, h) >= size:
            scale = s
            break
    qr.save(path, kind='png', scale=scale, border=2)
    return {'ok': True, 'path': path, 'filename': fname}

# Export CSV
@app.get('/api/export/rel/{pid}')
def api_export_rel(pid: int):
    conn = ensure_db()
    rows = platform_financials(conn, pid)
    headers = ['Plataforma','Bruto','Taxa','Imposto','Fixo','Impostos Total','Receita','Lucro c/ Mats','Margem']
    out = [','.join('"' + h.replace('"','""') + '"' for h in headers)]
    for r in rows:
        plataforma = r[0]
        bruto = f"{r[1]:.2f}"
        taxa = f"{r[2]*100:.2f}"
        imposto = f"{r[4]*100:.2f}"
        fixo = f"{r[3]:.2f}"
        impostos_total = f"{r[8]:.2f}"
        receita = f"{r[9]:.2f}"
        lucro_mats = f"{r[11]:.2f}"
        margem = f"{r[12]*100:.2f}"
        cells = [plataforma, bruto, taxa, imposto, fixo, impostos_total, receita, lucro_mats, margem]
        out.append(','.join('"' + str(c).replace('"','""') + '"' for c in cells))
    csv = '\n'.join(out)
    return Response(content=csv, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="relatorios.csv"'})

@app.get('/api/export/vendas/{pid}')
def api_export_vendas(pid: int):
    conn = ensure_db()
    rows = fetch_vendas(conn, pid)
    headers = ['Plataforma','Quantidade','Preço','Data']
    out = [','.join('"' + h.replace('"','""') + '"' for h in headers)]
    for r in rows:
        plataforma = r[1]
        quantidade = r[2]
        preco = f"{r[3]:.2f}"
        data = r[4]
        cells = [plataforma, quantidade, preco, data]
        out.append(','.join('"' + str(c).replace('"','""') + '"' for c in cells))
    csv = '\n'.join(out)
    return Response(content=csv, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="vendas.csv"'})

def _clean_component(s: str) -> str:
    if s is None:
        return 'item'
    # remove acentos
    norm = unicodedata.normalize('NFKD', s)
    s2 = ''.join(ch for ch in norm if not unicodedata.combining(ch))
    # espaços viram underscore
    s2 = s2.replace(' ', '_')
    # mantém apenas letras, números, underscore e hífen
    s2 = re.sub(r'[^A-Za-z0-9_\-]+', '', s2)
    return s2 or 'item'

# Backup e Restore
@app.get('/api/backup')
def api_backup():
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        # banco de dados
        db_path = os.path.join(BASE_DIR, 'bellart.db')
        if os.path.exists(db_path):
            z.write(db_path, arcname='bellart.db')
        # uploads (fotos e qrcodes salvos)
        up_dir = UPLOAD_DIR
        if os.path.isdir(up_dir):
            for root, dirs, files in os.walk(up_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, up_dir)
                    z.write(full, arcname=os.path.join('uploads', rel))
    content = buf.getvalue()
    return Response(content=content, media_type='application/zip', headers={'Content-Disposition':'attachment; filename="bellart-backup.zip"'})

@app.get('/api/network_info')
def api_network_info():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "127.0.0.1"
    return {'ip': ip, 'port': 8765}

@app.post('/api/restore')
def api_restore(data: bytes = Body(...)):
    import io, zipfile, shutil
    # abrir zip a partir do corpo
    try:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, 'r') as z:
            names = z.namelist()
            # restaurar banco
            if 'bellart.db' in names:
                db_target = os.path.join(BASE_DIR, 'bellart.db')
                # Fecha conexões antes se possível? No FastAPI é difícil fechar a conexão ativa
                # mas o sqlite lida bem com replace se não estiver travado.
                tmp = z.open('bellart.db')
                with open(db_target, 'wb') as f:
                    f.write(tmp.read())
            # restaurar uploads sob prefixo seguro
            up_target = UPLOAD_DIR
            os.makedirs(up_target, exist_ok=True)
            for name in names:
                if name.startswith('uploads/') and not name.endswith('/'):
                    # impedir path traversal
                    rel = name[len('uploads/'):]
                    rel = rel.replace('\\','/')
                    rel = rel.strip('/')
                    dest = os.path.join(up_target, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(name) as src, open(dest, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# Salvar backup diretamente em disco (pasta "backups" do projeto)
@app.post('/api/backup/save')
def api_backup_save(dest: str = 'backups'):
    import io, zipfile, datetime
    # gera o mesmo conteúdo do /api/backup
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        db_path = os.path.join(BASE_DIR, 'bellart.db')
        if os.path.exists(db_path):
            z.write(db_path, arcname='bellart.db')
        up_dir = UPLOAD_DIR
        if os.path.isdir(up_dir):
            for root, dirs, files in os.walk(up_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, up_dir)
                    z.write(full, arcname=os.path.join('uploads', rel))
    content = buf.getvalue()
    # decide diretório de destino
    if (dest or '').lower() == 'downloads':
        target_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
    else:
        target_dir = os.path.join(BASE_DIR, 'backups')
    os.makedirs(target_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f"bellart-backup-{ts}.zip"
    full_path = os.path.join(target_dir, filename)
    with open(full_path, 'wb') as f:
        f.write(content)
    return { 'ok': True, 'path': full_path }

@app.post('/api/print_qrs')
def api_print_qrs(data: list = Body(...)):
    import io
    import segno
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    import math

    buf = io.BytesIO()
    # Tamanho 10x15 cm
    c = canvas.Canvas(buf, pagesize=(10*cm, 15*cm))
    
    for item in data:
        prod_name = item.get('nome', 'Produto')
        codes = item.get('codes', []) # Expects list of {label: str, code: str}
        
        if not codes:
            continue
            
        # Draw Product Name
        c.setFont("Helvetica-Bold", 14)
        # Quebra de linha simples se nome for muito longo
        if len(prod_name) > 20:
            c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(5*cm, 14*cm, prod_name)
        
        num_qrs = len(codes)
        
        # Layout Grid dinâmico
        # Se <= 2: 1 coluna (vertical), bem espaçados
        # Se > 2: 2 colunas
        cols = 1 if num_qrs <= 2 else 2
        rows = math.ceil(num_qrs / cols)
        
        start_y = 13.5 * cm
        available_h = 12.5 * cm
        
        cell_w = (10 * cm) / cols
        cell_h = available_h / rows
        
        # Tamanho máximo do QR para caber na célula com margem
        max_qr_size = min(cell_w * 0.7, cell_h * 0.6)
        # Limita tamanho máximo absoluto para não ficar gigante se for só 1
        if max_qr_size > 5*cm: max_qr_size = 5*cm
        
        for i, code_obj in enumerate(codes):
            row = i // cols
            col = i % cols
            
            # Centro da célula
            cx = col * cell_w + cell_w/2
            cy = start_y - (row * cell_h) - cell_h/2
            
            # Label
            label = code_obj.get('label', '')
            c.setFont("Helvetica", 10)
            text_y = cy - max_qr_size/2 - 0.4*cm
            c.drawCentredString(cx, text_y, label)
            
            # QR Code
            qr_content = code_obj.get('code', '')
            if qr_content:
                qr = segno.make(qr_content)
                img_buf = io.BytesIO()
                qr.save(img_buf, kind='png', scale=5, border=0)
                img_buf.seek(0)
                
                img = ImageReader(img_buf)
                c.drawImage(img, cx - max_qr_size/2, cy - max_qr_size/2, width=max_qr_size, height=max_qr_size, mask='auto')
                
        c.showPage()
        
    c.save()
    pdf_content = buf.getvalue()
    return Response(content=pdf_content, media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="etiquetas_qr.pdf"'})

