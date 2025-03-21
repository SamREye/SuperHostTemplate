from typing import Union, Optional
import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, Form, File, UploadFile, Cookie, Request
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
app.mount("/static", StaticFiles(directory="static"), name="static")

client = MongoClient(os.getenv("MONGO_URL"))
domain = os.getenv("DOMAIN_NAME")
db_name = domain.replace('.', '-')
db = client[db_name]


@app.get("/robots.txt")
async def get_robots():
    from fastapi.responses import Response
    with open("static/robots.txt") as f:
        content = f.read().format(domain=domain)
    return Response(content, media_type="text/plain")


@app.get("/sitemap.xml")
async def get_sitemap():
    from fastapi.responses import Response
    pages = list(db.pages.find())

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Add home page
    xml += f'  <url>\n    <loc>https://{domain}/</loc>\n  </url>\n'

    # Add all pages
    for page in pages:
        xml += f'  <url>\n    <loc>https://{domain}/page/{page["path"]}</loc>\n  </url>\n'

    xml += '</urlset>'

    return Response(content=xml, media_type="application/xml")


# Setup Jinja2 templates
templates = Environment(loader=FileSystemLoader("templates"))
templates.filters["markdown"] = lambda text: markdown2.markdown(
    text) if text is not None else ""
fs = GridFS(db)


def verify_admin(session: Optional[str] = Cookie(None)) -> bool:
    if not session:
        return False
    return session == base64.b64encode(
        os.getenv("ADMIN_PASSWORD").encode()).decode()


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return templates.get_template("admin/login.html").render()


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
    return templates.get_template("admin/admin.html").render()


@app.get("/admin/pages", response_class=HTMLResponse)
async def list_pages(authorized: bool = Depends(verify_admin)):
    if not authorized:
        return RedirectResponse(url="/login")
    pages = list(db.pages.find())
    templates_list = [
        f for f in os.listdir("templates/pages") if f.endswith('.html')
    ]
    return templates.get_template("admin/pages.html").render(
        pages=pages, templates=templates_list)


@app.get("/admin/template-fields/{template}")
async def get_template_fields(template: str,
                              authorized: bool = Depends(verify_admin)):
    if not authorized:
        raise HTTPException(status_code=401)
    try:
        with open(f"templates/pages/{template}", "r") as f:
            content = f.read()
            # Find all {{ VAR }} patterns, including those with filters
            import re
            fields = re.findall(r'{{\s*(\w+)(?:\s*\|[^}]+)?\s*}}', content)
            return list(set(fields))  # Remove duplicates
    except:
        raise HTTPException(status_code=404)


@app.get("/admin/pages/{id}")
async def get_page(id: str, authorized: bool = Depends(verify_admin)):
    if not authorized:
        raise HTTPException(status_code=401)
    from bson.objectid import ObjectId
    page = db.pages.find_one({"_id": ObjectId(id)})
    if not page:
        raise HTTPException(status_code=404)
    page["_id"] = str(page["_id"])
    return page


@app.post("/admin/pages")
async def create_page(request: Request,
                      authorized: bool = Depends(verify_admin),
                      path: str = Form(...),
                      template: str = Form(...)):
    if not authorized:
        return RedirectResponse(url="/login")

    form = await request.form()
    content = {}
    pending_image_url = None

    for key, value in form.items():
        if key == "pending_image_url":
            pending_image_url = value
        elif key.startswith("field_"):
            field_name = key[6:]  # Remove 'field_' prefix
            content[field_name] = value

    # Handle pending image upload if exists
    if pending_image_url:
        try:
            response = requests.get(pending_image_url, verify=False)
            response.raise_for_status()

            filename = f"{path}.webp"
            file_id = fs.put(response.content, filename=filename)
            if file_id:
                content['image'] = f"/media/{filename}"
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"Failed to save image: {str(e)}")

    db.pages.insert_one({
        "path": path,
        "template": template,
        "content": content,
        "created_at": datetime.utcnow(),
        "modified_at": datetime.utcnow()
    })
    return RedirectResponse(url="/admin/pages", status_code=302)


@app.delete("/admin/pages/{id}")
async def delete_page(id: str, authorized: bool = Depends(verify_admin)):
    if not authorized:
        raise HTTPException(status_code=401)
    from bson.objectid import ObjectId
    result = db.pages.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"status": "success"}


@app.post("/admin/pages/{id}")
async def update_page(request: Request,
                      id: str,
                      authorized: bool = Depends(verify_admin)):
    if not authorized:
        return RedirectResponse(url="/login")

    from bson.objectid import ObjectId
    form = await request.form()
    content = {}
    pending_image_url = None

    for key, value in form.items():
        if key == "pending_image_url":
            pending_image_url = value
        elif key.startswith("field_"):
            field_name = key[6:]
            content[field_name] = value

    # Handle pending image upload if exists
    if pending_image_url:
        try:
            response = requests.get(pending_image_url, verify=False)
            response.raise_for_status()

            # Delete existing image if it exists
            page = db.pages.find_one({"_id": ObjectId(id)})
            filename = f"{page['path']}.webp"
            existing_file = fs.find_one({"filename": filename})
            if existing_file:
                fs.delete(existing_file._id)

            file_id = fs.put(response.content, filename=filename)
            if file_id:
                content['image'] = f"/media/{filename}"
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"Failed to save image: {str(e)}")

    from bson.objectid import ObjectId
    db.pages.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "content": content,
            "modified_at": datetime.utcnow()
        }})
    return RedirectResponse(url="/admin/pages", status_code=302)
    return RedirectResponse(url="/admin/pages", status_code=302)


@app.get("/admin/media", response_class=HTMLResponse)
async def list_media(authorized: bool = Depends(verify_admin)):
    if not authorized:
        return RedirectResponse(url="/login")
    files = fs.find()
    return templates.get_template("admin/media.html").render(files=files)


from pydantic import BaseModel


class UrlUpload(BaseModel):
    url: str
    slug: str


@app.post("/admin/media")
async def upload_media(authorized: bool = Depends(verify_admin),
                       file: UploadFile = File(...),
                       overwrite: bool = Form(False)):
    if not authorized:
        return RedirectResponse(url="/login")

    existing = fs.find_one({"filename": file.filename})
    if existing and not overwrite:
        return {"status": "confirm_overwrite", "filename": file.filename}

    if existing:
        fs.delete(existing._id)
    file_id = fs.put(file.file, filename=file.filename)
    return RedirectResponse(url="/admin/media", status_code=302)


@app.post("/upload_and_compress_image_from_url")
async def upload_from_url(upload: UrlUpload):
    url = upload.url
    slug = upload.slug
    if not slug:
        raise HTTPException(status_code=400, detail="Slug is required")
    import requests

    try:
        headers = {
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()

        filename = f"{slug}.webp"
        content_type = response.headers.get('content-type', '')

        if not content_type.startswith('image/'):
            raise HTTPException(status_code=400,
                                detail="URL does not point to an image")

        file_id = fs.put(response.content, filename=filename)
        if not file_id:
            raise HTTPException(status_code=500, detail="Failed to save file")

        return {"filename": filename, "id": str(file_id)}

    except requests.RequestException as e:
        raise HTTPException(status_code=400,
                            detail=f"Failed to fetch image: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.delete("/admin/media/{file_id}")
async def delete_media(file_id: str, authorized: bool = Depends(verify_admin)):
    if not authorized:
        raise HTTPException(status_code=401)
    try:
        from bson.objectid import ObjectId
        fs.delete(ObjectId(file_id))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/media/{filename:path}")
async def get_media(filename: str):
    from urllib.parse import unquote
    from fastapi.responses import Response
    import mimetypes

    decoded_filename = unquote(filename)
    file = fs.find_one({"filename": decoded_filename})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    content_type, _ = mimetypes.guess_type(decoded_filename)
    if not content_type:
        content_type = "application/octet-stream"

    headers = {"Content-Disposition": f"inline; filename={decoded_filename}"}
    return Response(file.read(), media_type=content_type, headers=headers)


@app.post("/admin/generate_image")
async def generate_image(prompt: dict):
    from prompting import generate_image
    return generate_image(prompt["prompt"])


@app.post("/admin/complement_article")
async def complement_article(content: dict,
                             authorized: bool = Depends(verify_admin)):
    if not authorized:
        raise HTTPException(status_code=401)
    from prompting import complement_article
    result = complement_article(content["content"])
    return result


@app.get("/")
async def read_root():
    template = templates.get_template("index.html")
    breadcrumbs = [{"name": "Home", "path": "/"}]
    return HTMLResponse(
        template.render(
            title=f"{domain} - Home",
            description="Welcome to our website",
            domain=domain,
            breadcrumbs=breadcrumbs
        ))


@app.get("/blog", response_class=HTMLResponse)
async def blog_index():
    articles = list(
        db.pages.find({
            "template": "article.html",
            "path": {
                "$regex": "^blog/"
            }
        }).sort("created_at", -1))

    breadcrumbs = [
        {"name": "Home", "path": "/"},
        {"name": "Blog", "path": "/blog"}
    ]
    
    template = templates.get_template("blog.html")
    return template.render(
        title="Blog",
        description="Latest blog posts",
        articles=articles,
        domain=domain,
        breadcrumbs=breadcrumbs
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    template = templates.get_template("error.html")
    return HTMLResponse(
        content=template.render(
            title="Page Not Found",
            error_message="The page you're looking for doesn't exist.",
            domain=domain,
            breadcrumbs=[{"name": "Home", "path": "/"}, {"name": "Error", "path": "#"}]
        ),
        status_code=404
    )

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    template = templates.get_template("error.html")
    return HTMLResponse(
        content=template.render(
            title="Server Error",
            error_message="An unexpected error occurred.",
            domain=domain,
            breadcrumbs=[{"name": "Home", "path": "/"}, {"name": "Error", "path": "#"}]
        ),
        status_code=500
    )

@app.get("/page/{path:path}", response_class=HTMLResponse)
async def get_page(path: str, request: Request):
    page = db.pages.find_one({"path": path})
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Build breadcrumbs based on path
    parts = path.split('/')
    breadcrumbs = [{"name": "Home", "path": "/"}]
    current_path = ""
    for part in parts:
        current_path += f"/{part}"
        breadcrumbs.append({
            "name": part.replace('-', ' ').title(),
            "path": f"/page{current_path}"
        })
    
    template_file = f"pages/{page['template']}"
    template = templates.get_template(template_file)
    return template.render(
        page=page,
        request=request,
        domain=domain,
        breadcrumbs=breadcrumbs,
        **page["content"]
    )
