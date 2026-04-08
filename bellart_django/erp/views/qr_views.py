"""erp/views/qr_views.py — Geração, consulta e impressão de QR codes."""
import io
import json
import math
import time
import uuid

import segno
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from erp.models import QRCode, Produto, Plataforma, Venda, PrecoPlatforma
from erp.decorators import login_required_api
from erp.views.vendas import _resolve_ml_platform, _get_price


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "-", s.lower()).strip("-")


def _generate_short_code() -> str:
    return uuid.uuid4().hex[:6].upper()


def _generate_num_code() -> str:
    import random
    return str(random.randint(100_000, 999_999))


def _get_or_create_qr(produto_id: int, plataforma_id: int,
                      ml_mode: str | None = None, force: bool = False) -> str:
    qs = QRCode.objects.filter(produto_id=produto_id, plataforma_id=plataforma_id)
    if ml_mode:
        qs = qs.filter(ml_mode=ml_mode)
    else:
        qs = qs.filter(ml_mode__isnull=True)

    if not force and qs.exists():
        return qs.first().code

    if force:
        qs.delete()

    # Garante que o produto tem código
    produto = Produto.objects.get(pk=produto_id)
    produto.ensure_codigo()

    code = produto.codigo + "-" + uuid.uuid4().hex[:8].upper()
    short_code = _generate_short_code()
    num_code   = _generate_num_code()

    # Garante unicidade de short_code e num_code
    while QRCode.objects.filter(short_code=short_code).exists():
        short_code = _generate_short_code()
    while QRCode.objects.filter(num_code=num_code).exists():
        num_code = _generate_num_code()

    QRCode.objects.create(
        produto_id    = produto_id,
        plataforma_id = plataforma_id,
        code          = code,
        short_code    = short_code,
        num_code      = num_code,
        ml_mode       = ml_mode,
    )
    return code


def _get_qr_by_code(code: str) -> QRCode | None:
    clean = "".join(ch for ch in code if ch.isalnum())
    try:
        return QRCode.objects.get(code=clean)
    except QRCode.DoesNotExist:
        pass
    try:
        return QRCode.objects.get(short_code=clean)
    except QRCode.DoesNotExist:
        pass
    try:
        return QRCode.objects.get(num_code=clean)
    except QRCode.DoesNotExist:
        return None


def _build_qr_png(code: str, size: int) -> bytes:
    size = max(128, min(int(size), 2048))
    qr = segno.make(code, error="h")
    scale = next((s for s in range(2, 50) if max(qr.symbol_size(scale=s, border=2)) >= size), 50)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


def _render_qr_pdf(data: list) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(10 * cm, 15 * cm))
    for item in data:
        prod_name = item.get("nome", "Produto")
        codes     = item.get("codes", [])
        if not codes:
            continue
        c.setFont("Helvetica-Bold", 12 if len(prod_name) > 20 else 14)
        c.drawCentredString(5 * cm, 14 * cm, prod_name)
        cols   = 1 if len(codes) <= 2 else 2
        rows   = math.ceil(len(codes) / cols)
        cell_w = (10 * cm) / cols
        cell_h = (12.5 * cm) / rows
        max_qr = min(cell_w * 0.7, cell_h * 0.6, 5 * cm)
        for i, obj in enumerate(codes):
            cx = (i % cols) * cell_w + cell_w / 2
            cy = 13.5 * cm - (i // cols) * cell_h - cell_h / 2
            c.setFont("Helvetica", 10)
            c.drawCentredString(cx, cy - max_qr / 2 - 0.4 * cm, obj.get("label", ""))
            if obj.get("code"):
                qr  = segno.make(obj["code"])
                ib  = io.BytesIO()
                qr.save(ib, kind="png", scale=5, border=0)
                ib.seek(0)
                c.drawImage(ImageReader(ib), cx - max_qr / 2, cy - max_qr / 2,
                            width=max_qr, height=max_qr, mask="auto")
        c.showPage()
    c.save()
    return buf.getvalue()


# ─── Views ───────────────────────────────────────────────────────────────────

@login_required_api
def api_qr_lookup(request):
    code  = request.GET.get("code", "")
    clean = "".join(ch for ch in code if ch.isalnum()).strip()
    qr    = _get_qr_by_code(clean)
    if not qr:
        return JsonResponse({"error": "Código não encontrado"}, status=404)

    ml_mode = qr.ml_mode
    real_plat_id = _resolve_ml_platform(qr.plataforma_id, ml_mode)

    if ml_mode == "premium":
        plat_nome = "Mercado Livre Premium"
    elif ml_mode == "classico":
        plat_nome = "Mercado Livre Clássico"
    else:
        plat_nome = qr.plataforma.nome

    return JsonResponse({
        "produto_id":      qr.produto_id,
        "plataforma_id":   real_plat_id,
        "produto_nome":    qr.produto.nome,
        "plataforma_nome": plat_nome,
        "ml_mode":         ml_mode,
    })


@login_required_api
@csrf_exempt
def api_register_sale_by_qr(request):
    data      = json.loads(request.body)
    code      = "".join(ch for ch in str(data.get("code", "")) if ch.isalnum()).strip()
    quantidade = int(data.get("quantidade", 1))
    data_str  = data.get("data") or time.strftime("%Y-%m-%d")

    qr = _get_qr_by_code(code)
    if not qr:
        # Tenta usar produto_id/plataforma_id direto
        try:
            pid  = int(data["produto_id"])
            plid = int(data["plataforma_id"])
            Produto.objects.get(pk=pid)
            Plataforma.objects.get(pk=plid)
            ml_mode      = None
            real_plat_id = plid
            produto_id   = pid
        except Exception:
            return JsonResponse({"error": "codigo_invalido"}, status=404)
    else:
        ml_mode      = qr.ml_mode
        real_plat_id = _resolve_ml_platform(qr.plataforma_id, ml_mode)
        produto_id   = qr.produto_id

    preco = _get_price(produto_id, real_plat_id)
    venda = Venda.objects.create(
        produto_id     = produto_id,
        plataforma_id  = real_plat_id,
        quantidade     = quantidade,
        preco_aplicado = preco,
        data           = data_str,
        via_qr         = True,
        ml_mode        = ml_mode,
    )
    return JsonResponse({"id": venda.id, "produto_id": produto_id})


@login_required_api
@csrf_exempt
def api_generate_all_qrs_global(request):
    try:
        produtos   = Produto.objects.filter(ativo=True)
        plataformas = Plataforma.objects.all().order_by("nome")
        count = 0
        for produto in produtos:
            for plat in plataformas:
                if plat.nome.lower() == "mercado livre":
                    _get_or_create_qr(produto.id, plat.id, ml_mode="classico")
                    _get_or_create_qr(produto.id, plat.id, ml_mode="premium")
                    count += 2
                else:
                    _get_or_create_qr(produto.id, plat.id)
                    count += 1
        return JsonResponse({"ok": True, "count": count})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})


@login_required_api
@csrf_exempt
def api_generate_qr(request, pid):
    force = int(request.GET.get("force", 0))
    plataformas = Plataforma.objects.all().order_by("nome")
    out = []
    for plat in plataformas:
        if plat.nome.lower() == "mercado livre":
            c1 = _get_or_create_qr(pid, plat.id, force=bool(force), ml_mode="classico")
            c2 = _get_or_create_qr(pid, plat.id, force=bool(force), ml_mode="premium")
            out += [
                {"plataforma": "Mercado Livre Clássico", "code": c1, "ml_mode": "classico"},
                {"plataforma": "Mercado Livre Premium",  "code": c2, "ml_mode": "premium"},
            ]
        else:
            c = _get_or_create_qr(pid, plat.id, force=bool(force))
            out.append({"plataforma": plat.nome, "code": c, "ml_mode": None})
    return JsonResponse(out, safe=False)


@login_required_api
def api_get_qr(request, pid):
    qrs = QRCode.objects.filter(produto_id=pid).select_related("plataforma")
    result = [
        {
            "id":           q.id,
            "plataforma_id": q.plataforma_id,
            "plataforma":   q.plataforma.nome,
            "code":         q.code,
            "short_code":   q.short_code,
            "num_code":     q.num_code,
            "ml_mode":      q.ml_mode,
        }
        for q in qrs
    ]
    return JsonResponse(result, safe=False)


@login_required_api
@csrf_exempt
def api_qr_by_product(request, pid):
    """
    GET    /api/qr/{pid}          → listar QR codes
    POST   /api/qr/{pid}?force=1  → gerar QR codes
    DELETE /api/qr/{pid}          → deletar todos
    """
    if request.method == "GET":
        return api_get_qr(request, pid)
    elif request.method == "POST":
        return api_generate_qr(request, pid)
    elif request.method == "DELETE":
        QRCode.objects.filter(produto_id=pid).delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_qr_plat(request, pid, plat_id):
    """
    DELETE /api/qr/{pid}/{plat_id}[?ml_mode=...] → deletar QR específico
    """
    if request.method == "DELETE":
        ml_mode = request.GET.get("ml_mode")
        qs = QRCode.objects.filter(produto_id=pid, plataforma_id=plat_id)
        if ml_mode:
            qs = qs.filter(ml_mode=ml_mode)
        else:
            qs = qs.filter(ml_mode__isnull=True)
        qs.delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_delete_all_qr(request, pid):
    QRCode.objects.filter(produto_id=pid).delete()
    return JsonResponse({"ok": True})


@login_required_api
@csrf_exempt
def api_delete_qr(request, pid, plat_id):
    ml_mode = request.GET.get("ml_mode")
    qs = QRCode.objects.filter(produto_id=pid, plataforma_id=plat_id)
    if ml_mode:
        qs = qs.filter(ml_mode=ml_mode)
    else:
        qs = qs.filter(ml_mode__isnull=True)
    qs.delete()
    return JsonResponse({"ok": True})


@login_required_api
def api_qr_png(request, pid, plat_id):
    from datetime import datetime
    size    = int(request.GET.get("size", 512))
    ml_mode = request.GET.get("ml_mode")

    try:
        produto    = Produto.objects.get(pk=pid)
        plataforma = Plataforma.objects.get(pk=plat_id)
    except (Produto.DoesNotExist, Plataforma.DoesNotExist):
        return JsonResponse({"error": "not found"}, status=404)

    qs = QRCode.objects.filter(produto_id=pid, plataforma_id=plat_id)
    if ml_mode:
        qs = qs.filter(ml_mode=ml_mode)
    else:
        qs = qs.filter(ml_mode__isnull=True)

    qr_obj = qs.first()
    if not qr_obj:
        return JsonResponse({"error": "codigo_inexistente"}, status=404)

    img   = _build_qr_png(qr_obj.code, size)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    sku   = (produto.sku or produto.nome).strip()
    fname = f"qr-{_clean(plataforma.nome)}-{_clean(sku)}-{stamp}.png"

    response = HttpResponse(img, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@login_required_api
@csrf_exempt
def api_print_qrs(request):
    data = json.loads(request.body)
    pdf  = _render_qr_pdf(data)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="etiquetas_qr.pdf"'
    return response
