from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any, metadata_candidates_value: Any = None) -> dict[str, Any]:
    payload = _payload(payload_value)
    metadata_candidates = _payload(metadata_candidates_value) or {}
    return {
        "question": payload.get("request", {}).get("question", ""),
        "state_summary": json.dumps(_state_summary(payload), ensure_ascii=False, indent=2),
        "metadata_candidates": json.dumps(metadata_candidates, ensure_ascii=False, indent=2),
        "output_schema": json.dumps(_schema(), ensure_ascii=False, indent=2),
    }


def _state_summary(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    return {
        "request_context": {
            "reference_date": request.get("reference_date", ""),
        },
        "state": payload.get("state", {}) if isinstance(payload.get("state"), dict) else {},
    }


def _schema() -> dict[str, Any]:
    return {
        "intent_plan": {
            "analysis_kind": "string",
            "pandas_function_case": {},
            "pandas_function_cases": [],
            "retrieval_jobs": [
                {
                    "dataset_key": "string",
                    "source_alias": "string",
                    "source_type": "string",
                    "source_config": {},
                    "required_params": {"DATA_CATALOG_REQUIRED_PARAM": "value"},
                    "filters": {"PANDAS_FILTER_COLUMN": {"operator": "eq|in|contains|not_in", "value": "value or list"}},
                }
            ],
            "pandas_execution_plan": [],
            "output_contract": {},
        },
        "metadata_refs": [{"section": "string", "key": "string"}],
        "trace": {"decision_reason": []},
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class IntentVariablesBuilder(Component):
    display_name = "02 의도 분석 변수 생성기"
    description = "Langflow 프롬프트 템플릿과 에이전트/LLM에 연결할 의도 분석 변수를 제공합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        DataInput(name="metadata_candidates_in", display_name="메타데이터 후보", required=False),
    ]
    outputs = [
        Output(name="question", display_name="사용자 질문", method="build_question", types=["Message"], group_outputs=True),
        Output(name="state_summary", display_name="상태/요청 컨텍스트 JSON", method="build_state_summary", types=["Message"], group_outputs=True),
        Output(name="metadata_candidates", display_name="메타데이터 후보 JSON", method="build_metadata_candidates", types=["Message"], group_outputs=True),
        Output(name="output_schema", display_name="출력 스키마 JSON", method="build_output_schema", types=["Message"], group_outputs=True),
    ]

    def build_question(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None))["question"])

    def build_state_summary(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None))["state_summary"])

    def build_metadata_candidates(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None))["metadata_candidates"])

    def build_output_schema(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None))["output_schema"])

