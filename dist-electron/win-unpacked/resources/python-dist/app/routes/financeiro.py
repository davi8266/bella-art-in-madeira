from fastapi import APIRouter, Body
from fastapi.responses import Response
from app.db import ensure_initialized, get_taxes, upsert_tax
from app.calc import platform_financials, store_financials, get_material_details

router = APIRouter(prefix="/api", tags=["financeiro"])


def _db():
    return ensure_initialized()


@router.get("/taxes")
def api_taxes():
    return get_taxes(_db())


@router.post("/taxes/{plataforma}")
def api_upsert_tax(plataforma: str, data: dict = Body(...)):
    upsert_tax(_db(), plataforma,
               float(data.get("percentual", 0)),
               float(data.get("fixo", 0)),
               float(data.get("imposto", 0)))
    return {"ok": True}


@router.get("/relatorios/{pid}")
def api_relatorios(pid: int):
    conn = _db()
    rows = platform_financials(conn, pid)
    mats = get_material_details(conn, pid)
    return [
        {
            "plataforma": r[0], "bruto": r[1], "taxa": r[2], "fixo": r[3],
            "imposto": r[4], "custo_total": r[5], "custo_mats": r[6],
            "impostos_total": r[8], "receita": r[9], "lucro_total": r[10],
            "lucro_mats": r[11], "margem": r[12], "materiais": mats,
        }
        for r in rows
    ]


@router.get("/reports/store")
def api_reports_store(start: str = None, end: str = None):
    return store_financials(_db(), start_date=start, end_date=end)


def _to_csv(headers, rows) -> str:
    q = lambda s: '"' + str(s).replace('"', '""') + '"'
    lines = [",".join(q(h) for h in headers)]
    lines += [",".join(q(c) for c in row) for row in rows]
    return "\n".join(lines)


@router.get("/export/rel/{pid}")
def api_export_rel(pid: int):
    rows = platform_financials(_db(), pid)
    headers = ["Plataforma","Bruto","Taxa","Imposto","Fixo",
               "Impostos Total","Receita","Lucro c/ Mats","Margem"]
    data = [[r[0], f"{r[1]:.2f}", f"{r[2]*100:.2f}", f"{r[4]*100:.2f}",
             f"{r[3]:.2f}", f"{r[8]:.2f}", f"{r[9]:.2f}", f"{r[11]:.2f}",
             f"{r[12]*100:.2f}"] for r in rows]
    return Response(_to_csv(headers, data), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="relatorios.csv"'})
