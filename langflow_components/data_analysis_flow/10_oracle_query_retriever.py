from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data

def oracle_retrieve(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    jobs = payload.get("retrieval_job_bundle", {}).get("jobs", [])
    if not jobs:
        return _skipped("oracle", "no oracle retrieval jobs")
    return _not_implemented("oracle", jobs)


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    data = getattr(value, "data", None)
    return deepcopy(data) if isinstance(data, dict) else {}


def _skipped(source_type: str, reason: str) -> dict[str, Any]:
    return {"source_type": source_type, "status": "skipped", "skipped": True, "skip_reason": reason, "source_results": [], "errors": [], "warnings": []}


def _not_implemented(source_type: str, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "status": "error",
        "skipped": False,
        "source_results": [],
        "errors": [{"type": "live_adapter_not_implemented", "message": f"{source_type} live adapter is not implemented in this skeleton.", "job_count": len(jobs)}],
        "warnings": [],
    }


class OracleQueryRetriever(Component):
    display_name = "10 Oracle 쿼리 조회기"
    description = "Oracle 조회 작업을 처리합니다. 현재 skeleton은 실제 어댑터 미구현 상태를 명확한 오류로 반환합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [Output(name="retrieval_payload", display_name="조회 페이로드", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=oracle_retrieve(getattr(self, "payload", None)))
