from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from .config import settings
from .routes import manifest, agents, tools, messages, attachments, fiscal
from .storage import storage

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
