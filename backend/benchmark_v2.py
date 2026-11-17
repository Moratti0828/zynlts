"""Independent, deterministic v2 grader. Never reinterpret archived v1 runs.

Evidence uses frozen paragraph IDs. Open-ended semantic judgements are excluded.
All planned items, including missing responses, stay in success denominators.
"""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import math
import random
import re
import unicodedata

VERSION = "reading-grader-v2.1-task-metrics-draft-20261013"
DIMENSIONS = ("D1", "D2", "D3", "D4", "D5")
STATES = {"candidate", "ai_checked", "human_reviewed", "frozen"}
KINDS = ("choice", "short", "numeric", "unanswerable")
PRIMARY_METRICS = ("choice_accuracy", "short_em", "short_token_f1", "numeric_strict_accuracy",
                   "evidence_exact_answerable", "evidence_precision_answerable",
                   "evidence_recall_answerable", "evidence_f1_answerable", "correct_refusal_rate",
                   "unanswerable_substantive_rate", "false_refusal_rate")


def exact_text(value):
    # Preserve negation, order, punctuation, signs and units. No bag-of-words.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def answer_tokens(value, language):
    """Local overlap protocol; not the SQuAD/LongBench official tokenizer.

    Both languages apply NFKC/casefold and drop punctuation, but retain negation
    and articles. Chinese Han characters are individual tokens, with contiguous
    Latin words/numbers as tokens. English uses Unicode word tokens. Order is
    intentionally ignored ONLY in partial-credit F1, never in strict correctness.
    """
    value = exact_text(value)
    words = r"[^\W_]+(?:['’][^\W_]+)*"
    if language == "zh":
        # Prevent adjacent Latin words from swallowing Han characters ("AI甲").
        word_part = r"[^\W_\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+"
        return re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]|" + word_part + r"(?:['’]" + word_part + r")*", value)
    if language == "en":
        return re.findall(words, value)
    raise ValueError("Short-answer token F1 requires zh or en")


def short_token_f1(prediction, aliases, language):
    predicted = answer_tokens(prediction, language)
    predicted_counts = Counter(predicted)
    scores = []
    for alias in aliases:
        gold = answer_tokens(alias, language)
        if not predicted or not gold:
            # A punctuation-only answer cannot earn credit by an empty-token match.
            scores.append(0.0)
            continue
        overlap = sum((predicted_counts & Counter(gold)).values())
        scores.append(2 * overlap / (len(predicted) + len(gold)))
    return max(scores, default=0.0)


def paragraph_map(text, article_id):
    return [{"id": f"{article_id}:p{i:03d}", "text": p.strip()}
            for i, p in enumerate((p for p in re.split(r"\n\s*\n", text) if p.strip()), 1)]


def _number(value):
    if not isinstance(value, str):
        raise ValueError("Numeric answers must be strings, without implicit units")
    value = unicodedata.normalize("NFKC", value).strip().replace("−", "-")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", value):
        raise ValueError("Invalid numeric answer")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid numeric answer") from None
    if not result.is_finite():
        raise ValueError("Non-finite numeric answer")
    return result


def validate_bank(bank, allow_draft=False):
    if bank.get("schema_version") != "reading-bank-v2":
        raise ValueError("Expected reading-bank-v2; v1 exports cannot be silently converted")
    articles = bank.get("articles")
    if not isinstance(articles, list) or not articles:
        raise ValueError("An explicit nonempty planned article/question bank is required")
    seen_articles, seen_questions = set(), set()
    for a in articles:
        aid = a.get("id")
        if not isinstance(aid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", aid) or aid in seen_articles:
            raise ValueError("Article IDs must be unique and safe")
        seen_articles.add(aid)
        if a.get("language") not in {"zh", "en"} or not a.get("source_cluster_id"):
            raise ValueError("Each article needs a language and source cluster")
        if a.get("annotation_state") not in STATES:
            raise ValueError("Explicit annotation state is required")
        if not allow_draft and a["annotation_state"] != "frozen":
            raise ValueError("Non-frozen bank: use --allow-draft for labelled diagnostics")
        ps = a.get("paragraphs")
        if not isinstance(ps, list) or not ps:
            raise ValueError("Frozen paragraph ID/text map is required")
        ids = [p.get("id") for p in ps]
        if len(ids) != len(set(ids)) or not all(isinstance(i, str) and i.startswith(aid + ":p") for i in ids):
            raise ValueError("Invalid or duplicate paragraph IDs")
        if not all(isinstance(p.get("text"), str) and p["text"].strip() for p in ps):
            raise ValueError("Empty paragraph")
        rendered = "\n\n".join(p["text"] for p in ps)
        if a.get("presented_text_sha256") != hashlib.sha256(rendered.encode("utf-8")).hexdigest():
            raise ValueError("Presented text hash differs from frozen paragraphs")
        qs = a.get("questions")
        if not isinstance(qs, list) or not qs:
            raise ValueError("Article has no planned questions")
        for q in qs:
            key = (aid, q.get("id"))
            if not isinstance(q.get("id"), str) or not q["id"] or key in seen_questions:
                raise ValueError("Question IDs must be unique per article")
            seen_questions.add(key)
            dim, kind = q.get("dimension"), q.get("kind")
            if dim not in (*DIMENSIONS, "D6") or kind not in {"choice", "short", "numeric", "unanswerable"}:
                raise ValueError("Unsupported dimension or deterministic answer kind")
            if (dim == "D6") != (kind == "unanswerable"):
                raise ValueError("D6 questions must be genuinely unanswerable")
            if not isinstance(q.get("prompt"), str) or not q["prompt"].strip():
                raise ValueError("Empty question")
            chains = q.get("evidence_sets")
            if kind == "unanswerable":
                if chains != [] or not q.get("missing_information"):
                    raise ValueError("Unanswerable item needs a missing-information explanation and no support set")
            elif not isinstance(chains, list) or not chains or any(
                not isinstance(c, list) or not c or len(c) != len(set(c)) or any(i not in ids for i in c)
                for c in chains
            ):
                raise ValueError("Gold chains must be complete nonempty sets of known paragraph IDs")
            if kind == "choice":
                options = q.get("options")
                if not isinstance(options, dict) or len(options) < 2 or q.get("correct_option") not in options:
                    raise ValueError("Choice key/options invalid")
            elif kind == "short":
                if not isinstance(q.get("answers"), list) or not q["answers"] or not all(isinstance(x, str) and x.strip() for x in q["answers"]):
                    raise ValueError("Short answers need frozen aliases")
            elif kind == "numeric":
                _number(q.get("value"))
                if _number(q.get("absolute_tolerance", "0")) < 0 or not isinstance(q.get("unit"), str):
                    raise ValueError("Numeric unit/tolerance invalid")
            if dim == "D3" and not q.get("reasoning_steps"):
                raise ValueError("D3 needs recorded necessary integration steps")
            if dim == "D4" and not q.get("operation"):
                raise ValueError("D4 must record an actual computation, not a numeric extraction")
            if not allow_draft:
                reviews = q.get("human_reviews", [])
                reviewers = {r.get("reviewer_id") for r in reviews if r.get("decision") == "accepted" and r.get("reviewed_at") and r.get("reviewer_id")}
                if len(reviewers) < 2 or not q.get("adjudication_complete"):
                    raise ValueError("Frozen questions require recorded independent human reviews and adjudication")
    # Translations/excerpts sharing a cluster must never cross splits or languages.
    clusters = defaultdict(set)
    for a in articles:
        clusters[a["source_cluster_id"]].add((a.get("split", "unspecified"), a["language"]))
    if any(len(v) > 1 for v in clusters.values()):
        raise ValueError("A source cluster spans splits/languages; score matched translations as a separate track")
    if not allow_draft and len(clusters) != len(articles):
        raise ValueError("Formal single-document bank requires independent source articles; repeated variants belong in a separate track")
    return articles


def grade(question, response, paragraph_ids, error=None, language=None):
    out = {"output_state": "error", "answer_correct": 0, "evidence_exact": 0,
           "joint_success": 0, "evidence_f1": 0 if question["kind"] != "unanswerable" else None,
           "evidence_precision": 0 if question["kind"] != "unanswerable" else None,
           "evidence_recall": 0 if question["kind"] != "unanswerable" else None,
           "correct_refusal": 0, "substantive_answer": 0, "false_refusal": 0,
           "unanswerable_substantive": 0, "brier_answer": None, "error": error,
           "choice_accuracy": 0 if question["kind"] == "choice" else None,
           "short_em": 0 if question["kind"] == "short" else None,
           "short_token_f1": 0 if question["kind"] == "short" else None,
           "numeric_strict_accuracy": 0 if question["kind"] == "numeric" else None}
    if error or response is None:
        out["error"] = error or "missing_planned_response"
        return out
    if not isinstance(response, dict) or not isinstance(response.get("answer"), str) or not isinstance(response.get("abstain"), bool):
        out["error"] = "invalid_answer_contract"
        return out
    supports = response.get("evidence_ids")
    if not isinstance(supports, list) or not all(isinstance(x, str) for x in supports) or len(supports) != len(set(supports)):
        out["error"] = "invalid_evidence_contract"
        return out
    confidence = response.get("confidence")
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        out["error"] = "invalid_confidence_contract"
        return out
    answer = response["answer"].strip()
    unknown = question["kind"] == "unanswerable"
    if response["abstain"]:
        if answer not in {"", "无法从文章确定", "Cannot be determined from the passage"} or supports:
            out["error"] = "refusal_contains_answer_or_evidence"
            return out
        out.update(output_state="refusal", correct_refusal=int(unknown), false_refusal=int(not unknown),
                   answer_correct=int(unknown), error=None)
    else:
        if not answer:
            out["error"] = "empty_substantive_answer"
            return out
        # Unknown cited IDs are a scored evidence failure, not a deleted sample.
        correct = False
        kind = question["kind"]
        if kind == "choice":
            correct = answer == question["correct_option"]
        elif kind == "short":
            correct = any(exact_text(answer) == exact_text(g) for g in question["answers"])
            # Optional language keeps standalone legacy grade() calls compatible;
            # evaluate() always supplies the explicitly frozen bank language.
            token_language = language or question.get("language") or ("zh" if any(re.search(r"[\u3400-\u9fff]", g) for g in question["answers"]) else "en")
            out["short_token_f1"] = short_token_f1(answer, question["answers"], token_language)
        elif kind == "numeric":
            try:
                correct = (response.get("unit") == question["unit"] and
                           abs(_number(answer) - _number(question["value"])) <= _number(question.get("absolute_tolerance", "0")))
            except ValueError:
                correct = False
        predicted = set(supports)
        support_ok, support_f1, support_p, support_r = 0, 0, 0, 0
        if not unknown and predicted <= set(paragraph_ids):
            for chain in question["evidence_sets"]:
                gold = set(chain)
                support_ok = max(support_ok, int(predicted == gold))
                overlap = len(predicted & gold)
                candidate_f1 = 2 * overlap / (len(predicted) + len(gold))
                if candidate_f1 > support_f1:
                    support_f1 = candidate_f1
                    support_p = overlap / len(predicted) if predicted else 0
                    support_r = overlap / len(gold)
        out.update(output_state="answer", answer_correct=int(correct), evidence_exact=support_ok,
                   joint_success=int(correct) * support_ok, substantive_answer=int(not unknown),
                   unanswerable_substantive=int(unknown), evidence_f1=None if unknown else support_f1,
                   evidence_precision=None if unknown else support_p, evidence_recall=None if unknown else support_r, error=None)
        if kind == "choice":
            out["choice_accuracy"] = int(correct)
        elif kind == "short":
            out["short_em"] = int(correct)
        elif kind == "numeric":
            out["numeric_strict_accuracy"] = int(correct)
    if confidence is not None:
        out["brier_answer"] = (confidence - out["answer_correct"]) ** 2
    return out


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _applicable_mean(rows, key):
    return _mean([r[key] for r in rows if r[key] is not None])


def _primary_metrics(rows):
    known = [r for r in rows if r["dimension"] != "D6"]
    unknown = [r for r in rows if r["dimension"] == "D6"]
    return {"choice_accuracy": _applicable_mean(rows, "choice_accuracy"),
            "short_em": _applicable_mean(rows, "short_em"),
            "short_token_f1": _applicable_mean(rows, "short_token_f1"),
            "numeric_strict_accuracy": _applicable_mean(rows, "numeric_strict_accuracy"),
            "evidence_exact_answerable": _mean([r["evidence_exact"] for r in known]),
            "evidence_precision_answerable": _mean([r["evidence_precision"] for r in known]),
            "evidence_recall_answerable": _mean([r["evidence_recall"] for r in known]),
            "evidence_f1_answerable": _mean([r["evidence_f1"] for r in known]),
            "correct_refusal_rate": _mean([r["correct_refusal"] for r in unknown]),
            "unanswerable_substantive_rate": _mean([r["unanswerable_substantive"] for r in unknown]),
            "false_refusal_rate": _mean([r["false_refusal"] for r in known])}


def _kind_summaries(rows):
    result = {}
    for kind in KINDS:
        selected = [r for r in rows if r["kind"] == kind]
        valid = [r for r in selected if r["output_state"] != "error"]
        result[kind] = {"planned_questions": len(selected),
                        "articles": len({r["article_id"] for r in selected}),
                        "errors": len(selected) - len(valid),
                        "valid_output_rate": len(valid) / len(selected) if selected else None,
                        "strict_answer_accuracy": _mean([r["answer_correct"] for r in selected]),
                        "primary_metrics": _primary_metrics(selected),
                        "joint_success_supplement": _mean([r["joint_success"] for r in selected]) if kind != "unanswerable" else None}
    return result


def _summary(rows, include_kind_breakdown=True):
    by_article_dim = defaultdict(list)
    for row in rows:
        if row["dimension"] in DIMENSIONS:
            by_article_dim[(row["article_id"], row["dimension"])].append(row["joint_success"])
    ds = {}
    for dim in DIMENSIONS:
        groups = [v for (_, d), v in by_article_dim.items() if d == dim]
        ds[dim] = {"joint_article_macro": _mean([_mean(v) for v in groups]),
                   "articles": len(groups), "questions": sum(map(len, groups))}
    values = [ds[d]["joint_article_macro"] for d in DIMENSIONS]
    known = [r for r in rows if r["dimension"] != "D6"]
    unknown = [r for r in rows if r["dimension"] == "D6"]
    refusal = _mean([r["correct_refusal"] for r in unknown])
    substantive = _mean([r["substantive_answer"] for r in known])
    valid = [r for r in rows if r["output_state"] != "error"]
    calibration = [r["brier_answer"] for r in valid if r["brier_answer"] is not None]
    primary = _primary_metrics(rows)
    grounded = _mean(values) if all(v is not None for v in values) else None
    joint = _mean([r["joint_success"] for r in known])
    return {"planned_questions": len(rows), "articles": len({r["article_id"] for r in rows}),
            "primary_metrics": primary, "by_question_kind": _kind_summaries(rows) if include_kind_breakdown else {},
            "supplemental_metrics": {"grounded_understanding": grounded, "joint_item_mean_answerable": joint,
                                     "dimension_scores": ds},
            "grounded_understanding": grounded,
            "dimension_scores": ds, "answerable_questions": len(known), "unanswerable_questions": len(unknown),
            "answer_accuracy_answerable": _mean([r["answer_correct"] for r in known]),
            "joint_item_mean_answerable": _mean([r["joint_success"] for r in known]),
            "evidence_precision_answerable": _mean([r["evidence_precision"] for r in known]),
            "evidence_recall_answerable": _mean([r["evidence_recall"] for r in known]),
            "evidence_f1_answerable": _mean([r["evidence_f1"] for r in known]),
            "answer_evidence_quadrants": {"both_correct": sum(r["answer_correct"] and r["evidence_exact"] for r in known),
                "answer_only": sum(r["answer_correct"] and not r["evidence_exact"] for r in known),
                "evidence_only": sum(not r["answer_correct"] and r["evidence_exact"] for r in known),
                "both_incorrect_or_error": sum(not r["answer_correct"] and not r["evidence_exact"] for r in known)},
            "correct_refusal_rate": refusal, "unanswerable_substantive_rate": _mean([r["unanswerable_substantive"] for r in unknown]),
            "false_refusal_rate": _mean([r["false_refusal"] for r in known]),
            "answerable_substantive_rate": substantive,
            "balanced_answerability": (refusal + substantive) / 2 if refusal is not None and substantive is not None else None,
            "valid_output_rate": len(valid) / len(rows) if rows else None, "errors": len(rows) - len(valid),
            "brier_answer": _mean(calibration), "brier_effective_n": len(calibration)}


def _interval(xs):
    if not xs:
        return None
    values = sorted(xs)
    def quantile(p):
        i = (len(values) - 1) * p
        lo, hi = math.floor(i), math.ceil(i)
        return values[lo] + (values[hi] - values[lo]) * (i - lo)
    return {"lower": quantile(.025), "upper": quantile(.975), "effective_resamples": len(values)}


def evaluate(bank, responses, model_ids, allow_draft=False, bootstrap_repetitions=2000, seed=42):
    articles = validate_bank(bank, allow_draft)
    if not model_ids or len(set(model_ids)) != len(model_ids):
        raise ValueError("Explicit unique model IDs are required, including models with no successful outputs")
    if not isinstance(responses, list):
        raise ValueError("responses must be an array")
    planned = {(a["id"], q["id"]) for a in articles for q in a["questions"]}
    records = {}
    for r in responses:
        key = (r.get("model_id"), r.get("article_id"), r.get("question_id"))
        if key[0] not in model_ids or key[1:] not in planned or key in records:
            raise ValueError("Unplanned/duplicate response; repeated trials require a separate evaluation")
        records[key] = r
    rows = []
    for model in model_ids:
        for a in articles:
            for q in a["questions"]:
                r = records.get((model, a["id"], q["id"]), {})
                g = grade(q, r.get("response"), [p["id"] for p in a["paragraphs"]], r.get("error"), a["language"])
                rows.append({"model_id": model, "article_id": a["id"], "question_id": q["id"],
                             "language": a["language"], "dimension": q["dimension"], "kind": q["kind"], **g})
    summaries = {m: {lang: _summary([r for r in rows if r["model_id"] == m and r["language"] == lang])
                     for lang in ("zh", "en")} for m in model_ids}
    for m in model_ids:
        scores = [summaries[m][lang]["grounded_understanding"] for lang in ("zh", "en")]
        summaries[m]["bilingual_equal_weight"] = _mean(scores) if all(x is not None for x in scores) else None
        summaries[m]["bilingual_equal_weight_role"] = "supplemental_custom_grounded_understanding"
    result = {"grader_version": VERSION, "formal": not allow_draft,
              "diagnostic_note": "Draft scores are scorer diagnostics, not a frozen benchmark/model ranking." if allow_draft else "Frozen review records supplied; scorer does not independently authenticate reviewer identity.",
              "evidence_granularity": "paragraph", "failure_policy": "all_planned_items_zero_on_error",
              "confidence_label": "strict_answer_correctness", "summaries": summaries, "rows": rows,
              "metric_protocol": {"primary": list(PRIMARY_METRICS),
                  "aggregation": "planned_item_mean_within_language_and_applicable_question_kind; no unified reading score",
                  "short_em": "NFKC + casefold + collapse whitespace; retain order, punctuation, negation and units; best frozen alias",
                  "short_f1_zh": "custom Han character / Latin Unicode word multiset F1; NFKC/casefold, punctuation removed, articles/negation retained",
                  "short_f1_en": "custom Unicode word multiset F1; NFKC/casefold, punctuation removed, articles/negation retained",
                  "short_f1_aliases": "maximum across frozen aliases; repeated tokens counted; punctuation-only answers receive zero",
                  "short_f1_label": "local_overlap_diagnostic_not_official_SQuAD_or_LongBench_score",
                  "numeric_strict_accuracy": "numeric value within frozen absolute tolerance AND exact frozen unit; signs preserved",
                  "supplemental": ["grounded_understanding", "joint_item_mean_answerable", "bilingual_equal_weight", "balanced_answerability"],
                  "legacy_keys": "preserved for compatibility; grounded_understanding and its legacy confidence intervals are supplemental",
                  "boundary_rates": "execution errors remain in planned denominators; refusal and substantive rates need not sum to one"}}
    if not 0 <= bootstrap_repetitions <= 10000:
        raise ValueError("Bootstrap repetitions must be 0..10000")
    rng = random.Random(seed)
    statistics = {"repetitions": bootstrap_repetitions, "seed": seed, "unit": "source_article_cluster",
                  "confidence_level": .95, "method": "stratified paired percentile bootstrap",
                  "legacy_score_interval_role": "supplemental_grounded_understanding",
                  "strata": ["language", "domain", "length_bin"], "languages": {}}
    for language in ("zh", "en"):
        pool = [a for a in articles if a["language"] == language]
        strata = defaultdict(set)
        lookup = defaultdict(list)
        for a in pool:
            strata[(a.get("domain", "unspecified"), a.get("length_bin", "unspecified"))].add(a["source_cluster_id"])
        memberships = defaultdict(set)
        for s, clusters in strata.items():
            for c in clusters:
                memberships[c].add(s)
        if any(len(v) > 1 for v in memberships.values()):
            raise ValueError("A source cluster spans strata; fix frozen stratification before bootstrap")
        for r in rows:
            if r["language"] == language:
                cluster = next(a["source_cluster_id"] for a in pool if a["id"] == r["article_id"])
                lookup[(r["model_id"], cluster)].append(r)
        samples = {m: [] for m in model_ids}
        deltas = {(a, b): [] for i, a in enumerate(model_ids) for b in model_ids[i + 1:]}
        primary_samples = {m: {metric: [] for metric in PRIMARY_METRICS} for m in model_ids}
        primary_deltas = {pair: {metric: [] for metric in PRIMARY_METRICS} for pair in deltas}
        for _ in range(bootstrap_repetitions):
            chosen = [rng.choice(sorted(clusters)) for clusters in strata.values() for _ in clusters]
            current = {}
            current_primary = {}
            for m in model_ids:
                selected = []
                for slot, cluster in enumerate(chosen):
                    # Repeated sampled clusters are distinct macro-weighted instances.
                    selected.extend({**r, "article_id": f"{slot}:{r['article_id']}"} for r in lookup[(m, cluster)])
                summary = _summary(selected, include_kind_breakdown=False)
                current[m] = summary["grounded_understanding"]
                current_primary[m] = summary["primary_metrics"]
                for metric, value in current_primary[m].items():
                    if value is not None:
                        primary_samples[m][metric].append(value)
                if current[m] is not None:
                    samples[m].append(current[m])
            for a, b in deltas:
                if current[a] is not None and current[b] is not None:
                    deltas[(a, b)].append(current[a] - current[b])
                for metric in PRIMARY_METRICS:
                    left, right = current_primary[a][metric], current_primary[b][metric]
                    if left is not None and right is not None:
                        primary_deltas[(a, b)][metric].append(left - right)
        statistics["languages"][language] = {"clusters": len(memberships), "strata": len(strata),
            "score_intervals": {m: _interval(xs) for m, xs in samples.items()},
            "paired_difference_intervals": {f"{a} minus {b}": _interval(xs) for (a, b), xs in deltas.items()},
            "primary_metric_intervals": {m: {metric: _interval(xs) for metric, xs in metrics.items()} for m, metrics in primary_samples.items()},
            "primary_paired_difference_intervals": {f"{a} minus {b}": {metric: _interval(xs) for metric, xs in metrics.items()} for (a, b), metrics in primary_deltas.items()},
            "note": "Primary intervals use all planned applicable items including errors at zero; omit resamples with no applicable items. Legacy U intervals require all D1-D5 dimensions. Inspect effective_resamples. Tiny strata or pilot banks cannot support population conclusions."}
    result["statistics"] = statistics
    return result
