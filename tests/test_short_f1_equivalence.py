"""Regression for moving predicted multiset construction outside the alias loop."""
import random
import unittest
from backend.benchmark_v2 import short_token_f1
from scripts.baselines.short_f1_v1 import short_token_f1 as original
from scripts.compare_short_f1 import fixtures, known_cases


class ShortF1Equivalence(unittest.TestCase):
    def test_known_negative_and_boundary_cases(self):
        self.assertTrue(known_cases(short_token_f1))
        for case in fixtures():
            with self.subTest(case=case):
                self.assertEqual(short_token_f1(case['prediction'], case['aliases'], case['language']),
                                 original(case['prediction'], case['aliases'], case['language']))

    def test_fixed_seed_random_multisets_and_alias_counts(self):
        rng = random.Random(20261117)
        tokens = ['red', 'red', 'not', '甲', '乙', 'ＡＩ', 'AI', '!', '−3', "isn't", '']
        for language in ['en', 'zh']:
            for _ in range(200):
                prediction = ' '.join(rng.choices(tokens, k=rng.randrange(30)))
                aliases = [' '.join(rng.choices(tokens, k=rng.randrange(20))) for _ in range(rng.randrange(12))]
                self.assertEqual(short_token_f1(prediction, aliases, language), original(prediction, aliases, language))
