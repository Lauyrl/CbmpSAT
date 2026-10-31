from cbmp import solve
import argparse
import multiprocessing as mp

def main(dataset, use_symmetry_break, use_heuristic_initial_ub, timeout):
    best_ub = mp.Value('i', -1)
    p = mp.Process(target=solve, args=(dataset, use_symmetry_break, use_heuristic_initial_ub, best_ub))
    
    p.start()
    p.join(timeout)       # parent lets this child run for up to [timeout] seconds

    if p.is_alive():      # child still running after waiting [timeout] seconds
        p.terminate()
        p.join()
        if best_ub.value == -1:
            print("timeout, no valid assignment was found")
        else:
            print("timeout, lowest bandwidth found:", best_ub.value)
    
    elif p.exitcode == 0: # child exited properly, loop ended on UNSAT
        print("minimum bandwidth:", best_ub.value)
    
    else:                 # child crashed
        print("child process crashed with exit code:", p.exitcode, "- lowest bandwidth found:", best_ub.value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", 
                        help="name of .mtx file in datasets/")
    parser.add_argument("--timeout", 
                        type=float, 
                        default=600, 
                        help="time limit in seconds")
    parser.add_argument("--symmetry-break", 
                        action="store_true", 
                        help="add rotation + reflection symmetry breaking")
    parser.add_argument("--heuristic-ub", 
                        action="store_true", 
                        help="use Cuthill-McKee initial upper bound")
    args = parser.parse_args()

    main(args.dataset, args.symmetry_break, args.heuristic_ub, args.timeout)
