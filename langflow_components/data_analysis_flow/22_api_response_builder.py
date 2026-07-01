from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data

def build_api_response(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    return {
        "response_type": "data_analysis",
        "status": "ok" if payload.get("analysis", {}).get("status") == "ok" else "error",
        "message": payload.get("answer_message", ""),
        "request": payload.get("request", {}),
        "data": payload.get("data", {}),
        "state": payload.get("state", {}),
        "trace": payload.get("trace", {}),
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    payload = deepcopy(data) if isinstance(data, dict) else {}
    payload.pop("runtime_sources", None)
    payload.pop("_runtime_rows_by_alias", None)
    return payload


class ApiResponseBuilder(Component):
    display_name = "22 API 응답 생성기"
    description = "최종 API 응답을 만들고 전체 런타임 소스 데이터를 제거합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [Output(name="api_response", display_name="API 응답", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=build_api_response(getattr(self, "payload", None)))
