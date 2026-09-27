"""OpenAI-compatible chat client (OpenRouter by default; also works with Groq, Gemini, Ollama).

Tries the configured models in order. If none of them exists anymore (free models come and
go), it asks OpenRouter which free models are listed today and tries those.
On OpenRouter only free models (ids ending in ":free") are ever called, so a typo or a pasted
paid model name can't spend credits.
"""
from __future__ import annotations

import json
import re

import httpx


class LLMError(Exception):
    """Message is shown to the user as-is."""


class _TryNext(Exception):
    pass


_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)
_PREFERRED = ("qwen", "glm", "deepseek", "kimi", "gemma", "llama", "mistral")


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply (tolerates <think> blocks and code fences)."""
    text = _FENCE_RE.sub("", _THINK_RE.sub("", text or "")).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object in the reply.")
    return json.loads(text[start : end + 1])


def is_openrouter(base_url: str) -> bool:
    return "openrouter.ai" in base_url.lower()


def is_free(model: str) -> bool:
    return model.strip().endswith(":free")


class ChatClient:
    def __init__(self, client: httpx.Client, base_url: str, models: list[str], api_key: str | None, timeout: float):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.models = list(models)
        if is_openrouter(self.base_url):
            self.models = [m for m in self.models if is_free(m)]  # empty: falls through to discovery
        self.api_key = api_key
        self.timeout = timeout

    def complete_json(self, prompt: str) -> tuple[dict, str]:
        """Returns (parsed_json, model_used). Raises LLMError with a readable reason."""
        if not self.api_key:
            raise LLMError("Add your free OpenRouter key in Settings to see natural rewrites.")
        problems: list[str] = []
        for model in self.models:
            try:
                return self._call(model, prompt), model
            except _TryNext as e:
                problems.append(f"{model.split('/')[-1]}: {e}")
        if all("not available" in p for p in problems):
            for model in self._discover_free_models()[:3]:
                if model in self.models:
                    continue
                try:
                    return self._call(model, prompt), model
                except _TryNext as e:
                    problems.append(f"{model.split('/')[-1]}: {e}")
        if any("limit" in p for p in problems):
            raise LLMError("Free AI quota reached for now (OpenRouter limits free use). It resets daily.")
        raise LLMError("No AI model answered. " + "; ".join(problems[:3]))

    def _call(self, model: str, prompt: str, *, reasoning_off: bool = True) -> dict:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 1200,
        }
        if reasoning_off:
            body["reasoning"] = {"enabled": False}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/verbalogic",
            "X-Title": "VerbaLogic",
        }
        try:
            r = self.client.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout)
        except httpx.TimeoutException:
            raise _TryNext("timed out")
        except httpx.HTTPError as e:
            raise LLMError(f"Couldn't reach the AI service ({e.__class__.__name__}).") from e
        if r.status_code == 401:
            raise LLMError("OpenRouter rejected the key. Check it in Settings.")
        if r.status_code == 400 and reasoning_off and "reason" in r.text.lower():
            return self._call(model, prompt, reasoning_off=False)
        if r.status_code == 429:
            raise _TryNext("rate limit")
        if r.status_code == 402:
            raise _TryNext("needs credits (limit)")
        if r.status_code in (400, 404):
            raise _TryNext("not available")
        if r.status_code >= 500:
            raise _TryNext(f"server error {r.status_code}")
        try:
            payload = r.json()
            if "error" in payload:
                code = str(payload["error"].get("code", ""))
                raise _TryNext("rate limit" if code == "429" else payload["error"].get("message", "error")[:80])
            content = payload["choices"][0]["message"]["content"]
            return extract_json(content)
        except (KeyError, IndexError, TypeError, ValueError):
            raise _TryNext("unreadable answer")

    def _discover_free_models(self) -> list[str]:
        try:
            r = self.client.get(f"{self.base_url}/models", timeout=10)
            ids = [m["id"] for m in r.json().get("data", []) if str(m.get("id", "")).endswith(":free")]
        except (httpx.HTTPError, ValueError, KeyError):
            return []
        rank = lambda i: next((n for n, name in enumerate(_PREFERRED) if name in i), len(_PREFERRED))  # noqa: E731
        return sorted(ids, key=rank)
