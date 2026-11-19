import pytest

from auditenv.env.calculator import CalcError, evaluate


@pytest.mark.parametrize("expr,val", [("1+2*3", "7"), ("(1.10+2.20)/3", "1.1"), ("-5*-(2)", "10"), ("0.1+0.2", "0.3"),
                                      ("10/4", "2.5"), ("+3", "3"), ("2-2", "0")])
def test_arithmetic(expr, val):
    assert evaluate(expr) == val


@pytest.mark.parametrize("expr", [
    "__import__('os').system('id')", "lambda: 1", "(lambda x: x)(1)", "9**9**9", "2**10", "a+1", "abs(-1)",
    "open('/etc/passwd').read()", "1" * 201, "1/0", "0/0", "(" * 11 + "1" + ")" * 11, "1e999", "[1,2]", "{}",
    "1 if 1 else 0", "~1", "1<2", "'a'", "1//2", "1%2", "", "   ", "().__class__", "1;2", "\\x41",
])
def test_rejected(expr):
    with pytest.raises(CalcError):
        evaluate(expr)


def test_non_string_rejected():
    for x in (None, 1, [1], {"e": 1}):
        with pytest.raises(CalcError):
            evaluate(x)


def test_ten_levels_ok_and_precision_34():
    assert evaluate("(" * 10 + "1" + ")" * 10) == "1"
    assert evaluate("1/3") == "0." + "3" * 34
