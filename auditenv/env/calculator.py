"""Safe AST calculator: decimal numbers, + - * /, unary minus/plus, parentheses. Nothing else.

Numbers are parsed from the source text as Decimal (never via float). Precision 34,
max 200 characters, max nesting depth 10. Names, calls, attributes, powers, strings,
comparisons, lambdas, subscripts, scientific notation: all rejected.
"""

import ast
import re
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext

MAX_LEN = 200
MAX_DEPTH = 10
_ALLOWED_CHARS = re.compile(r"^[0-9.+\-*/()\s]*$")
_NUMBER = re.compile(r"^[0-9]+(\.[0-9]+)?$|^\.[0-9]+$")


class CalcError(Exception):
    pass


def _eval(node, src, depth, ctx):
    if depth > MAX_DEPTH:
        raise CalcError("too deep")
    if isinstance(node, ast.Expression):
        return _eval(node.body, src, depth, ctx)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        text = ast.get_source_segment(src, node)
        if text is None or not _NUMBER.match(text):
            raise CalcError("bad number")
        return Decimal(text)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand, src, depth + 1, ctx)
        return ctx.minus(v) if isinstance(node.op, ast.USub) else ctx.plus(v)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a = _eval(node.left, src, depth + 1, ctx)
        b = _eval(node.right, src, depth + 1, ctx)
        if isinstance(node.op, ast.Add):
            return ctx.add(a, b)
        if isinstance(node.op, ast.Sub):
            return ctx.subtract(a, b)
        if isinstance(node.op, ast.Mult):
            return ctx.multiply(a, b)
        return ctx.divide(a, b)
    raise CalcError("node not allowed")


def evaluate(expression) -> str:
    if not isinstance(expression, str) or not expression.strip() or len(expression) > MAX_LEN:
        raise CalcError("bad expression")
    if not _ALLOWED_CHARS.match(expression) or "**" in expression or "//" in expression:
        raise CalcError("bad characters")
    depth = best = 0
    for ch in expression:
        if ch == "(":
            depth += 1
            best = max(best, depth)
        elif ch == ")":
            depth -= 1
    if best > MAX_DEPTH:
        raise CalcError("too deep")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        raise CalcError("syntax")
    with localcontext() as ctx:
        ctx.prec = 34
        ctx.traps[DivisionByZero] = True
        ctx.traps[InvalidOperation] = True
        ctx.traps[Overflow] = True
        try:
            v = ctx.plus(_eval(tree, expression, 0, ctx))
        except (DivisionByZero, InvalidOperation, Overflow, ArithmeticError):
            raise CalcError("arithmetic")
        if not v.is_finite():
            raise CalcError("arithmetic")
        out = format(v.normalize(ctx) if v != 0 else Decimal(0), "f")
    if len(out) > 120:
        out = format(v, "E")
    return out
