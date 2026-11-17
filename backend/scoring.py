"""Deterministic graders; Chinese character / English word F1, not official SQuAD."""
import collections
import math
import re
import unicodedata

VERSION = "reading-grader-v1.1"


def tokens(value):
    text = unicodedata.normalize("NFKC", str(value)).lower().replace("−", "-")
    found = re.findall(r"[\u3400-\u9fff]|[a-z]+|[+\-±]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)%?", text)
    return [t.replace(",", "") for t in found]


def normalize(value):
    return " ".join(tokens(value))


def f1(prediction, reference):
    pred, gold = tokens(prediction), tokens(reference)
    if not pred or not gold:
        return float(pred == gold)
    overlap = sum((collections.Counter(pred) & collections.Counter(gold)).values())
    return 2 * overlap / (len(pred) + len(gold))


def grade(question, response, passage, with_context=True):
    impossible = question["type"] == "unanswerable"
    abstain = response["abstain"]
    if impossible:
        em = answer_f1 = float(abstain)
    elif abstain:
        em = answer_f1 = 0.0
    else:
        em = max(float(normalize(response["answer"]) == normalize(a)) for a in question["answers"])
        answer_f1 = max(f1(response["answer"], a) for a in question["answers"])
    quotes = response["evidence"]
    valid = [quote for quote in quotes if quote and quote in passage] if with_context else []
    gold_evidence = question.get("evidence", [])
    evidence_f1 = f1(" ".join(valid), " ".join(gold_evidence)) if with_context and gold_evidence else None
    confidence = response.get("confidence")
    return {
        "em": em, "f1": answer_f1, "evidence_f1": evidence_f1,
        "valid_quote_rate": len(valid) / len(quotes) if quotes and with_context else None,
        "abstention_correct": float(abstain == impossible),
        "brier": (confidence - em) ** 2 if confidence is not None else None,
        "grader_version": VERSION,
    }


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(results, models):
    output = []
    for model in models:
        rows = [r for r in results if r["model_id"] == model["id"]]
        if not rows:
            continue
        good = [r for r in rows if not r.get("error")]
        metric = lambda name: mean([r["metrics"].get(name) for r in rows])
        latencies = sorted(r["latency_s"] for r in good)
        answerable = [r for r in good if r["type"] != "unanswerable"]
        impossible = [r for r in good if r["type"] == "unanswerable"]
        by_type = {}
        for kind in sorted({r["type"] for r in rows}):
            subset = [r for r in rows if r["type"] == kind]
            by_type[kind] = {"n": len(subset), "em": mean([r["metrics"]["em"] for r in subset]), "f1": mean([r["metrics"]["f1"] for r in subset])}
        output.append({
            "model_id": model["id"], "model_name": model["name"], "n": len(rows),
            "successful": len(good), "errors": len(rows) - len(good),
            "em": metric("em"), "f1": metric("f1"), "evidence_f1": metric("evidence_f1"),
            "evidence_n": sum(r["metrics"].get("evidence_f1") is not None for r in rows),
            "abstention_accuracy": mean([r["metrics"]["abstention_correct"] for r in good]),
            "unanswerable_recall": mean([float(r["abstain"]) for r in impossible]),
            "false_abstention_rate": mean([float(r["abstain"]) for r in answerable]),
            "brier": mean([r["metrics"].get("brier") for r in good]),
            "brier_n": sum(r["metrics"].get("brier") is not None for r in good),
            "mean_latency_s": mean(latencies),
            "p95_latency_s": latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else None,
            "input_tokens": sum(r.get("input_tokens") or 0 for r in rows),
            "output_tokens": sum(r.get("output_tokens") or 0 for r in rows),
            "by_type": by_type,
            "denominator_note": "EM/F1 包含请求失败题（计0）；校准与拒答仅统计有效响应；尚未执行题不在当前分母。",
        })
    return output
