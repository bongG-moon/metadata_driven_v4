from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data


DEFAULT_ROUTE_REGISTRY = {
    "routes": {
        "data_analysis": {
            "selected_flow": "data_analysis_flow",
            "flow_id_env": "LANGFLOW_DATA_ANALYSIS_FLOW_ID",
            "api_url_env": "LANGFLOW_DATA_ANALYSIS_API_URL",
            "input_kind": "question",
            "response_type": "data_analysis",
        },
        "metadata_qa": {
            "selected_flow": "metadata_qa_flow",
            "flow_id_env": "LANGFLOW_METADATA_QA_FLOW_ID",
            "api_url_env": "LANGFLOW_METADATA_QA_API_URL",
            "input_kind": "question",
            "response_type": "metadata_qa",
        },
        "domain_saving": {
            "selected_flow": "domain_saving_flow",
            "flow_id_env": "LANGFLOW_DOMAIN_SAVING_FLOW_ID",
            "api_url_env": "LANGFLOW_DOMAIN_SAVING_API_URL",
            "input_kind": "raw_text",
            "response_type": "metadata_authoring",
        },
        "table_catalog_saving": {
            "selected_flow": "table_catalog_saving_flow",
            "flow_id_env": "LANGFLOW_TABLE_CATALOG_SAVING_FLOW_ID",
            "api_url_env": "LANGFLOW_TABLE_CATALOG_SAVING_API_URL",
            "input_kind": "raw_text",
            "response_type": "metadata_authoring",
        },
        "main_flow_filter_saving": {
            "selected_flow": "main_flow_filters_saving_flow",
            "flow_id_env": "LANGFLOW_MAIN_FLOW_FILTER_SAVING_FLOW_ID",
            "api_url_env": "LANGFLOW_MAIN_FLOW_FILTER_SAVING_API_URL",
            "input_kind": "raw_text",
            "response_type": "metadata_authoring",
        },
        "dummy_data_analysis": {
            "selected_flow": "dummy_data_analysis_flow",
            "flow_id_env": "LANGFLOW_DUMMY_DATA_ANALYSIS_FLOW_ID",
            "api_url_env": "LANGFLOW_DUMMY_DATA_ANALYSIS_API_URL",
            "input_kind": "question",
            "response_type": "data_analysis",
        },
        "dummy_metadata_qa": {
            "selected_flow": "dummy_metadata_qa_flow",
            "flow_id_env": "LANGFLOW_DUMMY_METADATA_QA_FLOW_ID",
            "api_url_env": "LANGFLOW_DUMMY_METADATA_QA_API_URL",
            "input_kind": "question",
            "response_type": "metadata_qa",
        },
        "dummy_domain_saving": {
            "selected_flow": "dummy_domain_saving_flow",
            "flow_id_env": "LANGFLOW_DUMMY_DOMAIN_SAVING_FLOW_ID",
            "api_url_env": "LANGFLOW_DUMMY_DOMAIN_SAVING_API_URL",
            "input_kind": "raw_text",
            "response_type": "metadata_authoring",
        },
        "dummy_table_catalog_saving": {
            "selected_flow": "dummy_table_catalog_saving_flow",
            "flow_id_env": "LANGFLOW_DUMMY_TABLE_CATALOG_SAVING_FLOW_ID",
            "api_url_env": "LANGFLOW_DUMMY_TABLE_CATALOG_SAVING_API_URL",
            "input_kind": "raw_text",
            "response_type": "metadata_authoring",
        },
        "dummy_main_flow_filter_saving": {
            "selected_flow": "dummy_main_flow_filter_saving_flow",
            "flow_id_env": "LANGFLOW_DUMMY_MAIN_FLOW_FILTER_SAVING_FLOW_ID",
            "api_url_env": "LANGFLOW_DUMMY_MAIN_FLOW_FILTER_SAVING_API_URL",
            "input_kind": "raw_text",
            "response_type": "metadata_authoring",
        },
    }
}
DEFAULT_ROUTE_REGISTRY_JSON = json.dumps(DEFAULT_ROUTE_REGISTRY, ensure_ascii=False, indent=2)

ROUTE_ALIASES = {
    "analysis": "data_analysis",
    "dataanalysis": "data_analysis",
    "data_analysis": "data_analysis",
    "data_analysis_flow": "data_analysis",
    "metadata": "metadata_qa",
    "metadataqa": "metadata_qa",
    "metadata_qa": "metadata_qa",
    "metadata_qa_flow": "metadata_qa",
    "domain": "domain_saving",
    "domain_saving": "domain_saving",
    "domain_saving_flow": "domain_saving",
    "table": "table_catalog_saving",
    "catalog": "table_catalog_saving",
    "table_catalog": "table_catalog_saving",
    "table_catalog_saving": "table_catalog_saving",
    "table_catalog_saving_flow": "table_catalog_saving",
    "main_filter": "main_flow_filter_saving",
    "main_flow_filter": "main_flow_filter_saving",
    "main_flow_filter_saving": "main_flow_filter_saving",
    "main_flow_filters_saving_flow": "main_flow_filter_saving",
    "dummy_data_analysis": "dummy_data_analysis",
    "dummy_metadata_qa": "dummy_metadata_qa",
    "dummy_domain_saving": "dummy_domain_saving",
    "dummy_table_catalog_saving": "dummy_table_catalog_saving",
    "dummy_main_flow_filter_saving": "dummy_main_flow_filter_saving",
    "direct": "direct_answer",
    "directanswer": "direct_answer",
    "direct_answer": "direct_answer",
    "greeting": "direct_answer",
    "help": "direct_answer",
    "clarify": "clarification",
    "clarification": "clarification",
    "else": "clarification",
}

DIRECT_MESSAGES = {
    "direct_answer": (
        "안녕하세요. 제조 데이터 분석, 메타데이터 QA, 메타데이터 등록 요청을 도와드릴 수 있습니다.\n\n"
        "예를 들어 이렇게 요청할 수 있습니다.\n"
        "- 오늘 DA공정 생산량 알려줘\n"
        "- 현재 조회 가능한 데이터셋과 필수 조건 보여줘\n"
        "- DA 공정 그룹을 domain metadata로 등록해줘"
    ),
    "clarification": (
        "어떤 요청인지 조금 더 구체적으로 알려주세요.\n\n"
        "분석이 필요하면 기준일, 공정, 제품, 보고 싶은 지표를 알려주세요.\n"
        "메타데이터 확인이 필요하면 데이터셋, 컬럼, 계산 로직, 등록 규칙 중 무엇을 볼지 알려주세요.\n"
        "메타데이터 등록이 필요하면 등록할 원문과 metadata 종류를 함께 입력해주세요."
    ),
}


def build_route_api_request(
    original_input_value: Any,
    smart_router_output_value: Any = "",
    *,
    route_registry_json: str = "",
    base_url: str = "",
    session_id: str = "",
    input_type: str = "chat",
    output_type: str = "chat",
) -> dict[str, Any]:
    original_input = _input_text(original_input_value, preserve=True)
    decision = _decision_from_output(smart_router_output_value)
    route = _resolve_route(decision.get("route") or decision.get("selected_route") or decision.get("label") or decision.get("text"))
    registry = _route_registry(route_registry_json)

    if route in {"direct_answer", "clarification"}:
        return _direct_route_request(route, original_input, decision, session_id)

    route_item = _dict(registry.get(route))
    selected_flow = _clean(route_item.get("selected_flow")) or f"{route}_flow"
    resolved_base_url = _clean(base_url) or _clean(os.getenv("LANGFLOW_BASE_URL") or os.getenv("LANGFLOW_API_BASE_URL"))
    api_url = _resolve_api_url(route_item, resolved_base_url)
    request_session_id = _clean(session_id)
    warnings = []
    errors = []
    if not original_input.strip():
        errors.append({"type": "empty_input", "message": "하위 flow로 전달할 원문 입력이 비어 있습니다."})
    if not api_url:
        warnings.append(
            {
                "type": "missing_api_url",
                "message": "선택된 flow의 Langflow API URL을 확인할 수 없습니다.",
                "flow_id_env": route_item.get("flow_id_env", ""),
                "api_url_env": route_item.get("api_url_env", ""),
            }
        )

    subflow_call = {
        "selected_flow": selected_flow,
        "api_url": api_url,
        "flow_id": _clean(route_item.get("flow_id") or os.getenv(_clean(route_item.get("flow_id_env")))),
        "flow_id_env": _clean(route_item.get("flow_id_env")),
        "api_url_env": _clean(route_item.get("api_url_env")),
        "input_kind": _clean(route_item.get("input_kind") or "question"),
        "input_value": original_input,
        "input_type": _clean(input_type) or "chat",
        "output_type": _clean(output_type) or "chat",
        "session_id": request_session_id,
    }
    return {
        "status": "ready" if not errors else "error",
        "response_type": "route_api_request",
        "route": route,
        "selected_flow": selected_flow,
        "request": {
            "original_input": original_input,
            "input_length": len(original_input),
            "session_id": request_session_id,
        },
        "subflow_call": subflow_call,
        "route_decision": {
            "route": route,
            "selected_flow": selected_flow,
            "route_source": "smart_router",
            "raw_smart_router_output": decision.get("raw_output", ""),
        },
        "warnings": warnings,
        "errors": errors,
        "trace": {
            "router_v3": {
                "stage": "01_route_api_request_builder",
                "status": "ready" if not errors else "error",
                "input_kind": subflow_call["input_kind"],
                "input_length": len(original_input),
            }
        },
    }


def _direct_route_request(route: str, original_input: str, decision: dict[str, Any], session_id: str) -> dict[str, Any]:
    message = _clean(decision.get("message") or decision.get("answer") or decision.get("text")) or DIRECT_MESSAGES[route]
    status = "ok" if route == "direct_answer" else "needs_more_input"
    direct_payload = {
        "response_type": route,
        "status": status,
        "direct_response_ready": True,
        "message": message,
        "display_message": message,
        "request": {"question": original_input, "session_id": _clean(session_id)},
    }
    return {
        "status": status,
        "response_type": "route_api_request",
        "execution_mode": "direct",
        "route": route,
        "selected_flow": "",
        "request": {"original_input": original_input, "input_length": len(original_input), "session_id": _clean(session_id)},
        "subflow_call": {},
        "direct_response": direct_payload,
        "route_decision": {
            "route": route,
            "selected_flow": "",
            "route_source": "smart_router",
            "raw_smart_router_output": decision.get("raw_output", ""),
        },
        "warnings": [],
        "errors": [],
        "trace": {
            "router_v3": {
                "stage": "01_route_api_request_builder",
                "status": status,
                "input_length": len(original_input),
            }
        },
    }


def _decision_from_output(value: Any) -> dict[str, Any]:
    data = _payload(value)
    text = _input_text(value)
    parsed = _extract_json(text)
    if parsed:
        data = _deep_merge(data, parsed)
    if not data:
        data = {"text": text}
    for key in ("route", "selected_route", "label", "output_name", "branch", "result", "selected", "name"):
        if _clean(data.get(key)):
            data.setdefault("route", data.get(key))
            break
    data["raw_output"] = text or json.dumps(data, ensure_ascii=False, default=str)
    return data


def _route_registry(value: str) -> dict[str, dict[str, Any]]:
    registry = deepcopy(DEFAULT_ROUTE_REGISTRY["routes"])
    parsed = _extract_json(value)
    if not parsed:
        return registry
    raw_routes = parsed.get("routes") if isinstance(parsed.get("routes"), dict) else parsed
    if not isinstance(raw_routes, dict):
        return registry
    for raw_route, raw_item in raw_routes.items():
        route = _resolve_route(raw_route)
        item = _dict(raw_item)
        if route in {"direct_answer", "clarification"}:
            continue
        registry[route] = _deep_merge(registry.get(route, {}), item)
    return registry


def _resolve_route(value: Any) -> str:
    text = _clean(value)
    parsed = _extract_json(text)
    if parsed:
        for key in ("route", "selected_route", "label", "selected_flow"):
            if _clean(parsed.get(key)):
                text = _clean(parsed.get(key))
                break
    normalized = _route_key(text)
    if normalized in ROUTE_ALIASES:
        return ROUTE_ALIASES[normalized]
    for alias, route in ROUTE_ALIASES.items():
        if alias and alias in normalized:
            return route
    return "clarification"


def _resolve_api_url(route_item: dict[str, Any], base_url: str) -> str:
    explicit = _clean(route_item.get("api_url") or os.getenv(_clean(route_item.get("api_url_env"))))
    if explicit:
        return _normalize_api_url_or_flow_id(explicit, base_url)
    flow_id = _clean(route_item.get("flow_id") or os.getenv(_clean(route_item.get("flow_id_env"))))
    if base_url and flow_id:
        return _flow_run_url(base_url, flow_id)
    return ""


def _normalize_api_url_or_flow_id(value: str, base_url: str) -> str:
    text = _clean(value)
    if not text or text.lower() in {"none", "null", "n/a", "na"}:
        return ""
    if _is_http_url(text):
        return text
    if base_url:
        return _flow_run_url(base_url, text)
    return ""


def _flow_run_url(base_url: str, flow_id_or_path: str) -> str:
    base = _clean(base_url).rstrip("/")
    target = _clean(flow_id_or_path)
    if not base or not target:
        return ""
    if target.startswith("/"):
        return base + target
    if target.startswith("api/v1/run/"):
        return f"{base}/{target}"
    return f"{base}/api/v1/run/{target}"


def _is_http_url(value: str) -> bool:
    return _clean(value).lower().startswith(("http://", "https://"))


def _route_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "", _clean(value).lower())


def _extract_json(value: Any) -> dict[str, Any]:
    text = _clean(value)
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    candidates = [text]
    if "{" in text and "}" in text:
        candidates.append(text[text.find("{") : text.rfind("}") + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _input_text(value: Any, *, preserve: bool = False) -> str:
    if value is None:
        return ""
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text if preserve else text.strip()
    if isinstance(value, str):
        return value if preserve else value.strip()
    data = getattr(value, "data", value)
    if isinstance(data, dict):
        request = data.get("request") if isinstance(data.get("request"), dict) else {}
        for key in ("question", "raw_text", "input_value", "original_input", "message", "text"):
            nested = request.get(key) if key in request else data.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested if preserve else nested.strip()
    return ""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in extra.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


class RouteApiRequestBuilder(Component):
    display_name = "01 Route API 요청 생성기"
    description = "Smart Router 결과와 사용자 원문을 합쳐 선택된 Langflow 하위 flow API 호출 요청을 만듭니다."
    inputs = [
        MessageTextInput(name="original_input", display_name="원문 입력", required=True),
        MessageTextInput(name="smart_router_output", display_name="Smart Router 출력", required=True),
        MessageTextInput(name="route_registry_json", display_name="라우트 Registry JSON", value=DEFAULT_ROUTE_REGISTRY_JSON, required=False),
        MessageTextInput(name="base_url", display_name="Langflow 기본 URL", value="", required=False),
        MessageTextInput(name="session_id", display_name="세션 ID", value="", required=False, advanced=True),
        MessageTextInput(name="input_type", display_name="입력 Type", value="chat", required=False, advanced=True),
        MessageTextInput(name="output_type", display_name="출력 Type", value="chat", required=False, advanced=True),
    ]
    outputs = [
        Output(name="route_request", display_name="Route API 요청", method="build_payload", types=["Data"]),
    ]

    def build_payload(self) -> Data:
        return Data(
            data=build_route_api_request(
                getattr(self, "original_input", ""),
                getattr(self, "smart_router_output", ""),
                route_registry_json=getattr(self, "route_registry_json", ""),
                base_url=getattr(self, "base_url", ""),
                session_id=getattr(self, "session_id", ""),
                input_type=getattr(self, "input_type", "chat"),
                output_type=getattr(self, "output_type", "chat"),
            )
        )
