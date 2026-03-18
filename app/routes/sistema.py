import io
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime

from fastapi import APIRouter, Body
from fastapi.responses import Response

from app.db import BASE_DIR, ensure_initialized

router = APIRouter(prefix="/api", tags=["sistema"])
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")


def _db():
    return ensure_initialized()


@router.post("/exit")
def api_exit():
    def _do():
        time.sleep(0.2)
        os._exit(0)
    threading.Thread(target=_do, daemon=True).start()
    return {"ok": True}


@router.get("/network_info")
def api_network_info():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return {"ip": ip, "port": 8765}


def _build_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        db_path = os.path.join(BASE_DIR, "bellart.db")
        if os.path.exists(db_path):
            z.write(db_path, "bellart.db")
        if os.path.isdir(UPLOAD_DIR):
            for root, _, files in os.walk(UPLOAD_DIR):
                for f in files:
                    full = os.path.join(root, f)
                    z.write(full, os.path.join("uploads", os.path.relpath(full, UPLOAD_DIR)))
    return buf.getvalue()


@router.get("/backup")
def api_backup():
    return Response(_build_zip(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="bellart-backup.zip"'})


@router.post("/backup/save")
def api_backup_save(dest: str = "backups"):
    target = (os.path.join(os.path.expanduser("~"), "Downloads")
              if dest.lower() == "downloads"
              else os.path.join(BASE_DIR, "backups"))
    os.makedirs(target, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(target, f"bellart-backup-{ts}.zip")
    with open(path, "wb") as f:
        f.write(_build_zip())
    return {"ok": True, "path": path}


@router.post("/restore")
def api_restore(data: bytes = Body(...)):
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            names = z.namelist()
            if "bellart.db" in names:
                with z.open("bellart.db") as src:
                    with open(os.path.join(BASE_DIR, "bellart.db"), "wb") as dst:
                        dst.write(src.read())
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            for name in names:
                if name.startswith("uploads/") and not name.endswith("/"):
                    rel = name[len("uploads/"):].replace("\\", "/").strip("/")
                    dest = os.path.join(UPLOAD_DIR, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(name) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/login")
def api_login(data: dict = Body(...)):
    from app.db import verify_login
    conn = _db()
    u = verify_login(conn, str(data.get("username", "")).strip(), str(data.get("password", "")))
    if not u:
        return {"error": "login_invalido"}
    return {"ok": True, "user": {"id": u["id"], "username": u["username"]}}


@router.post("/users/password")
def api_change_password(data: dict = Body(...)):
    from app.db import change_password
    ok = change_password(_db(), str(data.get("username", "")).strip(),
                         str(data.get("old", "")), str(data.get("new", "")))
    return {"ok": True} if ok else {"error": "senha_invalida"}


@router.post("/products/{pid}/photo")
def api_upload_photo(pid: int, data: bytes = Body(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(UPLOAD_DIR, f"{pid}.png")
    with open(dest, "wb") as f:
        f.write(data)
    return {"ok": True, "path": f"/static/uploads/{pid}.png"}
