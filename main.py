from typing import Union, Optional
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Form, File, UploadFile, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from gridfs import GridFS
from jinja2 import Environment, FileSystemLoader
import markdown2
import secrets
import base64

app = FastAPI()
client = MongoClient(os.getenv("MONGO_URL"))
domain = os.getenv("DOMAIN_NAME")
db_name = domain.replace('.', '-')
db = client[db_name]

# Setup Jinja2 templates
templates = Environment(loader=FileSystemLoader("templates"))
fs = GridFS(db)


def verify_admin(session: Optional[str] = Cookie(None)) -> bool:
    if not session:
        return False
    return session == base64.b64encode(
        os.getenv("ADMIN_PASSWORD").encode()).decode()


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return templates.get_template("login.html").render()


@app.post("/login")
async def login(password: str = Form(...)):
    if password == os.getenv("ADMIN_PASSWORD"):
        response = RedirectResponse(url="/admin", status_code=302)
        session = base64.b64encode(password.encode()).decode()
        response.set_cookie(key="session", value=session)
        return response
    raise HTTPException(status_code=401)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(authorized: bool = Depends(verify_admin)):
    if not authorized:
        return RedirectResponse(url="/login")
    return templates.get_template("admin.html").render()


@app.get("/admin/pages", response_class=HTMLResponse)
async def list_pages(authorized: bool = Depends(verify_admin)):
    if not authorized:
        return RedirectResponse(url="/login")
    pages = list(db.pages.find())
    return templates.get_template("pages.html").render(pages=pages)


@app.post("/admin/pages")
async def create_page(authorized: bool = Depends(verify_admin),
                      path: str = Form(...),
                      title: str = Form(...),
                      description: str = Form(...),
                      template: str = Form(...),
                      content: str = Form(...)):
    if not authorized:
        return RedirectResponse(url="/login")
    db.pages.insert_one({
        "path": path,
        "title": title,
        "description": description,
        "template": template,
        "content": content,
        "created_at": datetime.utcnow()
    })
    return RedirectResponse(url="/admin/pages", status_code=302)


@app.get("/admin/media", response_class=HTMLResponse)
async def list_media(authorized: bool = Depends(verify_admin)):
    if not authorized:
        return RedirectResponse(url="/login")
    files = fs.find()
    return templates.get_template("media.html").render(files=files)


@app.post("/admin/media")
async def upload_media(authorized: bool = Depends(verify_admin),
                       file: UploadFile = File(...)):
    if not authorized:
        return RedirectResponse(url="/login")
    file_id = fs.put(file.file, filename=file.filename)
    return RedirectResponse(url="/admin/media", status_code=302)


@app.delete("/admin/media/{file_id}")
async def delete_media(file_id: str, authorized: bool = Depends(verify_admin)):
    if not authorized:
        raise HTTPException(status_code=401)
    fs.delete(file_id)
    return {"status": "success"}


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/page/{path:path}", response_class=HTMLResponse)
async def get_page(path: str):
    print(path)
    page = db.pages.find_one({"path": path})
    print(page)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    template = templates.get_template("base.html")
    return template.render(title=page.get("title", "Page"),
                           content=page.get("content", {}))
