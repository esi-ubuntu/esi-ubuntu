from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    logical_model: str = "log-investigator"
    policy_path: str = "/app/config/policy.yaml"
    system_prompt_path: str = "/app/config/system-prompt.txt"
    kibana_url: str | None = None
    kibana_api_key: str | None = None
    kibana_space_id: str | None = None
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen3:8b-q4_K_M"
    mcp_url: str = "http://elastic-mcp:8080/mcp"
    audit_dir: str = "/data/audit"
    internal_token: str | None = None
    sensitive_fields: tuple[str, ...] = (
        "customer.national_id",
        "national_id",
        "account.number",
        "account_number",
        "card.number",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        raw_sensitive = os.getenv("INVESTIGATOR_SENSITIVE_FIELDS")
        sensitive = cls.sensitive_fields
        if raw_sensitive:
            sensitive = tuple(item.strip() for item in raw_sensitive.split(",") if item.strip())
        return cls(
            logical_model=os.getenv("INVESTIGATOR_LOGICAL_MODEL", "log-investigator"),
            policy_path=os.getenv("INVESTIGATOR_POLICY_PATH", "/app/config/policy.yaml"),
            system_prompt_path=os.getenv("INVESTIGATOR_SYSTEM_PROMPT_PATH", "/app/config/system-prompt.txt"),
            kibana_url=os.getenv("KIBANA_URL") or None,
            kibana_api_key=os.getenv("KIBANA_API_KEY") or None,
            kibana_space_id=os.getenv("KIBANA_SPACE_ID") or None,
            ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b-q4_K_M"),
            mcp_url=os.getenv("ELASTIC_MCP_URL", "http://elastic-mcp:8080/mcp"),
            audit_dir=os.getenv("INVESTIGATOR_AUDIT_DIR", "/data/audit"),
            internal_token=os.getenv("INVESTIGATOR_INTERNAL_TOKEN") or None,
            sensitive_fields=sensitive,
        )
