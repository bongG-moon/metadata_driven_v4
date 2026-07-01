from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

def build_response(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    wr = payload.get("write_result", {}) if isinstance(payload.get("write_result"), dict) else {}
    return {"response_type": "metadata_authoring", "metadata_type": "table_catalog", "success": bool(wr.get("success")), "message": wr.get("message") or "저장하지 않았습니다.", "write_result": wr, "trace": {"raw_text_preview": payload.get("trace", {}).get("raw_text_preview", ""), "generated_items_preview": payload.get("trace", {}).get("generated_items_preview", []), "existing_matches": payload.get("existing_matches", [])}}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class TableCatalogAuthoringResponseBuilder(Component):
    display_name = "08 테이블 카탈로그 등록 응답 생성기"
    description = "테이블 카탈로그 등록 최종 API 응답과 사용자 메시지를 만듭니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="api_response", display_name="API 응답", method="build_api_response", types=["Data"], group_outputs=True),
        Output(name="message", display_name="메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def build_api_response(self) -> Data:
        return Data(data=build_response(getattr(self, "payload", None)))

    def build_message(self) -> Message:
        return Message(text=build_response(getattr(self, "payload", None))["message"])
