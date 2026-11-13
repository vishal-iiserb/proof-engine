"""Evaluates Z3 bug-detection accuracy and solver latency across test cases."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from examples.quant_alpha_guard import SAFE_POSITION_SIZER, UNSAFE_POSITION_SIZER
from examples.sample_functions import (
    BUGGY_DISCOUNT,
    BUGGY_PAYOUT,
    BUGGY_RATE_LIMITER,
    OFF_BY_ONE_BUFFER,
    SAFE_PAYOUT,
)
from src.verifier import verify_function

BENCHMARK_SUITE = [
    {
        "name": "Unguarded Financial Transfer",
        "code": BUGGY_PAYOUT,
        "pre": ["balance >= 0", "amount > 0", "fee >= 0"],
        "inv": ["return_val >= 0"],
        "expected": "VULNERABLE",
    },
    {
        "name": "Guarded Financial Transfer",
        "code": SAFE_PAYOUT,
        "pre": ["balance >= 0", "amount > 0", "fee >= 0"],
        "inv": ["return_val >= 0"],
        "expected": "PROVEN_SAFE",
    },
    {
        "name": "Off-by-One Buffer Indexing",
        "code": OFF_BY_ONE_BUFFER,
        "pre": ["capacity > 0"],
        "inv": ["return_val >= 0", "return_val < capacity"],
        "expected": "VULNERABLE",
    },
    {
        "name": "API Rate-Limiter Quota Underflow",
        "code": BUGGY_RATE_LIMITER,
        "pre": ["tokens_left >= 0", "cost > 0"],
        "inv": ["return_val >= 0"],
        "expected": "VULNERABLE",
    },
    {
        "name": "Unguarded Coupon Deduction",
        "code": BUGGY_DISCOUNT,
        "pre": ["price >= 0", "discount >= 0"],
        "inv": ["return_val >= 0"],
        "expected": "VULNERABLE",
    },
  {
        "name": "Unbounded Alpha Exposure Limit",
        "code": UNSAFE_POSITION_SIZER,
        "pre": ["max_exposure >= 1"],
        "inv": ["return_val >= 0", "return_val <= max_exposure"],
        "expected": "VULNERABLE",
    },
    {
        "name": "Guarded Alpha Exposure Limit",
        "code": SAFE_POSITION_SIZER,
        "pre": ["max_exposure >= 1"],
        "inv": ["return_val >= 0", "return_val <= max_exposure"],
        "expected": "PROVEN_SAFE",
    },

]
def main() -> None:
    print(f"{'Test Case':<36} | {'Expected':<12} | {'Actual':<12} | {'Time (ms)':<9}")
    print("-" * 78)

    passed = 0
    total_ms = 0.0

    for case in BENCHMARK_SUITE:
        res = verify_function(
            code_str=case["code"],
            preconditions=case["pre"],
            safety_invariants=case["inv"],
        )
        total_ms += res.solver_time_ms
        if res.status == case["expected"]:
            passed += 1

        print(
            f"{case['name']:<36} | {case['expected']:<12} | {res.status:<12} | {res.solver_time_ms:<9.2f}"
        )

    avg_ms = total_ms / len(BENCHMARK_SUITE)
    print("-" * 78)
    print(f"Matched Expected Verdict: {passed}/{len(BENCHMARK_SUITE)} | Avg Z3 Latency: {avg_ms:.2f} ms")


if __name__ == "__main__":
    main()
