#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: einen Rechenausdruck auswerten.

Zeigt, wie ein Werkzeug eine Grenze zieht: Es wertet **keinen beliebigen Code** aus,
sondern nur Zahlen, Rechenzeichen und ein paar benannte Funktionen. Ein Modell, das
``__import__('os').system(...)`` schickt, bekommt eine Fehlermeldung.
"""
import ast, math, operator, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug

ZEICHEN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
           ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
NAMEN = {"pi": math.pi, "e": math.e}
RUFE = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "exp": math.exp, "abs": abs,
        "round": round, "min": min, "max": max}


def wert(k):
    if isinstance(k, ast.Constant) and isinstance(k.value, (int, float)):
        return k.value
    if isinstance(k, ast.Name) and k.id in NAMEN:
        return NAMEN[k.id]
    if isinstance(k, ast.BinOp) and type(k.op) in ZEICHEN:
        return ZEICHEN[type(k.op)](wert(k.left), wert(k.right))
    if isinstance(k, ast.UnaryOp) and type(k.op) in ZEICHEN:
        return ZEICHEN[type(k.op)](wert(k.operand))
    if isinstance(k, ast.Call) and isinstance(k.func, ast.Name) and k.func.id in RUFE:
        return RUFE[k.func.id](*[wert(a) for a in k.args])
    raise ValueError(f"nicht erlaubt: {ast.dump(k)[:60]}")


def tun(e):
    a = e["ausdruck"]
    x = wert(ast.parse(a, mode="eval").body)
    return f"{a} = {x:.10g}"


sys.exit(werkzeug(
    "rechne", "Wertet einen Rechenausdruck aus. Erlaubt: + - * / ** % //, "
              "sqrt sin cos tan log log10 exp abs round min max, pi und e.",
    {"ausdruck": {"type": "string", "description": "z. B. 'sqrt(2)*1000' oder '70*9.81*1.5'"}},
    ["ausdruck"], {"ausdruck": "70*9.81*1.5"}, tun))
