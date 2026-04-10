#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从用户提交的 Python 源码中安全加载 backtrader.Strategy 子类。
禁止 import / exec / eval 等危险操作（基于 AST 与关键字黑名单）。
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, Optional, Type

FORBIDDEN_RE = re.compile(
    r"\b(__import__|exec|eval|compile|open|input|breakpoint|globals|locals|vars|"
    r"getattr|setattr|delattr|memoryview|help)\s*\(",
    re.I,
)
FORBIDDEN_SNIPPETS = (
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import requests",
    "import pickle",
    "import shelve",
    "import ctypes",
    "import multiprocessing",
    "from os",
    "from sys",
    "from subprocess",
    "__class__",
    "__bases__",
    "__subclasses__",
    "__globals__",
    "__code__",
)


class UnsafeCodeError(ValueError):
    pass


def _validate_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise UnsafeCodeError("策略代码中不允许使用 import（仅可使用注入的 bt）")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile", "__import__", "open", "input"):
                    raise UnsafeCodeError(f"禁止调用: {node.func.id}")


def load_custom_strategy_class(
    user_code: str,
    *,
    max_len: int = 12000,
) -> Type[Any]:
    """
    执行用户代码，返回其定义的、继承 bt.Strategy 的类（取第一个匹配的子类）。
    """
    if not user_code or not str(user_code).strip():
        raise UnsafeCodeError("请提供策略代码")

    code = str(user_code).strip()
    if len(code) > max_len:
        raise UnsafeCodeError(f"代码长度超过上限 {max_len} 字符")

    for snip in FORBIDDEN_SNIPPETS:
        if snip.lower() in code.lower():
            raise UnsafeCodeError("代码包含不允许的关键字")

    if FORBIDDEN_RE.search(code):
        raise UnsafeCodeError("代码包含不允许的调用")

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise UnsafeCodeError(f"语法错误: {e}") from e

    _validate_ast(tree)

    try:
        import backtrader as bt
    except ImportError as e:
        raise UnsafeCodeError("服务器未安装 backtrader，请执行: pip install backtrader") from e

    safe_builtins: Dict[str, Any] = {
        "range": range,
        "len": len,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sum": sum,
        "float": float,
        "int": int,
        "bool": bool,
        "str": str,
        "enumerate": enumerate,
        "zip": zip,
        "isinstance": isinstance,
        "super": super,
        "property": property,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "True": True,
        "False": False,
        "None": None,
    }

    g: Dict[str, Any] = {"__builtins__": safe_builtins, "bt": bt}
    lcl: Dict[str, Any] = {}

    try:
        exec(compile(tree, "<user_strategy>", "exec"), g, lcl)
    except Exception as e:
        raise UnsafeCodeError(f"策略执行失败: {e}") from e

    for _name, obj in lcl.items():
        if isinstance(obj, type) and issubclass(obj, bt.Strategy) and obj is not bt.Strategy:
            return obj

    raise UnsafeCodeError(
        "未找到继承 bt.Strategy 的策略类，请定义: class CustomStrategy(bt.Strategy): ..."
    )
