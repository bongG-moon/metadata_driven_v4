from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

KOREA_ZONE_NAME = "Asia/Seoul"


def build_dummy_request(question: Any, previous_state_value: Any = None) -> dict[str, Any]:
    text = str(question or "").strip()
    state = _payload(previous_state_value)
    return {
        "request": {
            "question": text,
            "session_id": _resolve_session_id(state),
            "reference_date": _korea_today(),
        },
        "state": state,
        "trace": {
            "warnings": [],
            "errors": [] if text else [{"type": "empty_question", "message": "질문이 비어 있습니다."}],
            "inspection": {"dummy_flow": {"stage": "00_dummy_request_loader", "status": "ok" if text else "warning"}},
        },
    }


def _resolve_session_id(state: dict[str, Any]) -> str:
    for key in ("session_id", "conversation_id", "thread_id"):
        value = state.get(key)
        if value:
            return str(value)
    request = state.get("request") if isinstance(state.get("request"), dict) else {}
    if request.get("session_id"):
        return str(request["session_id"])
    return "demo-session"


def _korea_today() -> str:
    return datetime.now(_korea_timezone()).strftime("%Y%m%d")


def _korea_timezone():
    try:
        zoneinfo = import_module("zoneinfo")
        return zoneinfo.ZoneInfo(KOREA_ZONE_NAME)
    except Exception:
        return timezone(timedelta(hours=9), "KST")


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class DummyRequestLoader(Component):
    display_name = "00 더미 분석 요청 로더"
    description = "라우터 개발 검증용 더미 분석 요청을 표준 페이로드로 변환합니다."
    inputs = [
        MessageTextInput(name="question", display_name="사용자 질문", required=True, tool_mode=True),
        DataInput(name="previous_state", display_name="이전 상태", required=False),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=build_dummy_request(getattr(self, "question", ""), getattr(self, "previous_state", None)))
