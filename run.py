"""
Entry point — run with: python run.py
Or production: uvicorn api:app --host 0.0.0.0 --port 5000 --workers 1
"""
import uvicorn
from config import API_PORT

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=API_PORT,
        log_level="info",
    )
