"""
erp/models.py — Modelos Django ORM para o Bellart ERP.
Mapeamento fiel do schema SQLite original para PostgreSQL via Django.
"""
import hashlib
import os
import uuid

from django.db import models


# ─── Usuários ────────────────────────────────────────────────────────────────

class Usuario(models.Model):
    username   = models.CharField(max_length=150, unique=True)
    senha_hash = models.CharField(max_length=255)
    salt       = models.CharField(max_length=64, blank=True, default="")
    ativo      = models.BooleanField(default=True)

    class Meta:
        db_table = "usuarios"
        verbose_name = "Usuário"

    def __str__(self):
        return self.username

    @staticmethod
    def hash_password(password: str) -> tuple[str, str]:
        """Retorna (salt_hex, hash_hex) usando pbkdf2_hmac."""
        salt = os.urandom(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return salt.hex(), h.hex()

    def verify_password(self, password: str) -> bool:
        if not self.salt:
            # Compatibilidade com senhas antigas (SHA-256 sem salt)
            legacy = hashlib.sha256(password.encode()).hexdigest()
            return legacy == self.senha_hash
        salt = bytes.fromhex(self.salt)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return h.hex() == self.senha_hash

    def set_password(self, password: str):
        self.salt, self.senha_hash = self.hash_password(password)


# ─── Plataformas ─────────────────────────────────────────────────────────────

class Plataforma(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "plataformas"
        verbose_name = "Plataforma"

    def __str__(self):
        return self.nome


# ─── Matérias-Primas ─────────────────────────────────────────────────────────

class MateriaPrima(models.Model):
    nome          = models.CharField(max_length=200, unique=True)
    unidade       = models.CharField(max_length=50, blank=True, default="")
    estoque_atual = models.FloatField(default=0)
    custo_medio   = models.FloatField(default=0)

    class Meta:
        db_table = "materias_primas"
        verbose_name = "Matéria-Prima"

    def __str__(self):
        return self.nome


# ─── Movimentos de Estoque ───────────────────────────────────────────────────

class MovimentoEstoque(models.Model):
    materia        = models.ForeignKey(MateriaPrima, on_delete=models.CASCADE,
                                       related_name="movimentos", db_column="materia_id")
    tipo           = models.CharField(max_length=20)  # "entrada" / "saida"
    quantidade     = models.FloatField()
    custo_unitario = models.FloatField(default=0)
    data           = models.CharField(max_length=10)  # "YYYY-MM-DD"
    ref            = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "movimentos_estoque"
        verbose_name = "Movimento de Estoque"


# ─── Produtos ────────────────────────────────────────────────────────────────

class Produto(models.Model):
    nome   = models.CharField(max_length=200, unique=True)
    sku    = models.CharField(max_length=100, blank=True, default="")
    codigo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    ativo  = models.BooleanField(default=True)

    class Meta:
        db_table = "produtos"
        verbose_name = "Produto"

    def __str__(self):
        return self.nome

    def ensure_codigo(self) -> str:
        """Garante que o produto tem um código único gerado."""
        if not self.codigo:
            self.codigo = "P" + uuid.uuid4().hex[:10].upper()
            self.save(update_fields=["codigo"])
        return self.codigo


# ─── Composição do Produto ───────────────────────────────────────────────────

class ProdutoComposicao(models.Model):
    produto               = models.ForeignKey(Produto, on_delete=models.CASCADE,
                                              related_name="composicoes", db_column="produto_id")
    materia               = models.ForeignKey(MateriaPrima, on_delete=models.CASCADE,
                                              db_column="materia_id")
    quantidade_por_unidade = models.FloatField()

    class Meta:
        db_table = "produto_composicao"
        verbose_name = "Composição"


# ─── Preços por Plataforma ───────────────────────────────────────────────────

class PrecoPlatforma(models.Model):
    produto    = models.ForeignKey(Produto, on_delete=models.CASCADE,
                                   related_name="precos", db_column="produto_id")
    plataforma = models.ForeignKey(Plataforma, on_delete=models.CASCADE,
                                   db_column="plataforma_id")
    preco_venda = models.FloatField(default=0)

    class Meta:
        db_table = "precos_plataforma"
        verbose_name = "Preço por Plataforma"
        unique_together = ("produto", "plataforma")


# ─── Taxas por Plataforma ────────────────────────────────────────────────────

class TaxaPlataforma(models.Model):
    plataforma          = models.OneToOneField(Plataforma, on_delete=models.CASCADE,
                                               related_name="taxa", db_column="plataforma_id")
    percentual          = models.FloatField(default=0)
    valor_fixo          = models.FloatField(default=0)
    imposto_percentual  = models.FloatField(default=0)

    class Meta:
        db_table = "taxas_plataforma"
        verbose_name = "Taxa de Plataforma"


# ─── Produção ────────────────────────────────────────────────────────────────

class Producao(models.Model):
    produto       = models.ForeignKey(Produto, on_delete=models.CASCADE,
                                      db_column="produto_id")
    quantidade    = models.IntegerField()
    data          = models.CharField(max_length=10)
    custo_extra   = models.FloatField(default=0)
    tempo_minutos = models.IntegerField(default=0)

    class Meta:
        db_table = "producao"
        verbose_name = "Produção"


# ─── Vendas ──────────────────────────────────────────────────────────────────

class Venda(models.Model):
    produto        = models.ForeignKey(Produto, on_delete=models.CASCADE,
                                       db_column="produto_id")
    plataforma     = models.ForeignKey(Plataforma, on_delete=models.CASCADE,
                                       db_column="plataforma_id")
    quantidade     = models.IntegerField(default=1)
    preco_aplicado = models.FloatField()
    data           = models.CharField(max_length=10)
    via_qr         = models.BooleanField(default=False)
    ml_mode        = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = "vendas"
        verbose_name = "Venda"


# ─── Configurações ───────────────────────────────────────────────────────────

class Configuracao(models.Model):
    chave = models.CharField(max_length=100, primary_key=True)
    valor = models.TextField(blank=True, default="")

    class Meta:
        db_table = "configuracoes"
        verbose_name = "Configuração"


# ─── QR Codes ────────────────────────────────────────────────────────────────

class QRCode(models.Model):
    produto    = models.ForeignKey(Produto, on_delete=models.CASCADE,
                                   db_column="produto_id")
    plataforma = models.ForeignKey(Plataforma, on_delete=models.CASCADE,
                                   db_column="plataforma_id")
    code       = models.CharField(max_length=100, unique=True)
    short_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    num_code   = models.CharField(max_length=20, unique=True, null=True, blank=True)
    ml_mode    = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = "qr_codes"
        verbose_name = "QR Code"
