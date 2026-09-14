from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()  # ← должен быть ДО любых других импортов

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
