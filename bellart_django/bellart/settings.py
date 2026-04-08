"""
bellart/settings.py — Configurações Django para Bellart ERP
Suporta desenvolvimento local (SQLite) e produção (PostgreSQL no Render).
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Segurança ───────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-change-in-production-bellart-2024"
)

DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ─── Apps ────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.messages",
    "erp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bellart.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bellart.wsgi.application"

# ─── Banco de Dados ──────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Produção: PostgreSQL no Render
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Desenvolvimento local: SQLite
    # Tenta usar a pasta data/ do projeto; se não conseguir escrever,
    # usa /tmp como fallback (útil em ambientes com filesystem de rede).
    import os as _os
    _data_dir = BASE_DIR / "data"
    _db_local  = _data_dir / "bellart.db"
    try:
        _data_dir.mkdir(parents=True, exist_ok=True)
        # Testa se consegue criar arquivo
        _test_file = _data_dir / ".write_test"
        _test_file.write_text("ok")
        _test_file.unlink()
        _db_path = _db_local
    except OSError:
        # Fallback: usa /tmp se a pasta do projeto for somente leitura
        _tmp_dir = Path("/tmp/bellart_data")
        _tmp_dir.mkdir(parents=True, exist_ok=True)
        _db_path = _tmp_dir / "bellart.db"

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _db_path,
        }
    }

# ─── Sessões ─────────────────────────────────────────────────────────────────

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 horas
SESSION_COOKIE_HTTPONLY = True

# ─── Internacionalização ─────────────────────────────────────────────────────

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ─── Arquivos Estáticos ───────────────────────────────────────────────────────

STATIC_URL = "/static/"

# Tenta escrever staticfiles na pasta do projeto;
# se não der (ex: filesystem de rede), usa /tmp como fallback.
_static_candidate = BASE_DIR / "staticfiles"
try:
    _static_candidate.mkdir(parents=True, exist_ok=True)
    _test = _static_candidate / ".write_test"
    _test.write_text("ok")
    _test.unlink()
    STATIC_ROOT = _static_candidate
except OSError:
    STATIC_ROOT = Path("/tmp/bellart_staticfiles")

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ─── Arquivos de Mídia (uploads de fotos) ────────────────────────────────────

MEDIA_URL = "/media/"
_media_candidate = BASE_DIR / "media"
try:
    _media_candidate.mkdir(parents=True, exist_ok=True)
    MEDIA_ROOT = _media_candidate
except OSError:
    MEDIA_ROOT = Path("/tmp/bellart_media")

# ─── Chave primária padrão ───────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
