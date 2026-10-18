import math

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
