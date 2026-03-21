"""
run.py — Entry point do Bellart ERP
Execute:  python run.py
"""
import sys
import os

# No Python embeddable, o diretório do script não é adicionado ao sys.path
# automaticamente. Precisamos fazer isso manualmente para que o módulo 'app' seja encontrado.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8765, reload=False)
