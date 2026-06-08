"""Safe calculator — AST-based expression evaluator (NO eval)."""
import ast
import math
import operator


class CalculatorTool:
    name = "calculator"
    description = "Safe math evaluator. Supports + - * / // % **, sqrt, abs, round, pow. Example: '(15 + 7) * 3 / 2'"
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "Math expression to evaluate."}},
        "required": ["expression"],
    }

    _ALLOWED_NODES = {
        ast.Expression, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub,
        ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.Call, ast.Name, ast.Load,
    }

    _ALLOWED_FUNCS = {"abs": abs, "round": round, "sqrt": math.sqrt, "pow": pow}

    _OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow,
    }

    def run(self, expression: str) -> str:
        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except SyntaxError as exc:
            return f'{{"error": "Syntax error: {exc}"}}'

        if not self._is_safe(tree):
            return '{"error": "Disallowed operation. Only basic arithmetic and sqrt/abs/round/pow are permitted."}'

        try:
            result = self._eval(tree.body)
        except ZeroDivisionError:
            return '{"error": "Division by zero."}'
        except Exception as exc:
            return f'{{"error": "Evaluation failed: {exc}"}}'

        if isinstance(result, float) and result == int(result):
            result = int(result)
        return str(result)

    def _is_safe(self, node: ast.AST) -> bool:
        if type(node) not in self._ALLOWED_NODES:
            return False
        return all(self._is_safe(c) for c in ast.iter_child_nodes(node))

    def _eval(self, node: ast.AST):
        match node:
            case ast.Expression(body=body):
                return self._eval(body)
            case ast.Constant(value=v):
                if isinstance(v, (int, float)): return v
                raise TypeError(f"Unsupported constant: {type(v)}")
            case ast.UnaryOp(op=op, operand=operand):
                val = self._eval(operand)
                if isinstance(op, ast.UAdd): return +val
                if isinstance(op, ast.USub): return -val
            case ast.BinOp(left=left, op=op, right=right):
                lv, rv = self._eval(left), self._eval(right)
                op_fn = self._OPS.get(type(op))
                if op_fn is None: raise TypeError(f"Unsupported operator: {type(op).__name__}")
                return op_fn(lv, rv)
            case ast.Call(func=func, args=args, keywords=keywords):
                if keywords: raise TypeError("Keyword arguments are not supported.")
                if not isinstance(func, ast.Name): raise TypeError("Only simple function calls allowed.")
                fn = self._ALLOWED_FUNCS.get(func.id)
                if fn is None: raise TypeError(f"Function '{func.id}' is not allowed.")
                return fn(*(self._eval(a) for a in args))
            case ast.Name(id=name):
                if name in self._ALLOWED_FUNCS: return self._ALLOWED_FUNCS[name]
                raise TypeError(f"Name '{name}' is not allowed.")
            case _:
                raise TypeError(f"Unsupported AST node: {type(node).__name__}")
