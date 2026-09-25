"""Gemini client with Pydantic-guided structured output (google.genai SDK).

Owned by P2, but the interface is the contract:
    generate_topics_for_module(module_text) -> list[MicroTopic]
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import TypeAdapter

from app.schemas import MicroTopic

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # backend/.env

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Free-tier quotas are per-model (20 req/day each), so on RESOURCE_EXHAUSTED
# we fail over to the next model in this list to multiply daily capacity.
MODEL_FAILOVER = [
    os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]

# Local fallback via Ollama — unlimited, no quota. Used when every Gemini
# model is quota-exhausted (free tier is 20 req/day per model).
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# ngrok free tier intercepts requests without this header and returns an
# HTML warning page instead of forwarding to Ollama. Every Ollama request
# must include it (works harmlessly for direct/local Ollama too).
OLLAMA_HEADERS = {"ngrok-skip-browser-warning": "69420"}


def _ollama_headers() -> dict[str, str]:
    """Headers sent on every Ollama request (ngrok free-tier bypass)."""
    return dict(OLLAMA_HEADERS)


def _log_ollama_startup_config() -> None:
    """Log Ollama fallback config at startup so Render logs show it clearly."""
    raw = os.getenv("OLLAMA_BASE_URL")
    is_set = bool(raw and raw.strip())
    header_configured = bool(OLLAMA_HEADERS.get("ngrok-skip-browser-warning"))
    logger.info(
        "[ollama] startup config: OLLAMA_BASE_URL set=%s value=%s, "
        "ngrok-skip-browser-warning header configured=%s value=%s",
        is_set,
        raw if is_set else OLLAMA_BASE_URL,
        header_configured,
        OLLAMA_HEADERS.get("ngrok-skip-browser-warning"),
    )


_log_ollama_startup_config()

# Raised when Gemini is at capacity and no Ollama fallback exists on this
# host (cloud deployments — Ollama runs on the user's PC, unreachable from
# Render). Keep the message stable; the API layer surfaces it to the client.
OLLAMA_ABSENT_MESSAGE = (
    "AI generation temporarily unavailable — Gemini is at capacity and no "
    "Ollama fallback is configured on this server. Please retry in a minute."
)

# Whole-chain retries: Gemini 503s are usually transient — a 3s retry often succeeds.
GEMINI_CHAIN_MAX_ATTEMPTS = 3
GEMINI_CHAIN_RETRY_DELAY_SECONDS = 3


def _is_transient_or_quota_error(exc: Exception) -> bool:
    """True for retry/failover-worthy Gemini errors: 503/UNAVAILABLE/quota/rate-limit/transient."""
    s = str(exc).lower()
    markers = (
        "503",
        "429",
        "500",
        "502",
        "unavailable",
        "resource_exhausted",
        "quota",
        "exhausted",
        "overloaded",
        "overload",
        "capacity",
        "rate limit",
        "rate_limit",
        "temporarily",
        "try again",
        "timeout",
        "deadline",
        "connection reset",
        "tps",
    )
    return any(m in s for m in markers)


def _short_status(exc: Exception) -> str:
    """Compact status for INFO logs (e.g. '503', '429', 'UNAVAILABLE')."""
    s = str(exc)
    low = s.lower()
    for code in ("503", "429", "500", "502", "400", "401", "403", "404"):
        if code in s:
            return code
    if "unavailable" in low:
        return "UNAVAILABLE"
    if "resource_exhausted" in low:
        return "RESOURCE_EXHAUSTED"
    if "quota" in low:
        return "quota-exhausted"
    return s[:120].replace("\n", " ")


def _is_ollama_absent() -> bool:
    """True when no usable Ollama fallback exists on this server.

    - OLLAMA_BASE_URL not set / empty → absent (cloud default).
    - OLLAMA_BASE_URL is localhost/127.0.0.1/::1 → absent on cloud hosts
      (Ollama runs on the user's PC, unreachable from Render).
    A non-localhost URL means an explicitly configured remote Ollama host.
    """
    raw = os.getenv("OLLAMA_BASE_URL")
    if not raw or not raw.strip():
        return True
    lowered = raw.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered or "::1" in lowered


def _raise_no_ollama_fallback(last_exc: Exception | None = None) -> None:
    """Raise a clear HTTP 503 instead of a confusing Gemini/Ollama error."""
    try:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=OLLAMA_ABSENT_MESSAGE) from last_exc
    except ImportError:
        raise RuntimeError(f"HTTP 503: {OLLAMA_ABSENT_MESSAGE} (last error: {last_exc})") from last_exc

SYSTEM_PROMPT = """You are a senior CSE professor creating exam-focused micro-lessons for engineering students.

For the syllabus text provided, produce an array of micro-topics. Each micro-topic must teach one clear, syllabus-supported concept that a student can absorb in 45-60 seconds of scrolling.

Rules:
- header: short, specific slide title, max 30 characters.
- body: concise, exam-focused explanation, max 140 characters.
- code_block: optional; include only when code directly improves understanding of the syllabus concept.
- code_block: max 22 lines and max 62 characters per line.
- language_tag: use only one of: python, java, cpp, c, js, sql, kotlin, go, bash, html, css.
- back_header: optional, short back-side prompt, max 30 chars, e.g. "Why it matters" or "Draw the Gantt chart".
- back_body: optional, exam-focused elaboration, max 140 chars, what VTU asks (diagram, formula, trap). Must be derivable from syllabus.
- exam_weight: optional, one of "low","medium","high" — 1 rarely asked .. 3 frequently asked / high-mark. Default "medium".
- Never use a language_tag that does not match the code_block.
- When code is CSS, use language_tag "css"; when code is HTML, use "html". Do not label CSS as HTML.
- If the syllabus requests a language not present in the language_tag whitelist, do not invent a different language; explain the concept without code.
- Cover every important technical topic in the syllabus, but combine closely related subtopics when one micro-lesson can teach them clearly.
- Keep each micro-topic focused on one concept; do not create generic filler slides.
- Stay strictly within the supplied syllabus. Do not add frameworks, APIs, libraries, languages, methods, or concepts that are not supported by the syllabus text.
- Prefer definitions, key characteristics, steps, comparisons, syntax, and exam-relevant facts over broad introductions.
- For implementation topics, show a minimal example only when it is directly supported by the syllabus.
- Do not claim details that are not stated or clearly implied by the supplied syllabus.
- No preamble, no explanation, no markdown fence — output ONLY valid JSON.
"""

CACHE_SCHEMA_VERSION = "v5"


def _hash(text: str) -> str:
    cache_input = f"{CACHE_SCHEMA_VERSION}:{text}"
    return hashlib.md5(cache_input.encode()).hexdigest()


def _build_system_prompt(depth_format: str = "detailed", tone: str = "default", slide_count: int = 10, has_resource: bool = False) -> str:
    base = SYSTEM_PROMPT
    extras = []
    # slide count guidance
    extras.append(f"Generate approximately {slide_count} micro-topics (target {slide_count}, acceptable {max(1, slide_count-1)}-{slide_count+1}). Do not hard-truncate if you return slightly more/fewer, but aim for {slide_count}.")
    # depth/format
    if depth_format == "detailed":
        extras.append("Depth: detailed — full explanations, weave in provided resource notes when present, use complete sentences, keep body up to 140 chars but be thorough.")
    elif depth_format == "short":
        extras.append("Depth: short & crisp — even more concise than default, bodies ~60-90 chars, no filler, bullet-like but still a sentence.")
    elif depth_format == "diagram":
        extras.append("Format: diagram only — for each topic, instead of a prose body, output a structured `diagram` field: {\"nodes\": [\"...\"], \"edges\": [[\"A\",\"B\"], ...]} with max 6 nodes, describing a simple block diagram for that concept. Keep body very short (e.g. \"See diagram\" ≤ 40 chars) and include diagram. Body still required but minimal. Diagram should be self-contained per slide.")
    elif depth_format == "both":
        extras.append("Format: both — normal body text (max 140) PLUS a `diagram` field per topic: {\"nodes\": [...], \"edges\": [[...]]} max 6 nodes. Provide both prose and diagram.")
    # resource weaving — always when present (A for both)
    if has_resource:
        extras.append("Weave the Additional resource notes into every topic where relevant — prioritize resource facts, examples, and terminology as primary source, while still staying within the syllabus scope.")
    # tone
    if tone == "eli5":
        extras.append("Tone: ELI5 — simple language, analogies, no jargon, explain like I'm 5 years old, friendly.")
    elif tone == "professional":
        extras.append("Tone: professional exam-ready — precise terminology, formal, VTU exam style, concise definitions.")
    else:
        extras.append("Tone: default — balanced, clear, exam-focused as in base rules.")
    # diagram field spec for all when needed
    if depth_format in ("diagram", "both"):
        extras.append("Diagram spec: nodes are short labels (≤ 20 chars each), edges are [source, target] string pairs where both names exactly match nodes. Keep to ≤6 nodes and ≤8 edges per diagram, simple vertical/grid flow.")
    return base + "\n\nAdditional instructions:\n- " + "\n- ".join(extras)


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL,
                 cache_dir: Optional[str] = None):
        from google import genai

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (backend/.env)")
        self.client = genai.Client(api_key=self.api_key)
        self.model = model
        self.cache_dir = cache_dir  # None disables cache; e.g. "backend/.cache"

    def _from_cache(self, key: str) -> Optional[list[dict]]:
        if not self.cache_dir:
            return None
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            with open(path) as fh:
                return json.load(fh)
        return None

    def _to_cache(self, key: str, payload: list[dict]) -> None:
        if not self.cache_dir:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(os.path.join(self.cache_dir, f"{key}.json"), "w") as fh:
            json.dump(payload, fh)

    def generate_topics(self, module_text: str, max_retries: int = 2,
                        repair_attempts: int = 1,
                        depth_format: str = "detailed", tone: str = "default",
                        slide_count: int = 10, resource_text: Optional[str] = None) -> list[MicroTopic]:
        """module_text -> validated MicroTopic list. Cache-aware, retry + repair-tolerant."""
        # include tailoring params in cache key so different options don't collide
        cache_src = f"{module_text}|{depth_format}|{tone}|{slide_count}|{(resource_text or '')[:800]}"
        cache_key = _hash(cache_src)
        cached = self._from_cache(cache_key)
        if cached is not None:
            return TypeAdapter(list[MicroTopic]).validate_python(cached)

        system_prompt = _build_system_prompt(depth_format, tone, slide_count, bool(resource_text))
        # build contents with optional resource — always weave when present (A for both)
        effective_text = module_text
        if resource_text:
            effective_text = f"{module_text}\n\nAdditional resource notes (weave into explanations when relevant, prioritize resource facts for accuracy):\n{resource_text[:6000]}"

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                raw = self._generate(effective_text, last_error=None, system_prompt=system_prompt)
                topics = TypeAdapter(list[MicroTopic]).validate_python(raw)
                self._to_cache(cache_key, [t.model_dump() for t in topics])
                return topics
            except Exception as exc:  # network, JSON, or validation failure
                # Preserve explicit HTTP 503 (Gemini at capacity, no Ollama fallback):
                # do not wrap or repair-loop it — surface it directly.
                if getattr(exc, "status_code", None) == 503:
                    raise
                last_exc = exc
                # If the model's JSON failed Pydantic validation, give it the
                # error back and ask for a corrected response. This is the
                # 'repair loop' — makes the pipeline self-healing.
                if (
                    "validation error" in str(exc).lower()
                    or isinstance(exc, json.JSONDecodeError)
                ):
                    for _ in range(repair_attempts):
                        try:
                            raw = self._generate(effective_text, last_error=str(exc), system_prompt=system_prompt)
                            topics = TypeAdapter(list[MicroTopic]).validate_python(raw)
                            self._to_cache(cache_key, [t.model_dump() for t in topics])
                            return topics
                        except Exception as exc2:
                            if getattr(exc2, "status_code", None) == 503:
                                raise
                            last_exc = exc2
        raise RuntimeError(f"Gemini generation failed after retries+repairs: {last_exc}")

    def _generate(self, module_text: str, last_error: Optional[str], system_prompt: str = SYSTEM_PROMPT) -> list[dict]:
        """One raw Gemini call; returns the parsed JSON payload.

        Fails over across MODEL_FAILOVER models when a model is
        quota-exhausted / overloaded (429/503/UNAVAILABLE). The whole
        5-model chain is retried up to GEMINI_CHAIN_MAX_ATTEMPTS times
        with a short sleep — Gemini 503s are usually transient.
        """
        contents = module_text
        if last_error:
            contents = (
                f"{module_text}\n\n"
                f"Your previous response failed schema validation with this error:\n"
                f"{last_error}\n\n"
                f"Please correct the offending fields and return ONLY valid JSON "
                f"conforming to the schema."
            )
        start_idx = MODEL_FAILOVER.index(self.model) if self.model in MODEL_FAILOVER else 0
        models_to_try = MODEL_FAILOVER[start_idx:]
        total_models = len(MODEL_FAILOVER)
        last_exc: Exception | None = None
        try:
            for chain_attempt in range(1, GEMINI_CHAIN_MAX_ATTEMPTS + 1):
                for model in models_to_try:
                    try:
                        model_num = MODEL_FAILOVER.index(model) + 1 if model in MODEL_FAILOVER else "?"
                    except ValueError:
                        model_num = "?"
                    try:
                        resp = self.client.models.generate_content(
                            model=model,
                            contents=contents,
                            config={
                                "system_instruction": system_prompt,
                                "temperature": 0.4,
                                "response_mime_type": "application/json",
                            },
                        )
                        logger.info(
                            f"Gemini attempt {chain_attempt}/{GEMINI_CHAIN_MAX_ATTEMPTS}, "
                            f"model {model_num}/{total_models}: {model} → 200 OK"
                        )
                        self.model = model  # pin the working model for subsequent calls
                        return json.loads(resp.text)
                    except Exception as exc:
                        status = _short_status(exc)
                        logger.info(
                            f"Gemini attempt {chain_attempt}/{GEMINI_CHAIN_MAX_ATTEMPTS}, "
                            f"model {model_num}/{total_models}: {model} → {status}"
                        )
                        if not _is_transient_or_quota_error(exc):
                            raise  # non-transient errors are not failover-worthy
                        last_exc = exc
                        continue
                if chain_attempt < GEMINI_CHAIN_MAX_ATTEMPTS:
                    logger.info(
                        f"Gemini chain attempt {chain_attempt}/{GEMINI_CHAIN_MAX_ATTEMPTS} "
                        f"exhausted, retrying in {GEMINI_CHAIN_RETRY_DELAY_SECONDS}s..."
                    )
                    time.sleep(GEMINI_CHAIN_RETRY_DELAY_SECONDS)
        except Exception:
            # Non-transient Gemini errors propagate immediately — no Ollama fallback.
            raise
        # All Gemini models failed with 503/UNAVAILABLE/quota errors across all chain retries.
        # Explicit Ollama fallback path: on cloud hosts Ollama doesn't exist
        # (it runs on the user's PC, unreachable from Render), so a localhost
        # fallback would fail silently with a confusing error. Try Ollama when
        # configured, but surface a clear HTTP 503 when it is absent.
        try:
            return self._generate_ollama(contents, system_prompt)
        except Exception as ollama_exc:
            if _is_ollama_absent():
                _raise_no_ollama_fallback(last_exc or ollama_exc)
            raise RuntimeError(
                f"Gemini quota exhausted and Ollama fallback failed: {ollama_exc}"
            ) from ollama_exc

    def _generate_ollama(self, contents: str, system_prompt: str = SYSTEM_PROMPT) -> list[dict]:
        """Fallback to a local Ollama model when Gemini quota is exhausted.

        OLLAMA_BASE_URL may point at an ngrok free-tier URL, which returns an
        HTML warning page unless every request carries
        ``ngrok-skip-browser-warning: 69420``. We therefore:

        1. Prefer ``ollama.Client(host=..., headers=...)`` (same for
           ``ollama.AsyncClient``) when the installed ``ollama`` package
           supports the ``headers=`` constructor kwarg (it does since 0.3+ —
           headers are forwarded via httpx).
        2. Otherwise fall back to ``httpx`` directly, sending the same header.
        """
        # Read env at call time so cloud vs local config is always fresh.
        ollama_base = os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
        ollama_model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)
        headers = _ollama_headers()

        # include diagram in Ollama schema when prompt asks for it
        has_diagram = "diagram" in system_prompt.lower()
        diagram_keys = ", diagram (object with nodes:[string] and edges:[[string,string]] or null)" if has_diagram else ""
        user_prompt = (
            f"{contents}\n\n"
            f"Respond with ONLY a JSON object of the form {{\"topics\": [ ... ] }}. "
            f"Each element of the array must have exactly these keys: header "
            f"(string, max 30 chars), body (string, max 140 chars), code_block "
            f"(string or null), language_tag (string or null), back_header (string or null, max 30), back_body (string or null, max 140), exam_weight (\"low\"|\"medium\"|\"high\" or null){diagram_keys}."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Path 1: ollama package with headers= support (preferred when installed).
        try:
            import inspect

            import ollama as ollama_pkg

            try:
                sig = inspect.signature(ollama_pkg.Client.__init__)
                supports_headers = "headers" in sig.parameters
            except (TypeError, ValueError):
                supports_headers = True  # assume modern client; TypeError only if exotic
            if supports_headers:
                logger.info("[ollama] using ollama.Client with ngrok-skip-browser-warning header")
                client = ollama_pkg.Client(host=ollama_base, headers=headers)
                resp = client.chat(
                    model=ollama_model,
                    messages=messages,
                    format="json",
                    options={"temperature": 0.4},
                )
                # ollama-python returns ChatResponse (attr access) or dict-like.
                content: Optional[str] = None
                message = getattr(resp, "message", None)
                if message is not None:
                    content = getattr(message, "content", None)
                    if content is None and isinstance(message, dict):
                        content = message.get("content")
                elif isinstance(resp, dict):
                    msg = resp.get("message", {})
                    content = msg.get("content") if isinstance(msg, dict) else None
                if not content:
                    raise RuntimeError(f"Ollama returned no message content: {resp!r:.200}")
                self.model = f"ollama:{ollama_model}"  # pin for diagnostics
                return json.loads(content)["topics"]
            else:
                logger.info("[ollama] installed ollama package lacks headers= support, using httpx fallback")
        except ImportError:
            # ollama package not installed — expected in this repo (httpx fallback below).
            logger.info("[ollama] ollama package not installed, using httpx fallback with ngrok-skip-browser-warning header")
        except Exception as exc:
            # If the ollama-client path itself failed with an HTML/ngrok-looking
            # error, surface it clearly; otherwise re-raise via the httpx fallback?
            # Prefer to try httpx before giving up, since it sends the same header.
            logger.info(f"[ollama] ollama.Client path failed ({exc:.150}), trying httpx fallback")

        # Path 2: httpx directly (pinned in requirements) with the same header.
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "All Gemini models quota-exhausted and neither `ollama` nor `httpx` is available for Ollama fallback"
            ) from exc

        try:
            url = f"{ollama_base.rstrip('/')}/api/chat"
            with httpx.Client(headers=headers, timeout=300.0) as http_client:
                resp = http_client.post(
                    url,
                    json={
                        "model": ollama_model,
                        "messages": messages,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.4},
                    },
                )
                resp.raise_for_status()
                # Detect ngrok warning-page HTML slipping through (header missing/blocked).
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type.lower():
                    raise RuntimeError(
                        "Ollama fallback got an HTML page instead of JSON — "
                        "likely ngrok browser-warning interception (ngrok-skip-browser-warning header missing?)"
                    )
                payload = resp.json()
            self.model = f"ollama:{ollama_model}"  # pin for diagnostics
            return json.loads(payload["message"]["content"])["topics"]
        except Exception as exc:
            raise RuntimeError(
                f"Gemini quota exhausted and Ollama fallback failed: {exc}"
            ) from exc


def generate_topics_for_module(module_text: str, api_key: Optional[str] = None,
                             depth_format: str = "detailed", tone: str = "default",
                             slide_count: int = 10, resource_text: Optional[str] = None) -> list[MicroTopic]:
    """Module-level entrypoint used by the pipeline."""
    return GeminiClient(api_key=api_key).generate_topics(
        module_text, depth_format=depth_format, tone=tone, slide_count=slide_count, resource_text=resource_text
    )