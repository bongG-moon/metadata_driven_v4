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
    filter_plan = _pandas_filter_plan(next_payload)
    code = _with_pandas_filter_preamble(code, filter_plan)
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
        next_payload.setdefault("trace", {}).setdefault("inspection", {})["pandas_execution"] = {
            "stage": "17_pandas_code_executor",
            "status": "ok",
            "generated_code": code,
            "pandas_filter_plan": filter_plan,
            "execution_result": {"row_count": len(rows), "columns": columns, "preview_rows": rows[:20]},
            "error": None,
        }
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
    payload.setdefault("trace", {}).setdefault("inspection", {})["pandas_execution"] = {"stage": "17_pandas_code_executor", "status": "error", "generated_code": code, "error": {"type": error_type, "message": message, "traceback_summary": tb[:1000]}}
    return payload


def _pandas_filter_plan(payload: dict[str, Any]) -> list[dict[str, Any]]:
    plan = payload.get("intent_plan") if isinstance(payload.get("intent_plan"), dict) else {}
    jobs = plan.get("retrieval_jobs") if isinstance(plan.get("retrieval_jobs"), list) else []
    filter_plan: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        alias = str(job.get("source_alias") or job.get("dataset_key") or "").strip()
        if not alias:
            continue
        conditions = _filter_conditions(job.get("filters"))
        if conditions:
            filter_plan.append({"source_alias": alias, "dataset_key": job.get("dataset_key", ""), "conditions": conditions})
    return filter_plan


def _with_pandas_filter_preamble(code: Any, filter_plan: list[dict[str, Any]]) -> str:
    base_code = str(code or "").strip()
    preamble = _pandas_filter_preamble(filter_plan)
    if not preamble:
        return base_code
    return preamble + "\n\n" + base_code


def _pandas_filter_preamble(filter_plan: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for job_index, item in enumerate(filter_plan, start=1):
        alias = str(item.get("source_alias") or "").strip()
        conditions = item.get("conditions") if isinstance(item.get("conditions"), list) else []
        if not alias or not conditions:
            continue
        df_var = f"_filtered_source_{job_index}_{_safe_name(alias)}"
        lines.append(f"{df_var} = sources.get({alias!r})")
        lines.append(f"if {df_var} is not None:")
        lines.append("    sources = dict(sources)")
        lines.append(f"    {df_var} = {df_var}.copy()")
        for condition_index, condition in enumerate(conditions, start=1):
            lines.extend(_condition_code(df_var, job_index, condition_index, condition))
        lines.append(f"    sources[{alias!r}] = {df_var}")
    return "\n".join(lines)


def _condition_code(df_var: str, job_index: int, condition_index: int, condition: dict[str, Any]) -> list[str]:
    field = str(condition.get("field") or "").strip()
    operator = str(condition.get("operator") or "eq").strip().lower()
    values = condition.get("values") if isinstance(condition.get("values"), list) else []
    if not field or not values:
        return []
    col_var = f"_filter_col_{job_index}_{condition_index}"
    values_var = f"_filter_values_{job_index}_{condition_index}"
    mask_var = f"_filter_mask_{job_index}_{condition_index}"
    candidates = _field_candidates(field)
    lines = [f"    {col_var} = {_column_choice_expression(df_var, candidates)}", f"    {values_var} = {values!r}", f"    if {col_var}:"]
    if operator in {"eq", "=", "in"}:
        lines.append(f"        {df_var} = {df_var}[{df_var}[{col_var}].isin({values_var})]")
    elif operator in {"ne", "!=", "not_in", "not in"}:
        lines.append(f"        {df_var} = {df_var}[~{df_var}[{col_var}].isin({values_var})]")
    elif operator in {"contains", "like"}:
        lines.append(f"        {mask_var} = {df_var}[{col_var}].astype(str).str.contains(str({values_var}[0]), case=False, na=False, regex=False)")
        lines.append(f"        for _filter_value in {values_var}[1:]:")
        lines.append(f"            {mask_var} = {mask_var} | {df_var}[{col_var}].astype(str).str.contains(str(_filter_value), case=False, na=False, regex=False)")
        lines.append(f"        {df_var} = {df_var}[{mask_var}]")
    return lines


def _column_choice_expression(df_var: str, candidates: list[str]) -> str:
    expression = "''"
    for candidate in reversed(candidates):
        expression = f"{candidate!r} if {candidate!r} in {df_var}.columns else ({expression})"
    return expression


def _filter_conditions(filters: Any) -> list[dict[str, Any]]:
    if isinstance(filters, list):
        items = [(condition.get("field") or condition.get("column"), condition) for condition in filters if isinstance(condition, dict)]
    elif isinstance(filters, dict):
        items = list(filters.items())
    else:
        return []
    result: list[dict[str, Any]] = []
    for field, condition in items:
        field_text = str(field or "").strip()
        if not field_text:
            continue
        if isinstance(condition, dict):
            operator = condition.get("operator", condition.get("op", "eq"))
            values = condition.get("values", condition.get("value", []))
        else:
            operator = "eq"
            values = condition
        normalized_values = _as_values(values)
        if normalized_values:
            result.append({"field": field_text, "operator": str(operator or "eq"), "values": normalized_values})
    return result


def _as_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]
    if isinstance(value, tuple):
        return [item for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [value]


def _field_candidates(field: str) -> list[str]:
    aliases = {
        "DATE": ["DATE", "WORK_DATE", "WORK_DT", "LOAD_DT", "BASE_DT"],
        "WORK_DATE": ["WORK_DATE", "WORK_DT", "DATE"],
        "MODE": ["MODE", "Mode"],
        "DEN": ["DEN", "DENSITY"],
        "PKG_TYPE1": ["PKG_TYPE1", "PKG1"],
        "PKG_TYPE2": ["PKG_TYPE2", "PKG2"],
        "MCP_NO": ["MCP_NO", "MCP NO"],
        "TSV_DIE_TYP": ["TSV_DIE_TYP", "TSV_DIE_TYPE"],
        "OPER_NUM": ["OPER_NUM", "OPER"],
        "OPER_NAME": ["OPER_NAME", "OPER_NM"],
        "EQP_ID": ["EQP_ID", "EQUIP_ID"],
        "EQP_MODEL": ["EQP_MODEL", "EQUIP_MODEL", "EQPIP_MODEL"],
    }
    return aliases.get(field, [field])


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"\W+", "_", value)
    return cleaned.strip("_") or "source"


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    text = _text_value(value)
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    elif "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _text_value(value: Any) -> str:
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text
    data = getattr(value, "data", None)
    if isinstance(data, dict):
        for key in ("text", "content", "message", "output"):
            if isinstance(data.get(key), str):
                return data[key]
    return str(value or "")


class PandasCodeExecutor(Component):
    display_name = "17 pandas 코드 실행기"
    description = "Langflow 에이전트/LLM이 반환한 pandas JSON 코드를 안전 검사 후 실행합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), MessageTextInput(name="llm_response", display_name="pandas 코드 LLM 응답", required=True)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=execute_pandas_code(getattr(self, "payload", None), getattr(self, "llm_response", "")))
