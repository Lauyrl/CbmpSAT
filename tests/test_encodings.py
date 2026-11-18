import itertools
import unittest

from pysat.solvers import Cadical195

from alo_amo_eo_encodings import exactly_one
from sat_encodings import direct_cyclic_edge, direct_edge_clause_count


class ExactlyOneEncodingTests(unittest.TestCase):
    def assert_exactly_one(self, encoding):
        X = [1, 2, 3, 4]
        clauses, _ = exactly_one(X, 5, encoding)
        solver = Cadical195(bootstrap_with=clauses)
        try:
            for values in itertools.product((False, True), repeat=len(X)):
                assumptions = [lit if value else -lit for lit, value in zip(X, values)]
                self.assertEqual(solver.solve(assumptions=assumptions), sum(values) == 1)
        finally:
            solver.delete()

    def test_pairwise_encoding(self):
        self.assert_exactly_one("pairwise")

    def test_product_encoding(self):
        self.assert_exactly_one("product")

    def test_commander_encoding(self):
        self.assert_exactly_one("commander")


class DirectDistanceEncodingTests(unittest.TestCase):
    def test_clause_count_matches_generated_clauses(self):
        n = 8
        X = [list(range(1, n + 1)), list(range(n + 1, 2 * n + 1))]
        clauses = direct_cyclic_edge(n, X, 0, 1, upper_bound=3)
        self.assertEqual(len(clauses), direct_edge_clause_count(n, 3))

    def test_direct_encoding_rejects_a_forbidden_distance(self):
        n = 8
        X = [list(range(1, n + 1)), list(range(n + 1, 2 * n + 1))]
        solver = Cadical195(bootstrap_with=direct_cyclic_edge(n, X, 0, 1, upper_bound=3))
        try:
            self.assertTrue(solver.solve(assumptions=[X[0][0], X[1][2]]))
            self.assertFalse(solver.solve(assumptions=[X[0][0], X[1][3]]))
        finally:
            solver.delete()
