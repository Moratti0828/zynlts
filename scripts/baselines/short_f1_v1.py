"""Frozen pre-change algorithm, captured 2026-11-17; shared tokenization is unchanged."""
from collections import Counter
from backend.benchmark_v2 import answer_tokens


def short_token_f1(prediction, aliases, language):
    predicted = answer_tokens(prediction, language)
    scores = []
    for alias in aliases:
        gold = answer_tokens(alias, language)
        if not predicted or not gold:
            # A punctuation-only answer cannot earn credit by an empty-token match.
            scores.append(0.0)
            continue
        overlap = sum((Counter(predicted) & Counter(gold)).values())
        scores.append(2 * overlap / (len(predicted) + len(gold)))
    return max(scores, default=0.0)

