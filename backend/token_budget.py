"""Frozen, offline chat-token accounting; importing this module never fetches data.

Model fields used by ``prepare_budget``::

    tokenizer_spec = {"repo_id": "Qwen/Qwen2.5-7B-Instruct",
                      "revision": "<40-character commit>",
                      "artifact_dir": "/local/frozen/tokenizer/directory",
                      "manifest_sha256": "<sha256 of manifest.json>"}
    runtime_template_kind = "raw_rendered_prompt"
    token_budget_margin = 512  # optional, additional context headroom

``manifest.json`` must contain schema_version=reading-tokenizer-v1, matching
repo_id/revision, and files={"tokenizer.json": sha256, "tokenizer_config.json":
sha256}. Values in files may also be objects with a sha256 member. Install the
optional tokenizers and jinja2 dependencies and freeze files in a separate,
explicit deployment step. This module only reads them.

Exact accounting supports ordinary Qwen2.5 Instruct text chat, without tools,
documents, images, or response-prefill. The returned rendered_prompt must be
sent verbatim to a raw generation endpoint. A chat endpoint may instead declare
runtime_template_kind=hf_chat_template_equivalent together with an independently
verified runtime_template_sha256 matching the frozen HF template. A generic
chat endpoint's undisclosed wrapper must never be labelled exact.

Draft fallback is a UTF-8 byte-based estimate with explicit wrapper headroom;
it is not proof of a provider's unknown full prompt or formal token compliance.
Gold answer fields are rejected in messages, but callers remain responsible
for constructing content from public article/question fields only.
"""
import hashlib
from functools import lru_cache
import json
from pathlib import Path
import re


VERSION = "reading-token-budget-v1"
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_QWEN_REPO = re.compile(r"Qwen/Qwen2\.5-(?:0\.5|1\.5|3|7|14|32|72)B-Instruct\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ROLES = {"system", "user", "assistant"}


class _Unavailable(ValueError):
    """No frozen compatible tokenizer or optional runtime is available."""


class _InvalidIdentity(ValueError):
    """Supplied frozen identity or files fail verification; never fall back."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _valid_integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _validate_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ValueError("messages may contain only role/content; gold, tools and hidden fields are forbidden")
        if message["role"] not in _ROLES or not isinstance(message["content"], str):
            raise ValueError("Only system/user/assistant text messages are supported")
    if messages[-1]["role"] != "user":
        raise ValueError("The last message must be user; response-prefill is unsupported")
    if any(m["role"] == "system" for m in messages[1:]):
        raise ValueError("A system message is allowed only at the start")


def _load_bundle(model):
    spec = model.get("tokenizer_spec")
    if not isinstance(spec, dict):
        raise _Unavailable("No frozen tokenizer_spec is configured")
    repo = spec.get("repo_id", "")
    revision = spec.get("revision", "")
    if not isinstance(repo, str) or not _QWEN_REPO.fullmatch(repo):
        raise _Unavailable("Exact compatibility currently supports Qwen2.5 Instruct only; other families need a verified adapter")
    if not isinstance(revision, str) or not _HEX40.fullmatch(revision):
        raise _InvalidIdentity("tokenizer revision must be an immutable 40-character commit, not a branch")
    expected_manifest = spec.get("manifest_sha256", "")
    if not isinstance(expected_manifest, str) or not _HEX64.fullmatch(expected_manifest):
        raise _InvalidIdentity("A pinned manifest_sha256 is required")
    artifact_dir = spec.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not artifact_dir:
        raise _Unavailable("No local tokenizer artifact directory is configured")
    directory = Path(artifact_dir).expanduser()
    if not directory.is_absolute():
        directory = _PROJECT_ROOT / directory
    directory = directory.resolve()
    try:
        manifest_bytes = (directory / "manifest.json").read_bytes()
    except FileNotFoundError:
        raise _Unavailable("Frozen tokenizer manifest is absent; no network fetch was attempted") from None
    if _sha(manifest_bytes) != expected_manifest:
        raise _InvalidIdentity("Tokenizer manifest SHA256 mismatch")
    try:
        manifest = json.loads(manifest_bytes)
    except (ValueError, UnicodeDecodeError):
        raise _InvalidIdentity("Tokenizer manifest is not valid JSON") from None
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != "reading-tokenizer-v1"
            or manifest.get("repo_id") != repo or manifest.get("revision") != revision):
        raise _InvalidIdentity("Tokenizer manifest schema/repo/revision does not match the configured identity")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise _InvalidIdentity("Tokenizer manifest files must contain pinned SHA256 values")
    loaded = {}
    for filename in ("tokenizer.json", "tokenizer_config.json"):
        recorded = files.get(filename)
        recorded = recorded.get("sha256") if isinstance(recorded, dict) else recorded
        if not isinstance(recorded, str) or not _HEX64.fullmatch(recorded):
            raise _InvalidIdentity(f"Manifest lacks a valid SHA256 for {filename}")
        try:
            contents = (directory / filename).read_bytes()
        except FileNotFoundError:
            raise _InvalidIdentity(f"Frozen tokenizer file is missing: {filename}") from None
        if _sha(contents) != recorded:
            raise _InvalidIdentity(f"Frozen tokenizer SHA256 mismatch: {filename}")
        loaded[filename] = contents
    try:
        config = json.loads(loaded["tokenizer_config.json"])
    except (ValueError, UnicodeDecodeError):
        raise _InvalidIdentity("tokenizer_config.json is not valid JSON") from None
    if not isinstance(config, dict):
        raise _InvalidIdentity("tokenizer_config.json must be an object")
    template = config.get("chat_template")
    if not isinstance(template, str) or not template:
        raise _Unavailable("A single, frozen string chat_template is required")
    identity = {"repo_id": repo, "revision": revision,
                "manifest_sha256": expected_manifest,
                "tokenizer_sha256": _sha(loaded["tokenizer.json"]),
                "tokenizer_config_sha256": _sha(loaded["tokenizer_config.json"]),
                "chat_template_sha256": _sha(template.encode("utf-8"))}
    return loaded["tokenizer.json"], config, template, identity


@lru_cache(maxsize=8)
def _native_tokenizer(tokenizer_bytes):
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_str(tokenizer_bytes.decode("utf-8"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer


def _render_and_count(tokenizer_bytes, config, template, messages):
    try:
        import tokenizers
        import jinja2
        from jinja2.sandbox import ImmutableSandboxedEnvironment
    except ImportError:
        raise _Unavailable("Optional tokenizers/jinja2 dependencies are absent; install them explicitly") from None

    def raise_exception(message):
        raise ValueError(str(message))

    # Mirror the normal HF chat-template environment for the supported family.
    environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
    environment.globals["raise_exception"] = raise_exception
    environment.filters["tojson"] = lambda value, **kwargs: json.dumps(value, ensure_ascii=False, **kwargs)
    variables = {"messages": messages, "add_generation_prompt": True, "tools": None, "documents": None}
    for name in ("bos_token", "eos_token", "unk_token", "sep_token", "pad_token", "cls_token", "mask_token"):
        token = config.get(name)
        if isinstance(token, dict):
            token = token.get("content")
        if isinstance(token, str):
            variables[name] = token
    try:
        prompt = environment.from_string(template).render(**variables)
        tokenizer = _native_tokenizer(tokenizer_bytes)
        # Some serialized tokenizers can carry truncation or padding settings.
        # Both must be disabled before counting the full, untruncated prompt.
        encoded = tokenizer.encode(prompt, add_special_tokens=False)
    except Exception as exc:
        raise _InvalidIdentity(f"Frozen tokenizer/template could not encode the complete chat: {type(exc).__name__}") from None
    return prompt, len(encoded.ids), {"tokenizers": tokenizers.__version__, "jinja2": jinja2.__version__}


def prepare_budget(model, messages, max_tokens, num_ctx=8192, strict=False):
    """Return an admission record without network calls or silent truncation.

    Missing compatible artifacts/dependencies refuse admission in strict mode.
    An integrity failure refuses admission even in draft mode. ``exact`` means
    the frozen native template and tokenizer count the actual generation input,
    conditional on the runner honoring its declared raw/equivalent template
    mode. A rejected record is returned instead of an exception for these
    expected deployment conditions; malformed input raises ValueError.
    """
    if not isinstance(model, dict):
        raise ValueError("model must be an object")
    if not isinstance(strict, bool):
        raise ValueError("strict must be boolean")
    _validate_messages(messages)
    max_tokens = _valid_integer(max_tokens, "max_tokens", 1)
    num_ctx = _valid_integer(num_ctx, "num_ctx", 1)
    margin = _valid_integer(model.get("token_budget_margin", 512), "token_budget_margin")
    result = {"version": VERSION, "allowed": False, "strict": strict,
              "method": "unavailable", "exact": False, "input_tokens": None,
              "reserved_output_tokens": max_tokens, "reserved_margin_tokens": margin,
              "total_tokens": None, "context_limit": num_ctx,
              "remaining_tokens": None, "tokenizer_identity": None,
              "prompt_sha256": None, "rendered_prompt": None,
              "reason": "", "warnings": []}
    unavailable = None
    try:
        tokenizer_bytes, config, template, identity = _load_bundle(model)
        result["tokenizer_identity"] = identity
        runtime_kind = model.get("runtime_template_kind")
        if runtime_kind == "raw_rendered_prompt":
            pass
        elif (runtime_kind == "hf_chat_template_equivalent"
              and model.get("runtime_template_sha256") == identity["chat_template_sha256"]):
            pass
        else:
            raise _Unavailable("Runtime template equivalence is unverified; send rendered_prompt verbatim through a raw endpoint")
        prompt, count, dependencies = _render_and_count(tokenizer_bytes, config, template, messages)
        declared_limit = config.get("model_max_length")
        if isinstance(declared_limit, int) and not isinstance(declared_limit, bool) and declared_limit > 0:
            result["context_limit"] = min(num_ctx, declared_limit)
        result.update(method="frozen_native_chat_tokens", exact=True, input_tokens=count,
                      prompt_sha256=_sha(prompt.encode("utf-8")), rendered_prompt=prompt,
                      dependency_versions=dependencies, runtime_template_kind=runtime_kind)
    except _InvalidIdentity as exc:
        result["reason"] = str(exc)
        result["method"] = "identity_verification_failed"
        return result
    except _Unavailable as exc:
        unavailable = str(exc)
        if strict:
            result["reason"] = unavailable
            return result
    except (OSError, TypeError, ValueError) as exc:
        result["reason"] = f"Frozen tokenizer configuration failed: {type(exc).__name__}"
        result["method"] = "identity_verification_failed"
        return result
    if unavailable is not None:
        # Byte-level BPE text content cannot require more tokens than its UTF-8
        # bytes; the separate reserve estimates wrappers that are not verified.
        # It is intentionally labelled draft and is never accepted as exact.
        byte_count = sum(len(m["content"].encode("utf-8")) for m in messages)
        wrapper_reserve = 512 + 32 * len(messages)
        result.update(method="draft_utf8_byte_upper_bound", input_tokens=byte_count + wrapper_reserve,
                      content_utf8_bytes=byte_count, estimated_wrapper_reserve=wrapper_reserve)
        result["warnings"] = [unavailable,
                              "Draft estimate only: content byte bound plus wrapper reserve; hidden runtime templates are unverified"]
    total = result["input_tokens"] + max_tokens + margin
    remaining = result["context_limit"] - total
    result.update(total_tokens=total, remaining_tokens=remaining, allowed=remaining >= 0)
    result["reason"] = "within_context_budget" if result["allowed"] else "context_budget_exceeded; input was not truncated"
    return result
