"""Local fake-blob tests; never downloads weights, connects SSH or invokes models."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import prepare_model_suite_20261024 as suite


class FrozenModelSuiteTests(unittest.TestCase):
    def test_workstation_weight_operation_refused(self):
        with self.assertRaisesRegex(ValueError, "server root|Linux|/home/jmy"):
            suite.assert_server_location(Path("C:/work/reading-bench"), "win32")
        with self.assertRaises(ValueError):
            suite.assert_server_location(Path("/home/other/project"), "linux")

    def test_registry_mutation_refused_before_pull(self):
        raw = b'{"schemaVersion":2,"layers":[]}'
        item = copy.deepcopy(suite.SUITE[0])
        with patch.object(suite.urllib.request, "urlopen", return_value=io.BytesIO(raw)):
            with self.assertRaisesRegex(ValueError, "Registry tag changed"):
                suite.fixed_manifest(item)

    def test_full_blob_hash_detects_same_size_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "blobs").mkdir()
            data = b"frozen weight tensor bytes"
            layer_sha = hashlib.sha256(data).hexdigest()
            layer = {"mediaType": "application/vnd.ollama.image.model", "digest": "sha256:" + layer_sha, "size": len(data)}
            manifest = {"config": layer, "layers": []}
            raw = json.dumps(manifest).encode()
            item = {"model": "fake:fixed", "digest": hashlib.sha256(raw).hexdigest()}
            manifest_path = root / "manifests/registry.ollama.ai/library/fake/fixed"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_bytes(raw)
            blob = root / "blobs" / ("sha256-" + layer_sha)
            blob.write_bytes(data)
            self.assertEqual(suite.verify_blobs(root, item, manifest)[0]["sha256"], layer_sha)
            blob.write_bytes(b"F" + data[1:])
            with self.assertRaisesRegex(ValueError, "SHA/size mismatch"):
                suite.verify_blobs(root, item, manifest)

    def test_existing_different_model_identity_not_overwritten(self):
        item = suite.SUITE[2]
        existing = suite.new_model_record(item, "2026-10-24T00:00:00Z")
        self.assertNotIn("tokenizer_spec", existing)
        self.assertNotIn("runtime_template_kind", existing)
        self.assertIn("original_registry_ChatML", existing["suite_record"]["tokenizer_status"])
        suite.assert_existing_identity(existing, item)
        existing["native_context_tokens"] = 8192
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            suite.assert_existing_identity(existing, item)

    def test_existing_tokenizer_corruption_refused_without_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = {"schema_version": "reading-tokenizer-v1", "repo_id": "01-ai/Yi-1.5-6B-Chat", "revision": suite.YI_REVISION, "files": {}}
            for name in ("tokenizer.json", "tokenizer_config.json"):
                data = b"{}"
                (root / name).write_bytes(data)
                manifest["files"][name] = {"sha256": hashlib.sha256(data).hexdigest()}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "tokenizer.json").write_bytes(b"[]")
            with patch.object(suite.urllib.request, "urlopen", side_effect=AssertionError("network must not run")):
                with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                    suite.freeze_yi_tokenizer(root)


if __name__ == "__main__":
    unittest.main()
