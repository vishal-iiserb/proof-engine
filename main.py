import json
from examples.sample_functions import BUGGY_PAYOUT
from src.pipeline import run_verification_loop


def main() -> None:
    print("Running ProofEngine Formal Verification Pipeline...\n")
    run = run_verification_loop(
        code_str=BUGGY_PAYOUT,
        preconditions=["balance >= 0", "amount > 0", "fee >= 0"],
        safety_invariants=["return_val >= 0"],
    )

    for idx, step in enumerate(run.iterations, start=1):
        print(f"--- Iteration {idx} ({step.solver_time_ms} ms) ---")
        print(f"Status: {step.status}")
        if step.counterexample:
            print("Z3 Counterexample:", json.dumps(step.counterexample))

    print("\nFinal Verified Function:")
    print(run.final_code)


if __name__ == "__main__":
    main()
