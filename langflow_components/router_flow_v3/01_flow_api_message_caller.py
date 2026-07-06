from __future__ import annotations

import json
import time
from copy import deepcopy
from typing import Any

import requests
from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


def run_flow_api_message(
    flow_input_value: Any,
    *,
    api_url: str = "",
    api_key: str = "",
    timeout_seconds: Any = 180,
    post_func: Any = None,
) -> dict[str, Any]:
    flow_input = _input_text(flow_input_value, preserve=True)
    api_url_value = _clean(api_url)
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if not flow_input.strip():
        errors.append({"type": "empty_input", "message": "하위 flow로 전달할 입력이 비어 있습니다."})
    if _looks_like_route_message(flow_input):
        errors.append(
            {
                "type": "route_message_used_as_input",
                "message": (
                    "Smart Router Route Message가 사용자 질문 대신 전달되었습니다. "
                    "API 호출 route의 Route Message를 비우고 Smart Router route output이 원문을 그대로 보내도록 설정하세요."
                ),
            }
        )
    if not api_url_value:
        errors.append({"type": "missing_api_url", "message": "하위 flow의 Langflow Run API URL이 비어 있습니다."})
    elif not api_url_value.lower().startswith(("http://", "https://")):
        warnings.append(
            {
                "type": "api_url_not_full_url",
                "message": "API URL은 http:// 또는 https://로 시작하는 전체 Langflow Run API URL을 권장합니다.",
            }
        )

    if errors:
        return _message_result(
            status="error",
            message=_format_errors(errors),
            flow_input=flow_input,
            api_url=api_url_value,
            warnings=warnings,
            errors=errors,
            raw_response={},
            duration_ms=0,
        )

    request_body = {
        "input_value": flow_input,
        "input_type": "chat",
        "output_type": "chat",
    }
    headers = {"Content-Type": "application/json"}
    if _clean(api_key):
        headers["x-api-key"] = _clean(api_key)

    started = time.monotonic()
    post = post_func or requests.post
    timeout = _safe_int(timeout_seconds, default=180)
    try:
        response = post(api_url_value, json=request_body, headers=headers, timeout=timeout)
        http_status = int(getattr(response, "status_code", 200) or 200)
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        parsed = response.json() if callable(getattr(response, "json", None)) else response
    except Exception as exc:
        return _message_result(
            status="error",
            message=f"하위 flow API 호출에 실패했습니다: {exc}",
            flow_input=flow_input,
            api_url=api_url_value,
            warnings=warnings,
            errors=[{"type": "api_call_failed", "message": str(exc)}],
            raw_response={},
            duration_ms=_duration_ms(started),
        )

    raw_response = parsed if isinstance(parsed, dict) else {"response": parsed}
    message = _extract_message_text(raw_response) or "하위 flow가 표시 메시지를 반환하지 않았습니다."
    result = _message_result(
        status="ok",
        message=message,
        flow_input=flow_input,
        api_url=api_url_value,
        warnings=warnings,
        errors=[],
        raw_response=raw_response,
        duration_ms=_duration_ms(started),
    )
    result["request_body"] = request_body
    result["http_status"] = http_status
    return result


def _message_result(
    *,
    status: str,
    message: str,
    flow_input: str,
    api_url: str,
    warnings: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    raw_response: dict[str, Any],
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "flow_input": flow_input,
        "api_url": api_url,
        "warnings": warnings,
        "errors": errors,
        "raw_response": raw_response,
        "duration_ms": duration_ms,
    }


def _looks_like_route_message(value: Any) -> bool:
    parsed = _parse_json_dict(str(value or ""))
    if not parsed:
        return False
    keys = {str(key) for key in parsed}
    return bool(keys & {"route", "selected_route", "route_name"}) and len(keys) <= 3


def _format_errors(errors: list[dict[str, Any]]) -> str:
    return "\n".join(f"- {error.get('message', '')}" for error in errors if error.get("message"))


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
        parsed = _parse_json_dict(value)
        if parsed:
            return _extract_message_text_inner(parsed, seen)
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


def _parse_json_dict(value: str) -> dict[str, Any]:
    text = _clean(value)
    if not text:
        return {}
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return deepcopy(parsed) if isinstance(parsed, dict) else {}


def _input_text(value: Any, *, preserve: bool = False) -> str:
    if value is None:
        return ""
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text if preserve else text.strip()
    if isinstance(value, str):
        return value if preserve else value.strip()
    data = getattr(value, "data", value)
    if isinstance(data, dict):
        for key in ("input_value", "question", "raw_text", "message", "text"):
            text = data.get(key)
            if isinstance(text, str):
                return text if preserve else text.strip()
    return ""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: int) -> int:
    try:
        return max(1, int(str(value or "").strip()))
    except Exception:
        return default


def _duration_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


class FlowApiMessageCaller(Component):
    display_name = "01 선택 Flow API 메시지 호출기"
    description = "Smart Router가 선택한 branch의 원문 메시지를 하위 Langflow Run API로 전달하고, 하위 flow의 표시 메시지만 반환합니다."
    inputs = [
        MessageTextInput(name="flow_input", display_name="Flow 입력", required=True),
        MessageTextInput(name="api_url", display_name="하위 Flow API URL", value="", required=True),
        MessageTextInput(name="api_key", display_name="Langflow API 키", value="", required=False, advanced=True),
        MessageTextInput(name="timeout_seconds", display_name="제한 시간(초)", value="180", required=False, advanced=True),
    ]
    outputs = [
        Output(name="message", display_name="메시지", method="build_message", types=["Message"]),
    ]

    def build_message(self) -> Message:
        result = run_flow_api_message(
            getattr(self, "flow_input", ""),
            api_url=getattr(self, "api_url", ""),
            api_key=getattr(self, "api_key", ""),
            timeout_seconds=getattr(self, "timeout_seconds", "180"),
        )
        return Message(text=_clean(result.get("message")))
