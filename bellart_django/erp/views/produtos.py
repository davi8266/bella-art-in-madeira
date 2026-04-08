"""erp/views/produtos.py — CRUD de produtos e preços."""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from erp.models import Produto, Plataforma, PrecoPlatforma
from erp.decorators import login_required_api


@login_required_api
def api_produtos(request):
    produtos = Produto.objects.order_by("nome").values("id", "nome", "sku", "ativo")
    return JsonResponse(list(produtos), safe=False)


@login_required_api
@csrf_exempt
def api_product(request, pid=None):
    """
    POST   /api/products       → criar produto
    PUT    /api/products/{pid} → atualizar produto
    DELETE /api/products/{pid} → deletar produto
    """
    if request.method == "POST":
        data = json.loads(request.body)
        nome = data.get("nome", "").strip()
        sku  = data.get("sku", "").strip()
        if not nome:
            return JsonResponse({"error": "nome vazio"}, status=400)
        produto, created = Produto.objects.get_or_create(
            nome__iexact=nome,
            defaults={"nome": nome, "sku": sku, "ativo": True},
        )
        if not created:
            produto.sku   = sku
            produto.ativo = True
            produto.save(update_fields=["sku", "ativo"])
        return JsonResponse({"id": produto.id})

    elif request.method == "PUT":
        data = json.loads(request.body)
        try:
            produto = Produto.objects.get(pk=pid)
            produto.nome = data.get("nome", produto.nome).strip()
            produto.sku  = data.get("sku", produto.sku).strip()
            produto.save(update_fields=["nome", "sku"])
            return JsonResponse({"ok": True})
        except Produto.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

    elif request.method == "DELETE":
        try:
            produto = Produto.objects.get(pk=pid)
            produto.precos.all().delete()
            produto.composicoes.all().delete()
            produto.qr_codes.all().delete()
            produto.venda_set.all().delete()
            produto.producao_set.all().delete()
            produto.delete()
            return JsonResponse({"ok": True})
        except Produto.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_upload_photo_via_products(request, pid):
    """POST /api/products/{pid}/photo"""
    from django.conf import settings
    upload_dir = settings.MEDIA_ROOT / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{pid}.png"
    dest.write_bytes(request.body)
    return JsonResponse({"ok": True, "path": f"/media/uploads/{pid}.png"})


@login_required_api
def api_get_prices(request, pid):
    precos = (
        PrecoPlatforma.objects
        .filter(produto_id=pid)
        .select_related("plataforma")
    )
    result = {pp.plataforma.nome: float(pp.preco_venda) for pp in precos}
    return JsonResponse(result)


@login_required_api
@csrf_exempt
def api_set_price(request, pid):
    data = json.loads(request.body)
    plataforma_nome = data.get("plataforma")
    preco = float(data.get("preco", 0))
    try:
        plataforma = Plataforma.objects.get(nome=plataforma_nome)
    except Plataforma.DoesNotExist:
        return JsonResponse({"error": "plataforma não encontrada"}, status=404)
    PrecoPlatforma.objects.update_or_create(
        produto_id=pid,
        plataforma=plataforma,
        defaults={"preco_venda": preco},
    )
    return JsonResponse({"ok": True})


@login_required_api
def api_platforms(request):
    plataformas = (
        Plataforma.objects
        .exclude(nome="Mercado Livre")
        .order_by("nome")
        .values("id", "nome")
    )
    return JsonResponse(list(plataformas), safe=False)
