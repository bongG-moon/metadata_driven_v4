from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

def build_answer_response(payload_value: Any, answer_text: Any = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    message = str(answer_text or "").strip()
    if not message:
        row_count = payload.get("data", {}).get("row_count", 0)
        message = f"분석 결과 {row_count}건을 확인했습니다." if payload.get("analysis", {}).get("status") == "ok" else "분석을 완료하지 못했습니다. trace의 오류를 확인해 주세요."
    next_payload = deepcopy(payload)
    next_payload["answer_message"] = message
    next_payload["state"] = {**next_payload.get("state", {}), "current_data": {"row_count": next_payload.get("data", {}).get("row_count", 0), "preview_rows": next_payload.get("data", {}).get("rows", [])[:5], "data_ref": next_payload.get("data", {}).get("data_ref", "")}}
    return next_payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class AnswerResponseBuilder(Component):
    display_name = "21 답변 응답 생성기"
    description = "Langflow 에이전트/LLM 답변 문장과 결정된 데이터를 합쳐 페이로드를 완성합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), MessageTextInput(name="answer_text", display_name="답변 문장", required=False)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=build_answer_response(getattr(self, "payload", None), getattr(self, "answer_text", "")))
