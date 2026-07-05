from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

METADATA_TYPE = "domain"


def build_response(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    item = {"section": "process_groups", "key": "DUMMY_DA", "payload": {"display_name": "더미 D/A 공정 그룹", "processes": ["D/A1", "D/A2"]}}
    message = "더미 도메인 등록 flow가 저장 없이 예시 item 1건을 생성했습니다."
    return {
        "response_type": "metadata_authoring",
        "metadata_type": METADATA_TYPE,
        "status": "dry_run",
        "success": False,
        "message": message,
        "items": [item],
        "review": {"status": "ok", "warnings": ["더미 flow이므로 MongoDB에 저장하지 않았습니다."]},
        "write_result": {"success": False, "dry_run": True, "message": "더미 flow는 저장하지 않습니다.", "saved_count": 0},
        "trace": {
            "raw_text_preview": _payload(payload.get("trace")).get("raw_text_preview", ""),
            "generated_items_preview": [item],
            "existing_matches": [],
            "conflict_warnings": [],
        },
        "warnings": [{"type": "dummy_saving_flow", "message": "실제 LLM/MongoDB 저장 없이 더미 등록 응답을 반환했습니다."}],
        "errors": _list(payload.get("errors")),
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _list(value: Any) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []


class DummyDomainSavingResponseBuilder(Component):
    display_name = "01 더미 도메인 등록 응답 생성기"
    description = "도메인 등록 flow와 같은 형태의 더미 API 응답과 메시지를 생성합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="api_response", display_name="API 응답", method="build_api_response", types=["Data"], group_outputs=True),
        Output(name="message", display_name="메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def build_api_response(self) -> Data:
        return Data(data=build_response(getattr(self, "payload", None)))

    def build_message(self) -> Message:
        return Message(text=build_response(getattr(self, "payload", None))["message"])
