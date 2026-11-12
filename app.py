import streamlit as st
from src.pipeline import run_verification_loop

st.set_page_config(page_title="ProofEngine | Z3 + LLM Formal Verification", layout="wide")

st.title("ProofEngine")
st.caption("Symbolic AST compilation + Microsoft Z3 SMT solving + counterexample-guided LLM patching")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("1. Python Function")
    default_code = """def process_transfer(balance, amount, fee):
    new_balance = balance - amount - fee
    return new_balance"""
    code_input = st.text_area("Source Code", value=default_code, height=180)

    pre_input = st.text_input(
        "Preconditions (comma-separated)",
        value="balance >= 0, amount > 0, fee >= 0",
    )
    inv_input = st.text_input(
        "Safety Invariants (comma-separated)",
        value="return_val >= 0",
    )

    run_btn = st.button("Verify & Auto-Patch", type="primary")

with col_right:
    st.subheader("2. Z3 Solver Proof & Patch Trace")
    if run_btn:
        preconditions = [p.strip() for p in pre_input.split(",") if p.strip()]
        invariants = [i.strip() for i in inv_input.split(",") if i.strip()]

        with st.spinner("Compiling AST to Z3 constraints and solving..."):
            result_run = run_verification_loop(
                code_str=code_input,
                preconditions=preconditions,
                safety_invariants=invariants,
            )

        for idx, iteration in enumerate(result_run.iterations, start=1):
            with st.expander(
                f"Iteration {idx}: {iteration.status} ({iteration.solver_time_ms} ms)",
                expanded=True,
            ):
                if iteration.status == "VULNERABLE":
                    st.error(f"Safety invariant violated: `{iteration.violated_invariant}`")
                    st.write("**Z3 Counterexample Inputs:**")
                    st.json(iteration.counterexample)
                elif iteration.status == "PROVEN_SAFE":
                    st.success("UNSAT: Proven safe across all inputs satisfying preconditions.")

        if result_run.is_verified:
            st.subheader("3. Verified Code")
            st.code(result_run.final_code, language="python")
