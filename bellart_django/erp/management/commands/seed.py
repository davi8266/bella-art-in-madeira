"""
Comando de management: python manage.py seed
Cria dados iniciais: admin, plataformas, materiais e produto exemplo.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed de dados iniciais do Bellart ERP"

    def handle(self, *args, **options):
        from erp.models import (
            Usuario, Plataforma, MateriaPrima, Produto,
            ProdutoComposicao, PrecoPlatforma, TaxaPlataforma, Configuracao,
        )

        # ── Usuário admin ──────────────────────────────────────────────────
        if not Usuario.objects.exists():
            admin = Usuario(username="admin")
            admin.set_password("admin")
            admin.save()
            self.stdout.write(self.style.SUCCESS("✓ Usuário admin criado (senha: admin)"))

        # ── Plataformas ────────────────────────────────────────────────────
        plataformas_nomes = [
            "Mercado Livre", "Mercado Livre Clássico", "Mercado Livre Premium",
            "Magalu", "Shopee",
        ]
        for nome in plataformas_nomes:
            p, created = Plataforma.objects.get_or_create(nome=nome)
            if created:
                TaxaPlataforma.objects.get_or_create(plataforma=p)
                self.stdout.write(f"  + Plataforma: {nome}")

        # ── Configurações ──────────────────────────────────────────────────
        Configuracao.objects.get_or_create(
            chave="custo_mao_obra_por_minuto",
            defaults={"valor": "0"},
        )

        # ── Matérias-primas ────────────────────────────────────────────────
        materiais = [
            ("MDF 6mm",  "placa", 1500, 50),
            ("Caixa 22", "un",    0,    0),
        ]
        for nome, und, est, custo in materiais:
            m, created = MateriaPrima.objects.get_or_create(
                nome=nome,
                defaults={"unidade": und, "estoque_atual": est, "custo_medio": custo},
            )
            if created:
                self.stdout.write(f"  + Matéria-prima: {nome}")

        # ── Produto exemplo ────────────────────────────────────────────────
        if not Produto.objects.exists():
            produto = Produto.objects.create(nome="Toalha", sku="TOA-001", ativo=True)
            produto.ensure_codigo()

            mdf   = MateriaPrima.objects.get(nome="MDF 6mm")
            caixa = MateriaPrima.objects.get(nome="Caixa 22")
            ProdutoComposicao.objects.create(produto=produto, materia=mdf,
                                              quantidade_por_unidade=1.0 / 6.0)
            ProdutoComposicao.objects.create(produto=produto, materia=caixa,
                                              quantidade_por_unidade=1.0)

            for nome_plat in ["Mercado Livre Clássico", "Mercado Livre Premium",
                               "Magalu", "Shopee"]:
                plat = Plataforma.objects.get(nome=nome_plat)
                PrecoPlatforma.objects.create(produto=produto, plataforma=plat,
                                               preco_venda=77.0)
            self.stdout.write(f"  + Produto: Toalha")

        self.stdout.write(self.style.SUCCESS("\n✅  Seed concluído!"))
