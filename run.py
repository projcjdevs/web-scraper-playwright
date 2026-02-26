import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        log_level="info",
        workers=1,

        timeout_graceful_shutdown=10,
    )