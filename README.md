# Bellart ERP — Bella Art in Madeira

Sistema de gestão (ERP) para controle de produtos, estoque, vendas, relatórios financeiros e QR codes.

---

## Requisitos

- **Python 3.11** — [python.org/downloads/release/python-3119](https://www.python.org/downloads/release/python-3119/)
  > ⚠️ Na instalação, marque a opção **"Add Python to PATH"** antes de instalar.

---

## Instalação

### 1. Obter o projeto

**Via Git:**
```bash
git clone https://github.com/davi8266/bella-art-in-madeira
cd bella-art-in-madeira
```

**Via ZIP:** extraia a pasta e abra o terminal dentro dela.

---

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

---

### 3. Rodar

**Como aplicação desktop (recomendado):**
```bash
python run_webview.py
```

**Como servidor web (acessível na rede local):**
```bash
python run.py
```
Depois acesse `http://127.0.0.1:8765` no navegador.

---

## Acesso padrão

| Campo | Valor |
|-------|-------|
| Usuário | `admin` |
| Senha | `admin` |

> Troque a senha após o primeiro acesso em **Perfil → Alterar Senha**.

---

## Estrutura do projeto

```
bella-art-in-madeira/
├── app/                    # Código Python (backend)
│   ├── main.py             # Servidor FastAPI
│   ├── db.py               # Banco de dados (SQLite)
│   ├── calc.py             # Cálculos financeiros
│   ├── utils.py            # Utilitários
│   └── routes/             # Rotas da API por módulo
│       ├── produtos.py
│       ├── materiais.py
│       ├── financeiro.py
│       ├── vendas.py
│       ├── qr.py
│       └── sistema.py
├── frontend/               # Interface web
│   ├── web/                # HTML, CSS, JS
│   ├── static/             # Imagens e ícones
│   └── assets/
├── scripts/                # Scripts utilitários
├── data/                   # Banco de dados (gerado automaticamente)
├── run.py                  # Iniciar como servidor web
├── run_webview.py          # Iniciar como app desktop
└── requirements.txt        # Dependências Python
```

---

## Funcionalidades

- **Relatórios** — visão geral da loja e análise por produto
- **Produtos** — cadastro, preços por plataforma, composição de materiais, fotos, QR codes
- **Materiais** — controle de estoque de matérias-primas
- **Vendas** — registro manual ou por leitura de QR code (lote ou individual)
- **Configurações** — taxas por plataforma (ML Clássico, ML Premium, Magalu, Shopee), backup e restauração
- **Auditoria** — histórico de todas as ações realizadas no sistema

---

## Modo servidor (acesso de outras máquinas na rede)

1. Rode `python run_webview.py` na máquina **servidora**
2. Anote o IP exibido no terminal (ex: `192.168.1.100`)
3. Nos outros computadores, abra o navegador e acesse `http://192.168.1.100:8765`

Para configurar uma máquina como **cliente fixo**, edite `data/bellart.ini`:
```ini
[Network]
mode = client
server_ip = 192.168.1.100
```

---

## Backup e restauração

- **Exportar:** Configurações → Exportar Backup (gera um `.zip` com banco + fotos)
- **Importar:** Configurações → Escolher Arquivo → Importar Backup
- **Backup automático local:** Configurações → Salvar Direto (salva na pasta `Downloads`)

---

## Dependências

| Pacote | Versão | Uso |
|--------|--------|-----|
| fastapi | 0.115 | Servidor web / API |
| uvicorn | 0.34 | Servidor ASGI |
| segno | 1.6 | Geração de QR codes |
| reportlab | 4.4 | Geração de PDFs |
| pywebview | 5.1 | Janela desktop |

---

## Problemas comuns

**`pip` não reconhecido:**
```bash
python -m pip install -r requirements.txt
```

**Erro ao instalar pywebview no Python 3.12+:**
Use Python 3.11 — versões mais novas ainda não têm suporte completo.

**Porta 8765 já em uso:**
Edite `run.py` e `run_webview.py` alterando `PORT = 8765` para outra porta livre.

**Banco de dados não encontrado:**
O arquivo `data/bellart.db` é criado automaticamente na primeira execução.
