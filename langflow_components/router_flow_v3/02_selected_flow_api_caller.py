from __future__ import annotations

import json
import time
from copy import deepcopy
from typing import Any

import requests
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


def run_selected_flow_api(
    route_request_value: Any,
    *,
    api_key: str = "",
    timeout_seconds: Any = 180,
    post_func: Any = None,
) -> dict[str, Any]:
    route_request = _payload(route_request_value)
    route = _clean(route_request.get("route") or _dict(route_request.get("route_decision")).get("route"))
    if route in {"direct_answer", "clarification"} or route_request.get("execution_mode") == "direct":
        return _direct_result(route_request)

    subflow_call = _dict(route_request.get("subflow_call"))
    api_url = _clean(subflow_call.get("api_url"))
    selected_flow = _clean(subflow_call.get("selected_flow") or route_request.get("selected_flow"))
    input_value = _value_text(subflow_call.get("input_value"))
    if not api_url:
        return _error_result(route_request, "missing_api_url", "선택된 flow의 Langflow API URL이 비어 있습니다.")
    if not input_value.strip():
        return _error_result(route_request, "empty_input", "선택된 flow로 전달할 입력값이 비어 있습니다.")

    request_body = {
        "input_value": input_value,
        "input_type": _clean(subflow_call.get("input_type")) or "chat",
        "output_type": _clean(subflow_call.get("output_type")) or "chat",
    }
    if _clean(subflow_call.get("session_id")):
        request_body["session_id"] = _clean(subflow_call.get("session_id"))

    headers = {"Content-Type": "application/json"}
    if _clean(api_key):
        headers["x-api-key"] = _clean(api_key)

    started = time.monotonic()
    post = post_func or requests.post
    timeout = _safe_int(timeout_seconds, default=180)
    try:
        response = post(api_url, json=request_body, headers=headers, timeout=timeout)
        http_status = int(getattr(response, "status_code", 200) or 200)
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        parsed = response.json() if callable(getattr(response, "json", None)) else response
    except Exception as exc:
        result = _error_result(route_request, "api_call_failed", f"선택된 flow API 호출에 실패했습니다: {exc}")
        result["trace"]["execution"]["duration_ms"] = _duration_ms(started)
        return result

    raw_response = parsed if isinstance(parsed, dict) else {"response": parsed}
    selected_flow_response = _extract_selected_flow_response(raw_response)
    message = _extract_message_text(selected_flow_response) or _extract_message_text(raw_response) or "선택된 flow가 표시 메시지를 반환하지 않았습니다."
    return {
        "response_type": "selected_flow_api_call_result",
        "status": "ok",
        "route": route,
        "selected_flow": selected_flow,
        "execution_mode": "langflow_api",
        "message": message,
        "display_message": message,
        "route_decision": _dict(route_request.get("route_decision")),
        "request": {
            "input_length": len(input_value),
            "session_id": _clean(subflow_call.get("session_id")),
        },
        "subflow_call": {
            "api_url": api_url,
            "selected_flow": selected_flow,
            "input_kind": _clean(subflow_call.get("input_kind")),
            "input_type": request_body["input_type"],
            "output_type": request_body["output_type"],
        },
        "selected_flow_response": selected_flow_response,
        "raw_response": raw_response,
        "warnings": list(route_request.get("warnings", [])) if isinstance(route_request.get("warnings"), list) else [],
        "errors": [],
        "trace": {
            "execution": {
                "stage": "02_selected_flow_api_caller",
                "status": "ok",
                "api_url": api_url,
                "http_status": http_status,
                "duration_ms": _duration_ms(started),
                "input_length": len(input_value),
            }
        },
    }


def _direct_result(route_request: dict[str, Any]) -> dict[str, Any]:
    direct_response = _dict(route_request.get("direct_response"))
    route = _clean(route_request.get("route") or direct_response.get("response_type") or "direct_answer")
    message = _extract_message_text(direct_response) or _clean(route_request.get("message"))
    return {
        "response_type": "selected_flow_api_call_result",
        "status": _clean(direct_response.get("status") or route_request.get("status") or "ok"),
        "route": route,
        "selected_flow": "",
        "execution_mode": "direct",
        "message": message,
        "display_message": message,
        "route_decision": _dict(route_request.get("route_decision")),
        "request": _dict(route_request.get("request")),
        "subflow_call": {},
        "selected_flow_response": direct_response,
        "raw_response": {"api_response": direct_response},
        "warnings": list(route_request.get("warnings", [])) if isinstance(route_request.get("warnings"), list) else [],
        "errors": list(route_request.get("errors", [])) if isinstance(route_request.get("errors"), list) else [],
        "trace": {
            "execution": {
                "stage": "02_selected_flow_api_caller",
                "status": "direct",
                "http_status": None,
                "duration_ms": 0,
            }
        },
    }


def _error_result(route_request: dict[str, Any], error_type: str, message: str) -> dict[str, Any]:
    subflow_call = _dict(route_request.get("subflow_call"))
    route = _clean(route_request.get("route") or _dict(route_request.get("route_decision")).get("route"))
    selected_flow = _clean(subflow_call.get("selected_flow") or route_request.get("selected_flow"))
    errors = list(route_request.get("errors", [])) if isinstance(route_request.get("errors"), list) else []
    errors.append({"type": error_type, "message": message})
    return {
        "response_type": "selected_flow_api_call_result",
        "status": "error",
        "route": route,
        "selected_flow": selected_flow,
        "execution_mode": "langflow_api",
        "message": message,
        "display_message": message,
        "route_decision": _dict(route_request.get("route_decision")),
        "request": _dict(route_request.get("request")),
        "subflow_call": {
            "api_url": _clean(subflow_call.get("api_url")),
            "selected_flow": selected_flow,
            "input_kind": _clean(subflow_call.get("input_kind")),
        },
        "selected_flow_response": {
            "response_type": "flow_error",
            "status": "error",
            "message": message,
            "errors": errors,
        },
        "raw_response": {},
        "warnings": list(route_request.get("warnings", [])) if isinstance(route_request.get("warnings"), list) else [],
        "errors": errors,
        "trace": {
            "execution": {
                "stage": "02_selected_flow_api_caller",
                "status": "error",
                "api_url": _clean(subflow_call.get("api_url")),
                "http_status": None,
                "duration_ms": 0,
            }
        },
    }


def _extract_selected_flow_response(value: Any) -> dict[str, Any]:
    for item in _walk(value):
        item = _parse_json_dict(item) if isinstance(item, str) else item
        if not isinstance(item, dict):
            continue
        api_response = item.get("api_response")
        if isinstance(api_response, dict) and _looks_like_flow_response(api_response):
            return deepcopy(api_response)
        data = item.get("data")
        if isinstance(data, dict) and _looks_like_flow_response(data):
            return deepcopy(data)
        if _looks_like_flow_response(item):
            return deepcopy(item)
    return {}


def _looks_like_flow_response(value: dict[str, Any]) -> bool:
    response_type = _clean(value.get("response_type"))
    return response_type in {
        "data_analysis",
        "metadata_qa",
        "metadata_authoring",
        "direct_answer",
        "clarification",
        "flow_error",
    } or any(key in value for key in ("answer_message", "display_message", "answer_sections", "metadata_authoring", "metadata_qa"))


def _extract_message_text(value: Any) -> str:
    if value is None:
        return ""
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("display_message", "message", "answer_message", "answer", "text", "content", "output", "response"):
            text = _extract_message_text(value.get(key))
            if text:
                return text
        message = value.get("message")
        if isinstance(message, dict):
            text = _extract_message_text(message)
            if text:
                return text
        data = value.get("data")
        if isinstance(data, dict):
            text = _extract_message_text(data)
            if text:
                return text
    if isinstance(value, list):
        for item in value:
            text = _extract_message_text(item)
            if text:
                return text
    return ""


def _walk(value: Any) -> list[Any]:
    items: list[Any] = []
    stack = [value]
    while stack:
        current = stack.pop()
        items.append(current)
        if isinstance(current, dict):
            for nested in current.values():
                if isinstance(nested, (dict, list, str)):
                    stack.append(nested)
        elif isinstance(current, list):
            stack.extend(reversed(current))
    return items


def _parse_json_dict(value: str) -> dict[str, Any]:
    text = _clean(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _value_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_int(value: Any, default: int) -> int:
    try:
        return max(1, int(str(value or "").strip()))
    except Exception:
        return default


def _duration_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


class SelectedFlowApiCaller(Component):
    display_name = "02 선택 Flow API 호출기"
    description = "Route API 요청에 담긴 선택 flow 하나만 Langflow HTTP API로 호출하고 결과를 정리합니다."
    inputs = [
        DataInput(name="route_request", display_name="Route API 요청", required=True),
        MessageTextInput(name="api_key", display_name="Langflow API 키", value="", required=False, advanced=True),
        MessageTextInput(name="timeout_seconds", display_name="제한 시간(초)", value="180", required=False, advanced=True),
    ]
    outputs = [
        Output(name="api_call_result", display_name="API 호출 결과", method="build_payload", types=["Data"], group_outputs=True),
        Output(name="message", display_name="표시 메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def _result(self) -> dict[str, Any]:
        cached = getattr(self, "_cached_result", None)
        if isinstance(cached, dict):
            return cached
        result = run_selected_flow_api(
            getattr(self, "route_request", None),
            api_key=getattr(self, "api_key", ""),
            timeout_seconds=getattr(self, "timeout_seconds", "180"),
        )
        self._cached_result = result
        return result

    def build_payload(self) -> Data:
        return Data(data=self._result())

    def build_message(self) -> Message:
        return Message(text=_clean(self._result().get("message")))
