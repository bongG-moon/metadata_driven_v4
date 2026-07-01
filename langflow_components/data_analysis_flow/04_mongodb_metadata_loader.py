from __future__ import annotations

import os
from copy import deepcopy
from importlib import import_module
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

DEFAULT_DATABASE = "datagov"
DEFAULT_DOMAIN_COLLECTION = "agent_v4_domain_items"
DEFAULT_TABLE_CATALOG_COLLECTION = "agent_v4_table_catalog_items"
DEFAULT_MAIN_FLOW_FILTER_COLLECTION = "agent_v4_main_flow_filters"


def load_metadata_candidates(
    mongo_uri: str = "",
    mongo_database: str = "",
    domain_collection: str = "",
    table_catalog_collection: str = "",
    main_flow_filter_collection: str = "",
    limit: str = "1000",
    status_filter: str = "active",
) -> dict[str, Any]:
    config = _resolve_config(mongo_uri, mongo_database, domain_collection, table_catalog_collection, main_flow_filter_collection)
    load_limit = _int(limit, 1000)
    empty_items = {"domain_items": [], "table_catalog_items": [], "main_flow_filters": []}
    if not config["mongo_uri"]:
        return _result(
            "skipped",
            empty_items,
            config,
            [{"type": "missing_mongo_uri", "message": "MONGODB_URI가 없어 MongoDB 메타데이터를 불러오지 않았습니다."}],
        )

    client = None
    try:
        mongo_client_cls = getattr(import_module("pymongo"), "MongoClient")
        client = mongo_client_cls(config["mongo_uri"], serverSelectionTimeoutMS=5000)
        database = client[config["mongo_database"]]
        query = _status_query(status_filter)
        items = {
            "domain_items": _load_collection(database[config["domain_collection"]], load_limit, query),
            "table_catalog_items": _load_collection(database[config["table_catalog_collection"]], load_limit, query),
            "main_flow_filters": _load_collection(database[config["main_flow_filter_collection"]], load_limit, query),
        }
        return _result("ok", items, config, [], status_filter)
    except Exception as exc:
        return _result("error", empty_items, config, [{"type": "mongo_load_error", "message": str(exc)}], status_filter)
    finally:
        if client is not None:
            client.close()


def _load_collection(collection: Any, limit: int, query: dict[str, Any]) -> list[dict[str, Any]]:
    docs = list(collection.find(query, {"_id": 0}).limit(limit))
    return [deepcopy(doc) for doc in docs if isinstance(doc, dict)]


def _resolve_config(
    mongo_uri: str = "",
    mongo_database: str = "",
    domain_collection: str = "",
    table_catalog_collection: str = "",
    main_flow_filter_collection: str = "",
) -> dict[str, str]:
    return {
        "mongo_uri": mongo_uri or os.getenv("MONGODB_URI", ""),
        "mongo_database": mongo_database or os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE),
        "domain_collection": domain_collection or os.getenv("MONGODB_DOMAIN_COLLECTION", DEFAULT_DOMAIN_COLLECTION),
        "table_catalog_collection": table_catalog_collection or os.getenv("MONGODB_TABLE_CATALOG_COLLECTION", DEFAULT_TABLE_CATALOG_COLLECTION),
        "main_flow_filter_collection": main_flow_filter_collection or os.getenv("MONGODB_MAIN_FLOW_FILTER_COLLECTION", DEFAULT_MAIN_FLOW_FILTER_COLLECTION),
    }


def _result(
    status: str,
    items: dict[str, list[dict[str, Any]]],
    config: dict[str, str],
    errors: list[dict[str, Any]],
    status_filter: str = "active",
) -> dict[str, Any]:
    safe_items = {
        "domain_items": deepcopy(items.get("domain_items", [])),
        "table_catalog_items": deepcopy(items.get("table_catalog_items", [])),
        "main_flow_filters": deepcopy(items.get("main_flow_filters", [])),
    }
    metadata_load = {
        "status": status,
        "database": config["mongo_database"],
        "collections": {
            "domain_items": config["domain_collection"],
            "table_catalog_items": config["table_catalog_collection"],
            "main_flow_filters": config["main_flow_filter_collection"],
        },
        "counts": {key: len(value) for key, value in safe_items.items()},
        "status_filter": status_filter or "active",
        "errors": errors,
    }
    return {
        **safe_items,
        "metadata_candidates": safe_items,
        "metadata_load": metadata_load,
    }


def _int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except Exception:
        return default


def _status_query(status_filter: str) -> dict[str, Any]:
    value = str(status_filter or "active").strip()
    if not value or value.lower() == "all":
        return {}
    return {"status": value}


class MongoDBMetadataLoader(Component):
    display_name = "04 MongoDB 메타데이터 로더"
    description = "MongoDB에서 도메인, 테이블 카탈로그, 메인 플로우 필터 메타데이터를 읽어 의도 분석에 전달합니다."
    inputs = [
        MessageTextInput(name="mongo_uri", display_name="MongoDB 연결 URI", required=False, advanced=True),
        MessageTextInput(name="mongo_database", display_name="MongoDB 데이터베이스", required=False, advanced=True),
        MessageTextInput(name="domain_collection", display_name="도메인 컬렉션", required=False, advanced=True),
        MessageTextInput(name="table_catalog_collection", display_name="테이블 카탈로그 컬렉션", required=False, advanced=True),
        MessageTextInput(name="main_flow_filter_collection", display_name="메인 플로우 필터 컬렉션", required=False, advanced=True),
        MessageTextInput(name="limit", display_name="컬렉션별 조회 제한", required=False, value="1000", advanced=True),
        MessageTextInput(name="status_filter", display_name="상태 필터", required=False, value="active", advanced=True),
    ]
    outputs = [Output(name="metadata_candidates", display_name="메타데이터 후보", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(
            data=load_metadata_candidates(
                getattr(self, "mongo_uri", ""),
                getattr(self, "mongo_database", ""),
                getattr(self, "domain_collection", ""),
                getattr(self, "table_catalog_collection", ""),
                getattr(self, "main_flow_filter_collection", ""),
                getattr(self, "limit", "1000"),
                getattr(self, "status_filter", "active"),
            )
        )
