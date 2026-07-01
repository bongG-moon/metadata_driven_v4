from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, Output
from lfx.schema.data import Data

SOURCE_TYPES = ("dummy", "oracle", "h_api", "datalake", "goodocs")


def route_retrieval_jobs(payload_value: Any, target_source_type: str, retrieval_mode: Any = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    jobs = payload.get("intent_plan", {}).get("retrieval_jobs", [])
    jobs = jobs if isinstance(jobs, list) else []
    live_enabled = _live_enabled(retrieval_mode)
    if not live_enabled:
        selected = [deepcopy(job) for job in jobs if isinstance(job, dict)] if target_source_type == "dummy" else []
    else:
        selected = [deepcopy(job) for job in jobs if isinstance(job, dict) and job.get("source_type") == target_source_type]
    routed = deepcopy(payload)
    routed["retrieval_job_bundle"] = {
        "source_type": target_source_type,
        "jobs": selected,
        "live_source_retrieval": live_enabled,
    }
    return routed


def _live_enabled(retrieval_mode: Any = "") -> bool:
    mode = str(retrieval_mode or "").strip().lower()
    if mode in {"dummy", "더미", "false", "off", "0", "no"}:
        return False
    if mode in {"live", "actual", "real", "실제", "true", "on", "1", "yes"}:
        return True
    return str(os.getenv("RUN_LIVE_SOURCE_RETRIEVAL", "false")).lower() == "true"


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    data = getattr(value, "data", None)
    return deepcopy(data) if isinstance(data, dict) else {}


class RetrievalJobRouter(Component):
    display_name = "07 데이터 조회 작업 라우터"
    description = "데이터 조회 작업을 소스 유형별 분기로 나눕니다. 실제 소스 조회가 꺼져 있으면 더미 데이터가 모든 작업을 처리합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        DropdownInput(name="retrieval_mode", display_name="조회 모드", options=["dummy", "live"], value="dummy"),
    ]
    outputs = [
        Output(name="dummy_jobs", display_name="더미 작업", method="dummy_jobs_out", group_outputs=True),
        Output(name="oracle_jobs", display_name="Oracle 작업", method="oracle_jobs_out", group_outputs=True),
        Output(name="h_api_jobs", display_name="H-API 작업", method="h_api_jobs_out", group_outputs=True),
        Output(name="datalake_jobs", display_name="데이터레이크 작업", method="datalake_jobs_out", group_outputs=True),
        Output(name="goodocs_jobs", display_name="Goodocs 작업", method="goodocs_jobs_out", group_outputs=True),
    ]

    def dummy_jobs_out(self) -> Data:
        return Data(data=route_retrieval_jobs(getattr(self, "payload", None), "dummy", getattr(self, "retrieval_mode", "dummy")))

    def oracle_jobs_out(self) -> Data:
        return Data(data=route_retrieval_jobs(getattr(self, "payload", None), "oracle", getattr(self, "retrieval_mode", "dummy")))

    def h_api_jobs_out(self) -> Data:
        return Data(data=route_retrieval_jobs(getattr(self, "payload", None), "h_api", getattr(self, "retrieval_mode", "dummy")))

    def datalake_jobs_out(self) -> Data:
        return Data(data=route_retrieval_jobs(getattr(self, "payload", None), "datalake", getattr(self, "retrieval_mode", "dummy")))

    def goodocs_jobs_out(self) -> Data:
        return Data(data=route_retrieval_jobs(getattr(self, "payload", None), "goodocs", getattr(self, "retrieval_mode", "dummy")))
