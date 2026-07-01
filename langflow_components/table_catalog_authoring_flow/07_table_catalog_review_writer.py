from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

TRUNCATED = ("...", "생략", "omitted", "truncated")
DEFAULT_DATABASE = "datagov"
DEFAULT_COLLECTION = "agent_v4_table_catalog_items"
COLLECTION_ENV = "MONGODB_TABLE_CATALOG_COLLECTION"


def review_and_write(payload_value: Any, review_response: Any = "", mongo_uri: str = "", mongo_database: str = "", collection_name: str = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    errors = _deterministic_errors(payload)
    llm_review = _json(review_response)
    review = _merge_review(llm_review, payload, errors)
    duplicate_blocked = bool(payload.get("existing_matches")) and payload.get("duplicate_decision", {}).get("action") == "ask"
    ready = bool(review.get("ready_to_save")) and not duplicate_blocked
    next_payload = deepcopy(payload)
    next_payload["review"] = review
    if not ready:
        next_payload["write_result"] = {"success": False, "ready_to_save": False, "saved_count": 0, "message": "비슷한 기존 정보가 있어 아직 저장하지 않았습니다. 처리 방식을 선택해 주세요." if duplicate_blocked else "아직 저장하지 않았습니다. 아래 정보를 더 알려주세요.", "requires_duplicate_decision": duplicate_blocked, "errors": review.get("errors", [])}
    elif payload.get("request", {}).get("dry_run", True):
        next_payload["write_result"] = {"success": True, "ready_to_save": True, "dry_run": True, "saved_count": 0, "would_save_count": len(payload.get("items", [])), "message": "드라이런입니다. MongoDB에는 저장하지 않았습니다.", "keys": [item.get("dataset_key") for item in payload.get("items", [])]}
    else:
        next_payload["write_result"] = _write_to_mongodb(payload, mongo_uri, mongo_database, collection_name)
    return next_payload


def _deterministic_errors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    errors = []
    for item in payload.get("items", []):
        p = item.get("payload", {}) if isinstance(item.get("payload"), dict) else {}
        sc = p.get("source_config", {}) if isinstance(p.get("source_config"), dict) else {}
        source_type = p.get("source_type") or sc.get("source_type")
        if not item.get("dataset_key"):
            errors.append({"type": "missing_key", "message": "dataset_key가 없습니다."})
        if not source_type:
            errors.append({"type": "missing_source_type", "message": "payload.source_type이 없습니다."})
        if source_type in {"oracle", "datalake"}:
            query = str(sc.get("query_template") or "")
            if not query:
                errors.append({"type": "missing_query_template", "message": "Oracle/Datalake dataset에는 query_template이 필요합니다."})
            if any(marker in query.lower() for marker in TRUNCATED):
                errors.append({"type": "truncated_query", "message": "query_template이 축약되어 저장하지 않습니다."})
        if source_type == "goodocs" and not sc.get("doc_id"):
            errors.append({"type": "missing_doc_id", "message": "Goodocs dataset에는 doc_id가 필요합니다."})
    return errors


def _merge_review(llm_review: dict[str, Any], payload: dict[str, Any], deterministic_errors: list[dict[str, Any]]) -> dict[str, Any]:
    if not llm_review:
        return {"ready_to_save": bool(payload.get("items")) and not deterministic_errors, "errors": deterministic_errors, "supplement_requests": []}
    merged = deepcopy(llm_review)
    merged_errors = _list(merged.get("errors")) + deterministic_errors
    merged_supplements = _list(merged.get("supplement_requests"))
    merged["errors"] = merged_errors
    merged["supplement_requests"] = merged_supplements
    merged["ready_to_save"] = bool(merged.get("ready_to_save")) and not merged_errors and not merged_supplements and bool(payload.get("items"))
    return merged


def _write_to_mongodb(payload: dict[str, Any], mongo_uri: str, mongo_database: str, collection_name: str) -> dict[str, Any]:
    mongo_uri, mongo_database, collection_name = _resolve_mongo_config(mongo_uri, mongo_database, collection_name)
    if not mongo_uri or not mongo_database or not collection_name:
        return {"success": False, "ready_to_save": False, "saved_count": 0, "message": "MongoDB 저장 정보가 부족해 저장하지 않았습니다.", "errors": [{"type": "missing_mongo_config", "message": "mongo_uri, mongo_database, collection_name are required"}]}
    client = None
    try:
        mongo_client_cls = getattr(import_module("pymongo"), "MongoClient")
        client = mongo_client_cls(mongo_uri, serverSelectionTimeoutMS=5000)
        collection = client[mongo_database][collection_name]
        operations = []
        now = datetime.now(timezone.utc).isoformat()
        raw_text = payload.get("request", {}).get("raw_text", "")
        for item in payload.get("items", []):
            doc = deepcopy(item)
            doc["_id"] = f"table_catalog:{doc.get('dataset_key')}"
            doc["updated_at"] = now
            if raw_text:
                doc["registration_trace"] = {"raw_text": raw_text}
            collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            operations.append({"key": doc.get("dataset_key"), "operation": "upserted"})
        return {"success": True, "ready_to_save": True, "saved_count": len(operations), "operation_by_key": operations, "database": mongo_database, "collection_name": collection_name, "message": "저장했습니다.", "errors": []}
    except Exception as exc:
        return {"success": False, "ready_to_save": False, "saved_count": 0, "message": "MongoDB 저장 중 오류가 발생했습니다.", "errors": [{"type": "mongo_write_error", "message": str(exc)}]}
    finally:
        if client is not None:
            client.close()


def _resolve_mongo_config(mongo_uri: str = "", mongo_database: str = "", collection_name: str = "") -> tuple[str, str, str]:
    return (
        mongo_uri or os.getenv("MONGODB_URI", ""),
        mongo_database or os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE),
        collection_name or os.getenv(COLLECTION_ENV, DEFAULT_COLLECTION),
    )


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    text = str(value or "")
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class TableCatalogReviewWriter(Component):
    display_name = "07 테이블 카탈로그 검수/저장 처리기"
    description = "검수 결과를 적용하고 드라이런 기준 저장 결과를 만듭니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        MessageTextInput(name="review_response", display_name="검수 응답", required=False),
        MessageTextInput(name="mongo_uri", display_name="MongoDB 연결 URI", required=False, advanced=True),
        MessageTextInput(name="mongo_database", display_name="MongoDB 데이터베이스", required=False, advanced=True),
        MessageTextInput(name="collection_name", display_name="컬렉션 이름", required=False, advanced=True),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=review_and_write(getattr(self, "payload", None), getattr(self, "review_response", ""), getattr(self, "mongo_uri", ""), getattr(self, "mongo_database", ""), getattr(self, "collection_name", "")))
