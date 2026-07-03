from __future__ import annotations

import ast
import json
import re
import traceback
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

FORBIDDEN_NAMES = {"open", "exec", "eval", "__import__", "compile", "input"}
RESULT_PREVIEW_LIMIT = 50
TRACE_PREVIEW_LIMIT = 5


def execute_pandas_code(payload_value: Any, llm_response: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    parsed = _json(llm_response)
    llm_code = str(parsed.get("code") or parsed.get("pandas_code") or "")
    code = llm_code
    next_payload = deepcopy(payload)
    if not code:
        return _analysis_error(next_payload, "missing_code", "pandas code LLM 응답에 code가 없습니다.", "")
    filter_plan = _pandas_filter_plan(next_payload)
    filter_preamble = _pandas_filter_preamble(filter_plan)
    code = _with_pandas_filter_preamble(code, filter_plan)
    helper_trace = _runtime_helper_trace(code)
    guard_error = _guard_code(code)
    if guard_error:
        return _analysis_error(next_payload, "unsafe_code", guard_error, code, "", llm_code, filter_preamble, filter_plan)
    try:
        import pandas as pd  # type: ignore

        sources = {alias: pd.DataFrame(rows) for alias, rows in next_payload.get("runtime_sources", {}).items()}
        safe_builtins = {
            "all": all,
            "any": any,
            "bool": bool,
            "dict": dict,
            "enumerate": enumerate,
            "float": float,
            "hasattr": hasattr,
            "int": int,
            "isinstance": isinstance,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "range": range,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
        }
        exec_ns: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "pd": pd,
            "sources": sources,
            "result": None,
            "result_df": None,
        }
        exec(compile(code, "<pandas_code>", "exec"), exec_ns, exec_ns)
        result = exec_ns.get("result")
        if result is None:
            result = exec_ns.get("result_df")
        rows, columns = _result_to_rows(result)
        next_payload["_full_result_rows"] = rows
        next_payload["analysis"] = {
            "status": "ok",
            "row_count": len(rows),
            "columns": columns,
            "rows": rows[:RESULT_PREVIEW_LIMIT],
            "analysis_code": code,
            "llm_generated_code": llm_code,
            "pandas_filter_preamble": filter_preamble,
            "effective_code_with_helpers": helper_trace["effective_code_with_helpers"],
            "used_helpers": helper_trace["used_helpers"],
        }
        next_payload["data"] = {"columns": columns, "rows": rows[:RESULT_PREVIEW_LIMIT], "row_count": len(rows), "data_ref": ""}
        next_payload.setdefault("trace", {}).setdefault("inspection", {})["pandas_execution"] = {
            "stage": "17_pandas_code_executor",
            "status": "ok",
            "generated_code": code,
            "llm_generated_code": llm_code,
            "pandas_filter_preamble": filter_preamble,
            "effective_code_with_helpers": helper_trace["effective_code_with_helpers"],
            "used_helpers": helper_trace["used_helpers"],
            "helper_sources": helper_trace["helper_sources"],
            "pandas_filter_plan": filter_plan,
            "execution_result": {"row_count": len(rows), "columns": columns, "preview_rows": rows[:TRACE_PREVIEW_LIMIT]},
            "error": None,
        }
        return next_payload
    except Exception as exc:
        return _analysis_error(next_payload, "pandas_execution_error", f"{type(exc).__name__}: {exc}", code, traceback.format_exc(limit=3), llm_code, filter_preamble, filter_plan)


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
    rows = [_json_ready(row if isinstance(row, dict) else {"value": row}) for row in rows]
    columns = sorted({column for row in rows for column in row})
    return rows, columns


def _json_ready(value: Any) -> Any:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        return None if value != value or value in (float("inf"), -float("inf")) else value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_ready(item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _json_ready(item_value) for key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item_value) for item_value in value]
    try:
        if value != value:
            return None
    except Exception:
        pass
    return str(value)


def _analysis_error(
    payload: dict[str, Any],
    error_type: str,
    message: str,
    code: str,
    tb: str = "",
    llm_code: str = "",
    filter_preamble: str = "",
    filter_plan: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    helper_trace = _runtime_helper_trace(code)
    payload["analysis"] = {
        "status": "error",
        "row_count": 0,
        "columns": [],
        "rows": [],
        "error": {"type": error_type, "message": message},
        "errors": [message],
        "repairable_errors": [message],
        "analysis_code": code,
        "llm_generated_code": llm_code or code,
        "pandas_filter_preamble": filter_preamble,
        "effective_code_with_helpers": helper_trace["effective_code_with_helpers"],
        "used_helpers": helper_trace["used_helpers"],
    }
    payload.setdefault("trace", {}).setdefault("errors", []).append({"type": error_type, "message": message})
    payload.setdefault("trace", {}).setdefault("inspection", {})["pandas_execution"] = {
        "stage": "17_pandas_code_executor",
        "status": "error",
        "generated_code": code,
        "llm_generated_code": llm_code or code,
        "pandas_filter_preamble": filter_preamble,
        "pandas_filter_plan": filter_plan or [],
        "effective_code_with_helpers": helper_trace["effective_code_with_helpers"],
        "used_helpers": helper_trace["used_helpers"],
        "helper_sources": helper_trace["helper_sources"],
        "error": {"type": error_type, "message": message, "traceback_summary": tb[:1000]},
    }
    return payload


def _runtime_helper_trace(code: str) -> dict[str, Any]:
    helper_names = _used_inline_helpers(code)
    return {
        "used_helpers": helper_names,
        "helper_sources": [],
        "effective_code_with_helpers": str(code or "").strip(),
    }


def _used_inline_helpers(code: str) -> list[str]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    top_level_functions = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]
    used: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in top_level_functions:
            if node.func.id not in used:
                used.append(node.func.id)
    return used


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, "", {}, []):
        return []
    return [value]


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
    operator = _normalize_filter_operator(condition.get("operator") or "eq")
    values = condition.get("values") if isinstance(condition.get("values"), list) else []
    if not field or (not values and operator not in {"is_null", "is_empty", "null_or_empty", "not_null", "not_empty"}):
        return []
    col_var = f"_filter_col_{job_index}_{condition_index}"
    values_var = f"_filter_values_{job_index}_{condition_index}"
    mask_var = f"_filter_mask_{job_index}_{condition_index}"
    candidates = _field_candidates(field)
    lines = [f"    {col_var} = {_column_choice_expression(df_var, candidates)}", f"    {values_var} = {values!r}", f"    if {col_var}:"]
    if operator in {"eq", "in"}:
        lines.append(f"        {df_var} = {df_var}[{df_var}[{col_var}].isin({values_var})]")
    elif operator in {"ne", "not_in"}:
        lines.append(f"        {df_var} = {df_var}[~{df_var}[{col_var}].isin({values_var})]")
    elif operator in {"contains", "like"}:
        lines.append(f"        {mask_var} = {df_var}[{col_var}].astype(str).str.contains(str({values_var}[0]), case=False, na=False, regex=False)")
        lines.append(f"        for _filter_value in {values_var}[1:]:")
        lines.append(f"            {mask_var} = {mask_var} | {df_var}[{col_var}].astype(str).str.contains(str(_filter_value), case=False, na=False, regex=False)")
        lines.append(f"        {df_var} = {df_var}[{mask_var}]")
    elif operator in {"starts_with", "startswith", "prefix"}:
        lines.append(f"        {mask_var} = {df_var}[{col_var}].astype(str).str.startswith(str({values_var}[0]), na=False)")
        lines.append(f"        for _filter_value in {values_var}[1:]:")
        lines.append(f"            {mask_var} = {mask_var} | {df_var}[{col_var}].astype(str).str.startswith(str(_filter_value), na=False)")
        lines.append(f"        {df_var} = {df_var}[{mask_var}]")
    elif operator in {"ends_with", "endswith", "suffix"}:
        lines.append(f"        {mask_var} = {df_var}[{col_var}].astype(str).str.endswith(str({values_var}[0]), na=False)")
        lines.append(f"        for _filter_value in {values_var}[1:]:")
        lines.append(f"            {mask_var} = {mask_var} | {df_var}[{col_var}].astype(str).str.endswith(str(_filter_value), na=False)")
        lines.append(f"        {df_var} = {df_var}[{mask_var}]")
    elif operator in {"is_null", "is_empty", "null_or_empty", "not_null", "not_empty"}:
        lines.extend(_null_empty_condition_lines(df_var, col_var, mask_var, operator))
    elif operator in {"or", "any"} and _has_operator_dict(values):
        lines.extend(_compound_condition_lines(df_var, col_var, mask_var, values))
    else:
        lines.append("        pass")
    return lines


def _normalize_filter_operator(value: Any) -> str:
    text = re.sub(r"[\s-]+", "_", str(value or "eq").strip()).lower()
    aliases = {
        "=": "eq",
        "==": "eq",
        "!=": "ne",
        "not in": "not_in",
        "notin": "not_in",
        "starts": "starts_with",
        "startwith": "starts_with",
        "startswith": "starts_with",
        "starts_with_any": "starts_with",
        "prefix": "starts_with",
        "endswith": "ends_with",
        "suffix": "ends_with",
        "isnull": "is_null",
        "is_null": "is_null",
        "null": "is_null",
        "none": "is_null",
        "isempty": "is_empty",
        "is_empty": "is_empty",
        "empty": "is_empty",
        "blank": "is_empty",
        "null_or_empty": "null_or_empty",
        "is_null_or_empty": "null_or_empty",
        "notnull": "not_null",
        "not_null": "not_null",
        "notempty": "not_empty",
        "not_empty": "not_empty",
        "any": "any",
        "or": "or",
    }
    return aliases.get(text, text)


def _null_empty_condition_lines(df_var: str, col_var: str, mask_var: str, operator: str) -> list[str]:
    series = f"{df_var}[{col_var}]"
    if operator == "is_null":
        return [f"        {df_var} = {df_var}[{series}.isna()]"]
    if operator == "is_empty":
        return [f"        {df_var} = {df_var}[{series}.astype(str).str.strip().eq('')]"]
    if operator == "null_or_empty":
        return [f"        {mask_var} = {series}.isna() | {series}.astype(str).str.strip().eq('')", f"        {df_var} = {df_var}[{mask_var}]"]
    if operator == "not_null":
        return [f"        {df_var} = {df_var}[{series}.notna()]"]
    if operator == "not_empty":
        return [f"        {df_var} = {df_var}[~{series}.astype(str).str.strip().eq('')]"]
    return ["        pass"]


def _has_operator_dict(values: list[Any]) -> bool:
    return any(isinstance(item, dict) and (item.get("operator") or item.get("op")) for item in values)


def _compound_condition_lines(df_var: str, col_var: str, mask_var: str, values: list[Any]) -> list[str]:
    series = f"{df_var}[{col_var}]"
    lines = [f"        {mask_var} = False"]
    for item in values:
        if not isinstance(item, dict):
            continue
        op = _normalize_filter_operator(item.get("operator") or item.get("op") or "eq")
        raw_values = _as_values(item.get("values", item.get("value", [])))
        if op == "is_null":
            lines.append(f"        {mask_var} = {mask_var} | {series}.isna()")
        elif op == "is_empty":
            lines.append(f"        {mask_var} = {mask_var} | {series}.astype(str).str.strip().eq('')")
        elif op == "null_or_empty":
            lines.append(f"        {mask_var} = {mask_var} | {series}.isna() | {series}.astype(str).str.strip().eq('')")
        elif op in {"eq", "in"} and raw_values:
            lines.append(f"        {mask_var} = {mask_var} | {series}.isin({raw_values!r})")
        elif op == "starts_with" and raw_values:
            lines.append(f"        {mask_var} = {mask_var} | {series}.astype(str).str.startswith(str({raw_values[0]!r}), na=False)")
            for raw_value in raw_values[1:]:
                lines.append(f"        {mask_var} = {mask_var} | {series}.astype(str).str.startswith(str({raw_value!r}), na=False)")
        elif op in {"contains", "like"} and raw_values:
            lines.append(f"        {mask_var} = {mask_var} | {series}.astype(str).str.contains(str({raw_values[0]!r}), case=False, na=False, regex=False)")
            for raw_value in raw_values[1:]:
                lines.append(f"        {mask_var} = {mask_var} | {series}.astype(str).str.contains(str({raw_value!r}), case=False, na=False, regex=False)")
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
        elif isinstance(condition, list) and _has_operator_dict(condition):
            operator = "or"
            values = condition
        else:
            operator = "eq"
            values = condition
        normalized_values = _as_values(values)
        normalized_operator = _normalize_filter_operator(operator or "eq")
        if normalized_values or normalized_operator in {"is_null", "is_empty", "null_or_empty", "not_null", "not_empty"}:
            result.append({"field": field_text, "operator": normalized_operator, "values": normalized_values})
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
        try:
            parsed = json.loads(text, strict=False)
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
