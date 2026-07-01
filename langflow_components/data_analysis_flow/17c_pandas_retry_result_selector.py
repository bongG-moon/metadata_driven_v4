from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


def select_pandas_result(original_payload_value: Any, retry_payload_value: Any = None) -> dict[str, Any]:
    original = _payload(original_payload_value)
    retry = _payload(retry_payload_value)
    if _analysis_status(retry) == "ok":
        selected = deepcopy(retry)
        selected.setdefault("trace", {}).setdefault("inspection", {})["pandas_retry_selection"] = {
            "selected": "retry",
            "reason": "재생성 pandas 코드 실행이 성공하여 retry 결과를 채택했습니다.",
        }
        return selected
    selected = deepcopy(original)
    selected.setdefault("trace", {}).setdefault("inspection", {})["pandas_retry_selection"] = {
        "selected": "original",
        "reason": "retry 결과가 없거나 실패하여 original payload를 유지했습니다.",
        "retry_status": _analysis_status(retry),
    }
    return selected


def _analysis_status(payload: dict[str, Any]) -> str:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    return str(analysis.get("status") or "")


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class PandasRetryResultSelector(Component):
    display_name = "17C pandas 재생성 결과 선택기"
    description = "초기 pandas 결과와 재생성 결과 중 성공한 재생성 결과를 우선 선택합니다."
    inputs = [
        DataInput(name="original_payload", display_name="초기 pandas 페이로드", required=True),
        DataInput(name="retry_payload", display_name="재생성 pandas 페이로드", required=False),
    ]
    outputs = [Output(name="payload_out", display_name="선택된 페이로드", method="build_payload", types=["Data"])]

    def build_payload(self) -> Data:
        return Data(data=select_pandas_result(getattr(self, "original_payload", None), getattr(self, "retry_payload", None)))
