"""Check executable reference lineage, preserved raw QA and cluster admission."""
import copy
import json
from pathlib import Path
import unittest
from backend import benchmark_v2 as scorer
from backend.experiment_v2 import digest

ROOT = Path(__file__).resolve().parents[1]


class ReferenceExecutionTests(unittest.TestCase):
    def test_full_references_admit_without_changing_original_qa(self):
        for dataset in ("squad2", "cmrc2018"):
            with self.subTest(dataset=dataset):
                original = json.loads((ROOT / f"data/reference/initial-import-banks-20261024/reference-{dataset}-20261024.json").read_text(encoding="utf-8"))
                executable = json.loads((ROOT / f"data/annotation/reference-{dataset}-20261025.json").read_text(encoding="utf-8"))
                self.assertEqual(executable["parent_bank"]["canonical_sha256"], digest(original))
                for before, after in zip(original["articles"], executable["articles"]):
                    restored = copy.deepcopy(after)
                    restored["length_bin"] = restored.pop("original_passage_length_bin")
                    self.assertEqual(before, restored)
                evaluated = scorer.evaluate(executable, [], ["no-model-fixture"], allow_draft=True, bootstrap_repetitions=0)
                self.assertFalse(evaluated["formal"])

    def test_initial_mixed_title_stratification_remains_detectable(self):
        original = json.loads((ROOT / "data/reference/initial-import-banks-20261024/reference-squad2-20261024.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "source cluster spans strata"):
            scorer.evaluate(original, [], ["no-model-fixture"], allow_draft=True, bootstrap_repetitions=0)


if __name__ == "__main__":
    unittest.main()
