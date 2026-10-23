import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "algorithm"))
import stallings  # noqa: E402


class StallingsCoreTests(unittest.TestCase):
    def run_case(self, rank, lines):
        return json.loads(stallings.run_folding_json(rank, json.dumps(lines)))

    def test_sample_generators_fold(self):
        result = self.run_case(2, ["abab^{-1}", "abb", "bab", "baaab^{-1}"])
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["steps"]) - 1, 11)
        final = result["steps"][-1]["graph"]
        self.assertEqual(len(final["vertices"]), 2)
        self.assertEqual(len(final["edges"]), 4)

    def test_empty_input_is_one_basepoint(self):
        result = self.run_case(2, [])
        self.assertTrue(result["ok"])
        final = result["steps"][-1]["graph"]
        self.assertEqual(final["vertices"], [0])
        self.assertEqual(final["edges"], [])

    def test_free_reduction(self):
        result = self.run_case(2, ["aa^{-1}bB"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["reducedWords"], [[]])

    def test_invalid_rank(self):
        result = self.run_case(1001, ["a"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["errorKey"], "invalidRank")

    def test_unknown_generator(self):
        result = self.run_case(2, ["c"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["errorKey"], "generatorOutOfRange")

    def test_final_graph_satisfies_folding_condition(self):
        result = self.run_case(2, ["ab", "ab^{-1}", "abb", "bab"])
        self.assertTrue(result["ok"])
        graph = result["steps"][-1]["graph"]
        incidence = {}
        for edge in graph["edges"]:
            incidence.setdefault((edge["u"], edge["label"], 1), 0)
            incidence[(edge["u"], edge["label"], 1)] += 1
            incidence.setdefault((edge["v"], edge["label"], -1), 0)
            incidence[(edge["v"], edge["label"], -1)] += 1
        self.assertTrue(all(count <= 1 for count in incidence.values()))


if __name__ == "__main__":
    unittest.main()
