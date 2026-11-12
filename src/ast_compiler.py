import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import z3


@dataclass
class CompiledFunction:
    name: str
    input_vars: Dict[str, z3.ArithRef]
    all_symbols: Dict[str, z3.ArithRef]
    constraints: List[z3.BoolRef]
    raised_expr: z3.BoolRef
    return_var: z3.ArithRef
    has_return: bool


class ASTToZ3Compiler(ast.NodeVisitor):
    """
    Walks a Python function AST and lowers integer arithmetic, assignments,
    conditionals, and raise guards into Z3 first-order logic constraints.
    """

    def __init__(self) -> None:
        self.func_name: str = ""
        self.var_versions: Dict[str, int] = {}
        self.z3_symbols: Dict[str, z3.ArithRef] = {}
        self.input_vars: Dict[str, z3.ArithRef] = {}
        self.constraints: List[z3.BoolRef] = []

        self.path_conds: List[z3.BoolRef] = []
        self.terminated_conds: List[z3.BoolRef] = []
        self.raise_conds: List[z3.BoolRef] = []
        self.return_exprs: List[Tuple[z3.BoolRef, z3.ArithRef]] = []

    def _new_ssa_var(self, name: str) -> z3.ArithRef:
        # Increment version suffix (x_0, x_1, ...) so imperative reassignments
        # turn into pure mathematical equalities in Z3.
        version = self.var_versions.get(name, -1) + 1
        self.var_versions[name] = version
        ssa_name = f"{name}_{version}"
        # Use unbounded z3.Int rather than BitVec since Python integers have arbitrary precision.
        sym = z3.Int(ssa_name)
        self.z3_symbols[ssa_name] = sym
        return sym

    def _current_var(self, name: str) -> z3.ArithRef:
        if name not in self.var_versions:
            raise ValueError(f"Variable '{name}' referenced before assignment.")
        ssa_name = f"{name}_{self.var_versions[name]}"
        return self.z3_symbols[ssa_name]

    def _active_path_guard(self) -> z3.BoolRef:
        guards = list(self.path_conds)
        for term in self.terminated_conds:
            guards.append(z3.Not(term))
        if not guards:
            return z3.BoolVal(True)
        return z3.simplify(z3.And(*guards))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.func_name = node.name
        for arg in node.args.args:
            sym = self._new_ssa_var(arg.arg)
            self.input_vars[arg.arg] = sym

        for stmt in node.body:
            self.visit(stmt)

    def visit_Expr(self, node: ast.Expr) -> None:
        # Ignore function docstrings
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise ValueError("Only single-target variable assignments (x = expr) are supported.")

        target_name = node.targets[0].id
        rhs_expr = self.compile_expr(node.value)
        prev_sym = (
            self.z3_symbols.get(f"{target_name}_{self.var_versions[target_name]}")
            if target_name in self.var_versions
            else None
        )
        new_sym = self._new_ssa_var(target_name)

        guard = self._active_path_guard()
        if prev_sym is not None and not z3.is_true(guard):
            self.constraints.append(new_sym == z3.If(guard, rhs_expr, prev_sym))
        else:
            self.constraints.append(new_sym == rhs_expr)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if not isinstance(node.target, ast.Name):
            raise ValueError("Only simple variable augmented assignments (+=, -=) are supported.")
        bin_expr = ast.BinOp(left=node.target, op=node.op, right=node.value)
        assign_node = ast.Assign(targets=[node.target], value=bin_expr)
        self.visit_Assign(assign_node)

    def visit_If(self, node: ast.If) -> None:
        cond = self.compile_bool(node.test)
        base_versions = dict(self.var_versions)

        # True branch
        self.path_conds.append(cond)
        for stmt in node.body:
            self.visit(stmt)
        self.path_conds.pop()
        true_versions = dict(self.var_versions)

        # False (else) branch
        self.var_versions = dict(base_versions)
        self.path_conds.append(z3.Not(cond))
        for stmt in node.orelse:
            self.visit(stmt)
        self.path_conds.pop()
        false_versions = dict(self.var_versions)

        # Need phi-style z3.If merges here so variables modified in only one branch
        # keep their prior SSA version on the opposite path.
        all_vars = set(true_versions.keys()) | set(false_versions.keys())
        for var in all_vars:
            t_ver = true_versions.get(var)
            f_ver = false_versions.get(var)
            if t_ver != f_ver:
                if t_ver is not None and f_ver is not None:
                    t_sym = self.z3_symbols[f"{var}_{t_ver}"]
                    f_sym = self.z3_symbols[f"{var}_{f_ver}"]
                    merged = self._new_ssa_var(var)
                    self.constraints.append(merged == z3.If(cond, t_sym, f_sym))
                elif t_ver is not None:
                    self.var_versions[var] = t_ver
                elif f_ver is not None:
                    self.var_versions[var] = f_ver

    def visit_Raise(self, node: ast.Raise) -> None:
        guard = self._active_path_guard()
        self.raise_conds.append(guard)
        self.terminated_conds.append(guard)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            return
        guard = self._active_path_guard()
        ret_val = self.compile_expr(node.value)
        self.return_exprs.append((guard, ret_val))
        self.terminated_conds.append(guard)

    def compile_expr(self, node: ast.AST, extra_vars: Optional[Dict[str, z3.ArithRef]] = None) -> Any:
        if isinstance(node, ast.Name):
            if extra_vars and node.id in extra_vars:
                return extra_vars[node.id]
            return self._current_var(node.id)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, int) and not isinstance(node.value, bool):
                return node.value
            raise ValueError(f"Unsupported constant value: {node.value!r}")

        if isinstance(node, ast.UnaryOp):
            operand = self.compile_expr(node.operand, extra_vars)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.BinOp):
            left = self.compile_expr(node.left, extra_vars)
            right = self.compile_expr(node.right, extra_vars)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            # Python's // performs floor division (toward -inf), matching Z3's integer '/' operator.
            if isinstance(node.op, ast.FloorDiv):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

        raise ValueError(f"Unsupported AST expression node: {type(node).__name__}")

    def compile_bool(self, node: ast.AST, extra_vars: Optional[Dict[str, z3.ArithRef]] = None) -> z3.BoolRef:
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return z3.BoolVal(node.value)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return z3.Not(self.compile_bool(node.operand, extra_vars))

        if isinstance(node, ast.BoolOp):
            values = [self.compile_bool(v, extra_vars) for v in node.values]
            if isinstance(node.op, ast.And):
                return z3.And(*values)
            if isinstance(node.op, ast.Or):
                return z3.Or(*values)

        if isinstance(node, ast.Compare):
            # Split chained comparisons (e.g. 0 <= x < n) into pairwise Z3 conjunctions
            clauses = []
            left = self.compile_expr(node.left, extra_vars)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.compile_expr(comparator, extra_vars)
                if isinstance(op, ast.Eq):
                    clauses.append(left == right)
                elif isinstance(op, ast.NotEq):
                    clauses.append(left != right)
                elif isinstance(op, ast.Lt):
                    clauses.append(left < right)
                elif isinstance(op, ast.LtE):
                    clauses.append(left <= right)
                elif isinstance(op, ast.Gt):
                    clauses.append(left > right)
                elif isinstance(op, ast.GtE):
                    clauses.append(left >= right)
                else:
                    raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
                left = right
            return z3.And(*clauses) if len(clauses) > 1 else clauses[0]

        raise ValueError(f"Unsupported boolean AST node: {type(node).__name__}")


def compile_python_function(code_str: str) -> Tuple[ASTToZ3Compiler, CompiledFunction]:
    tree = ast.parse(code_str)
    func_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not func_defs:
        raise ValueError("No function definition found in provided Python snippet.")

    compiler = ASTToZ3Compiler()
    compiler.visit(func_defs[0])

    raised_expr = z3.simplify(z3.Or(*compiler.raise_conds)) if compiler.raise_conds else z3.BoolVal(False)
    return_var = z3.Int("return_val")

    if compiler.return_exprs:
        ret_combined: Any = z3.IntVal(0)
        for guard, expr in reversed(compiler.return_exprs):
            ret_combined = z3.If(guard, expr, ret_combined)
        compiler.constraints.append(return_var == ret_combined)

    compiled = CompiledFunction(
        name=compiler.func_name,
        input_vars=compiler.input_vars,
        all_symbols=compiler.z3_symbols,
        constraints=compiler.constraints,
        raised_expr=raised_expr,
        return_var=return_var,
        has_return=bool(compiler.return_exprs),
    )
    return compiler, compiled
