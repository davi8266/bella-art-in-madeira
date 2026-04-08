"""erp/views/materiais.py — CRUD de matérias-primas e composição de produtos."""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from erp.models import MateriaPrima, ProdutoComposicao
from erp.decorators import login_required_api


@login_required_api
@csrf_exempt
def api_materias(request):
    """
    GET  /api/materias  → listar
    POST /api/materias  → criar
    """
    if request.method == "GET":
        mats = MateriaPrima.objects.order_by("nome").values(
            "id", "nome", "unidade", "estoque_atual", "custo_medio"
        )
        result = [
            {"id": m["id"], "nome": m["nome"], "unidade": m["unidade"],
             "estoque": m["estoque_atual"], "custo": m["custo_medio"]}
            for m in mats
        ]
        return JsonResponse(result, safe=False)

    elif request.method == "POST":
        data = json.loads(request.body)
        m = MateriaPrima.objects.create(
            nome          = data.get("nome", "").strip(),
            unidade       = data.get("unidade", ""),
            estoque_atual = float(data.get("estoque", 0)),
            custo_medio   = float(data.get("custo", 0)),
        )
        return JsonResponse({"id": m.id})

    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_materia_detail(request, mid):
    """
    PUT    /api/materias/{mid} → atualizar
    DELETE /api/materias/{mid} → deletar
    """
    try:
        m = MateriaPrima.objects.get(pk=mid)
    except MateriaPrima.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    if request.method == "PUT":
        data = json.loads(request.body)
        m.nome          = data.get("nome", m.nome)
        m.unidade       = data.get("unidade", m.unidade)
        m.estoque_atual = float(data.get("estoque", m.estoque_atual))
        m.custo_medio   = float(data.get("custo", m.custo_medio))
        m.save()
        return JsonResponse({"ok": True})

    elif request.method == "DELETE":
        m.delete()
        return JsonResponse({"ok": True})

    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_get_composicao(request, pid):
    """
    GET    /api/composicao/{pid} → listar composição do produto
    PUT    /api/composicao/{pid} → atualizar item de composição (pid = cid aqui)
    DELETE /api/composicao/{pid} → deletar item de composição (pid = cid aqui)
    """
    if request.method == "GET":
        comps = (
            ProdutoComposicao.objects
            .filter(produto_id=pid)
            .select_related("materia")
        )
        result = [
            {"id": c.id, "materia": c.materia.nome, "unidade": c.materia.unidade,
             "qtd": c.quantidade_por_unidade, "custo_medio": c.materia.custo_medio}
            for c in comps
        ]
        return JsonResponse(result, safe=False)

    elif request.method == "PUT":
        data = json.loads(request.body)
        try:
            comp = ProdutoComposicao.objects.get(pk=pid)
            comp.quantidade_por_unidade = float(data.get("quantidade", 0))
            comp.save(update_fields=["quantidade_por_unidade"])
            return JsonResponse({"ok": True})
        except ProdutoComposicao.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

    elif request.method == "DELETE":
        try:
            ProdutoComposicao.objects.get(pk=pid).delete()
            return JsonResponse({"ok": True})
        except ProdutoComposicao.DoesNotExist:
            return JsonResponse({"error": "not found"}, status=404)

    return JsonResponse({"error": "method not allowed"}, status=405)


@login_required_api
@csrf_exempt
def api_composicao(request):
    """POST /api/composicao → criar item de composição."""
    if request.method == "POST":
        data = json.loads(request.body)
        ProdutoComposicao.objects.create(
            produto_id             = int(data["produto_id"]),
            materia_id             = int(data["materia_id"]),
            quantidade_por_unidade = float(data.get("quantidade", 0)),
        )
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "method not allowed"}, status=405)


# Alias para compatibilidade com imports existentes
api_composicao_detail = api_get_composicao
