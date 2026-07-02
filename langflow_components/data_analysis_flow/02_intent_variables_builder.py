from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any, metadata_candidates_value: Any = None, specialized_prompt_text: Any = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    metadata_candidates = _payload(metadata_candidates_value) or {}
    return {
        "question": payload.get("request", {}).get("question", ""),
        "state_summary": json.dumps(_state_summary(payload), ensure_ascii=False, indent=2),
        "metadata_candidates": json.dumps(metadata_candidates, ensure_ascii=False, indent=2),
        "specialized_prompt": _text(specialized_prompt_text),
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
        "metadata_refs": [],
        "trace": {"decision_reason": []},
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _text(value: Any) -> str:
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text.strip()
    data = getattr(value, "data", None)
    if isinstance(data, dict):
        for key in ("text", "content", "message", "output"):
            if isinstance(data.get(key), str):
                return data[key].strip()
    return str(value or "").strip()


class IntentVariablesBuilder(Component):
    display_name = "02 의도 분석 변수 생성기"
    description = "Langflow 프롬프트 템플릿과 에이전트/LLM에 연결할 의도 분석 변수를 제공합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        DataInput(name="metadata_candidates_in", display_name="메타데이터 후보", required=False),
        MessageTextInput(name="specialized_prompt_text", display_name="공정 특화 프롬프트", required=False, advanced=True),
    ]
    outputs = [
        Output(name="question", display_name="사용자 질문", method="build_question", types=["Message"], group_outputs=True),
        Output(name="state_summary", display_name="상태/요청 컨텍스트 JSON", method="build_state_summary", types=["Message"], group_outputs=True),
        Output(name="metadata_candidates", display_name="메타데이터 후보 JSON", method="build_metadata_candidates", types=["Message"], group_outputs=True),
        Output(name="specialized_prompt", display_name="공정 특화 프롬프트", method="build_specialized_prompt", types=["Message"], group_outputs=True),
        Output(name="output_schema", display_name="출력 스키마 JSON", method="build_output_schema", types=["Message"], group_outputs=True),
    ]

    def build_question(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None), getattr(self, "specialized_prompt_text", ""))["question"])

    def build_state_summary(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None), getattr(self, "specialized_prompt_text", ""))["state_summary"])

    def build_metadata_candidates(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None), getattr(self, "specialized_prompt_text", ""))["metadata_candidates"])

    def build_specialized_prompt(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None), getattr(self, "specialized_prompt_text", ""))["specialized_prompt"])

    def build_output_schema(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None), getattr(self, "metadata_candidates_in", None), getattr(self, "specialized_prompt_text", ""))["output_schema"])

