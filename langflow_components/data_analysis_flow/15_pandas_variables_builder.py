from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    schemas = {alias: sorted({column for row in rows[:20] for column in row}) for alias, rows in payload.get("runtime_sources", {}).items() if isinstance(rows, list)}
    previews = {alias: rows[:5] for alias, rows in payload.get("runtime_sources", {}).items() if isinstance(rows, list)}
    return {
        "intent_plan_json": json.dumps(payload.get("intent_plan", {}), ensure_ascii=False, indent=2),
        "source_schema_json": json.dumps(schemas, ensure_ascii=False, indent=2),
        "source_preview_json": json.dumps(previews, ensure_ascii=False, indent=2),
        "function_case_context_json": json.dumps(_function_case_context(payload), ensure_ascii=False, indent=2),
        "output_contract_json": json.dumps(payload.get("intent_plan", {}).get("output_contract", {}), ensure_ascii=False, indent=2),
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _function_case_context(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("intent_plan") if isinstance(payload.get("intent_plan"), dict) else {}
    case = plan.get("pandas_function_case") if isinstance(plan.get("pandas_function_case"), dict) else {}
    steps = plan.get("pandas_execution_plan") if isinstance(plan.get("pandas_execution_plan"), list) else []
    selected_steps = [
        deepcopy(step)
        for step in steps
        if isinstance(step, dict)
        and str(step.get("operation") or "").strip() == "apply_pandas_function_case"
    ]
    function_names = {
        str(item.get("function_name") or "").strip()
        for item in [case, *selected_steps]
        if isinstance(item, dict) and str(item.get("function_name") or "").strip()
    }
    helpers = []
    if "match_product_tokens" in function_names or _looks_like_product_token_case(case, selected_steps):
        helpers.append(
            {
                "function_name": "match_product_tokens",
                "signature": "match_product_tokens(input_text, frame, token_columns=None, output_order=None)",
                "description": "제품 속성 token을 TECH, DEN/DENSITY, MODE, PKG_TYPE1/PKG1, PKG_TYPE2/PKG2, LEAD, MCP_NO, DEVICE, DEVICE_DESC 등 제품 속성 컬럼에서 모두 매칭해 제품 row를 필터링한다.",
                "default_token_columns": [
                    "TECH",
                    "DEN",
                    "DENSITY",
                    "MODE",
                    "PKG_TYPE1",
                    "PKG1",
                    "PKG_TYPE2",
                    "PKG2",
                    "LEAD",
                    "MCP_NO",
                    "DEVICE",
                    "DEVICE_DESC",
                    "TSV_DIE_TYP",
                    "TSV_DIE_TYPE",
                ],
                "usage_rule": "선택된 제품 token function case에서는 외부 import 없이 이 helper를 직접 호출할 수 있다. helper 결과를 먼저 만든 뒤 이후 집계/조인/정렬 단계에 사용한다.",
            }
        )
    return {
        "selected_case": deepcopy(case),
        "selected_steps": selected_steps,
        "available_helpers": helpers,
    }


def _looks_like_product_token_case(case: dict[str, Any], steps: list[dict[str, Any]]) -> bool:
    text = json.dumps({"case": case, "steps": steps}, ensure_ascii=False).lower()
    return "product_token" in text or "제품 token" in text or "제품 토큰" in text or "match_product_tokens" in text


class PandasVariablesBuilder(Component):
    display_name = "15 pandas 변수 생성기"
    description = "Langflow 프롬프트 템플릿과 에이전트/LLM에 연결할 pandas 코드 생성 변수를 제공합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="intent_plan_json", display_name="의도 계획 JSON", method="build_intent_plan_json", types=["Message"], group_outputs=True),
        Output(name="source_schema_json", display_name="소스 스키마 JSON", method="build_source_schema_json", types=["Message"], group_outputs=True),
        Output(name="source_preview_json", display_name="소스 미리보기 JSON", method="build_source_preview_json", types=["Message"], group_outputs=True),
        Output(name="function_case_context_json", display_name="특화 함수 컨텍스트 JSON", method="build_function_case_context_json", types=["Message"], group_outputs=True),
        Output(name="output_contract_json", display_name="출력 계약 JSON", method="build_output_contract_json", types=["Message"], group_outputs=True),
    ]

    def build_intent_plan_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["intent_plan_json"])

    def build_source_schema_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["source_schema_json"])

    def build_source_preview_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["source_preview_json"])

    def build_function_case_context_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["function_case_context_json"])

    def build_output_contract_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["output_contract_json"])

