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
    answer_type = str(parsed.get("answer_type") or fallback.get("answer_type") or context.get("answer_mode") or "general_metadata_search").strip()
    answer_message = str(parsed.get("answer_message") or parsed.get("answer") or fallback["answer_message"]).strip()
    summary = str(parsed.get("summary") or fallback["summary"]).strip()
    parsed_sections = _dict(parsed.get("answer_sections"))
    table = _dict(parsed.get("table")) or _dict(parsed_sections.get("detail_table")) or fallback["table"]
    columns = _string_list(table.get("columns")) or _columns_from_rows(_row_list(table.get("rows")))
    rows = _row_list(table.get("rows"))
    source_refs = _list(parsed.get("source_refs")) or _list(context.get("source_refs"))
    warnings = _list(parsed.get("warnings"))
    sql_blocks = _list(parsed_sections.get("sql_blocks")) or _list(parsed.get("sql_blocks")) or fallback.get("sql_blocks", [])
    answer_sections = parsed_sections or fallback.get("answer_sections") or _build_answer_sections(answer_type, answer_message, summary, table, sql_blocks, source_refs, context, warnings)

    next_payload = deepcopy(payload)
    next_payload["response_type"] = "metadata_qa"
    next_payload["status"] = "ok"
    next_payload["direct_response_ready"] = True
    next_payload["answer_type"] = answer_type
    next_payload["answer_message"] = answer_message
    next_payload["answer_sections"] = answer_sections
    next_payload["metadata_qa"] = {
        "summary": summary,
        "answer_type": answer_type,
        "answer_mode": context.get("answer_mode") or _dict(next_payload.get("metadata_route")).get("answer_mode"),
        "items": _list(context.get("candidate_rows"))[:20],
        "source_refs": source_refs,
        "sql_blocks": sql_blocks,
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
        "answer_type": answer_type,
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
    answer_type = answer_mode
    if not rows and not source_refs:
        if answer_mode == "data_analysis_redirect":
            message = "이 질문은 실제 데이터 값을 계산해야 하므로 metadata QA가 아니라 data_analysis flow에서 처리하는 것이 적절합니다."
            table = {"columns": ["항목", "내용"], "rows": [{"항목": "권장 route", "내용": "data_analysis"}]}
            return _fallback_payload(answer_type, message, table, [], source_refs, context)
        message = "질문과 직접 매칭되는 등록 메타데이터를 찾지 못했습니다. 데이터셋명, 도메인 용어, 또는 등록 key를 조금 더 구체적으로 알려주세요."
        return _fallback_payload(answer_type, message, {"columns": [], "rows": []}, [], source_refs, context)

    if answer_mode == "dataset_sql":
        sql_blocks = [_sql_block(item) for item in datasets if _sql_block(item)]
        target = _display_name(datasets[0]) if datasets else "요청한 데이터셋"
        message = f"{target}에 등록된 조회 설정과 query_template 기준으로 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, sql_blocks, source_refs, context)
    if answer_mode == "available_sources":
        message = f"현재 질문 기준으로 조회 가능한 데이터셋 후보 {len(rows)}개를 정리했습니다. 각 데이터셋의 연결 방식과 필수 조건은 표를 확인하세요."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "dataset_detail":
        target = str(rows[0].get("display_name") or rows[0].get("key") or "요청한 데이터셋") if rows else "요청한 데이터셋"
        message = f"{target}의 등록 정보와 사용 기준을 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "required_params":
        message = f"질문과 관련된 데이터셋의 필수 조회 조건 {len(rows)}건을 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "calculation_logic_list":
        message = f"등록된 계산/분석 관련 메타데이터 후보 {len(rows)}개를 정리했습니다. 실제 계산 실행은 data_analysis_flow의 pandas 단계에서 수행됩니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode in {"product_domain_info", "product_condition"}:
        message = f"제품/POP 조건과 관련된 도메인 메타데이터 후보 {len(rows)}개를 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "product_token_rule":
        message = f"제품 속성 token 해석과 관련된 메타데이터 후보 {len(rows)}개를 정리했습니다. 실제 제품 매칭은 data_analysis_flow의 분석 단계에서 수행됩니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "process_group":
        message = f"공정 그룹과 세부 공정 해석에 관련된 메타데이터 후보 {len(rows)}개를 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "term_definition":
        message = f"질문과 관련된 용어 정의 메타데이터 후보 {len(rows)}개를 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)
    if answer_mode == "question_to_dataset":
        message = f"이 질문에 답할 때 참고할 데이터셋과 조건 후보 {len(rows)}개를 정리했습니다."
        return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)

    message = f"질문 '{question}'과 관련된 메타데이터 후보 {len(rows)}개를 정리했습니다."
    return _fallback_payload(answer_type, message, {"columns": _columns_from_rows(rows), "rows": rows}, [], source_refs, context)


def _fallback_payload(
    answer_type: str,
    message: str,
    table: dict[str, Any],
    sql_blocks: list[Any],
    source_refs: list[Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    sections = _build_answer_sections(answer_type, message, message, table, sql_blocks, source_refs, context, [])
    return {
        "answer_type": answer_type,
        "answer_message": message,
        "summary": message,
        "table": table,
        "sql_blocks": sql_blocks,
        "answer_sections": sections,
    }


def _build_answer_sections(
    answer_type: str,
    answer_message: str,
    summary: str,
    table: dict[str, Any],
    sql_blocks: list[Any],
    source_refs: list[Any],
    context: dict[str, Any],
    warnings: list[Any],
) -> dict[str, Any]:
    rows = _row_list(table.get("rows"))
    columns = _string_list(table.get("columns")) or _columns_from_rows(rows)
    return {
        "summary": {"headline": answer_message, "description": summary},
        "detail_table": {
            "title": _table_title(answer_type),
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        },
        "sql_blocks": [block for block in sql_blocks if isinstance(block, dict)],
        "usage_examples": _usage_examples(answer_type, context),
        "related_items": [ref for ref in source_refs if isinstance(ref, dict)][:10],
        "route_hint": _route_hint(answer_type),
        "warnings": [warning for warning in warnings if isinstance(warning, dict)],
    }


def _table_title(answer_type: str) -> str:
    return {
        "available_sources": "조회 가능한 데이터",
        "dataset_detail": "데이터셋 등록 정보",
        "required_params": "필수 조회 조건",
        "dataset_sql": "데이터셋 등록 정보",
        "term_definition": "등록된 용어 정의",
        "process_group": "공정 그룹",
        "product_condition": "제품 조건",
        "product_domain_info": "제품 조건",
        "product_token_rule": "제품 token 해석 규칙",
        "calculation_logic_list": "계산/분석 로직",
        "question_to_dataset": "질문에 필요한 데이터와 조건",
        "data_analysis_redirect": "권장 실행 경로",
    }.get(answer_type, "관련 메타데이터")


def _usage_examples(answer_type: str, context: dict[str, Any]) -> list[str]:
    question = str(context.get("question") or "").strip()
    examples = {
        "available_sources": ["오늘 DA공정 생산량 알려줘", "현재 재공이 많은 제품 알려줘"],
        "dataset_detail": ["이 데이터로 답할 수 있는 대표 질문을 알려줘"],
        "required_params": ["어제 기준으로 다시 조회해줘"],
        "term_definition": ["생산량 기준으로 제품별 상위 5개 알려줘"],
        "process_group": ["DA공정 차수별 생산량 알려줘"],
        "product_condition": ["HBM제품의 오늘 아침재공 제품별로 알려줘"],
        "product_token_rule": ["RG 32G DDR4 FBGA 96 DDP 제품 생산량 알려줘"],
        "calculation_logic_list": ["등록된 계산 로직 중 생산 달성률 기준 알려줘"],
        "question_to_dataset": [question] if question else [],
    }
    return examples.get(answer_type, [])


def _route_hint(answer_type: str) -> dict[str, str]:
    if answer_type == "data_analysis_redirect":
        return {"target_route": "data_analysis", "message": "실제 수량 계산은 data_analysis flow에서 실행합니다."}
    return {}


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
