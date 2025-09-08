# mcp_servers/utils_table_server.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI(title="MCP Table Utils Server")


class TableIn(BaseModel):
    rows: List[Dict[str, Any]]


@app.post("/jsonToMarkdownTable")
def json_to_md(payload: TableIn):
    rows = payload.rows or []
    if not rows:
        return {"markdown": "*(empty)*"}

    headers = sorted({k for r in rows for k in r.keys()})
    head = "| " + " | ".join(headers) + " |\n"
    sep = "|" + "|".join("---" for _ in headers) + "|\n"
    body = ""
    for r in rows:
        body += "| " + " | ".join(str(r.get(h, "")) for h in headers) + " |\n"
    return {"markdown": head + sep + body}
