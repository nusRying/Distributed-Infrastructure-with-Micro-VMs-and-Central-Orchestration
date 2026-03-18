from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/test/{item_id}")
def test_post(item_id: str):
    return {"received": item_id}
