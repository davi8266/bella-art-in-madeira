try:
    import fastapi
    import uvicorn
    import sqlite3
    print("Imports OK")
except Exception as e:
    print(f"Error: {e}")
