
from typing import Union
import os
from fastapi import FastAPI
from pymongo import MongoClient

app = FastAPI()
client = MongoClient(os.getenv("MONGO_URL"))
db = client.get_default_database()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
