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
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import Config

TIMEOUT_S = 300  # free tiers can be slow on a full lecture transcript
MIN_CALL_GAP_S = 6.0        # spacing between calls, free tiers are strict
RATE_LIMIT_BACKOFF_S = 20.0  # extra wait after a rate-limit response

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


_last_call = 0.0


def _readable(code: int, body: str) -> str:
    """Turn a provider error into something worth reading in a log."""
    if code == 429:
        return "the AI quota is exhausted for now - it will retry later"
    if code in (401, 403):
        return "the API key was rejected"
    try:
        msg = json.loads(body)["error"]["message"]
        return f"HTTP {code}: {msg[:160]}"
    except Exception:
        return f"HTTP {code}: {body[:160]}"


def _post(url: str, payload: dict, headers: dict, retries: int = 2) -> dict:
    """POST with pacing and one retry, because free tiers rate-limit hard."""
    global _last_call
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        gap = MIN_CALL_GAP_S - (time.time() - _last_call)
        if gap > 0:
            time.sleep(gap)
        _last_call = time.time()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < retries:
                time.sleep(RATE_LIMIT_BACKOFF_S * (attempt + 1))
                continue
            raise AIError(_readable(e.code, body)) from None
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                continue
            raise AIError(str(e)[:160]) from None
    raise AIError("no response")


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

    # -- transcription ----------------------------------------------------

    @property
    def can_transcribe(self) -> bool:
        """Only Gemini is wired up to read media directly."""
        return self.enabled and self.provider == "gemini"

    def transcribe_youtube(self, url: str) -> str:
        """Ask Gemini to read a YouTube video.

        Google fetches the video on its own servers, so this still works when
        YouTube has rate-limited our address - which is exactly when we need
        a fallback.
        """
        if not self.can_transcribe:
            return ""
        return self._gemini_media({"file_data": {"file_uri": url}})

    def transcribe_file(self, path: Path, mime: str = "video/mp4") -> str:
        """Upload a local recording and read back what is said in it."""
        if not self.can_transcribe:
            return ""
        uri = self._gemini_upload(path, mime)
        try:
            return self._gemini_media({"file_data": {"file_uri": uri,
                                                     "mime_type": mime}})
        finally:
            self._gemini_delete(uri)

    _TRANSCRIBE_PROMPT = (
        "Transcribe everything spoken in this recording as plain running "
        "text. No timestamps, no speaker labels, no commentary. Keep "
        "technical terms exact. If the recording has no speech, reply with "
        "exactly: NO_SPEECH")

    # A verbatim transcript can trip the provider's recitation filter. Asking
    # for the same content in its own words gets the meaning through, which is
    # what the notes are for.
    _RETELL_PROMPT = (
        "Write detailed study notes covering everything explained in this "
        "recording, in your own words and in the order it was presented. "
        "Include every definition, example, formula and instruction given. "
        "Do not quote long passages verbatim. If there is no speech, reply "
        "with exactly: NO_SPEECH")

    def _gemini_media(self, media_part: dict) -> str:
        url = (f"{self.base_url}/models/{self.model}:generateContent"
               f"?key={self.key}")
        for prompt in (self._TRANSCRIBE_PROMPT, self._RETELL_PROMPT):
            out = _post(url, {"contents": [{"parts": [
                {"text": prompt}, media_part]}]}, {})
            candidate = (out.get("candidates") or [{}])[0]
            parts = (candidate.get("content") or {}).get("parts") or []
            if parts:
                text = parts[0].get("text", "").strip()
                return "" if text.startswith("NO_SPEECH") else text
            if candidate.get("finishReason") != "RECITATION":
                break  # a different failure - retrying the same way won't help
        raise AIError("the provider would not return the contents of this "
                      "recording")

    def _gemini_upload(self, path: Path, mime: str) -> str:
        """Resumable upload; returns the file URI to reference in a prompt."""
        size = path.stat().st_size
        start = urllib.request.Request(
            f"{self.base_url.replace('/v1beta', '')}/upload/v1beta/files"
            f"?key={self.key}",
            data=json.dumps({"file": {"display_name": path.name}}).encode(),
            method="POST",
            headers={"X-Goog-Upload-Protocol": "resumable",
                     "X-Goog-Upload-Command": "start",
                     "X-Goog-Upload-Header-Content-Length": str(size),
                     "X-Goog-Upload-Header-Content-Type": mime,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(start, timeout=TIMEOUT_S) as resp:
                upload_url = resp.headers.get("X-Goog-Upload-URL")
        except Exception as e:
            raise AIError(f"upload could not start: {e}") from None
        if not upload_url:
            raise AIError("upload could not start: no upload URL")

        put = urllib.request.Request(
            upload_url, data=path.read_bytes(), method="POST",
            headers={"Content-Length": str(size),
                     "X-Goog-Upload-Offset": "0",
                     "X-Goog-Upload-Command": "upload, finalize"})
        try:
            with urllib.request.urlopen(put, timeout=TIMEOUT_S * 4) as resp:
                info = json.loads(resp.read().decode())
        except Exception as e:
            raise AIError(f"upload failed: {e}") from None

        file_info = info.get("file", {})
        uri, name = file_info.get("uri"), file_info.get("name")
        # Large media is processed asynchronously; wait for it to be ready.
        for _ in range(60):
            if file_info.get("state") == "ACTIVE":
                return uri
            if file_info.get("state") == "FAILED":
                raise AIError("the provider could not process this recording")
            time.sleep(5)
            try:
                with urllib.request.urlopen(
                        f"{self.base_url}/{name}?key={self.key}",
                        timeout=TIMEOUT_S) as r:
                    file_info = json.loads(r.read().decode())
            except Exception:
                break
        return uri

    def _gemini_delete(self, uri: str) -> None:
        if not uri:
            return
        name = uri.split("/files/")[-1]
        req = urllib.request.Request(
            f"{self.base_url}/files/{name}?key={self.key}", method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=30)
        except Exception:
            pass  # the provider expires uploads on its own anyway

    # -- provider wire formats -------------------------------------------

    def _gemini(self, prompt: str) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.key}"
        out = _post(url, {"contents": [{"parts": [{"text": prompt}]}]}, {})
        candidate = (out.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        if parts:
            return parts[0].get("text", "").strip()
        why = candidate.get("finishReason", "no content")
        if why == "RECITATION":
            raise AIError("the provider declined to summarise this material")
        raise AIError(f"no summary returned ({why})")

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
