"""
run.py — Entry point do Bellart ERP
Execute:  python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8765, reload=False)
