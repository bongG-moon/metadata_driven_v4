from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_message(payload_value: Any) -> str:
    payload = _payload(payload_value)
    return str(payload.get("answer_message") or "")


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class AnswerMessageAdapter(Component):
    display_name = "22 답변 메시지 어댑터"
    description = "최종 답변 메시지를 채팅 출력용 메시지로 변환합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [Output(name="message", display_name="메시지", method="build_output_message", types=["Message"])]

    def build_output_message(self) -> Message:
        return Message(text=build_message(getattr(self, "payload", None)))
