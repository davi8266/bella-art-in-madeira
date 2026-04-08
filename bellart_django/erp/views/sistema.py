"""erp/views/sistema.py — Login, upload de foto, backup e sistema."""
import io
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from erp.models import Usuario
from erp.decorators import login_required_api


# ─── Autenticação ─────────────────────────────────────────────────────────────

@csrf_exempt
def api_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    data     = json.loads(request.body)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    try:
        usuario = Usuario.objects.get(username__iexact=username, ativo=True)
    except Usuario.DoesNotExist:
        return JsonResponse({"error": "login_invalido"})

    if not usuario.verify_password(password):
        return JsonResponse({"error": "login_invalido"})

    request.session["usuario_id"]   = usuario.id
    request.session["usuario_nome"] = usuario.username
    return JsonResponse({"ok": True, "user": {"id": usuario.id, "username": usuario.username}})


@login_required_api
@csrf_exempt
def api_logout(request):
    request.session.flush()
    return JsonResponse({"ok": True})


@login_required_api
@csrf_exempt
def api_change_password(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    data     = json.loads(request.body)
    username = str(data.get("username", "")).strip()
    old_pw   = str(data.get("old", ""))
    new_pw   = str(data.get("new", ""))

    try:
        usuario = Usuario.objects.get(username__iexact=username, ativo=True)
    except Usuario.DoesNotExist:
        return JsonResponse({"error": "senha_invalida"})

    if not usuario.verify_password(old_pw):
        return JsonResponse({"error": "senha_invalida"})

    usuario.set_password(new_pw)
    usuario.save(update_fields=["senha_hash", "salt"])
    return JsonResponse({"ok": True})


# ─── Upload de Foto ──────────────────────────────────────────────────────────

@login_required_api
@csrf_exempt
def api_upload_photo(request, pid):
    """POST /api/products/{pid}/photo"""
    upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{pid}.png"
    dest.write_bytes(request.body)
    return JsonResponse({"ok": True, "path": f"/media/uploads/{pid}.png"})


# ─── Informações de Rede ──────────────────────────────────────────────────────

@login_required_api
def api_network_info(request):
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return JsonResponse({"ip": ip, "port": 8000})


# ─── Exit (web: faz logout em vez de fechar o processo) ───────────────────────

@login_required_api
@csrf_exempt
def api_exit(request):
    """No modo web, 'sair' = logout da sessão."""
    request.session.flush()
    return JsonResponse({"ok": True})


# ─── Backup / Restore ────────────────────────────────────────────────────────

def _build_zip() -> bytes:
    buf        = io.BytesIO()
    db_name    = settings.DATABASES["default"].get("NAME", "")
    upload_dir = Path(settings.MEDIA_ROOT) / "uploads"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Só inclui o arquivo .db se for SQLite local
        if str(db_name).endswith(".db") and os.path.exists(str(db_name)):
            z.write(str(db_name), "bellart.db")
        if upload_dir.is_dir():
            for f in upload_dir.rglob("*"):
                if f.is_file():
                    z.write(str(f), f"uploads/{f.relative_to(upload_dir)}")
    return buf.getvalue()


@login_required_api
def api_backup(request):
    data     = _build_zip()
    response = HttpResponse(data, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="bellart-backup.zip"'
    return response


@login_required_api
@csrf_exempt
def api_backup_save(request):
    """POST /api/backup/save — salva backup em pasta local (ambiente desktop)."""
    dest_param = request.GET.get("dest", "backups")
    if dest_param.lower() == "downloads":
        target = Path.home() / "Downloads"
    else:
        target = Path(settings.BASE_DIR) / "backups"
    target.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target / f"bellart-backup-{ts}.zip"
    path.write_bytes(_build_zip())
    return JsonResponse({"ok": True, "path": str(path)})


@login_required_api
@csrf_exempt
def api_restore(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    try:
        upload_dir = Path(settings.MEDIA_ROOT) / "uploads"
        with zipfile.ZipFile(io.BytesIO(request.body), "r") as z:
            names = z.namelist()
            if "bellart.db" in names:
                db_name = str(settings.DATABASES["default"].get("NAME", ""))
                if db_name.endswith(".db"):
                    os.makedirs(os.path.dirname(db_name), exist_ok=True)
                    with z.open("bellart.db") as src:
                        with open(db_name, "wb") as dst:
                            dst.write(src.read())
            upload_dir.mkdir(parents=True, exist_ok=True)
            for name in names:
                if name.startswith("uploads/") and not name.endswith("/"):
                    rel  = name[len("uploads/"):].replace("\\", "/").strip("/")
                    dest = upload_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(name) as src:
                        dest.write_bytes(src.read())
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})
