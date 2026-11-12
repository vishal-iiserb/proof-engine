# ProofEngine

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Solver](https://img.shields.io/badge/SMT_Solver-Microsoft_Z3-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

A formal verification pipeline that compiles Python functions from their Abstract Syntax Tree (`ast`) into **Z3 SMT** constraints to catch arithmetic and boundary bugs before execution, then feeds Z3's counterexamples back to an LLM agent to patch them automatically.

## Motivation

While studying probability, discrete logic, and the mathematical foundations of language models at **IISER Bhopal**, one limitation of LLM code generation kept coming up: next-token prediction is probabilistic, not deductive. Models often write clean-looking code that quietly breaks on boundary cases (integer underflows, off-by-one bounds, unguarded leverage or fee deductions).

Standard unit tests only check the specific inputs a developer remembers to write. I built **ProofEngine** to test a **Counterexample-Guided Inductive Synthesis (CEGIS)** loop:
1. Lower a Python function's AST into symbolic Z3 integer constraints.
2. Ask Z3 to mathematically prove whether *any* valid input can violate a safety invariant.
3. If Z3 returns `SAT` (a counterexample exists), pass those exact failing variable assignments to an LLM patch agent and re-verify until Z3 proves `UNSAT` (mathematically safe).

## Architecture

```text
  Python Function ──► AST-to-Z3 Compiler (SSA + Branch Guards)
                              │
                              ▼
                     Z3 SMT Solver Check ◄── Preconditions & Safety Invariants
                        │            │
                 [SAT: Bug Found]  [UNSAT: Proven Safe]
                        │            │
                        ▼            ▼
             Extract Counterexample  Verified Output
                        │
                        ▼
               LLM Remediation Agent ──► Loops back for re-verification
```

### Repository Layout

```text
proof-engine/
├── src/
│   ├── ast_compiler.py      # Lowers Python AST (SSA variables, if/else, raise) to Z3
│   ├── verifier.py          # Z3 solver wrapper & counterexample extractor
│   ├── agents.py            # Invariant inference & counterexample-guided patch agent
│   └── pipeline.py          # Closed-loop Verify -> Patch -> Re-Verify orchestrator
├── examples/
│   ├── sample_functions.py  # Financial, buffer-indexing, and rate-limiter edge cases
│   └── quant_alpha_guard.py # Portfolio position-sizing & leverage-cap verification
├── benchmarks/
│   └── run_benchmarks.py    # Evaluates detection accuracy & Z3 latency across test cases
├── tests/
│   └── test_verifier.py     # Pytest formal verification test suite
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI workflow
├── app.py                   # Interactive Streamlit web dashboard
├── main.py                  # Command-line demo runner
├── requirements.txt
└── .env.example
```

## Quickstart

### 1. Clone and Install
```bash
git clone https://github.com/vishal-iiserb/proof-engine.git
cd proof-engine

python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run Tests, Benchmarks, and CLI Demo
```bash
# Run automated formal verification unit tests
pytest -v

# Run the benchmark suite (detection accuracy + Z3 solver time)
python benchmarks/run_benchmarks.py

# Run the end-to-end verification + auto-patch demo
python main.py
```

### 3. Launch the Streamlit UI (Optional)
To enable live LLM invariant inference and code patching (OpenAI, compatible endpoints, or local Ollama), copy `.env.example` to `.env` and add your credentials:
```bash
cp .env.example .env
streamlit run app.py
```

## Example Verification Trace

Given an unguarded transfer function (`examples/sample_functions.py`):
```python
def process_transfer(balance, amount, fee):
    new_balance = balance - amount - fee
    return new_balance
```
With preconditions `balance >= 0, amount > 0, fee >= 0` and safety invariant `return_val >= 0`:

1. **Iteration 1 (`VULNERABLE`):** Z3 finds counterexample `{"balance": 0, "amount": 1, "fee": 0, "return_val": -1}`.
2. **Patch Step:** The remediation agent adds an explicit guard (`if balance < amount + fee: raise ValueError(...)`).
3. **Iteration 2 (`PROVEN_SAFE`):** Z3 proves `UNSAT` (no non-negative input combination can return a negative balance).

## Implementation Notes & Edge Cases

- **Python Floor Division vs. Z3 Division:** Python's `//` operator performs floor division (rounding toward $-\infty$), which aligns directly with Z3's integer `/` semantics rather than C-style truncation toward zero.
- **Arbitrary-Precision Integers:** Variables are modeled with `z3.Int` instead of fixed-width bitvectors (`z3.BitVec`) so Python integers do not falsely wrap around at 32 or 64 bits.
- **Chained Comparisons:** Python parses expressions like `0 <= x < n` as a single `ast.Compare` node with multiple operators, so `compile_bool` splits them into pairwise Z3 conjunctions.
- **Current Scope:** Translating arbitrary Python semantics into first-order logic is undecidable in general. The compiler intentionally scopes to a decidable subset (integer arithmetic `+`, `-`, `*`, `//`, `%`, chained comparisons, boolean logic, SSA assignments, `if/else` branches, and `raise` guards). Planned extensions include bounded loop unrolling (`for`/`while` up to $k$ steps) and Z3 `Array` theory for list slice verification.
## Benchmark Coverage

The benchmark suite (`benchmarks/run_benchmarks.py`) evaluates 7 verification scenarios across integer arithmetic, buffer bounds, and portfolio leverage limits:

| Test Case | Expected Verdict |
| :--- | :--- |
| Unguarded Financial Transfer | `VULNERABLE` |
| Guarded Financial Transfer | `PROVEN_SAFE` |
| Off-by-One Buffer Indexing | `VULNERABLE` |
| API Rate-Limiter Quota Underflow | `VULNERABLE` |
| Unguarded Coupon Deduction | `VULNERABLE` |
| Unbounded Alpha Leverage Exposure | `VULNERABLE` |
| Guarded Alpha Leverage Exposure | `PROVEN_SAFE` |

- **Tested Environment:** Verified on macOS (Python 3.13, Z3 SMT Solver).
