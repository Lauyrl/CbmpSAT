import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cbmp import DATASETS, SatConfig, compute_cyclic_bandwidth, load_instance, solve_timed
from helper.helper import (canonical, completed_keys, display_name, export_csv,
                           find_instance_path, write_record)
from main import main


class HelperTests(unittest.TestCase):
    def test_harwell_boeing_name_normalization(self):
        self.assertEqual(canonical("can___24.mtx"), canonical("can_24"))
        self.assertEqual(display_name("dwt__234.mtx"), "dwt_234")
        self.assertTrue(find_instance_path(DATASETS, "can_24").is_file())

    def test_checkpoint_and_csv_helpers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            records_path = directory / "records.jsonl"
            write_record(records_path, {"key": "run-1", "instance": "can_24", "status": "OPTIMAL"})
            self.assertEqual(completed_keys(records_path), {"run-1"})
            export_csv(records_path, directory / "results.csv")
            self.assertTrue((directory / "results.csv").is_file())


class CbmpIntegrationTests(unittest.TestCase):
    def test_bandwidth_of_a_known_layout(self):
        self.assertEqual(compute_cyclic_bandwidth(6, [(0, 1), (1, 4)], [0, 1, 2, 3, 4, 5]), 3)

    def test_small_instance_solves_with_the_shared_api(self):
        instance = load_instance("can_24")
        config = SatConfig(exactly_one="product", symmetry="reflection", heuristic=True)
        result = solve_timed(instance, config, timeout=5)
        self.assertEqual(result.status, "OPTIMAL")
        self.assertEqual(result.best_ub, 5)
        self.assertGreater(result.variables, 0)
        self.assertGreater(result.clauses, 0)

    def test_cli_entry_point_uses_the_shared_solver_api(self):
        output = io.StringIO()
        with redirect_stdout(output):
            main("can_24", True, True, timeout=5)
        self.assertIn("minimum bandwidth: 5", output.getvalue())
