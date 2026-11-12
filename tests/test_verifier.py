from examples.quant_alpha_guard import SAFE_POSITION_SIZER, UNSAFE_POSITION_SIZER
from examples.sample_functions import (
    BUGGY_DISCOUNT,
    BUGGY_PAYOUT,
    OFF_BY_ONE_BUFFER,
    SAFE_PAYOUT,
)
from src.pipeline import run_verification_loop
from src.verifier import verify_function


def test_detects_negative_balance_bug():
    res = verify_function(
        code_str=BUGGY_PAYOUT,
        preconditions=["balance >= 0", "amount > 0", "fee >= 0"],
        safety_invariants=["return_val >= 0"],
    )
    assert res.status == "VULNERABLE"
    assert res.counterexample is not None
    assert res.counterexample["return_val"] < 0


def test_proves_guarded_payout_safe():
    res = verify_function(
        code_str=SAFE_PAYOUT,
        preconditions=["balance >= 0", "amount > 0", "fee >= 0"],
        safety_invariants=["return_val >= 0"],
    )
    assert res.status == "PROVEN_SAFE"
    assert res.counterexample is None


def test_detects_off_by_one_index_bound():
    res = verify_function(
        code_str=OFF_BY_ONE_BUFFER,
        preconditions=["capacity > 0"],
        safety_invariants=["return_val >= 0", "return_val < capacity"],
    )
    assert res.status == "VULNERABLE"
    assert res.counterexample is not None
    assert res.counterexample["index"] == res.counterexample["capacity"]


def test_detects_coupon_underflow():
    res = verify_function(
        code_str=BUGGY_DISCOUNT,
        preconditions=["price >= 0", "discount >= 0"],
        safety_invariants=["return_val >= 0"],
    )
    assert res.status == "VULNERABLE"
    assert res.counterexample is not None
    assert res.counterexample["discount"] > res.counterexample["price"]


def test_detects_alpha_leverage_breach():
    res = verify_function(
        code_str=UNSAFE_POSITION_SIZER,
        preconditions=["max_exposure >= 1"],
        safety_invariants=["return_val >= 0", "return_val <= max_exposure"],
    )
    assert res.status == "VULNERABLE"
    assert res.counterexample is not None
    assert res.counterexample["return_val"] > res.counterexample["max_exposure"]


def test_proves_guarded_alpha_position_sizer_safe():
    res = verify_function(
        code_str=SAFE_POSITION_SIZER,
        preconditions=["max_exposure >= 1"],
        safety_invariants=["return_val >= 0", "return_val <= max_exposure"],
    )
    assert res.status == "PROVEN_SAFE"
    assert res.counterexample is None

def test_cegis_loop_repairs_and_verifies():
    run = run_verification_loop(
        code_str=BUGGY_PAYOUT,
        preconditions=["balance >= 0", "amount > 0", "fee >= 0"],
        safety_invariants=["return_val >= 0"],
    )
    assert len(run.iterations) == 2
    assert run.iterations[0].status == "VULNERABLE"
    assert run.iterations[1].status == "PROVEN_SAFE"
    assert run.is_verified is True
