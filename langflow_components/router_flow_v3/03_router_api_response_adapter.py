from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


def build_router_api_response(api_call_result_value: Any) -> dict[str, Any]:
    result = _payload(api_call_result_value)
    selected_flow_response = _dict(result.get("selected_flow_response"))
    message = _text(result.get("display_message") or result.get("message")) or _extract_message_text(selected_flow_response)
    status = _text(result.get("status") or selected_flow_response.get("status") or "ok")
    route = _text(result.get("route") or _dict(result.get("route_decision")).get("route"))
    selected_flow = _text(result.get("selected_flow"))
    errors = list(result.get("errors", [])) if isinstance(result.get("errors"), list) else []
    warnings = list(result.get("warnings", [])) if isinstance(result.get("warnings"), list) else []

    compact_raw_response = {"api_response": selected_flow_response} if selected_flow_response else _dict(result.get("raw_response"))
    response = {
        "response_type": "routed_flow_execution",
        "status": status,
        "route": route,
        "selected_flow": selected_flow,
        "execution_mode": _text(result.get("execution_mode") or "langflow_api"),
        "route_decision": _dict(result.get("route_decision")) or {"route": route, "selected_flow": selected_flow},
        "message": message,
        "display_message": message,
        "selected_flow_response": selected_flow_response,
        "raw_response": compact_raw_response,
        "warnings": warnings,
        "errors": errors,
        "trace": _merge_trace(result),
    }
    if selected_flow_response.get("state"):
        response["state"] = selected_flow_response.get("state")
    return response


def _merge_trace(result: dict[str, Any]) -> dict[str, Any]:
    trace = _dict(result.get("trace"))
    execution = _dict(trace.get("execution"))
    subflow_call = _dict(result.get("subflow_call"))
    if subflow_call:
        execution.setdefault("api_url", subflow_call.get("api_url", ""))
        execution.setdefault("selected_flow", subflow_call.get("selected_flow", result.get("selected_flow", "")))
        execution.setdefault("input_kind", subflow_call.get("input_kind", ""))
    request = _dict(result.get("request"))
    if request:
        execution.setdefault("input_length", request.get("input_length", 0))
    trace["execution"] = execution
    return trace


def _extract_message_text(value: Any) -> str:
    return _extract_message_text_inner(value, set())


def _extract_message_text_inner(value: Any, seen: set[int]) -> str:
    if value is None:
        return ""
    value_id = id(value)
    if value_id in seen:
        return ""
    seen.add(value_id)
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("api_response", "display_message", "answer_message", "answer", "text", "content", "output", "response", "message"):
            text = _extract_message_text_inner(value.get(key), seen)
            if text:
                return text
        for key in ("results", "artifacts", "outputs", "data", "messages"):
            text = _extract_message_text_inner(value.get(key), seen)
            if text:
                return text
    if isinstance(value, list):
        for item in value:
            text = _extract_message_text_inner(item, seen)
            if text:
                return text
    return ""


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


class RouterApiResponseAdapter(Component):
    display_name = "03 Router API 응답 정리기"
    description = "선택 flow API 호출 결과를 Web/API와 Chat Output에서 읽기 쉬운 router 응답으로 정리합니다."
    inputs = [
        DataInput(name="api_call_result", display_name="API 호출 결과", required=True),
    ]
    outputs = [
        Output(name="api_response", display_name="API 응답", method="build_payload", types=["Data"], group_outputs=True),
        Output(name="display_message", display_name="채팅 표시 메시지", method="build_display_message", types=["Message"], group_outputs=True),
    ]

    def _response(self) -> dict[str, Any]:
        cached = getattr(self, "_cached_response", None)
        if isinstance(cached, dict):
            return cached
        response = build_router_api_response(getattr(self, "api_call_result", None))
        self._cached_response = response
        return response

    def build_payload(self) -> Data:
        return Data(data=self._response())

    def build_display_message(self) -> Message:
        return Message(text=_text(self._response().get("display_message") or self._response().get("message")))
