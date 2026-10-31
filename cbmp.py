from scipy.io import mmread
from scipy.sparse.csgraph import reverse_cuthill_mckee
from sat_encodings import *
from pysat.solvers import Cadical195
import numpy as np

def compute_cyclic_bandwidth(N, edges, assignment):
    return max(
        min(
            abs(assignment[u] - assignment[v]), 
            N - abs(assignment[u] - assignment[v])
        ) for u, v in edges
    )

def cuthill_mckee_layout(GRAPH, N):
    perm = reverse_cuthill_mckee(GRAPH.tocsr(), symmetric_mode=False)      # perm[k] = vertex placed at position k
    assignment = np.empty(N, dtype=int)
    assignment[perm] = np.arange(N)                                        # assignment[u] = position of vertex u
    return assignment

def solve(dataset, use_symmetry_break, use_heuristic_initial_ub, best_ub):
    # ============ READ INPUT
    GRAPH = mmread(f"datasets/{dataset}.mtx") 
    N = GRAPH.shape[0]  # num vertices

    rows, cols = GRAPH.nonzero()  # edge if: matrix cell has nonzero val
    edges = [(u, v) for u, v in zip(rows, cols) if u < v] # ignoring duplicate pairs, and diagonal

    # ============ BUILD VARIABLES
    x_start = 1
    g_start = x_start + N * N
    a_start = g_start + (N + 1) * N
    X = [[(x_start + u * N + i) for i in range(N)] for u in range(N)]
    G = [[(g_start + u * (N + 1) + i) for i in range(N + 1)] for u in range(N)]

    # ============ BUILD BASE CLAUSES
    clauses = []
    injectivity_surjectivity_clauses, _ = injectivity_surjectivity_X(N, X, a_start)

    clauses.extend(injectivity_surjectivity_clauses)
    clauses.extend(monotonic_G(N, G))
    clauses.extend(lower_upper_bound_G(N, G)) # this one forces all vertices to be at least 1 (G[u][0])
    clauses.extend(biconditional_X_and_G(N, X, G))
    
    # === CBMP symmetry breaking
    if use_symmetry_break:
        ANCHOR_VERTEX = 0
        clauses.extend(break_rotation_symmetry(X, ANCHOR_VERTEX))
        clauses.extend(break_reflection_symmetry(N, X, G))

    # ============ ITERATIVE SAT
    # === INIT
    if use_heuristic_initial_ub:
        HEURISTIC_ASSIGNMENT = cuthill_mckee_layout(GRAPH, N)
        UB = int(compute_cyclic_bandwidth(N, edges, HEURISTIC_ASSIGNMENT))
        best_ub.value = UB
    else:
        UB = N // 2 + 1 # trivial bound, with cyclic values, dist cant exceed N//2

    solver = Cadical195()
    solver.append_formula(clauses)

    # === ITERATE
    while True:
        # === UPPER BOUND MINIMIZATION CLAUSES
        for edge in edges:
            u, v = edge

            # === |f(u) - f(v)| < UB   OR   N - |f(u) - f(v)| < UB
            solver.append_formula(cyclic_edge(N, X, G, u, v, UB))

        result = solver.solve()
        if not result: break
        
        model = solver.get_model()

        # === EXTRACT BANDWIDTH RESULT
        assignment = [0 for i in range(N)]

        for lit in model[:N * N]:           # only check label variables (X_u)
            if lit > 0:
                u_, i_ = divmod(lit - 1, N) # divmod(lit - 1, N) returns ((lit - 1) // N, (lit - 1) % N) 
                assignment[u_] = i_

        bandwidth = compute_cyclic_bandwidth(N, edges, assignment)
        assert bandwidth < UB # catch bugs

        UB = bandwidth
        best_ub.value = UB
        print(UB)

    solver.delete()
