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
        "applied_scope_json": _json_dumps(payload.get("trace", {}).get("inspection", {})),
        "warnings_errors_json": _json_dumps({"warnings": payload.get("trace", {}).get("warnings", []), "errors": payload.get("trace", {}).get("errors", [])}),
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


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
        Output(name="warnings_errors_json", display_name="경고/오류 JSON", method="build_warnings_errors", types=["Message"], group_outputs=True),
    ]

    def build_question(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["question"])

    def build_result_summary(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["result_summary_json"])

    def build_applied_scope(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["applied_scope_json"])

    def build_warnings_errors(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["warnings_errors_json"])

