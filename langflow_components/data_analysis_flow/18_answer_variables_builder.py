from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    return {
        "question": payload.get("request", {}).get("question", ""),
        "result_summary_json": _json_dumps(payload.get("data", {})),
        "applied_scope_json": _json_dumps(_compact_applied_scope(payload)),
        "answer_context_json": _json_dumps(_answer_context(payload)),
        "warnings_errors_json": _json_dumps({"warnings": payload.get("trace", {}).get("warnings", []), "errors": payload.get("trace", {}).get("errors", [])}),
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _compact_applied_scope(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("intent_plan") if isinstance(payload.get("intent_plan"), dict) else {}
    inspection = payload.get("trace", {}).get("inspection", {}) if isinstance(payload.get("trace"), dict) else {}
    if not isinstance(inspection, dict):
        inspection = {}

    retrieval_jobs = plan.get("retrieval_jobs") if isinstance(plan.get("retrieval_jobs"), list) else []
    pandas_plan = plan.get("pandas_execution_plan") if isinstance(plan.get("pandas_execution_plan"), list) else []
    result: dict[str, Any] = {
        "intent": _omit_empty(
            {
                "analysis_kind": plan.get("analysis_kind") or _dict(inspection.get("intent")).get("analysis_kind"),
                "retrieval_job_count": len(retrieval_jobs),
                "pandas_step_count": len(pandas_plan),
                "metadata_ref_count": len(payload.get("metadata_refs", [])) if isinstance(payload.get("metadata_refs"), list) else 0,
            }
        ),
        "retrieval": [_compact_source_result(item) for item in _list(payload.get("source_results"))],
        "pandas_execution": _compact_pandas_execution(payload, _dict(inspection.get("pandas_execution"))),
    }
    result_store = _compact_result_store(_dict(inspection.get("result_store")))
    if result_store:
        result["result_store"] = result_store
    return result


def _compact_source_result(value: Any) -> dict[str, Any]:
    source = _dict(value)
    source_execution = _dict(source.get("source_execution"))
    return _omit_empty(
        {
            "source_alias": source.get("source_alias"),
            "dataset_key": source.get("dataset_key"),
            "source_type": source.get("source_type"),
            "status": source.get("status"),
            "row_count": source.get("row_count"),
            "columns": source.get("columns"),
            "applied_params": source.get("applied_params"),
            "pandas_filters": source.get("pandas_filters"),
            "used_dummy_data": source_execution.get("used_dummy_data"),
            "adapter": source_execution.get("adapter"),
            "params_applied_in_retriever": source_execution.get("params_applied_in_retriever"),
            "filters_applied_in_retriever": source_execution.get("filters_applied_in_retriever"),
        }
    )


def _compact_pandas_execution(payload: dict[str, Any], pandas_execution: dict[str, Any]) -> dict[str, Any]:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    execution_result = _dict(pandas_execution.get("execution_result"))
    return _omit_empty(
        {
            "stage": pandas_execution.get("stage"),
            "status": pandas_execution.get("status") or analysis.get("status"),
            "row_count": execution_result.get("row_count", analysis.get("row_count")),
            "columns": execution_result.get("columns", analysis.get("columns")),
            "used_helpers": pandas_execution.get("used_helpers", analysis.get("used_helpers")),
            "pandas_filter_plan": pandas_execution.get("pandas_filter_plan"),
            "error": _compact_error(pandas_execution.get("error") or analysis.get("error")),
        }
    )


def _compact_error(value: Any) -> Any:
    error = _dict(value)
    if not error:
        return None
    return _omit_empty({"type": error.get("type"), "message": error.get("message")})


def _compact_result_store(result_store: dict[str, Any]) -> dict[str, Any]:
    return _omit_empty(
        {
            "status": result_store.get("status"),
            "data_ref": result_store.get("data_ref"),
            "ttl_hours": result_store.get("ttl_hours"),
            "expires_at": result_store.get("expires_at"),
        }
    )


def _answer_context(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    pandas_execution = _dict(_dict(payload.get("trace")).get("inspection")).get("pandas_execution")
    pandas_execution = _dict(pandas_execution)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    step_outputs = _list(analysis.get("step_outputs")) or _list(pandas_execution.get("step_outputs"))
    function_case_results = _list(analysis.get("function_case_results")) or _list(pandas_execution.get("function_case_results"))
    return {
        "number_display_policy": {
            "under_10000": "comma_full_number",
            "gte_10000": "k_unit",
            "display_only": True,
        },
        "result_shape": _omit_empty(
            {
                "row_count": data.get("row_count", analysis.get("row_count")),
                "columns": data.get("columns") or analysis.get("columns"),
            }
        ),
        "step_outputs": deepcopy(step_outputs),
        "function_case_results": deepcopy(function_case_results),
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _omit_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if _has_compact_value(item)}


def _has_compact_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_ready(value), ensure_ascii=False, indent=2)


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


class AnswerVariablesBuilder(Component):
    display_name = "18 답변 생성 변수 생성기"
    description = "Langflow 프롬프트 템플릿과 에이전트/LLM에 연결할 답변 생성 변수를 제공합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="question", display_name="사용자 질문", method="build_question", types=["Message"], group_outputs=True),
        Output(name="result_summary_json", display_name="결과 요약 JSON", method="build_result_summary", types=["Message"], group_outputs=True),
        Output(name="applied_scope_json", display_name="적용 범위 JSON", method="build_applied_scope", types=["Message"], group_outputs=True),
        Output(name="answer_context_json", display_name="답변 컨텍스트 JSON", method="build_answer_context", types=["Message"], group_outputs=True),
        Output(name="warnings_errors_json", display_name="경고/오류 JSON", method="build_warnings_errors", types=["Message"], group_outputs=True),
    ]

    def build_question(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["question"])

    def build_result_summary(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["result_summary_json"])

    def build_applied_scope(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["applied_scope_json"])

    def build_answer_context(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["answer_context_json"])

    def build_warnings_errors(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["warnings_errors_json"])

