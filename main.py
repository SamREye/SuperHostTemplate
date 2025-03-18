from typing import Union
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from jinja2 import Environment, FileSystemLoader
import markdown2

app = FastAPI()
client = MongoClient(os.getenv("MONGO_URL"))
db = client[os.getenv("DOMAIN_NAME")]

# Setup Jinja2 templates
templates = Environment(loader=FileSystemLoader("templates"))

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/page/{path}", response_class=HTMLResponse)
async def get_page(path: str):
    page = db.pages.find_one({"path": path})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    template = templates.get_template("base.html")
    return template.render(
        title=page.get("title", "Page"),
        content=page.get("content", {})
    )

