import math
from math import ceil, sqrt


# ================= PRODUCT
def exactly_one_product(X, a_base):
    """
    Product encoding for EO
    """
    clauses = []
    n = len(X)

    if n == 0: return [[]], a_base

    if n == 1: return [[X[0]]], a_base

    p = ceil(sqrt(n))  # num rows
    q = ceil(n / p)    # num columns

    row_vars = list(range(a_base, a_base + p))
    a_base += p

    col_vars = list(range(a_base, a_base + q))
    a_base += q

    # Each variable implies its row and column
    for idx, x in enumerate(X):
        row = idx // q
        col = idx % q

        clauses.append([-x, row_vars[row]])
        clauses.append([-x, col_vars[col]])

    # Pairwise AMO on row variables
    for i in range(p):
        for j in range(i + 1, p):
            clauses.append([-row_vars[i], -row_vars[j]])

    # Pairwise AMO on col variables
    for i in range(q):
        for j in range(i + 1, q):
            clauses.append([-col_vars[i], -col_vars[j]])

    # ALO on original variables
    clauses.append(list(X))

    return clauses, a_base


# ================= COMMANDER
GROUP_WIDTH = 3

def exactly_one_commander(X, a_base):
    """
    Integrate ALO shortcut by enforcing it upon the top-level commanders and letting logic propagate downwards
    """
    clauses = []

    top_commanders, a_base = at_most_one_commander_recurse(X, a_base, clauses)
    top_level_alo = list(top_commanders)

    clauses.append(top_level_alo)

    return clauses, a_base

def at_most_one_commander_recurse(X, a_base, clauses):
    # When recursion begins with enough variables for only 1 group, no longer need recursive encodings,
    # because we no longer need to enforce inter-group AMO
    if (len(X) <= GROUP_WIDTH):
        clauses.extend(at_most_one_commander_group(X, None))
        return X, a_base

    commanders = []
    n_groups = math.ceil(len(X)/GROUP_WIDTH) # consider 1 or 2 left-over variables their own groups

    for g in range(n_groups):
        commander = a_base
        commanders.append(commander)

        a_base += 1   # increment base for next commanders

        group = X[g*GROUP_WIDTH : (g+1)*GROUP_WIDTH]
        clauses.extend(at_most_one_commander_group(list(group), commander))

    # Create encodings recursively for the commanders, let recursive call relay the updated base
    top_commanders, a_base = at_most_one_commander_recurse(commanders, a_base, clauses)

    # Important for reporting s_i to parent after recursion
    return top_commanders, a_base

def at_most_one_commander_group(X, commander):
    pairwise_clauses = []

    if (len(X) == 1): 
        if (commander):
            # Enforce the defined properties of the commander variable
            pairwise_clauses.append([-X[0], commander])

            # Reverse relationship only useful for propagating ALO logic
            pairwise_clauses.append([-commander, X[0]])

    if (len(X) == 2):
        if (commander):
            # Enforce the defined properties of the commander variable
            pairwise_clauses.append([-X[0], commander])
            pairwise_clauses.append([-X[1], commander])

            # Reverse relationship only useful for propagating ALO logic
            pairwise_clauses.append([-commander, X[0], X[1]])

        # Pairwise AMO within the group
        pairwise_clauses.append([-X[0], -X[1]])
    
    if (len(X) == 3):
        if (commander):
            # Enforce the defined properties of the commander variable
            pairwise_clauses.append([-X[0], commander])
            pairwise_clauses.append([-X[1], commander])
            pairwise_clauses.append([-X[2], commander])

            # Reverse relationship only useful for propagating ALO logic
            pairwise_clauses.append([-commander, X[0], X[1], X[2]])

        # Pairwise AMO within the group
        pairwise_clauses.append([-X[0], -X[1]])
        pairwise_clauses.append([-X[1], -X[2]])
        pairwise_clauses.append([-X[2], -X[0]])

    return pairwise_clauses
