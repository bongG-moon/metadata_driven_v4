from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


def build_api_payload(api_response_value: Any) -> dict[str, Any]:
    payload = _payload(api_response_value)
    if not payload:
        payload = {"response_type": "metadata_authoring", "metadata_type": "domain", "status": "error", "message": "API 응답이 비어 있습니다."}
    payload.setdefault("response_type", "metadata_authoring")
    payload.setdefault("metadata_type", "domain")
    return {"api_response": payload}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    if isinstance(data, dict):
        return deepcopy(data)
    text = getattr(value, "text", data)
    if isinstance(text, str) and text.strip():
        try:
            parsed = json.loads(text)
        except Exception:
            return {"response_type": "metadata_authoring", "metadata_type": "domain", "message": text}
        return deepcopy(parsed) if isinstance(parsed, dict) else {}
    return {}


class DomainAuthoringApiAdapter(Component):
    display_name = "09 도메인 등록 API 연결 어댑터"
    description = "도메인 등록 결과를 Web/Run API에서 안정적으로 읽을 수 있는 JSON 메시지로 변환합니다."
    inputs = [DataInput(name="api_response", display_name="API 응답", required=True)]
    outputs = [
        Output(name="api_payload", display_name="API 페이로드", method="build_payload", types=["Data"], group_outputs=True),
        Output(name="api_message", display_name="API 메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def build_payload(self) -> Data:
        return Data(data=build_api_payload(getattr(self, "api_response", None)))

    def build_message(self) -> Message:
        return Message(text=json.dumps(build_api_payload(getattr(self, "api_response", None)), ensure_ascii=False, default=str))
