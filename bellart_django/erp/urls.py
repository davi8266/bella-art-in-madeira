"""erp/urls.py — Rotas que espelham exatamente as rotas FastAPI originais."""
from django.urls import path
from django.views.generic import TemplateView

from erp.views import vendas, financeiro, sistema
from erp.views import qr_views as qr
from erp.views.produtos import (
    api_produtos, api_product, api_upload_photo_via_products,
    api_get_prices, api_set_price, api_platforms,
)
from erp.views.materiais import (
    api_materias, api_materia_detail, api_get_composicao,
    api_composicao, api_composicao_detail,
)

urlpatterns = [
    # ── Página principal (SPA) ─────────────────────────────────────────────
    path("", TemplateView.as_view(template_name="erp/index.html"), name="index"),

    # ── Auth ───────────────────────────────────────────────────────────────
    path("api/login",           sistema.api_login,           name="api_login"),
    path("api/logout",          sistema.api_logout,          name="api_logout"),
    path("api/users/password",  sistema.api_change_password, name="api_change_password"),

    # ── Sistema ────────────────────────────────────────────────────────────
    path("api/network_info",    sistema.api_network_info,    name="api_network_info"),
    path("api/exit",            sistema.api_exit,            name="api_exit"),
    path("api/backup",          sistema.api_backup,          name="api_backup"),
    path("api/backup/save",     sistema.api_backup_save,     name="api_backup_save"),
    path("api/restore",         sistema.api_restore,         name="api_restore"),

    # ── Produtos (GET lista, POST criar) ───────────────────────────────────
    path("api/produtos",                  api_produtos,      name="api_produtos"),
    path("api/products",                  api_product,       name="api_add_product"),
    # PUT update / DELETE delete — mesmo URL, método diferente
    path("api/products/<int:pid>",        api_product,       name="api_product_detail"),
    # Upload de foto
    path("api/products/<int:pid>/photo",  api_upload_photo_via_products, name="api_upload_photo"),

    # ── Preços ─────────────────────────────────────────────────────────────
    path("api/prices/<int:pid>",          api_get_prices,    name="api_get_prices"),
    path("api/prices/<int:pid>/set",      api_set_price,     name="api_set_price"),  # alias para POST
    path("api/platforms",                 api_platforms,     name="api_platforms"),

    # ── Matérias-primas ────────────────────────────────────────────────────
    path("api/materias",                  api_materias,      name="api_materias"),
    path("api/materias/<int:mid>",        api_materia_detail, name="api_materia_detail"),

    # ── Composição ─────────────────────────────────────────────────────────
    path("api/composicao/<int:pid>",      api_get_composicao,    name="api_get_composicao"),
    path("api/composicao",                api_composicao,        name="api_composicao"),
    path("api/composicao/<int:cid>",      api_composicao_detail, name="api_composicao_detail"),

    # ── Vendas ─────────────────────────────────────────────────────────────
    path("api/vendas/batch",              vendas.api_vendas_batch,  name="api_vendas_batch"),
    path("api/vendas/<int:pid>",          vendas.api_get_vendas,    name="api_get_vendas"),
    path("api/vendas",                    vendas.api_vendas,        name="api_vendas"),
    path("api/vendas/<int:vid>",          vendas.api_venda_detail,  name="api_venda_detail"),
    path("api/export/vendas/<int:pid>",   vendas.api_export_vendas, name="api_export_vendas"),

    # ── Financeiro ─────────────────────────────────────────────────────────
    path("api/taxes",                     financeiro.api_taxes,       name="api_taxes"),
    path("api/taxes/<str:plataforma_nome>", financeiro.api_upsert_tax, name="api_upsert_tax"),
    path("api/relatorios/<int:pid>",      financeiro.api_relatorios,  name="api_relatorios"),
    path("api/reports/store",             financeiro.api_reports_store, name="api_reports_store"),
    path("api/export/rel/<int:pid>",      financeiro.api_export_rel,  name="api_export_rel"),

    # ── QR Codes ───────────────────────────────────────────────────────────
    path("api/qr/lookup",                 qr.api_qr_lookup,              name="api_qr_lookup"),
    path("api/qr/register",              qr.api_register_sale_by_qr,    name="api_qr_register"),
    path("api/qr/generate_all_global",   qr.api_generate_all_qrs_global, name="api_qr_generate_all"),
    path("api/print_qrs",                qr.api_print_qrs,              name="api_print_qrs"),
    # GET / POST / DELETE por produto
    path("api/qr/<int:pid>",             qr.api_qr_by_product,          name="api_qr_by_product"),
    # GET / DELETE por produto+plataforma
    path("api/qr/png/<int:pid>/<int:plat_id>", qr.api_qr_png,           name="api_qr_png"),
    path("api/qr/<int:pid>/<int:plat_id>",     qr.api_qr_plat,          name="api_qr_plat"),
]
