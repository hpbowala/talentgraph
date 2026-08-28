"""Local development API (FastAPI). Production serving uses app/main.py on
AgentCore; both delegate to app.service."""

import base64
import binascii

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import AuthError, auth_enabled, authenticate
from app.cv_store import CVStoreError
from app.models import ChatResponse, ConversationDetail, ConversationSummary, CVLibrary
from app.service import (
    add_cv,
    delete_conversation,
    delete_cv,
    get_conversation,
    handle_chat,
    list_conversations,
    list_cvs,
    reindex_library,
)

app = FastAPI(title="TalentGraph", description="Conversational workforce knowledge graph")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes reachable without a Cognito access token. Everything else is denied by
# default, so a new route is protected unless it is added here deliberately.
# The docs endpoints stay open because they expose the schema, never the data.
PUBLIC_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})


@app.middleware("http")
async def require_access_token(request: Request, call_next):
    """Mirrors the Lambda proxy's gate (infrastructure/proxy/handler.py).

    No-ops entirely unless COGNITO_USER_POOL_ID is set, which keeps local
    development free of AWS; see backend/app/auth.py.
    """
    # Preflights never carry an Authorization header — rejecting them here
    # would break CORS before the browser ever sends the real request.
    if auth_enabled() and request.method != "OPTIONS" and request.url.path not in PUBLIC_PATHS:
        try:
            authenticate(request.headers.get("authorization"))
        except AuthError as err:
            return JSONResponse(status_code=401, content={"detail": str(err)})
    return await call_next(request)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class CVUploadRequest(BaseModel):
    """Uploads are base64 in JSON rather than multipart so the browser talks to
    the local server and the deployed Lambda proxy through one contract."""

    filename: str
    content_base64: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return handle_chat(request.message, request.conversation_id)


@app.get("/conversations", response_model=list[ConversationSummary])
def conversations() -> list[ConversationSummary]:
    return list_conversations()


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: str) -> ConversationDetail:
    detail = get_conversation(conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown conversation_id")
    return detail


@app.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: str) -> dict:
    delete_conversation(conversation_id)
    return {"deleted": conversation_id}


@app.get("/cvs", response_model=CVLibrary)
def cvs() -> CVLibrary:
    return list_cvs()


@app.post("/cvs", response_model=CVLibrary, status_code=202)
def upload_cv(request: CVUploadRequest, background: BackgroundTasks) -> CVLibrary:
    """Accepts the CV, then rebuilds the graph in the background — the client
    polls GET /cvs until `indexed_at` moves. Mirrors the deployed path, where
    the Lambda proxy invokes the runtime's reindex asynchronously."""
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError) as err:
        raise HTTPException(status_code=400, detail="content_base64 is not valid base64") from err
    try:
        library = add_cv(request.filename, content)
    except CVStoreError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    background.add_task(reindex_library)
    return library


@app.delete("/cvs/{filename}", response_model=CVLibrary, status_code=202)
def remove_cv(filename: str, background: BackgroundTasks) -> CVLibrary:
    try:
        library = delete_cv(filename)
    except CVStoreError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    background.add_task(reindex_library)
    return library


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
