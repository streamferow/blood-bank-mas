import json
import os
import time
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano")


def client() -> OpenAI:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("В .env нет OPENAI_API_KEY")
    return OpenAI(api_key=key)


def complete(system: str, user: str, temperature: float = 0) -> tuple[str, dict]:
    started = time.perf_counter()
    kwargs = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # У gpt-5* температура часто недоступна; дешёвые chat-модели её принимают.
    if not MODEL.startswith("gpt-5"):
        kwargs["temperature"] = temperature
    resp = client().chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    usage = {
        "prompt": resp.usage.prompt_tokens if resp.usage else 0,
        "completion": resp.usage.completion_tokens if resp.usage else 0,
        "seconds": round(time.perf_counter() - started, 3),
        "model": MODEL,
    }
    return text, usage


def parse_json(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"нет JSON: {text[:240]}")
    return json.loads(raw[start : end + 1])
