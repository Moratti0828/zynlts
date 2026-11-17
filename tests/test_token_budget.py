"""Admission boundaries and frozen-template integrity, using no model weights."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.token_budget import prepare_budget, _Unavailable


def sha(data):
    return hashlib.sha256(data).hexdigest()


EXACT_DEPS = all(importlib.util.find_spec(name) for name in ("tokenizers", "jinja2"))
TEMPLATE = "{% for m in messages %}{{ '<|im_start|>' + m['role'] + '\\n' + m['content'] + '<|im_end|>\\n' }}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\\n' }}{% endif %}"


class BudgetContract(unittest.TestCase):
    def setUp(self):
        self.messages = [{"role": "system", "content": "read"}, {"role": "user", "content": "中文A"}]

    def test_missing_identity_is_draft_only_and_counts_output(self):
        strict = prepare_budget({}, self.messages, 512, strict=True)
        self.assertFalse(strict["allowed"])
        self.assertFalse(strict["exact"])
        self.assertEqual(strict["method"], "unavailable")
        draft = prepare_budget({}, self.messages, 512)
        self.assertTrue(draft["allowed"])
        self.assertFalse(draft["exact"])
        self.assertEqual(draft["content_utf8_bytes"], 11)
        self.assertEqual(draft["total_tokens"], draft["input_tokens"] + 1024)
        self.assertIn("unverified", draft["warnings"][-1])

    def test_boundary_and_no_truncation(self):
        model = {"token_budget_margin": 0}
        trial = prepare_budget(model, self.messages, 10)
        limit = trial["total_tokens"]
        self.assertTrue(prepare_budget(model, self.messages, 10, limit)["allowed"])
        failed = prepare_budget(model, self.messages, 10, limit - 1)
        self.assertFalse(failed["allowed"])
        self.assertEqual(failed["remaining_tokens"], -1)
        self.assertEqual(self.messages[-1]["content"], "中文A")
        self.assertIn("not truncated", failed["reason"])

    def test_gold_extra_fields_and_non_text_are_refused(self):
        invalid = [
            [{"role": "user", "content": "Q", "answers": ["gold"]}],
            [{"role": "user", "content": [{"type": "image_url"}]}],
            [{"role": "tool", "content": "Q"}],
            [{"role": "assistant", "content": "prefill"}],
            [{"role": "user", "content": "Q"}, {"role": "system", "content": "hidden"}],
        ]
        for messages in invalid:
            with self.assertRaises(ValueError):
                prepare_budget({}, messages, 512)
        for max_tokens in (True, 0, -1, "512"):
            with self.assertRaises(ValueError):
                prepare_budget({}, self.messages, max_tokens)

    def make_bundle(self, directory, tokenizer_bytes=b"{}"):
        config_bytes = json.dumps({"chat_template": TEMPLATE, "model_max_length": 32768}, ensure_ascii=False).encode()
        manifest = {"schema_version": "reading-tokenizer-v1", "repo_id": "Qwen/Qwen2.5-7B-Instruct",
                    "revision": "a" * 40, "files": {"tokenizer.json": sha(tokenizer_bytes), "tokenizer_config.json": sha(config_bytes)}}
        manifest_bytes = json.dumps(manifest).encode()
        Path(directory, "tokenizer.json").write_bytes(tokenizer_bytes)
        Path(directory, "tokenizer_config.json").write_bytes(config_bytes)
        Path(directory, "manifest.json").write_bytes(manifest_bytes)
        return {"tokenizer_spec": {"repo_id": manifest["repo_id"], "revision": manifest["revision"],
                                   "artifact_dir": directory, "manifest_sha256": sha(manifest_bytes)},
                "runtime_template_kind": "raw_rendered_prompt", "token_budget_margin": 0}

    def test_digest_and_mutable_revision_never_silently_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            model = self.make_bundle(directory)
            Path(directory, "tokenizer_config.json").write_text("{}")
            for strict in (False, True):
                record = prepare_budget(model, self.messages, 10, strict=strict)
                self.assertFalse(record["allowed"])
                self.assertEqual(record["method"], "identity_verification_failed")
                self.assertIn("SHA256 mismatch", record["reason"])
            model["tokenizer_spec"]["revision"] = "main"
            record = prepare_budget(model, self.messages, 10)
            self.assertFalse(record["allowed"])
            self.assertIn("immutable", record["reason"])

    def test_unsupported_family_and_unverified_runtime_refuse_strict(self):
        unknown = {"tokenizer_spec": {"repo_id": "mistralai/Mistral-7B-Instruct-v0.3"}}
        self.assertIn("verified adapter", prepare_budget(unknown, self.messages, 10, strict=True)["reason"])
        with tempfile.TemporaryDirectory() as directory:
            model = self.make_bundle(directory)
            model["runtime_template_kind"] = "ollama_chat"
            self.assertFalse(prepare_budget(model, self.messages, 10, strict=True)["allowed"])
            model["runtime_template_kind"] = "hf_chat_template_equivalent"
            model["runtime_template_sha256"] = "wrong"
            self.assertFalse(prepare_budget(model, self.messages, 10, strict=True)["allowed"])

    def test_missing_dependencies_are_not_claimed_as_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            model = self.make_bundle(directory)
            with patch("backend.token_budget._render_and_count", side_effect=_Unavailable("optional runtime absent")):
                strict = prepare_budget(model, self.messages, 10, strict=True)
                draft = prepare_budget(model, self.messages, 10)
            self.assertFalse(strict["allowed"])
            self.assertFalse(draft["exact"])
            self.assertEqual(draft["method"], "draft_utf8_byte_upper_bound")

    @unittest.skipUnless(EXACT_DEPS, "Optional tokenizers/jinja2 dependencies are absent")
    def test_native_tokens_include_special_wrappers_and_assistant_prefix(self):
        from tokenizers import AddedToken, Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        tokenizer = Tokenizer(WordLevel({"[UNK]": 0, "system": 1, "user": 2, "assistant": 3,
                                         "read": 4, "中文A": 5}, unk_token="[UNK]"))
        tokenizer.pre_tokenizer = Whitespace()
        tokenizer.add_special_tokens([AddedToken("<|im_start|>", special=True), AddedToken("<|im_end|>", special=True)])
        # Detect that full counting disables serialized truncation and padding.
        tokenizer.enable_truncation(max_length=2)
        tokenizer.enable_padding(length=30)
        with tempfile.TemporaryDirectory() as directory:
            model = self.make_bundle(directory, tokenizer.to_str().encode())
            record = prepare_budget(model, self.messages, 10, strict=True)
            self.assertTrue(record["allowed"])
            self.assertTrue(record["exact"])
            self.assertEqual(record["input_tokens"], 10)
            self.assertEqual(record["rendered_prompt"], "<|im_start|>system\nread<|im_end|>\n<|im_start|>user\n中文A<|im_end|>\n<|im_start|>assistant\n")
            self.assertEqual(record["prompt_sha256"], sha(record["rendered_prompt"].encode()))
            self.assertTrue(prepare_budget(model, self.messages, 10, 20, True)["allowed"])
            self.assertFalse(prepare_budget(model, self.messages, 10, 19, True)["allowed"])
            model["runtime_template_kind"] = "hf_chat_template_equivalent"
            model["runtime_template_sha256"] = sha(TEMPLATE.encode())
            self.assertTrue(prepare_budget(model, self.messages, 10, strict=True)["exact"])


if __name__ == "__main__":
    unittest.main()
