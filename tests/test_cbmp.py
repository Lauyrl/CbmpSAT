import unittest

from cbmp import DATASETS, SatConfig, compute_cyclic_bandwidth, load_instance, solve_timed
from helper.helper import canonical, display_name, find_instance_path


class HelperTests(unittest.TestCase):
    def test_harwell_boeing_name_normalization(self):
        self.assertEqual(canonical("can___24.mtx"), canonical("can_24"))
        self.assertEqual(display_name("dwt__234.mtx"), "dwt_234")
        self.assertTrue(find_instance_path(DATASETS, "can_24").is_file())


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
