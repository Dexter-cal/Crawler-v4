from fastapi import FastAPI
from . import api

app = FastAPI()

app.include_router(api.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Crawler C2 is operational."}
