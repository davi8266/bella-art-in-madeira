"""erp/views/financeiro.py — Relatórios financeiros e taxas."""
import csv
import io
import json

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from erp.models import Plataforma, TaxaPlataforma
from erp.calc import platform_financials, store_financials, get_material_details
from erp.decorators import login_required_api


@login_required_api
def api_taxes(request):
    taxas = TaxaPlataforma.objects.select_related("plataforma").all()
    result = {}
    for t in taxas:
        result[t.plataforma.nome] = {
            "percentual": t.percentual,
            "fixo":       t.valor_fixo,
            "imposto":    t.imposto_percentual,
        }
    return JsonResponse(result)


@login_required_api
@csrf_exempt
def api_upsert_tax(request, plataforma_nome):
    data = json.loads(request.body)
    try:
        plataforma = Plataforma.objects.get(nome=plataforma_nome)
    except Plataforma.DoesNotExist:
        return JsonResponse({"error": "plataforma não encontrada"}, status=404)

    TaxaPlataforma.objects.update_or_create(
        plataforma=plataforma,
        defaults={
            "percentual":         float(data.get("percentual", 0)),
            "valor_fixo":         float(data.get("fixo", 0)),
            "imposto_percentual": float(data.get("imposto", 0)),
        },
    )
    return JsonResponse({"ok": True})


@login_required_api
def api_relatorios(request, pid):
    rows = platform_financials(pid)
    mats = get_material_details(pid)
    result = [
        {
            "plataforma":    r[0],
            "bruto":         r[1],
            "taxa":          r[2],
            "fixo":          r[3],
            "imposto":       r[4],
            "custo_total":   r[5],
            "custo_mats":    r[6],
            "impostos_total": r[8],
            "receita":       r[9],
            "lucro_total":   r[10],
            "lucro_mats":    r[11],
            "margem":        r[12],
            "materiais":     mats,
        }
        for r in rows
    ]
    return JsonResponse(result, safe=False)


@login_required_api
def api_reports_store(request):
    start = request.GET.get("start")
    end   = request.GET.get("end")
    return JsonResponse(store_financials(start_date=start, end_date=end))


@login_required_api
def api_export_rel(request, pid):
    rows = platform_financials(pid)
    buf  = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Plataforma", "Bruto", "Taxa", "Imposto", "Fixo",
                     "Impostos Total", "Receita", "Lucro c/ Mats", "Margem"])
    for r in rows:
        writer.writerow([
            r[0], f"{r[1]:.2f}", f"{r[2]*100:.2f}", f"{r[4]*100:.2f}",
            f"{r[3]:.2f}", f"{r[8]:.2f}", f"{r[9]:.2f}", f"{r[11]:.2f}",
            f"{r[12]*100:.2f}",
        ])
    response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="relatorios.csv"'
    return response
