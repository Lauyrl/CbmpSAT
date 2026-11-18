import unittest

from cbmp import load_instance
from solvers import cp_sat, cplex_cp, cplex_mip, gurobi
from solvers.common import unavailable


class SolverBackendTests(unittest.TestCase):
    REQUIRED_FIELDS = {"status", "best_ub", "encoding_time", "solve_time", "variables", "clauses", "message"}

    def test_unavailable_result_contract(self):
        result = unavailable("Example")
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertTrue(self.REQUIRED_FIELDS.issubset(result))

    def test_each_backend_returns_a_valid_bounded_result(self):
        instance = load_instance("can_24")
        for name, backend in {
            "CP-SAT": cp_sat.solve,
            "CPLEX CP": cplex_cp.solve,
            "CPLEX MIP": cplex_mip.solve,
            "Gurobi": gurobi.solve,
        }.items():
            with self.subTest(backend=name):
                result = backend(instance, timeout=2)
                self.assertTrue(self.REQUIRED_FIELDS.issubset(result))
                self.assertIn(result["status"], {"UNAVAILABLE", "OPTIMAL", "TIMEOUT", "ERROR"})
                if result["status"] == "OPTIMAL":
                    self.assertEqual(result["best_ub"], 5)
