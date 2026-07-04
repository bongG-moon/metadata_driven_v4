from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data


def normalize_metadata_qa_response(payload_value: Any, llm_response_value: Any = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    context = _dict(payload.get("metadata_qa_context"))
    question = str(_dict(payload.get("request")).get("question") or context.get("question") or "").strip()
    parsed = _parse_llm_response(llm_response_value)
    fallback = _fallback_answer(question, context)
    answer_message = str(parsed.get("answer_message") or parsed.get("answer") or fallback["answer_message"]).strip()
    summary = str(parsed.get("summary") or fallback["summary"]).strip()
    table = _dict(parsed.get("table")) or fallback["table"]
    columns = _string_list(table.get("columns")) or _columns_from_rows(_row_list(table.get("rows")))
    rows = _row_list(table.get("rows"))
    source_refs = _list(parsed.get("source_refs")) or _list(context.get("source_refs"))
    warnings = _list(parsed.get("warnings"))

    next_payload = deepcopy(payload)
    next_payload["response_type"] = "metadata_qa"
    next_payload["status"] = "ok"
    next_payload["direct_response_ready"] = True
    next_payload["answer_message"] = answer_message
    next_payload["metadata_qa"] = {
        "summary": summary,
        "answer_mode": context.get("answer_mode") or _dict(next_payload.get("metadata_route")).get("answer_mode"),
        "items": _list(context.get("candidate_rows"))[:20],
        "source_refs": source_refs,
        "sql_blocks": fallback.get("sql_blocks", []),
    }
    next_payload["data"] = {"columns": columns, "rows": rows, "row_count": len(rows)}
    next_payload["state"] = {
        **_dict(next_payload.get("state")),
        "current_metadata_qa": {
            "question": question,
            "answer_mode": next_payload["metadata_qa"].get("answer_mode"),
            "source_refs": source_refs[:10],
        },
    }
    trace = _dict(next_payload.get("trace"))
    trace.setdefault("warnings", []).extend(warnings)
    trace.setdefault("inspection", {})["metadata_qa_response"] = {
        "stage": "04_metadata_qa_response_normalizer",
        "status": "ok",
        "row_count": len(rows),
        "used_llm_response": bool(parsed),
    }
    next_payload["trace"] = trace
    return next_payload


def _fallback_answer(question: str, context: dict[str, Any]) -> dict[str, Any]:
    answer_mode = str(context.get("answer_mode") or "general_metadata_search")
    rows = _row_list(context.get("candidate_rows"))
    source_refs = _list(context.get("source_refs"))
    datasets = _list(context.get("matched_datasets"))
    if not rows and not source_refs:
        message = "질문과 직접 매칭되는 등록 메타데이터를 찾지 못했습니다. 데이터셋명, 도메인 용어, 또는 등록 key를 조금 더 구체적으로 알려주세요."
        return {"answer_message": message, "summary": message, "table": {"columns": [], "rows": []}, "sql_blocks": []}

    if answer_mode == "dataset_sql":
        sql_blocks = [_sql_block(item) for item in datasets if _sql_block(item)]
        target = _display_name(datasets[0]) if datasets else "요청한 데이터셋"
        message = f"{target}에 등록된 조회 설정과 query_template 기준으로 정리했습니다."
        return {"answer_message": message, "summary": message, "table": {"columns": _columns_from_rows(rows), "rows": rows}, "sql_blocks": sql_blocks}
    if answer_mode == "available_sources":
        message = f"현재 질문 기준으로 조회 가능한 데이터셋 후보 {len(rows)}개를 정리했습니다. 각 데이터셋의 연결 방식과 필수 조건은 표를 확인하세요."
        return {"answer_message": message, "summary": message, "table": {"columns": _columns_from_rows(rows), "rows": rows}, "sql_blocks": []}
    if answer_mode == "calculation_logic_list":
        message = f"등록된 계산/분석 관련 메타데이터 후보 {len(rows)}개를 정리했습니다. 실제 계산 실행은 data_analysis_flow의 pandas 단계에서 수행됩니다."
        return {"answer_message": message, "summary": message, "table": {"columns": _columns_from_rows(rows), "rows": rows}, "sql_blocks": []}
    if answer_mode == "product_domain_info":
        message = f"제품/POP 조건과 관련된 도메인 메타데이터 후보 {len(rows)}개를 정리했습니다."
        return {"answer_message": message, "summary": message, "table": {"columns": _columns_from_rows(rows), "rows": rows}, "sql_blocks": []}

    message = f"질문 '{question}'과 관련된 메타데이터 후보 {len(rows)}개를 정리했습니다."
    return {"answer_message": message, "summary": message, "table": {"columns": _columns_from_rows(rows), "rows": rows}, "sql_blocks": []}


def _sql_block(item: Any) -> dict[str, str]:
    table = _dict(item)
    payload = _dict(table.get("payload"))
    source_config = _dict(payload.get("source_config"))
    sql = str(source_config.get("query_template") or payload.get("query_template") or "").strip()
    if not sql:
        return {}
    return {"label": _display_name(table), "sql": sql}


def _display_name(item: Any) -> str:
    table = _dict(item)
    payload = _dict(table.get("payload"))
    return str(payload.get("display_name") or table.get("display_name") or table.get("dataset_key") or table.get("key") or "").strip()


def _parse_llm_response(value: Any) -> dict[str, Any]:
    text = _text(value)
    if not text:
        return {}
    candidates = [text.strip()]
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        candidates.insert(0, match.group(1).strip())
    if "{" in text and "}" in text:
        candidates.append(text[text.find("{") : text.rfind("}") + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return deepcopy(parsed)
    return {"answer_message": text}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text.strip()
    data = getattr(value, "data", None)
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, default=str)
    return str(value or "").strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _row_list(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item or "").strip()] if isinstance(value, list) else []


def _columns_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(str(key))
    return columns


class MetadataQaResponseNormalizer(Component):
    display_name = "04 메타데이터 QA 응답 정규화기"
    description = "Langflow Agent/LLM 응답을 메타데이터 QA 표준 페이로드로 정규화합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        MessageTextInput(name="llm_response", display_name="LLM 응답", required=False),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload", types=["Data"])]

    def build_payload(self) -> Data:
        return Data(data=normalize_metadata_qa_response(getattr(self, "payload", None), getattr(self, "llm_response", "")))
