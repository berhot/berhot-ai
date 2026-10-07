import uvicorn
import os


if __name__ == "__main__":
    uvicorn.run(
        "src.serving.server:app",
        host="127.0.0.1",
        port=int(os.environ.get("JSM_PORT", "8000")),
        reload=False,
        proxy_headers=False,
    )
