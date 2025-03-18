
# FastAPI CMS Template

A simple Content Management System (CMS) built with FastAPI and MongoDB, designed for easy content management and media handling.

## Features

- Admin dashboard with authentication
- Page management with customizable templates
- Media upload and management
- MongoDB integration for data storage
- Template-based content rendering

## Getting Started

1. Click "Use Template" to create your own Repl
2. Set up your environment secrets in the Secrets tab:
   - `MONGO_URL`: Your MongoDB connection string
   - `ADMIN_PASSWORD`: Password for accessing the admin dashboard
   - `DOMAIN_NAME`: Your site's domain name

## Usage

### Admin Access
1. Access `/admin` and log in with your admin password
2. Navigate through the dashboard to manage:
   - Pages: Create and edit content pages
   - Media: Upload and manage files

### Page Management
1. Create new pages by selecting a template
2. Fill in the template fields
3. Access your pages at `/page/{path}`

### Media Management
1. Upload files through the media dashboard
2. Files are stored in MongoDB GridFS
3. Access media files at `/media/{filename}`

### Templates
Templates are stored in `templates/pages/`. Create new templates by adding HTML files with Jinja2 variables:
```html
<title>{{ title }}</title>
<meta name="description" content="{{ description }}">
<main>{{ content }}</main>
```

## Development

The application runs on port 8000 by default. Main components:

- `main.py`: Core application logic
- `templates/`: HTML templates
- `templates/admin/`: Admin interface templates
- `templates/pages/`: Page templates

## Security

- Admin authentication required for management
- Secure file handling with GridFS
- Environment variables for sensitive data
