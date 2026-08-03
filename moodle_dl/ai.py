"""Optional AI summaries.

Everything else in this tool works without an account. This part is the
exception, so it stays strictly opt-in: with no API key configured the
summary sections simply do not appear.

Three wire formats cover every provider worth using:

  gemini     Google           free tier available
  anthropic  Claude
  openai     OpenAI, DeepSeek, Moonshot (Kimi), Zhipu GLM, Qwen, Ollama, ...
             - anything that speaks the OpenAI chat-completions API

Keys live in the user's own config file and are never sent anywhere except
to the provider they belong to.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Config

TIMEOUT_S = 120

# Sensible defaults so a user only has to supply a key
PRESETS = {
    "gemini": {
        # The "-latest" aliases are the ones the free tier actually serves;
        # pinned versions often answer 404 or 429 on a free key.
        "model": "gemini-flash-lite-latest",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "note": "Free tier available at aistudio.google.com/apikey",
    },
    "anthropic": {
        "model": "claude-sonnet-4-5",
        "base_url": "https://api.anthropic.com/v1",
        "note": "Keys from console.anthropic.com",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "note": "Keys from platform.openai.com",
    },
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "note": "OpenAI-compatible; very cheap",
    },
    "moonshot": {
        "model": "kimi-k2-0905-preview",
        "base_url": "https://api.moonshot.cn/v1",
        "note": "Kimi; OpenAI-compatible",
    },
    "zhipu": {
        "model": "glm-4-flash",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "note": "GLM; free flash tier",
    },
    "qwen": {
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "note": "Alibaba Qwen; OpenAI-compatible",
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434/v1",
        "note": "Runs locally, no key, no cost",
    },
}

# Providers that speak the OpenAI wire format
_OPENAI_STYLE = {"openai", "deepseek", "moonshot", "zhipu", "qwen", "ollama"}


class AIError(RuntimeError):
    pass


def _post(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json",
                                          **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise AIError(f"HTTP {e.code}: {detail}") from None
    except Exception as e:
        raise AIError(str(e)) from None


class Summariser:
    """Turns long course text into a short study note."""

    def __init__(self, cfg: Config):
        self.provider = (cfg.ai_provider or "").strip().lower()
        self.key = (cfg.ai_api_key or "").strip()
        preset = PRESETS.get(self.provider, {})
        self.model = (cfg.ai_model or preset.get("model") or "").strip()
        self.base_url = (cfg.ai_base_url or preset.get("base_url") or "").rstrip("/")

    @property
    def enabled(self) -> bool:
        if not self.provider or not self.base_url or not self.model:
            return False
        return bool(self.key) or self.provider == "ollama"

    def summarise(self, title: str, text: str, max_chars: int = 60_000) -> str:
        if not self.enabled:
            return ""
        body = text[:max_chars]
        prompt = (
            "You are helping a university student revise. Summarise the "
            "material below into concise study notes in Markdown:\n"
            "- open with a one-sentence description of what it covers\n"
            "- then the key points as bullets, grouped under short headings\n"
            "- keep technical terms, formulas and definitions exact\n"
            "- note anything flagged as assessable or examinable\n"
            "- do not invent anything that is not in the material\n\n"
            f"Material title: {title}\n\n---\n\n{body}"
        )
        if self.provider == "gemini":
            return self._gemini(prompt)
        if self.provider == "anthropic":
            return self._anthropic(prompt)
        if self.provider in _OPENAI_STYLE:
            return self._openai(prompt)
        raise AIError(f"Unknown ai_provider: {self.provider}")

    # -- provider wire formats -------------------------------------------

    def _gemini(self, prompt: str) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.key}"
        out = _post(url, {"contents": [{"parts": [{"text": prompt}]}]}, {})
        try:
            return out["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise AIError(f"Unexpected response: {str(out)[:200]}") from None

    def _anthropic(self, prompt: str) -> str:
        out = _post(f"{self.base_url}/messages",
                    {"model": self.model, "max_tokens": 2000,
                     "messages": [{"role": "user", "content": prompt}]},
                    {"x-api-key": self.key,
                     "anthropic-version": "2023-06-01"})
        try:
            return out["content"][0]["text"].strip()
        except (KeyError, IndexError):
            raise AIError(f"Unexpected response: {str(out)[:200]}") from None

    def _openai(self, prompt: str) -> str:
        out = _post(f"{self.base_url}/chat/completions",
                    {"model": self.model, "max_tokens": 2000,
                     "messages": [{"role": "user", "content": prompt}]},
                    {"Authorization": f"Bearer {self.key or 'none'}"})
        try:
            return out["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            raise AIError(f"Unexpected response: {str(out)[:200]}") from None
