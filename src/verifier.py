import ast
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
import z3
from src.ast_compiler import compile_python_function


@dataclass
class VerificationResult:
    status: str  # "PROVEN_SAFE" | "VULNERABLE" | "UNKNOWN"
    function_name: str
    solver_time_ms: float
    counterexample: Optional[Dict[str, int]] = None
    violated_invariant: Optional[str] = None
    smt2_summary: str = ""


def verify_function(
    code_str: str,
    preconditions: List[str],
    safety_invariants: List[str],
    timeout_ms: int = 5000,
) -> VerificationResult:
    """
    Checks whether `safety_invariants` hold for all inputs obeying `preconditions`
    whenever the function returns normally without raising an exception.
    """
    start_time = time.perf_counter()
    compiler, compiled = compile_python_function(code_str)

    solver = z3.Solver()
    solver.set("timeout", timeout_ms)

    for constraint in compiled.constraints:
        solver.add(constraint)

    scope_vars: Dict[str, z3.ArithRef] = dict(compiled.input_vars)
    scope_vars["return_val"] = compiled.return_var

    for pre_str in preconditions:
        pre_ast = ast.parse(pre_str.strip(), mode="eval").body
        solver.add(compiler.compile_bool(pre_ast, extra_vars=scope_vars))

    if not safety_invariants:
        raise ValueError("At least one safety invariant must be provided.")

    inv_exprs = []
    for inv_str in safety_invariants:
        inv_ast = ast.parse(inv_str.strip(), mode="eval").body
        inv_exprs.append(compiler.compile_bool(inv_ast, extra_vars=scope_vars))

    combined_safety = z3.And(*inv_exprs) if len(inv_exprs) > 1 else inv_exprs[0]

    # Only flag inputs that bypass explicit raise guards and still violate the postcondition.
    # Negating combined_safety turns universal verification into an existential SAT search.
    solver.add(z3.Not(compiled.raised_expr))
    solver.add(z3.Not(combined_safety))

    check_status = solver.check()
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    if check_status == z3.sat:
        model = solver.model()
        counterexample: Dict[str, int] = {}
        for arg_name, sym in compiled.input_vars.items():
            val = model.eval(sym, model_completion=True)
            counterexample[arg_name] = val.as_long()

        if compiled.has_return:
            ret_val = model.eval(compiled.return_var, model_completion=True)
            counterexample["return_val"] = ret_val.as_long()

        return VerificationResult(
            status="VULNERABLE",
            function_name=compiled.name,
            solver_time_ms=elapsed_ms,
            counterexample=counterexample,
            violated_invariant=" and ".join(safety_invariants),
            smt2_summary=solver.to_smt2(),
        )

    if check_status == z3.unsat:
        return VerificationResult(
            status="PROVEN_SAFE",
            function_name=compiled.name,
            solver_time_ms=elapsed_ms,
            smt2_summary=solver.to_smt2(),
        )

    return VerificationResult(
        status="UNKNOWN",
        function_name=compiled.name,
        solver_time_ms=elapsed_ms,
        smt2_summary=solver.to_smt2(),
    )
