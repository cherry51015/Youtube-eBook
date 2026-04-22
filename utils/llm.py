"""
utils/llm.py

Single entry point for all LLM calls.
Backend is selected from config.yaml → llm.backend.

Supported backends:
  ollama     — local, free, default
  anthropic  — cloud, requires ANTHROPIC_API_KEY env var
  openai     — cloud, requires OPENAI_API_KEY env var

All backends expose the same interface:
  call(prompt, system=None, cfg=None) -> str
"""

import os
import json
import time
import logging
import requests
from typing import Optional

log = logging.getLogger(__name__)


# ── Ollama ────────────────────────────────────────────────────────────────────

def _call_ollama(prompt: str, system: Optional[str], cfg: dict) -> str:
    lc = cfg["llm"]
    url = f"{lc['ollama_url']}/api/generate"
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    payload = {
        "model": lc["model"],
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": lc["temperature"],
            "num_predict": lc["max_tokens"],
        },
    }
    try:
        resp = requests.post(url, json=payload, timeout=600)
        resp.raise_for_status()
        return resp.json()["response"].strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Ollama not reachable at %s. "
            "Install from https://ollama.ai and run: ollama pull %s"
            % (lc["ollama_url"], lc["model"])
        )


# ── Anthropic ─────────────────────────────────────────────────────────────────

def _call_anthropic(prompt: str, system: Optional[str], cfg: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY env var not set")
    lc = cfg["llm"]
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": lc["max_tokens"],
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _call_openai(prompt: str, system: Optional[str], cfg: dict) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY env var not set")
    lc = cfg["llm"]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": messages,
            "max_tokens": lc["max_tokens"],
            "temperature": lc["temperature"],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── Dispatcher ────────────────────────────────────────────────────────────────

_BACKENDS = {
    "ollama": _call_ollama,
    "anthropic": _call_anthropic,
    "openai": _call_openai,
}


def call(
    prompt: str,
    system: Optional[str] = None,
    cfg: Optional[dict] = None,
    retries: int = 3,
    backoff: float = 4.0,
) -> str:
    if cfg is None:
        from utils.config_loader import load_config
        cfg = load_config()

    backend = cfg["llm"]["backend"]
    fn = _BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"Unknown LLM backend: {backend!r}. Choose from {list(_BACKENDS)}")

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            result = fn(prompt, system, cfg)
            if not result.strip():
                raise ValueError("LLM returned empty response")
            return result
        except Exception as exc:
            last_exc = exc
            log.warning("LLM call attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)

    raise RuntimeError(f"LLM call failed after {retries} attempts: {last_exc}") from last_exc
