from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from .config import settings
from .routes import manifest, agents, tools, messages, attachments, fiscal
from .storage import storage

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title=settings.app_title,
    description="Auditable economic gateway, fiscal governance engine, and multi-agent coordination system for AHP.",
    version=settings.app_version
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Favicon & OpenGraph assets matching nuts.services fleet
@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    target = STATIC_DIR / "favicon.ico"
    if target.exists():
        return FileResponse(target, media_type="image/x-icon")
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/favicon.png", include_in_schema=False)
async def favicon_png():
    return FileResponse(STATIC_DIR / "favicon.png", media_type="image/png")


@app.get("/favicon-192.png", include_in_schema=False)
async def favicon_192():
    return FileResponse(STATIC_DIR / "favicon-192.png", media_type="image/png")


@app.get("/favicon-512.png", include_in_schema=False)
async def favicon_512():
    return FileResponse(STATIC_DIR / "favicon-512.png", media_type="image/png")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon():
    return FileResponse(STATIC_DIR / "apple-touch-icon.png", media_type="image/png")


@app.get("/og-preview.png", include_in_schema=False)
async def og_preview():
    return FileResponse(STATIC_DIR / "og-preview.png", media_type="image/png")


# Include Routers
app.include_router(manifest.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(messages.router)
app.include_router(attachments.router)
app.include_router(fiscal.router)

# Dynamic OpenAPI Customization with x-ahp Metadata per AHP §4.2
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Inject x-ahp cost metadata for registered tools
    registered_tools = storage.list_tools()
    paths = openapi_schema.get("paths", {})
    
    for tool in registered_tools:
        tool_path = tool.get("path")
        if tool_path and tool_path in paths:
            for method in paths[tool_path]:
                paths[tool_path][method]["x-ahp"] = {
                    "cost": str(tool.get("cost", "0")),
                    "unit": tool.get("unit", "sat"),
                    "metered": tool.get("metered", False),
                    "per": tool.get("per"),
                    "free_quota": tool.get("free_quota")
                }
                
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    # User Rule 7: Bind to 0.0.0.0, not localhost
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
