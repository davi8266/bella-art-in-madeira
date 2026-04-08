# Deploy do Bellart ERP no Render

## Como hospedar no Render (passo a passo)

### 1. Crie uma conta no Render
Acesse [render.com](https://render.com) e crie sua conta gratuita.

### 2. Suba o código para o GitHub
```bash
cd bellart_django
git init
git add .
git commit -m "Bellart ERP - Django"
# Crie um repositório no GitHub e faça o push
git remote add origin https://github.com/seu-usuario/bellart-erp.git
git push -u origin main
```

### 3. Crie o serviço no Render

**Opção A — via render.yaml (automático):**
- No painel do Render, clique em **"New" → "Blueprint"**
- Conecte o repositório GitHub
- O Render detecta o `render.yaml` e configura tudo automaticamente

**Opção B — manual:**
1. New → **Web Service**
2. Conecte o repositório
3. Configure:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py seed && python manage.py collectstatic --noinput`
   - **Start Command:** `gunicorn bellart.wsgi --log-file -`
4. Adicione as variáveis de ambiente:
   - `SECRET_KEY` → gere em https://djecrety.ir/
   - `DEBUG` → `False`
5. New → **PostgreSQL** → copie a `DATABASE_URL` e adicione nas env vars do web service

### 4. Variáveis de ambiente necessárias

| Variável | Valor | Obrigatório |
|---|---|---|
| `SECRET_KEY` | string aleatória longa | ✅ |
| `DEBUG` | `False` | ✅ |
| `DATABASE_URL` | URL do PostgreSQL do Render | ✅ em prod |

### 5. Acesso após deploy

- URL: `https://bellart-erp.onrender.com`
- Login padrão: **admin / admin**
- ⚠️ **Mude a senha do admin após o primeiro acesso!**

---

## Desenvolvimento local

```bash
# Instalar dependências
pip install -r requirements.txt

# Criar banco e dados iniciais
python manage.py migrate --run-syncdb
python manage.py seed

# Rodar servidor
python manage.py runserver
# Acesse: http://localhost:8000
```

---

## Estrutura do projeto

```
bellart_django/
├── bellart/          # Config Django (settings, urls, wsgi)
├── erp/              # App principal
│   ├── models.py     # Modelos Django ORM (12 tabelas)
│   ├── views/        # Views JSON por módulo
│   ├── templates/    # HTML (Django template)
│   ├── static/       # JS, CSS, ícones
│   ├── calc.py       # Cálculos financeiros
│   └── management/   # Comando: python manage.py seed
├── requirements.txt
├── Procfile          # Para Render/Heroku
└── render.yaml       # Deploy automático no Render
```
