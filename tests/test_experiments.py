import tempfile
import unittest
from pathlib import Path

from experiments import group_jobs, sat_config
from helper.plots import _pyplot, plot_ablation, plot_encoding, plot_incumbents, plot_methods


class ExperimentConfigurationTests(unittest.TestCase):
    def test_every_group_has_the_expected_jobs(self):
        self.assertEqual(len(group_jobs("methods")), 5)
        self.assertEqual(len(group_jobs("encodings")), 3)
        self.assertEqual(len(group_jobs("ub-time")), 1)
        self.assertEqual(len(group_jobs("ablation")), 6)

    def test_ablation_configs_change_only_the_targeted_features(self):
        self.assertEqual(sat_config({"level": "weak"}).symmetry, "none")
        self.assertFalse(sat_config({"level": "weak"}).heuristic)
        self.assertEqual(sat_config({"level": "medium"}).symmetry, "rotation")
        self.assertFalse(sat_config({"level": "medium"}).heuristic)
        self.assertEqual(sat_config({"level": "strong"}).symmetry, "reflection")
        self.assertTrue(sat_config({"level": "strong"}).heuristic)
        self.assertFalse(sat_config({"level": "no_heuristic"}).heuristic)


class PlotTests(unittest.TestCase):
    def test_all_plot_helpers_write_their_expected_files(self):
        if _pyplot() is None:
            self.skipTest("matplotlib is not installed")
        rows = [{
            "instance": "can_24",
            "method": "order",
            "n": 24,
            "edges": 68,
            "clauses": 6209,
            "exactly_one": "product",
            "status": "OPTIMAL",
            "encoding_time": 0.01,
            "solve_time": 0.02,
            "level": "strong",
            "incumbents": [{"elapsed": 0.01, "ub": 5}],
        }]
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            plot_methods(rows, directory)
            plot_encoding(rows, directory)
            plot_incumbents(rows, directory)
            plot_ablation(rows, directory)
            for filename in ("method_times.png", "clauses_per_edge.png", "ub_vs_time.png", "per_level_times.png"):
                self.assertTrue((directory / filename).is_file(), filename)
