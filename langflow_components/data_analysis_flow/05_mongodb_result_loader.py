from __future__ import annotations

import os
from copy import deepcopy
from importlib import import_module
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

DEFAULT_DATABASE = "datagov"
DEFAULT_COLLECTION = "agent_v4_result_store"


def load_previous_result(payload_value: Any, data_ref: str = "", mongo_uri: str = "", mongo_database: str = "", collection_name: str = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    ref = data_ref or _find_data_ref(payload)
    mongo_uri, mongo_database, collection_name = _resolve_config(mongo_uri, mongo_database, collection_name)
    next_payload = deepcopy(payload)
    if not ref:
        return _mark_skipped(next_payload, mongo_database, collection_name, "missing_data_ref", "data_ref가 없어 이전 결과를 불러오지 않았습니다.")
    if not mongo_uri:
        return _mark_skipped(next_payload, mongo_database, collection_name, "missing_mongo_uri", "MONGODB_URI가 없어 이전 결과를 불러오지 않았습니다.", ref)

    client = None
    try:
        mongo_client_cls = getattr(import_module("pymongo"), "MongoClient")
        client = mongo_client_cls(mongo_uri, serverSelectionTimeoutMS=5000)
        doc = client[mongo_database][collection_name].find_one({"_id": ref}, {"_id": 0}) or {}
        if not doc:
            return _mark_skipped(next_payload, mongo_database, collection_name, "result_not_found", "data_ref에 해당하는 이전 결과가 없습니다.", ref)
        stored_payload = doc.get("payload", {}) if isinstance(doc.get("payload"), dict) else {}
        for key in ("source_results", "runtime_sources", "analysis", "data"):
            if key in stored_payload:
                next_payload[key] = deepcopy(stored_payload[key])
        next_payload.setdefault("data", {})["data_ref"] = ref
        next_payload.setdefault("trace", {}).setdefault("inspection", {})["result_loader"] = {
            "stage": "05_mongodb_result_loader",
            "status": "ok",
            "database": mongo_database,
            "collection_name": collection_name,
            "data_ref": ref,
            "errors": [],
        }
        return next_payload
    except Exception as exc:
        return _mark_error(next_payload, mongo_database, collection_name, ref, [{"type": "mongo_load_error", "message": str(exc)}])
    finally:
        if client is not None:
            client.close()


def _resolve_config(mongo_uri: str = "", mongo_database: str = "", collection_name: str = "") -> tuple[str, str, str]:
    return (
        mongo_uri or os.getenv("MONGODB_URI", ""),
        mongo_database or os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE),
        collection_name or os.getenv("MONGODB_RESULT_COLLECTION", DEFAULT_COLLECTION),
    )


def _find_data_ref(payload: dict[str, Any]) -> str:
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    state = payload.get("state", {}) if isinstance(payload.get("state"), dict) else {}
    current_data = state.get("current_data", {}) if isinstance(state.get("current_data"), dict) else {}
    return str(data.get("data_ref") or current_data.get("data_ref") or state.get("data_ref") or "")


def _mark_skipped(
    payload: dict[str, Any],
    database: str,
    collection_name: str,
    error_type: str,
    message: str,
    data_ref: str = "",
) -> dict[str, Any]:
    payload.setdefault("trace", {}).setdefault("warnings", []).append({"type": error_type, "message": message})
    payload.setdefault("trace", {}).setdefault("inspection", {})["result_loader"] = {
        "stage": "05_mongodb_result_loader",
        "status": "skipped",
        "database": database,
        "collection_name": collection_name,
        "data_ref": data_ref,
        "errors": [{"type": error_type, "message": message}],
    }
    return payload


def _mark_error(payload: dict[str, Any], database: str, collection_name: str, data_ref: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    payload.setdefault("trace", {}).setdefault("errors", []).extend(errors)
    payload.setdefault("trace", {}).setdefault("inspection", {})["result_loader"] = {
        "stage": "05_mongodb_result_loader",
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


class MongoDBResultLoader(Component):
    display_name = "05 MongoDB 이전 결과 로더"
    description = "MongoDB result store에서 data_ref 기준 이전 분석 결과를 복원합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        MessageTextInput(name="data_ref", display_name="데이터 참조 ID", required=False),
        MessageTextInput(name="mongo_uri", display_name="MongoDB 연결 URI", required=False, advanced=True),
        MessageTextInput(name="mongo_database", display_name="MongoDB 데이터베이스", required=False, advanced=True),
        MessageTextInput(name="collection_name", display_name="결과 컬렉션", required=False, advanced=True),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(
            data=load_previous_result(
                getattr(self, "payload", None),
                getattr(self, "data_ref", ""),
                getattr(self, "mongo_uri", ""),
                getattr(self, "mongo_database", ""),
                getattr(self, "collection_name", ""),
            )
        )
