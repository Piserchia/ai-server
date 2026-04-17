"""<NAME> — FastAPI service."""

from fastapi import FastAPI

app = FastAPI(title="<NAME>")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"name": "<NAME>", "status": "running"}
