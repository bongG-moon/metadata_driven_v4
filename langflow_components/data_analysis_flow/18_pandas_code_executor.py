from __future__ import annotations

import ast
import json
import re
import traceback
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

FORBIDDEN_NAMES = {"open", "exec", "eval", "__import__", "compile", "input"}


def execute_pandas_code(payload_value: Any, llm_response: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    parsed = _json(llm_response)
    code = parsed.get("code") or parsed.get("pandas_code") or ""
    next_payload = deepcopy(payload)
    if not code:
        return _analysis_error(next_payload, "missing_code", "pandas code LLM 응답에 code가 없습니다.", "")
    guard_error = _guard_code(code)
    if guard_error:
        return _analysis_error(next_payload, "unsafe_code", guard_error, code)
    try:
        import pandas as pd  # type: ignore

        sources = {alias: pd.DataFrame(rows) for alias, rows in next_payload.get("runtime_sources", {}).items()}
        local_ns: dict[str, Any] = {"pd": pd, "sources": sources, "result": None}
        exec(compile(code, "<pandas_code>", "exec"), {"__builtins__": {"len": len, "sum": sum, "min": min, "max": max, "round": round, "str": str, "int": int, "float": float, "list": list, "dict": dict}}, local_ns)
        result = local_ns.get("result")
        rows, columns = _result_to_rows(result)
        next_payload["analysis"] = {"status": "ok", "row_count": len(rows), "columns": columns, "rows": rows[:50]}
        next_payload["data"] = {"columns": columns, "rows": rows[:50], "row_count": len(rows), "data_ref": ""}
        next_payload.setdefault("trace", {}).setdefault("inspection", {})["pandas_execution"] = {"stage": "18_pandas_code_executor", "status": "ok", "generated_code": code, "execution_result": {"row_count": len(rows), "columns": columns, "preview_rows": rows[:20]}, "error": None}
        return next_payload
    except Exception as exc:
        return _analysis_error(next_payload, "pandas_execution_error", f"{type(exc).__name__}: {exc}", code, traceback.format_exc(limit=3))


def _guard_code(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "import 문은 허용하지 않습니다."
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
            return f"{node.func.id} 호출은 허용하지 않습니다."
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return "dunder attribute 접근은 허용하지 않습니다."
    return ""


def _result_to_rows(result: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if result is None:
        return [], []
    if hasattr(result, "to_dict"):
        rows = result.to_dict(orient="records")
    elif isinstance(result, list):
        rows = result
    elif isinstance(result, dict):
        rows = [result]
    else:
        rows = [{"result": result}]
    rows = [row if isinstance(row, dict) else {"value": row} for row in rows]
    columns = sorted({column for row in rows for column in row})
    return rows, columns


def _analysis_error(payload: dict[str, Any], error_type: str, message: str, code: str, tb: str = "") -> dict[str, Any]:
    payload["analysis"] = {"status": "error", "row_count": 0, "columns": [], "rows": [], "error": {"type": error_type, "message": message}}
    payload.setdefault("trace", {}).setdefault("errors", []).append({"type": error_type, "message": message})
    payload.setdefault("trace", {}).setdefault("inspection", {})["pandas_execution"] = {"stage": "18_pandas_code_executor", "status": "error", "generated_code": code, "error": {"type": error_type, "message": message, "traceback_summary": tb[:1000]}}
    return payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    text = str(value or "")
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class PandasCodeExecutor(Component):
    display_name = "18 pandas 코드 실행기"
    description = "Langflow 에이전트/LLM이 반환한 pandas JSON 코드를 안전 검사 후 실행합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), MessageTextInput(name="llm_response", display_name="pandas 코드 LLM 응답", required=True)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=execute_pandas_code(getattr(self, "payload", None), getattr(self, "llm_response", "")))
