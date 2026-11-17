"""Read-only final HTTP/deployment checks; does not start an evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8877")
    args = parser.parse_args()

    def raw(path):
        with urllib.request.urlopen(args.base_url + path, timeout=30) as response:
            return response.read()

    def get(path):
        return json.loads(raw(path))

    health = get("/api/health")
    models = get("/api/models")["models"]
    assert health["status"] == "ok" and len(models) == 11
    assert all(m["available"] for m in models)
    assert {m["id"] for m in models}.issuperset({"gemma2-9b", "phi35-mini", "yi15-6b"})
    js_hash = hashlib.sha256(raw("/app.js")).hexdigest()
    assert js_hash == hashlib.sha256((ROOT / "frontend/app.js").read_bytes()).hexdigest()
    expected = {"dev-collection40-20261025": (40, 320), "dev-recent-additions-20261024": (20, 160),
                "reference-squad2-20261025": (50, 150), "reference-cmrc2018-20261025": (50, 150)}
    checked = {}
    for identity, (articles, questions) in expected.items():
        value = get("/api/v2/banks/" + identity)
        bank = value.get("bank", value)
        assert (bank["counts"]["articles"], bank["counts"]["questions"]) == (articles, questions)
        assert not bank["formal_eligible"]
        checked[identity] = {"counts": bank["counts"], "sha256": bank["bank_sha256"],
                             "annotation_origin": bank.get("annotation_origin"), "collection_view": bank.get("collection_view", False)}
    workspace = get("/api/corpus-workspace")
    assert workspace["annotation_counts"]["articles"] == 40
    assert workspace["annotation_counts"]["questions"] == 320
    assert workspace["annotation_counts"]["frozen_questions"] == 0
    result = {"health": health, "model_configurations_available": 11, "frontend_js_sha256": js_hash,
              "banks": checked, "candidate_count": workspace["counts"]["total"],
              "recent_authoring_counts": workspace["annotation_counts"], "model_calls": 0,
              "browser_recheck": "disabled_by_client_Work_settings; earlier browser checks and offline JS contracts retained"}
    (ROOT / "output/platform-contract-check-20261025.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"health": health, "models": 11, "recent_articles": 40, "recent_questions": 320,
                      "public_reference_contexts": 100, "public_reference_questions": 300, "js_hash_match": True, "model_calls": 0}))


if __name__ == "__main__":
    main()
