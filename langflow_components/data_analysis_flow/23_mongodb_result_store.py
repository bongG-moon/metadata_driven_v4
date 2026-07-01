from __future__ import annotations

import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

DEFAULT_DATABASE = "datagov"
DEFAULT_COLLECTION = "agent_v4_result_store"


def store_result(payload_value: Any, mongo_uri: str = "", mongo_database: str = "", collection_name: str = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    mongo_uri, mongo_database, collection_name = _resolve_config(mongo_uri, mongo_database, collection_name)
    next_payload = deepcopy(payload)
    if not mongo_uri:
        return _mark_skipped(next_payload, mongo_database, collection_name, "MONGODB_URI가 없어 분석 결과를 result store에 저장하지 않았습니다.")

    client = None
    data_ref = _build_data_ref(next_payload)
    now = datetime.now(timezone.utc).isoformat()
    try:
        mongo_client_cls = getattr(import_module("pymongo"), "MongoClient")
        client = mongo_client_cls(mongo_uri, serverSelectionTimeoutMS=5000)
        collection = client[mongo_database][collection_name]
        doc = {
            "_id": data_ref,
            "data_ref": data_ref,
            "session_id": str(next_payload.get("request", {}).get("session_id") or ""),
            "question": str(next_payload.get("request", {}).get("question") or ""),
            "created_at": now,
            "payload": {
                "request": deepcopy(next_payload.get("request", {})),
                "metadata_refs": deepcopy(next_payload.get("metadata_refs", [])),
                "intent_plan": deepcopy(next_payload.get("intent_plan", {})),
                "source_results": deepcopy(next_payload.get("source_results", [])),
                "runtime_sources": deepcopy(next_payload.get("runtime_sources", {})),
                "analysis": deepcopy(next_payload.get("analysis", {})),
                "data": deepcopy(next_payload.get("data", {})),
            },
        }
        collection.replace_one({"_id": data_ref}, doc, upsert=True)
        next_payload.setdefault("data", {})["data_ref"] = data_ref
        next_payload.setdefault("trace", {}).setdefault("inspection", {})["result_store"] = {
            "stage": "23_mongodb_result_store",
            "status": "ok",
            "database": mongo_database,
            "collection_name": collection_name,
            "data_ref": data_ref,
            "errors": [],
        }
        return next_payload
    except Exception as exc:
        return _mark_error(next_payload, mongo_database, collection_name, data_ref, [{"type": "mongo_write_error", "message": str(exc)}])
    finally:
        if client is not None:
            client.close()


def _resolve_config(mongo_uri: str = "", mongo_database: str = "", collection_name: str = "") -> tuple[str, str, str]:
    return (
        mongo_uri or os.getenv("MONGODB_URI", ""),
        mongo_database or os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE),
        collection_name or os.getenv("MONGODB_RESULT_COLLECTION", DEFAULT_COLLECTION),
    )


def _build_data_ref(payload: dict[str, Any]) -> str:
    existing = payload.get("data", {}).get("data_ref") if isinstance(payload.get("data"), dict) else ""
    if existing:
        return str(existing)
    session_id = str(payload.get("request", {}).get("session_id") or "session")
    return f"result:{session_id}:{uuid.uuid4().hex}"


def _mark_skipped(payload: dict[str, Any], database: str, collection_name: str, message: str) -> dict[str, Any]:
    payload.setdefault("trace", {}).setdefault("warnings", []).append({"type": "missing_mongo_uri", "message": message})
    payload.setdefault("trace", {}).setdefault("inspection", {})["result_store"] = {
        "stage": "23_mongodb_result_store",
        "status": "skipped",
        "database": database,
        "collection_name": collection_name,
        "data_ref": "",
        "errors": [{"type": "missing_mongo_uri", "message": message}],
    }
    return payload


def _mark_error(payload: dict[str, Any], database: str, collection_name: str, data_ref: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    payload.setdefault("trace", {}).setdefault("errors", []).extend(errors)
    payload.setdefault("trace", {}).setdefault("inspection", {})["result_store"] = {
        "stage": "23_mongodb_result_store",
        "status": "error",
        "database": database,
        "collection_name": collection_name,
        "data_ref": data_ref,
        "errors": errors,
    }
    return payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class MongoDBResultStore(Component):
    display_name = "23 MongoDB 결과 저장소"
    description = "pandas 분석 결과와 런타임 조회 결과를 MongoDB result store에 저장하고 data_ref를 페이로드에 남깁니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        MessageTextInput(name="mongo_uri", display_name="MongoDB 연결 URI", required=False, advanced=True),
        MessageTextInput(name="mongo_database", display_name="MongoDB 데이터베이스", required=False, advanced=True),
        MessageTextInput(name="collection_name", display_name="결과 컬렉션", required=False, advanced=True),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(
            data=store_result(
                getattr(self, "payload", None),
                getattr(self, "mongo_uri", ""),
                getattr(self, "mongo_database", ""),
                getattr(self, "collection_name", ""),
            )
        )
