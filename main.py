from scipy.io import mmread
from sat_encodings import *
from pysat.solvers import Glucose4

# ============ READ INPUT
GRAPH = mmread("datasets/662_bus/30_bus.mtx") 
N = GRAPH.shape[0]  # num vertices

rows, cols = GRAPH.nonzero()  # edge if: matrix cell has nonzero val
edges = [(u, v) for u, v in zip(rows, cols) if u < v] # ignoring duplicate pairs, and diagonal

# ============ BUILD VARIABLES
x_start = 1
g_start = x_start + (N - 1) * N + (N - 1) + 1
X = [[(x_start + u * N + i) for i in range(N)] for u in range(N)]
G = [[(g_start + u * (N + 1) + i) for i in range(N + 1)] for u in range(N)]

# ============ BUILD BASE CLAUSES
clauses = []

clauses.extend(injectivity_X(N, X))
clauses.extend(injectivity_G(N, G))
clauses.extend(monotonic_G(N, G))
clauses.extend(lower_upper_bound_G(N, G)) # this one forces all vertices to be at least 1 (G[u][1])
clauses.extend(biconditional_X_and_G(N, X, G))

# ============ ITERATIVE SAT
# === INIT
UB = N - 1 # trivial bound

solver = Glucose4()
solver.append_formula(clauses)

# === ITERATE
while True:
    # UPPER BOUND MINIMIZATION CLAUSES
    for edge in edges:
        u, v = edge

        for i in range(N): # fix u = i
            right_bound = i + UB
            if i + UB < N:
                solver.add_clause([-X[u][i]] + lt(G, v, right_bound))

            left_bound = i - UB
            if i - UB + 1 > 0:
                solver.add_clause([-X[u][i]] + gte(G, v, left_bound + 1))

    result = solver.solve()
    if not result: break
    
    model = solver.get_model()

    values = [0 for i in range(N)]

    for lit in model[:N * N]:
        if lit > 0:
            u_, i_ = divmod(lit - 1, N) # divmod(lit - 1, N) returns (lit - 1 // N, lit - 1 % N) 
            values[u_] = i_

    bandwidth = 0
    for edge in edges:
        u, v = edge

        bandwidth = max(bandwidth, abs(values[u] - values[v])) 

    UB = bandwidth
    print(UB)
    
