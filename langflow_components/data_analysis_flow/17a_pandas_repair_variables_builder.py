from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, Output
from lfx.schema.message import Message

DEFAULT_MAX_ATTEMPTS = 1


def build_repair_payload(payload_value: Any, max_attempts: Any = DEFAULT_MAX_ATTEMPTS) -> dict[str, Any]:
    payload = _payload(payload_value)
    attempt = _int(payload.get("pandas_retry_attempt"), 0) + 1
    max_count = _int(max_attempts, DEFAULT_MAX_ATTEMPTS)
    errors = _pandas_errors(payload)
    required = bool(errors) and attempt <= max_count
    next_payload = deepcopy(payload)
    next_payload["pandas_retry_attempt"] = attempt if required else payload.get("pandas_retry_attempt", 0)
    next_payload["pandas_repair"] = {
        "required": required,
        "route": "repair" if required else ("success" if not errors else "failed"),
        "attempt": attempt,
        "max_attempts": max_count,
        "errors": errors,
        "reason": "pandas 실행 실패 정보를 기반으로 LLM 재생성이 필요합니다." if required else "pandas repair가 필요하지 않습니다.",
    }
    return next_payload


def build_variables(payload_value: Any, max_attempts: Any = DEFAULT_MAX_ATTEMPTS) -> dict[str, Any]:
    payload = build_repair_payload(payload_value, max_attempts)
    context = _repair_context(payload)
    return {
        "repair_required": "true" if payload.get("pandas_repair", {}).get("required") else "false",
        "intent_plan_json": json.dumps(payload.get("intent_plan", {}), ensure_ascii=False, indent=2),
        "source_schema_json": json.dumps(context["source_schema"], ensure_ascii=False, indent=2),
        "source_preview_json": json.dumps(context["source_preview"], ensure_ascii=False, indent=2),
        "failed_code": context["failed_code"],
        "error_context_json": json.dumps(context["error_context"], ensure_ascii=False, indent=2),
        "function_case_selection_json": json.dumps(_function_case_selection(payload), ensure_ascii=False, indent=2),
        "output_schema": json.dumps({"code": "수정된 pandas code. 반드시 result 또는 result_df를 설정한다."}, ensure_ascii=False, indent=2),
    }


def _repair_context(payload: dict[str, Any]) -> dict[str, Any]:
    runtime_sources = payload.get("runtime_sources") if isinstance(payload.get("runtime_sources"), dict) else {}
    schema = {alias: sorted({column for row in rows[:20] for column in row}) for alias, rows in runtime_sources.items() if isinstance(rows, list)}
    preview = {alias: rows[:5] for alias, rows in runtime_sources.items() if isinstance(rows, list)}
    pandas_trace = payload.get("trace", {}).get("inspection", {}).get("pandas_execution", {}) if isinstance(payload.get("trace"), dict) else {}
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    failed_code = str(pandas_trace.get("llm_generated_code") or analysis.get("llm_generated_code") or "")
    executed_code = str(pandas_trace.get("generated_code") or analysis.get("analysis_code") or "")
    return {
        "source_schema": schema,
        "source_preview": preview,
        "failed_code": failed_code or executed_code,
        "error_context": {
            "analysis_error": deepcopy(analysis.get("error", {})),
            "analysis_errors": deepcopy(analysis.get("errors", [])),
            "repairable_errors": deepcopy(analysis.get("repairable_errors", [])),
            "trace_error": deepcopy(pandas_trace.get("error", {})),
            "executed_code_with_preamble": executed_code,
            "pandas_filter_preamble": str(pandas_trace.get("pandas_filter_preamble") or analysis.get("pandas_filter_preamble") or ""),
            "pandas_filter_plan": deepcopy(pandas_trace.get("pandas_filter_plan", [])),
            "repair_code_scope": "failed_code는 LLM이 생성한 원본 pandas 코드입니다. executor가 pandas_filter_preamble을 retry 실행 때 다시 자동으로 붙입니다.",
            "pandas_repair": deepcopy(payload.get("pandas_repair", {})),
        },
    }


def _function_case_selection(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("intent_plan") if isinstance(payload.get("intent_plan"), dict) else {}
    case = plan.get("pandas_function_case") if isinstance(plan.get("pandas_function_case"), dict) else {}
    steps = plan.get("pandas_execution_plan") if isinstance(plan.get("pandas_execution_plan"), list) else []
    selected_steps = [deepcopy(step) for step in steps if isinstance(step, dict) and str(step.get("operation") or "") == "apply_pandas_function_case"]
    selected_cases = _selected_function_cases(plan, case, selected_steps)
    return {
        "selected_case": deepcopy(case),
        "selected_cases": selected_cases,
        "selected_steps": selected_steps,
        "available_helpers": _helpers_from_selected_cases(selected_cases),
    }


def _helpers_from_selected_cases(selected_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    helpers = []
    for item in selected_cases:
        if not isinstance(item, dict):
            continue
        name = str(item.get("function_name") or "").strip()
        if not name or any(helper.get("function_name") == name for helper in helpers):
            continue
        helper = {"function_name": name}
        for key in (
            "signature",
            "description",
            "rule",
            "usage_rule",
            "default_token_columns",
        ):
            if item.get(key) not in (None, "", [], {}):
                helper[key] = deepcopy(item.get(key))
        helpers.append(helper)
    return helpers


def _pandas_errors(payload: dict[str, Any]) -> list[str]:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    errors: list[str] = []
    for value in [analysis.get("errors"), analysis.get("repairable_errors"), analysis.get("error")]:
        if isinstance(value, list):
            errors.extend(str(item) for item in value if str(item or "").strip())
        elif isinstance(value, dict):
            text = value.get("message") or value.get("type")
            if text:
                errors.append(str(text))
        elif value:
            errors.append(str(value))
    return list(dict.fromkeys(errors))


def _selected_function_cases(plan: dict[str, Any], case: dict[str, Any], selected_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    if case:
        cases.append(deepcopy(case))
    for item in plan.get("pandas_function_cases", []) if isinstance(plan.get("pandas_function_cases"), list) else []:
        if isinstance(item, dict) and item not in cases:
            cases.append(deepcopy(item))
    for item in plan.get("selected_function_cases", []) if isinstance(plan.get("selected_function_cases"), list) else []:
        if isinstance(item, dict) and item not in cases:
            cases.append(deepcopy(item))
    for step in selected_steps:
        item = {
            "key": step.get("function_case_key", ""),
            "function_name": step.get("function_name", ""),
            "input_text": step.get("input_text", ""),
            "source_alias": step.get("source_alias", ""),
        }
        if item not in cases:
            cases.append(item)
    return cases


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


class PandasRepairVariablesBuilder(Component):
    display_name = "17A pandas 재생성 변수 생성기"
    description = "pandas 실행 실패 시 LLM 재생성 Prompt Template에 전달할 오류/코드/source 변수를 만듭니다. function case 선택 정보는 17B Prompt Template에 연결하고, 실제 함수 코드는 별도 입력으로 넣습니다."
    inputs = [
        DataInput(name="payload", display_name="실패/성공 페이로드", required=True),
        DropdownInput(name="max_attempts", display_name="최대 재생성 횟수", options=["0", "1", "2"], value="1", advanced=True),
    ]
    outputs = [
        Output(name="repair_required", display_name="재생성 필요 여부", method="build_repair_required", types=["Message"], group_outputs=True),
        Output(name="intent_plan_json", display_name="의도 계획 JSON", method="build_intent_plan_json", types=["Message"], group_outputs=True),
        Output(name="source_schema_json", display_name="소스 스키마 JSON", method="build_source_schema_json", types=["Message"], group_outputs=True),
        Output(name="source_preview_json", display_name="소스 미리보기 JSON", method="build_source_preview_json", types=["Message"], group_outputs=True),
        Output(name="failed_code", display_name="실패 pandas 코드", method="build_failed_code", types=["Message"], group_outputs=True),
        Output(name="error_context_json", display_name="오류 컨텍스트 JSON", method="build_error_context_json", types=["Message"], group_outputs=True),
        Output(name="function_case_selection_json", display_name="Function Case 선택 정보 JSON", method="build_function_case_selection_json", types=["Message"], group_outputs=True),
        Output(name="output_schema", display_name="출력 스키마 JSON", method="build_output_schema", types=["Message"], group_outputs=True),
    ]

    def _variables(self) -> dict[str, Any]:
        return build_variables(getattr(self, "payload", None), getattr(self, "max_attempts", DEFAULT_MAX_ATTEMPTS))

    def build_repair_required(self) -> Message:
        return Message(text=self._variables()["repair_required"])

    def build_intent_plan_json(self) -> Message:
        return Message(text=self._variables()["intent_plan_json"])

    def build_source_schema_json(self) -> Message:
        return Message(text=self._variables()["source_schema_json"])

    def build_source_preview_json(self) -> Message:
        return Message(text=self._variables()["source_preview_json"])

    def build_failed_code(self) -> Message:
        return Message(text=self._variables()["failed_code"])

    def build_error_context_json(self) -> Message:
        return Message(text=self._variables()["error_context_json"])

    def build_function_case_selection_json(self) -> Message:
        return Message(text=self._variables()["function_case_selection_json"])

    def build_output_schema(self) -> Message:
        return Message(text=self._variables()["output_schema"])
