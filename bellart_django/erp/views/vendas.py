"""erp/views/vendas.py — Registro e consulta de vendas."""
import csv
import io
import json
import time

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from erp.models import Venda, Plataforma, PrecoPlatforma
from erp.decorators import login_required_api


def _resolve_ml_platform(plataforma_id: int, ml_mode: str | None) -> int:
    """Retorna o ID correto da plataforma com base no ml_mode."""
    if not ml_mode:
        return plataforma_id
    mapping = {
        "premium":  "Mercado Livre Premium",
        "classico": "Mercado Livre Clássico",
    }
    nome_alvo = mapping.get((ml_mode or "").lower())
    if nome_alvo:
        try:
            return Plataforma.objects.get(nome=nome_alvo).id
        except Plataforma.DoesNotExist:
            pass
    return plataforma_id


def _get_price(produto_id: int, plataforma_id: int) -> float:
    try:
        pp = PrecoPlatforma.objects.get(produto_id=produto_id, plataforma_id=plataforma_id)
        return float(pp.preco_venda)
    except PrecoPlatforma.DoesNotExist:
        return 0.0


@login_required_api
@csrf_exempt
def api_get_vendas(request, vid):
    """
    GET    /api/vendas/{pid} → listar vendas do produto
    DELETE /api/vendas/{vid} → deletar venda específica
    """
    if request.method == "GET":
        vendas = (
            Venda.objects
            .filter(produto_id=vid)
            .select_related("plataforma", "produto")
            .order_by("-data", "-id")
        )
        result = [
            {
                "id":           v.id,
                "plataforma":   v.plataforma.nome,
                "quantidade":   v.quantidade,
                "preco":        v.preco_aplicado,
                "data":         v.data,
                "via_qr":       int(v.via_qr or 0),
                "produto_nome": v.produto.nome,
                "ml_mode":      v.ml_mode,
            }
            for v in vendas
        ]
        return JsonResponse(result, safe=False)

    elif request.method == "DELETE":
        try:
            Venda.objects.get(pk=vid).delete()
            return JsonResponse({"ok": True})
        except Venda.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_venda_detail(request, vid):
    """DELETE /api/vendas/{vid} — alias kept for compatibility."""
    return api_get_vendas(request, vid)


@login_required_api
@csrf_exempt
def api_vendas(request):
    """POST /api/vendas → registrar venda."""
    if request.method == "POST":
        data         = json.loads(request.body)
        produto_id   = int(data["produto_id"])
        plataforma_id = int(data["plataforma_id"])
        quantidade   = int(data.get("quantidade", 1))
        ml_mode      = data.get("ml_mode") or None
        data_str     = data.get("data") or time.strftime("%Y-%m-%d")

        real_plat_id = _resolve_ml_platform(plataforma_id, ml_mode)
        preco        = _get_price(produto_id, real_plat_id)

        venda = Venda.objects.create(
            produto_id     = produto_id,
            plataforma_id  = real_plat_id,
            quantidade     = quantidade,
            preco_aplicado = preco,
            data           = data_str,
            via_qr         = False,
            ml_mode        = ml_mode,
        )
        return JsonResponse({"id": venda.id})
    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_venda_detail(request, vid):
    """DELETE /api/vendas/{vid} → deletar venda."""
    if request.method == "DELETE":
        try:
            Venda.objects.get(pk=vid).delete()
            return JsonResponse({"ok": True})
        except Venda.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)
    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_vendas_batch(request):
    """POST /api/vendas/batch → registrar múltiplas vendas."""
    if request.method == "POST":
        items = json.loads(request.body)
        count = 0
        for item in items:
            pid  = item.get("produto_id")
            plid = item.get("plataforma_id")
            if not (pid and plid):
                continue
            ml_mode   = item.get("ml_mode") or None
            real_plid = _resolve_ml_platform(int(plid), ml_mode)
            preco     = _get_price(int(pid), real_plid)
            dt        = item.get("data") or time.strftime("%Y-%m-%d")
            Venda.objects.create(
                produto_id     = int(pid),
                plataforma_id  = real_plid,
                quantidade     = int(item.get("quantidade", 1)),
                preco_aplicado = preco,
                data           = dt,
                via_qr         = True,
                ml_mode        = ml_mode,
            )
            count += 1
        return JsonResponse({"ok": True, "count": count})
    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
def api_export_vendas(request, pid):
    vendas = (
        Venda.objects
        .filter(produto_id=pid)
        .select_related("plataforma")
        .order_by("data")
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Plataforma", "Quantidade", "Preço", "Data"])
    for v in vendas:
        writer.writerow([v.plataforma.nome, v.quantidade, f"{v.preco_aplicado:.2f}", v.data])

    response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="vendas.csv"'
    return response
