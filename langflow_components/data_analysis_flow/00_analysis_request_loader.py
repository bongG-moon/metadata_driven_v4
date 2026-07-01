from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

def build_request(question: Any, previous_state_value: Any = None, session_id: str = "demo-session", reference_date: str = "", timezone: str = "Asia/Seoul") -> dict[str, Any]:
    return {
        "request": {
            "question": str(question or ""),
            "session_id": session_id or "demo-session",
            "reference_date": reference_date,
            "timezone": timezone or "Asia/Seoul",
        },
        "state": _payload(previous_state_value),
        "metadata_refs": [],
        "intent_plan": {},
        "source_results": [],
        "runtime_sources": {},
        "analysis": {},
        "data": {},
        "answer_message": "",
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class AnalysisRequestLoader(Component):
    display_name = "00 분석 요청 로더"
    description = "질문과 이전 상태를 표준 데이터 분석 페이로드로 변환합니다."
    inputs = [
        MessageTextInput(name="question", display_name="사용자 질문", required=True),
        DataInput(name="previous_state", display_name="이전 상태", required=False),
        MessageTextInput(name="session_id", display_name="세션 ID", required=False, value="demo-session"),
        MessageTextInput(name="reference_date", display_name="기준일", required=False),
        MessageTextInput(name="timezone", display_name="시간대", required=False, value="Asia/Seoul"),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=build_request(getattr(self, "question", ""), getattr(self, "previous_state", None), getattr(self, "session_id", "demo-session"), getattr(self, "reference_date", ""), getattr(self, "timezone", "Asia/Seoul")))
