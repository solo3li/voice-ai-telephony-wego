# SPDX-License-Identifier: Apache-2.0
import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("universal-mcp-gateway")

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)
TENANTS_FILE = os.path.join(DATA_DIR, "tenants.json")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
INDEX_HTML_PATH = os.path.join(TEMPLATES_DIR, "index.html")

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "http://chatwoot_rails:3000")
CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_TOKEN", "jXAkbazr7faTZWeoNbVf8Lt2")
PUBLIC_BRIDGE_URL = os.getenv("PUBLIC_BRIDGE_URL", "https://mcp.169.58.32.179.nip.io")

app = FastAPI(
    title="Universal Multi-Tenant FastMCP Gateway",
    description="Universal gateway connecting Voice AI and Chatwoot to any dynamic FastMCP server per tenant.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    if "X-Frame-Options" in response.headers:
        del response.headers["X-Frame-Options"]
    return response

class TenantConfig(BaseModel):
    tenant_id: str
    name: str
    mcp_url: str
    access_token: Optional[str] = None
    chatwoot_account_id: Optional[int] = 2
    chatwoot_assistant_id: Optional[int] = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# In-memory tenant registry
tenants_db: Dict[str, TenantConfig] = {}
# Cached tools per tenant
cached_tools: Dict[str, List[Dict[str, Any]]] = {}

def load_tenants_from_disk():
    global tenants_db
    if os.path.exists(TENANTS_FILE):
        try:
            with open(TENANTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    t = TenantConfig(**item)
                    tenants_db[t.tenant_id] = t
            logger.info(f"Loaded {len(tenants_db)} tenants from {TENANTS_FILE}")
        except Exception as e:
            logger.error(f"Error loading tenants file: {e}")

    # Seed default tenant 1 if empty
    if "1" not in tenants_db:
        t1 = TenantConfig(
            tenant_id="1",
            name="سلسلة مطاعم كُـورَا",
            mcp_url="https://uggu.space/sse",
            access_token="ak_live_DXm-0yhymjVa8OU5lUWNkxmoxpxUEI2BR3aGj1iuR8k",
            chatwoot_account_id=2,
            chatwoot_assistant_id=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        tenants_db["1"] = t1
        save_tenants_to_disk()

def save_tenants_to_disk():
    try:
        data = [t.model_dump() for t in tenants_db.values()]
        with open(TENANTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving tenants file: {e}")

def get_tenant_or_404(tenant_id: str) -> TenantConfig:
    tenant = tenants_db.get(str(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    return tenant

async def fetch_tenant_tools(tenant: TenantConfig) -> List[Dict[str, Any]]:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    
    headers = {}
    if tenant.access_token:
        headers["Authorization"] = f"Bearer {tenant.access_token}"
        
    try:
        url = tenant.mcp_url
        if tenant.access_token and "access_key=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}access_key={tenant.access_token}"

        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_res = await asyncio.wait_for(session.list_tools(), timeout=12.0)
                res = []
                for t in tools_res.tools:
                    schema = getattr(t, 'input_schema', None) or getattr(t, 'inputSchema', None) or {}
                    res.append({
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": schema
                    })
                cached_tools[tenant.tenant_id] = res
                logger.info(f"Loaded {len(res)} tools for tenant '{tenant.tenant_id}' ({tenant.name}).")
                return res
    except Exception as e:
        logger.error(f"Failed to fetch tools for tenant '{tenant.tenant_id}': {e}")
        return cached_tools.get(tenant.tenant_id, [])

async def execute_tenant_tool(tenant: TenantConfig, tool_name: str, arguments: Dict[str, Any]) -> Any:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    if arguments is None:
        arguments = {}

    headers = {}
    if tenant.access_token:
        headers["Authorization"] = f"Bearer {tenant.access_token}"

    url = tenant.mcp_url
    if tenant.access_token and "access_key=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}access_key={tenant.access_token}"

    logger.info(f"Calling tool '{tool_name}' for tenant '{tenant.tenant_id}' with args: {arguments}")
    try:
        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(session.call_tool(tool_name, arguments=arguments), timeout=20.0)
                
                out_texts = []
                for c in result.content:
                    if hasattr(c, "text"):
                        out_texts.append(c.text)
                    else:
                        out_texts.append(str(c))
                raw_text = "\n".join(out_texts) if out_texts else "{}"
                
                try:
                    return json.loads(raw_text)
                except Exception:
                    return {"result": raw_text, "is_error": getattr(result, "is_error", False)}
    except asyncio.TimeoutError:
        logger.warning(f"Timeout calling tool '{tool_name}' for tenant '{tenant.tenant_id}'")
        return {"ok": False, "error": "انتهت المهلة الزمنية أثناء الاتصال بخادم الـ MCP."}
    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}' for tenant '{tenant.tenant_id}': {e}", exc_info=True)
        return {"ok": False, "error": f"خطأ أثناء استدعاء الأداة: {str(e)}"}

def convert_mcp_schema_to_chatwoot(schema: dict) -> list:
    properties = schema.get("properties", {})
    required_list = schema.get("required", []) or []
    params = []
    for prop_name, prop_data in properties.items():
        if prop_name in ["access_key", "api_key"]:
            continue
        prop_type = "string"
        t = prop_data.get("type")
        if not t and "anyOf" in prop_data:
            types = [x.get("type") for x in prop_data["anyOf"] if x.get("type") != "null"]
            t = types[0] if types else "string"
        if t in ["integer", "number", "float"]:
            prop_type = "number"
        elif t in ["boolean", "bool"]:
            prop_type = "boolean"
        else:
            prop_type = "string"
        desc = prop_data.get("description", "")
        params.append({
            "name": prop_name,
            "type": prop_type,
            "description": desc,
            "required": prop_name in required_list
        })
    return params

@app.on_event("startup")
async def startup_event():
    load_tenants_from_disk()
    for tenant in tenants_db.values():
        asyncio.create_task(fetch_tenant_tools(tenant))

# ----------------- Root & Dashboard -----------------
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return JSONResponse(content={
            "service": "Universal Multi-Tenant FastMCP Gateway",
            "status": "running",
            "tenants_count": len(tenants_db),
            "tenants": [
                {"tenant_id": t.tenant_id, "name": t.name, "mcp_url": t.mcp_url, "tools_count": len(cached_tools.get(t.tenant_id, []))}
                for t in tenants_db.values()
            ]
        })
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse("<h1>Universal FastMCP Gateway Running</h1>", status_code=200)

@app.get("/api/status")
async def api_status():
    return {
        "service": "Universal Multi-Tenant FastMCP Gateway",
        "status": "running",
        "tenants_count": len(tenants_db),
        "tenants": [
            {"tenant_id": t.tenant_id, "name": t.name, "mcp_url": t.mcp_url, "tools_count": len(cached_tools.get(t.tenant_id, []))}
            for t in tenants_db.values()
        ]
    }

# ----------------- Tenant Management -----------------
@app.get("/tenants")
async def list_tenants():
    return list(tenants_db.values())

@app.post("/tenants")
async def create_or_update_tenant(tenant: TenantConfig, background_tasks: BackgroundTasks):
    now = datetime.now(timezone.utc).isoformat()
    if tenant.tenant_id in tenants_db:
        existing = tenants_db[tenant.tenant_id]
        tenant.created_at = existing.created_at or now
    else:
        tenant.created_at = now
    tenant.updated_at = now
    
    tenants_db[tenant.tenant_id] = tenant
    save_tenants_to_disk()
    background_tasks.add_task(fetch_tenant_tools, tenant)
    return {"ok": True, "message": f"Tenant '{tenant.tenant_id}' saved successfully", "tenant": tenant}

@app.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str):
    return get_tenant_or_404(tenant_id)

@app.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str):
    if tenant_id in tenants_db:
        del tenants_db[tenant_id]
        cached_tools.pop(tenant_id, None)
        save_tenants_to_disk()
        return {"ok": True, "message": f"Tenant '{tenant_id}' deleted"}
    raise HTTPException(status_code=404, detail="Tenant not found")

# ----------------- Dynamic Tools Discovery & Execution -----------------
@app.get("/tenants/{tenant_id}/tools")
async def get_tenant_tools(tenant_id: str):
    tenant = get_tenant_or_404(tenant_id)
    if tenant.tenant_id not in cached_tools:
        await fetch_tenant_tools(tenant)
    return {"tenant_id": tenant.tenant_id, "name": tenant.name, "tools": cached_tools.get(tenant.tenant_id, [])}

@app.post("/tenants/{tenant_id}/tools/{tool_name}")
async def execute_tenant_tool_route(tenant_id: str, tool_name: str, request: Request):
    tenant = get_tenant_or_404(tenant_id)
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    args = body.get("arguments", body) if isinstance(body, dict) else {}
    if not isinstance(args, dict):
        args = {}

    res = await execute_tenant_tool(tenant, tool_name, args)
    return res

# ----------------- Auto-Sync to Chatwoot Captain Tools -----------------
@app.post("/tenants/{tenant_id}/sync-chatwoot")
async def sync_tenant_to_chatwoot(tenant_id: str):
    tenant = get_tenant_or_404(tenant_id)
    tools = await fetch_tenant_tools(tenant)
    if not tools:
        raise HTTPException(status_code=400, detail="No tools returned by tenant MCP server")

    acc_id = tenant.chatwoot_account_id or 2
    asst_id = tenant.chatwoot_assistant_id or 1

    headers = {
        "api_access_token": CHATWOOT_API_TOKEN,
        "Content-Type": "application/json",
        "X-Forwarded-Proto": "https"
    }

    # 1. Fetch existing custom tools in Chatwoot
    async with httpx.AsyncClient(timeout=15.0) as client:
        cw_url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{acc_id}/captain/custom_tools?assistant_id={asst_id}"
        resp = await client.get(cw_url, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Chatwoot API error: {resp.text}")
        
        existing_tools = {t["slug"]: t for t in resp.json().get("payload", [])}
        synced_count = 0
        created_count = 0
        updated_count = 0

        # 2. Iterate discovered MCP tools and sync to Chatwoot
        for mcp_tool in tools:
            tool_name = mcp_tool["name"]
            slug = tool_name[:60]
            title = f"{tool_name} ({tenant.name[:15]})"
            desc = (mcp_tool.get("description") or f"MCP tool {tool_name}")[:500]
            endpoint = f"{PUBLIC_BRIDGE_URL}/tenants/{tenant.tenant_id}/tools/{tool_name}"
            params = convert_mcp_schema_to_chatwoot(mcp_tool.get("input_schema", {}))

            tool_payload = {
                "custom_tool": {
                    "title": title,
                    "description": desc,
                    "endpoint_url": endpoint,
                    "http_method": "POST",
                    "auth_type": "none",
                    "enabled": True,
                    "param_schema": params,
                    "headers": {}
                }
            }

            if slug in existing_tools:
                tool_id = existing_tools[slug]["id"]
                up_url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{acc_id}/captain/custom_tools/{tool_id}?assistant_id={asst_id}"
                r = await client.patch(up_url, json=tool_payload, headers=headers)
                if r.status_code in [200, 201]:
                    updated_count += 1
                    synced_count += 1
            else:
                create_url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{acc_id}/captain/custom_tools?assistant_id={asst_id}"
                # For create, let slug be set by rails or title
                r = await client.post(create_url, json=tool_payload, headers=headers)
                if r.status_code in [200, 201]:
                    created_count += 1
                    synced_count += 1

    return {
        "ok": True,
        "tenant_id": tenant.tenant_id,
        "tenant_name": tenant.name,
        "total_mcp_tools": len(tools),
        "synced_tools": synced_count,
        "created": created_count,
        "updated": updated_count
    }

# ----------------- Legacy Compatibility Endpoints -----------------
@app.get("/tools")
async def list_tools_legacy():
    tenant = tenants_db.get("1")
    if not tenant:
        return {"tools": []}
    tools = cached_tools.get("1", [])
    if not tools:
        tools = await fetch_tenant_tools(tenant)
    return {"tools": tools}

@app.post("/tools/{tool_name}")
async def call_single_tool_legacy(tool_name: str, request: Request):
    tenant = tenants_db.get("1")
    if not tenant:
        raise HTTPException(status_code=404, detail="Default tenant 1 not configured")
    try:
        body = await request.json()
    except Exception:
        body = {}
    args = body.get("arguments", body) if isinstance(body, dict) else {}
    if not isinstance(args, dict):
        args = {}
    return await execute_tenant_tool(tenant, tool_name, args)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8086))
    uvicorn.run(app, host="0.0.0.0", port=port)
