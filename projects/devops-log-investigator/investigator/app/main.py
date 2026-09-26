from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .audit import AuditWriter
from .catalog import Catalog
from .kibana import KibanaClient
from .llm import OllamaClient
from .mcp_client import ElasticMCPClient
from .orchestrator import Investigator
from .policy import Policy
from .settings import Settings


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False


def create_app(*, investigator: Any | None = None, settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    app = FastAPI(title="DevOps Log Investigator", docs_url=None, redoc_url=None)
    app.state.investigator = investigator
    app.state.settings = runtime

    def authorize(authorization: str | None) -> None:
        expected = runtime.internal_token
        if not expected:
            return
        if authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    def get_investigator() -> Any:
        if app.state.investigator is None:
            app.state.investigator = _build_default_investigator(runtime)
        return app.state.investigator

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models(authorization: str | None = Header(default=None)) -> dict[str, object]:
        authorize(authorization)
        return {
            "object": "list",
            "data": [
                {
                    "id": runtime.logical_model,
                    "object": "model",
                    "created": 0,
                    "owned_by": "local",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: ChatCompletionRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        authorize(authorization)
        if request.model != runtime.logical_model:
            raise HTTPException(status_code=400, detail=f"Unsupported model: {request.model}")
        if request.stream:
            raise HTTPException(status_code=400, detail="Streaming is not supported by the MVP")
        user_messages = [message.content.strip() for message in request.messages if message.role == "user" and message.content.strip()]
        if not user_messages:
            raise HTTPException(status_code=400, detail="A non-empty user message is required")
        question = user_messages[-1]
        try:
            result = await get_investigator().investigate(question)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Investigator temporarily unavailable") from exc

        return {
            "id": f"chatcmpl-{result.request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": runtime.logical_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.answer_fa},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "investigator": {
                "status": result.status,
                "confidence": result.confidence,
                "verification": result.verification,
                "request_id": result.request_id,
                "resolved_time_window": result.resolved_time_window,
                "indices": result.indices,
                "fields": result.fields,
                "queries": result.queries,
            },
        }

    return app


def _build_default_investigator(settings: Settings) -> Investigator:
    policy = Policy.load(settings.policy_path)
    if settings.kibana_url:
        catalog = KibanaClient(
            settings.kibana_url,
            api_key=settings.kibana_api_key,
            space_id=settings.kibana_space_id,
        ).fetch_catalog()
    else:
        catalog = Catalog(entries=[], health="disabled")

    prompt_path = Path(settings.system_prompt_path)
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else None
    return Investigator(
        policy=policy,
        catalog=catalog,
        llm=OllamaClient(settings.ollama_url, model=settings.ollama_model),
        mcp=ElasticMCPClient(settings.mcp_url),
        audit_writer=AuditWriter(settings.audit_dir),
        sensitive_fields=set(settings.sensitive_fields),
        system_prompt=system_prompt,
    )


app = create_app()
