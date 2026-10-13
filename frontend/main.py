"""FastAPI proxy for deployed A2A Agent on Agent Runtime."""

import json
import os
import uuid

import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.protobuf.json_format import MessageToDict
import httpx
from a2a.client import ClientConfig, create_client
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
)
from a2a.utils.constants import (
    PROTOCOL_VERSION_1_0,
    VERSION_HEADER,
    TransportProtocol,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)

app = FastAPI()

_creds = None
_contexts: dict[str, str] = {}


def _get_auth_token() -> str:
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default()
    if not _creds.valid:
        _creds.refresh(GoogleAuthRequest())
    return _creds.token


def _extract_part(part: Part) -> dict | None:
    if part.text:
        return {"kind": "text", "text": part.text}
    elif part.url:
        return {"kind": "text", "text": f"[file: {part.url}]"}
    elif part.HasField("data"):
        data_dict = MessageToDict(part.data)
        return {"kind": "a2ui", "data": data_dict}
    return None


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message_text = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    req_headers = {
        "Authorization": f"Bearer {_get_auth_token()}",
        VERSION_HEADER: PROTOCOL_VERSION_1_0,
    }

    try:
        async with httpx.AsyncClient(headers=req_headers, timeout=120) as http_client:
            config = ClientConfig(
                httpx_client=http_client,
                supported_protocol_bindings=[
                    TransportProtocol.JSONRPC,
                    TransportProtocol.HTTP_JSON,
                ],
            )
            a2a_client = await create_client(A2A_BASE, config)
            session_id = _contexts.get(user_id, "")

            msg = Message(
                message_id=str(uuid.uuid4()),
                role=Role.ROLE_USER,
                parts=[Part(text=message_text)],
                context_id=session_id,
            )

            async for chunk in a2a_client.send_message(SendMessageRequest(message=msg)):
                if chunk.HasField("status_update"):
                    su = chunk.status_update
                    if su.context_id:
                        _contexts[user_id] = su.context_id
                    if su.status.HasField("message"):
                        for p in su.status.message.parts:
                            extracted = _extract_part(p)
                            if extracted:
                                parts.append(extracted)
                elif chunk.HasField("artifact_update"):
                    if chunk.artifact_update.context_id:
                        _contexts[user_id] = chunk.artifact_update.context_id
                    for p in chunk.artifact_update.artifact.parts:
                        extracted = _extract_part(p)
                        if extracted:
                            parts.append(extracted)
                elif chunk.HasField("task"):
                    if chunk.task.context_id:
                        _contexts[user_id] = chunk.task.context_id
                    for artifact in chunk.task.artifacts:
                        for p in artifact.parts:
                            extracted = _extract_part(p)
                            if extracted:
                                parts.append(extracted)
                elif chunk.HasField("message"):
                    for p in chunk.message.parts:
                        extracted = _extract_part(p)
                        if extracted:
                            parts.append(extracted)

    except Exception as e:
        parts = [{"kind": "text", "text": f"Error communicating with agent: {str(e)}"}]

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]

    return JSONResponse({"parts": parts})


app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8088)))
