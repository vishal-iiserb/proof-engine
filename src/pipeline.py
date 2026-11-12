from dataclasses import dataclass, field
from typing import List, Optional
from src.agents import generate_remediation_patch, synthesize_invariants
from src.verifier import VerificationResult, verify_function


@dataclass
class PipelineRun:
    original_code: str
    final_code: str
    preconditions: List[str]
    safety_invariants: List[str]
    iterations: List[VerificationResult] = field(default_factory=list)
    is_verified: bool = False


def run_verification_loop(
    code_str: str,
    preconditions: Optional[List[str]] = None,
    safety_invariants: Optional[List[str]] = None,
    max_iterations: int = 3,
) -> PipelineRun:
    """
    Runs a Counterexample-Guided Inductive Synthesis (CEGIS) loop:
    verify -> extract counterexample -> synthesize patch -> re-verify.
    """
    if preconditions is None or safety_invariants is None:
        inferred = synthesize_invariants(code_str)
        preconditions = preconditions or inferred["preconditions"]
        safety_invariants = safety_invariants or inferred["safety_invariants"]

    current_code = code_str.strip()
    history: List[VerificationResult] = []

    for _ in range(max_iterations):
        result = verify_function(
            code_str=current_code,
            preconditions=preconditions,
            safety_invariants=safety_invariants,
        )
        history.append(result)

        if result.status == "PROVEN_SAFE":
            return PipelineRun(
                original_code=code_str.strip(),
                final_code=current_code,
                preconditions=preconditions,
                safety_invariants=safety_invariants,
                iterations=history,
                is_verified=True,
            )

        if result.status == "VULNERABLE" and result.counterexample:
            current_code = generate_remediation_patch(
                code_str=current_code,
                counterexample=result.counterexample,
                violated_invariant=result.violated_invariant or "",
            )
        else:
            break

    return PipelineRun(
        original_code=code_str.strip(),
        final_code=current_code,
        preconditions=preconditions,
        safety_invariants=safety_invariants,
        iterations=history,
        is_verified=False,
    )
