"""Short, real demonstrations using the existing versioned evaluation engine.

Status checks never call a generation endpoint. Presets select existing frozen
questions and retain each article's complete passage. They are demonstrations,
not a new benchmark or a replacement for formal, human-reviewed testing.
"""
import copy
import datetime as dt
import hashlib
import os
import platform
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType

from . import experiment_v2

VERSION = "reading-live-demo-v1-20261026"
BANK_ID = "dev-expanded-20261020"
BANK_SHA256 = "8d37696d74067a2095f800192e8398b85f72d1ef09ca254f0da3f0ffb2c99a3f"
ACTIVE = {"queued", "running"}
SPECS = (
    ("zh-quick", "中文 · 单题速跑", "zh-cas-1cf079b15eb7-dev20261020", ("q01",)),
    ("zh-reading", "中文 · 三题阅读", "zh-cas-1cf079b15eb7-dev20261020", ("q01", "q03", "q07")),
    ("en-quick", "English · 单题速跑", "en-nasa-2b3fb9c367c3-dev20261020", ("q01",)),
    ("en-reading", "English · 三题阅读", "en-nasa-2b3fb9c367c3-dev20261020", ("q01", "q03", "q07")),
)
ARTICLE_PUBLIC_FIELDS = ("id", "title", "language", "published_at", "source_url", "paragraphs",
                         "source_cluster_id", "presented_text_sha256", "first_published_at",
                         "earliest_observed_publication", "promulgated_at")
QUESTION_PUBLIC_FIELDS = ("id", "prompt", "kind", "dimension", "options")


def _presets(bridge: ModuleType) -> list[dict]:
    bank = experiment_v2.banks(bridge).get(BANK_ID)
    if bank is None:
        raise ValueError("现场演示题库缺失，请保留 data/annotation/dev-expanded-20261020.json")
    if experiment_v2.digest(bank) != BANK_SHA256:
        raise ValueError("现场演示题库版本发生变化，拒绝按旧预设运行；请恢复冻结版本")
    index = {article["id"]: article for article in bank["articles"]}
    output = []
    for identity, label, article_id, question_ids in SPECS:
        article = index[article_id]
        questions = {question["id"]: question for question in article["questions"]}
        output.append({"id": identity, "label": label, "language": article["language"],
                       "bank_id": BANK_ID, "source_bank_sha256": BANK_SHA256,
                       "article": copy.deepcopy(article),
                       "questions": [copy.deepcopy(questions[qid]) for qid in question_ids],
                       "question_count": len(question_ids), "formal": False,
                       "note": "完整原文、已有冻结开发题；人工复核0。现场演示不形成正式排名。"})
    return output


def _public_preset(preset: dict) -> dict:
    return {**{key: value for key, value in preset.items() if key not in {"article", "questions"}},
            "article": {key: copy.deepcopy(preset["article"][key]) for key in ARTICLE_PUBLIC_FIELDS
                        if key in preset["article"]},
            "questions": [{key: copy.deepcopy(question[key]) for key in QUESTION_PUBLIC_FIELDS
                           if key in question} for question in preset["questions"]]}


def _model_statuses(bridge: ModuleType) -> list[dict]:
    models = bridge.all_objects("model")
    bases = sorted({m["base_url"] for m in models if m["provider"] == "ollama"})

    def tags(base: str) -> tuple[str, list | None, str | None]:
        try:
            response = bridge.request_json(base + "/api/tags", timeout=5)
            if not isinstance(response.get("models"), list):
                raise ValueError("模型服务的模型列表格式无效")
            return base, response["models"], None
        except Exception as exc:
            return base, None, str(exc)[:200]

    # One tags read per Ollama service, even when it hosts many registered models.
    with ThreadPoolExecutor(max_workers=4) as pool:
        grouped = {base: (known, error) for base, known, error in pool.map(tags, bases)}
    statuses = []
    for model in models:
        if model["provider"] != "ollama":
            statuses.append(bridge.model_status(model))
            continue
        known, error = grouped[model["base_url"]]
        if error:
            statuses.append({**model, "digest": None, "available": False,
                             "temporal_verified": False, "status": error})
        else:
            statuses.append(bridge.model_status(model, known_tags=known))
    return statuses


def _context(model: dict) -> int:
    native = model.get("native_context_tokens")
    if native is None:
        return 8192
    if type(native) is not int or native < 1024:
        raise ValueError("登记的原生上下文上限无效")
    return min(native, 8192)


def _time_gate(model: dict, preset: dict, bridge: ModuleType) -> bool:
    if not model.get("temporal_verified"):
        return False
    article = preset["article"]
    dates = [bridge.iso_date(article["published_at"])]
    dates.extend(bridge.iso_date(article[key]) for key in
                 ("first_published_at", "earliest_observed_publication", "promulgated_at") if article.get(key))
    return bridge.iso_date(model["release_date"]) < min(dates)


def _compatibility(model: dict, preset: dict, bridge: ModuleType) -> dict:
    result = {"allowed": False, "reason": model.get("status", "模型未连接"), "num_ctx": None,
              "strict_time": False, "strict_budget": False}
    if not model.get("available"):
        return result
    try:
        num_ctx = _context(model)
        result["num_ctx"] = num_ctx
        article = preset["article"]
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
        if bridge.iso_date(article["published_at"]) > today:
            raise ValueError("演示文章日期在未来，不能执行")
        enriched = experiment_v2.enriched_model(model, bridge)
        records = [experiment_v2.budget(enriched, experiment_v2.messages(article, question, "with_context"),
                   {"num_ctx": num_ctx, "max_tokens": 512, "strict_budget": False})
                   for question in preset["questions"]]
        result.update(allowed=True, reason="完整原文与全部选中问题通过当前上下文预算检查",
                      strict_time=_time_gate(model, preset, bridge),
                      budget_method=records[0]["method"], exact_budget=all(r.get("exact") for r in records),
                      max_input_tokens=max(r["input_tokens"] for r in records))
    except (ValueError, TypeError, KeyError) as exc:
        result["reason"] = str(exc)
    return result


def _run_summary(run: dict) -> dict:
    return {key: copy.deepcopy(run[key]) for key in
            ("id", "status", "created_at", "started_at", "finished_at", "progress", "config", "live_demo", "error")
            if key in run}


def status(bridge: ModuleType) -> dict:
    problems = []
    try:
        presets = _presets(bridge)
    except (ValueError, KeyError, TypeError) as exc:
        presets = []
        problems.append(str(exc))
    models = _model_statuses(bridge)
    for model in models:
        model["compatibility"] = {preset["id"]: _compatibility(model, preset, bridge) for preset in presets}
        model["compatible_preset_ids"] = [pid for pid, result in model["compatibility"].items() if result["allowed"]]
        try:
            model["demo_context_tokens"] = _context(model)
        except ValueError:
            model["demo_context_tokens"] = None
    public = [_public_preset(preset) for preset in presets]
    for preset in public:
        preset["compatible_model_ids"] = [model["id"] for model in models
                                          if preset["id"] in model["compatible_preset_ids"]]
    compatible = [model for model in models if model["compatible_preset_ids"]]
    if not compatible:
        problems.append("没有可执行本次演示的模型连接；请启动Ollama或检查模型服务地址与已安装模型")
    all_runs = bridge.all_objects("run")
    active = next((run for run in all_runs if run.get("status") in ACTIVE), None)
    recent = [_run_summary(run) for run in all_runs if run.get("live_demo", {}).get("version") == VERSION][:8]
    default_model = next((m for m in compatible if m["id"] == "qwen25-7b"), compatible[0] if compatible else None)
    default_preset = next((preset["id"] for preset in public
                           if default_model and default_model["id"] in preset["compatible_model_ids"]), None)
    if active:
        problems.append("已有实验正在排队或运行，请查看该实验或等待完成后再开始现场演示")
    return {"version": VERSION, "ready": bool(compatible) and active is None,
            "status": "busy" if active else "ready" if compatible else "unavailable",
            "problems": problems,
            "deployment": {"label": os.environ.get("READING_BENCH_DEPLOYMENT_LABEL") or
                           ("本机 Windows 平台" if platform.system() == "Windows" else platform.system() + " 平台"),
                           "hostname": socket.gethostname(),
                           "model_connection_note": "模型调用由当前平台后端发起；服务地址中的127.0.0.1指后端所在机器。"},
            "models": models, "presets": public,
            "default_model_id": default_model["id"] if default_model else None,
            "default_preset_id": default_preset,
            "active_run": _run_summary(active) if active else None,
            "recent_runs": recent, "model_calls": 0}


def create_run(body: dict, bridge: ModuleType) -> dict:
    permitted = {"model_id", "preset_id", "allow_draft", "client_request_id", "request_id", "bank_id"}
    if set(body) - permitted:
        raise ValueError("现场演示仅接受固定预设、单个模型与请求标识；请在完整实验页配置其他参数")
    if body.get("allow_draft") is not True:
        raise ValueError("请确认使用未完成人工审题的开发题进行现场演示")
    model_id, preset_id = body.get("model_id"), body.get("preset_id")
    request_id = body.get("client_request_id", body.get("request_id"))
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request_id):
        raise ValueError("需要8—100位client_request_id，供断线后安全重试，避免重复推理")
    if body.get("request_id") and body.get("client_request_id") and body["request_id"] != body["client_request_id"]:
        raise ValueError("请求标识不一致")
    if not isinstance(model_id, str) or not isinstance(preset_id, str):
        raise ValueError("请选择有效模型与现场演示预设")
    if body.get("bank_id", BANK_ID) != BANK_ID:
        raise ValueError("演示预设与题库不一致")
    request_key = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    fingerprint = experiment_v2.digest({"model_id": model_id, "preset_id": preset_id,
                                        "bank_sha256": BANK_SHA256, "version": VERSION})
    with bridge.LOCK:
        requests = {record["id"]: record for record in bridge.all_objects("demo_request")}
        existing = requests.get(request_key)
        if existing:
            if existing["fingerprint"] != fingerprint:
                raise ValueError("同一请求标识不能用于不同模型或预设；请重新开始一次演示")
            run = bridge.get("run", existing["run_id"])
            return {"id": run["id"], "run_id": run["id"], "run": run, "reused": True}
        if any(run.get("status") in ACTIVE for run in bridge.all_objects("run")):
            raise ValueError("已有活动实验；请等待完成或取消后再开始，避免现场请求排队")
        presets = {preset["id"]: preset for preset in _presets(bridge)}
        if preset_id not in presets:
            raise ValueError("现场演示预设不存在")
        preset = presets[preset_id]
        model = bridge.model_status(bridge.get("model", model_id))
        compatibility = _compatibility(model, preset, bridge)
        if not compatibility["allowed"]:
            raise ValueError("所选模型不能执行此完整原文预设：" + compatibility["reason"])
        created = experiment_v2.create_run({"bank_id": BANK_ID, "model_ids": [model_id],
            "article_ids": [preset["article"]["id"]], "question_ids": [q["id"] for q in preset["questions"]],
            "question_limit": preset["question_count"], "allow_draft": True,
            "strict_time": compatibility["strict_time"], "strict_budget": False,
            "mode": "with_context", "num_ctx": compatibility["num_ctx"], "max_tokens": 512,
            "temperature": 0, "bootstrap_repetitions": 0}, bridge)
        run = bridge.get("run", created["id"])
        run["live_demo"] = {"version": VERSION, "preset_id": preset_id, "label": preset["label"],
                            "client_request_key_sha256": request_key, "full_passage": True,
                            "source_bank_sha256": BANK_SHA256,
                            "note": "现场真实推理；AI开发题，人审0，不形成正式排名。"}
        bridge.put("run", run["id"], run)
        bridge.put("demo_request", request_key, {"id": request_key, "fingerprint": fingerprint,
                   "run_id": run["id"], "created_at": bridge.now()})
        return {"id": run["id"], "run_id": run["id"], "run": run, "reused": False}
