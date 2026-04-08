"""erp/decorators.py — Decorators de autenticação para as views da API."""
import functools
from django.http import JsonResponse


def login_required_api(view_func):
    """
    Decorator que verifica se o usuário está autenticado via sessão Django.
    Retorna 401 JSON se não estiver autenticado.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("usuario_id"):
            return JsonResponse({"error": "não autenticado"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper
