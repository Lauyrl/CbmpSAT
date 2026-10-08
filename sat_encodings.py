# ============================== ORDER ENCODING ========================================
"""
    G: upper bound of X
    X[u][i] <-> (G[u][i] and -G[u][i+1]), vd:
           0 1 2 3 4 5 6
    X[u] = F F F F T F F
           0 1 2 3 4 5 6
    G[u] = T T T T T F F
"""
# === monotonicity
def monotonic_G(N, G):
    """
    G[u][i] -> G[u][i-1]
    G[u][i+1] -> G[u][i] == -G[u][i] -> -G[u][i+1]
    """
    clauses = []
    for u in range(N):
        for i in range(N):
            clauses.append([-G[u][i + 1], G[u][i]]) # G[u][i+1] -> G[u][i]
    return clauses

# === G lower, upper bounds
def lower_upper_bound_G(N, G):
    """
    G[u][1] = true : for every u
    G[u][N + 1] = false : for every u
    """
    clauses = []
    for u in range(N):
        clauses.append([G[u][0]])
        clauses.append([-G[u][N]])

    return clauses

# === X_and_G
def biconditional_X_and_G(N, X, G):
    """
    X[u][i] <-> (G[u][i] and -G[u][i+1])
        * X[u][i] -> (G[u][i] and -G[u][i+1])
        * (G[u][i] and -G[u][i+1]) -> X[u][i]
    """
    clauses = []
    for u in range(N):
        for i in range(N):
            # X to G
            clauses.append([-X[u][i], G[u][i]])
            clauses.append([-X[u][i], -G[u][i + 1]])

            # G to X
            clauses.append([-G[u][i], G[u][i + 1], X[u][i]])
    return clauses

# === LT
def lt(G, v, k):
    """
    if X[v] < k, then -G[v][k]
    """
    return [-G[v][k]]

# === GTE
def gte(G, v, k):
    """
    if X[v] >= k, then G[v][k]
    """
    return [G[v][k]]

# === injectivity X
def injectivity_X(N, X):
    """
    x_u != x_v: X[u][i] -> -X[v][i] == -X[u][i] or -X[v][i]  ==  -X[v][i] or -X[u][i] == X[v][i] -> -X[u][i]  
    """
    clauses = []
    for i in range(N):
        for u in range(N - 1):
            for v in range(u + 1, N):
                clauses.append([-X[u][i], -X[v][i]])
    return clauses

# === injectivity G
def injectivity_G(N, G):
    """
    (G[u][i] and -G[u][i+1]) -> -(G[v][i] and -G[v][i+1])  
    """
    clauses = []
    for i in range(N):
        for u in range(N - 1):
            for v in range(u + 1, N):
                clauses.append([-G[u][i], G[u][i + 1], -G[v][i], G[v][i + 1]])
    return clauses

#  surjectivity and injectivity


# ===================================== UNUSUED ========================================





# ========================= NAIVE EXACT VALUE LT, GT ENCODINGS =========================
# need |v - u| < ub, so: if u = j, then j - ub < v < j + ub
# can act as EO
def less_than(N, nv, ui, k): # ui: u = i
    clauses = []
    # v < i + ub -----> v <= i + ub - 1
    for j in range(1, k):
        clauses.append([-ui, nv + (j - 1)])     # (u = i) --> v = j, j < k
        
    for j in range(k, N + 1):
        clauses.append([-ui, -(nv + (j - 1))])  # (u = i) --> -(v = j), j >= k

    nv += N
    return clauses, nv

def greater_than(N, nv, ui, k): # ui: u = i
    clauses = []
    # v > i - ub -----> v >= i - ub + 1
    for j in range(1, k + 1):
        clauses.append([-ui, -(nv + (j - 1))])  # (u = i) --> -(v = j), j <= k 
            
    for j in range(k + 1, N + 1):
        clauses.append([-ui, (nv + (j - 1))])   # (u = i) --> v = j, j > k

    nv += N
    return clauses, nv
