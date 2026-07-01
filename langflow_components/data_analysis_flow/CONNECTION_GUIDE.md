# Data Analysis Flow Connection Guide

이 flow는 `의도분석 -> 데이터 조회 -> pandas code 실행 -> 답변/API response`를 연결하는 skeleton이다. Prompt와 LLM/Agent 실행은 Langflow 기본 Prompt Template과 Agent/LLM 노드를 사용한다.

## Required Connections: Intent

메타데이터 로딩은 의도분석 LLM 호출보다 반드시 앞에 둔다. 의도분석 LLM은 domain/table catalog/main variable metadata를 보고 dataset, filter, metric, retrieval job을 선택해야 하므로 `01A~01D`가 끝난 뒤 `02 Intent Variables Builder`와 Prompt Template으로 넘어간다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 1 | `Chat Input.message` 또는 `Text Input.message` | `00 Analysis Request Loader.question` |
| 2 | optional previous state Data | `00 Analysis Request Loader.previous_state` |
| 3 | `01A MongoDB Domain Metadata Loader.domain_items` | `01D Metadata Candidates Builder.domain_items` |
| 4 | `01B MongoDB Table Catalog Loader.table_catalog_items` | `01D Metadata Candidates Builder.table_catalog_items` |
| 5 | `01C MongoDB Main Variable Loader.main_flow_filters` | `01D Metadata Candidates Builder.main_flow_filters` |
| 6 | `01D Metadata Candidates Builder.metadata_candidates` | `02 Intent Variables Builder.metadata_candidates_in` |
| 7 | `00 Analysis Request Loader.payload_out` | `02 Intent Variables Builder.payload` |
| 8 | `02 Intent Variables Builder.question` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.question` |
| 9 | `02 Intent Variables Builder.state_summary` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.state_summary` |
| 10 | `02 Intent Variables Builder.metadata_candidates` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.metadata_candidates` |
| 11 | `02 Intent Variables Builder.output_schema` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.output_schema` |
| 12 | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 13 | `00 Analysis Request Loader.payload_out` | `04 Intent Plan Normalizer.payload` |
| 14 | `Langflow Agent/LLM.output` | `04 Intent Plan Normalizer.llm_response` |

## Optional Previous Result Restore

이전 turn의 `data_ref`로 전체 rows를 복원해야 할 때만 넣는다. 필요 없으면 `04 Intent Plan Normalizer.payload_out`을 바로 `06 Retrieval Job Validator.payload`에 연결한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 15A | `04 Intent Plan Normalizer.payload_out` | `05 MongoDB Previous Result Loader.payload` |
| 15B | `05 MongoDB Previous Result Loader.payload_out` | `06 Retrieval Job Validator.payload` |

Skip restore path:

| From node.output | To node.input |
| --- | --- |
| `04 Intent Plan Normalizer.payload_out` | `06 Retrieval Job Validator.payload` |

## Required Connections: Retrieval

로컬 검증 기본값은 `07 Retrieval Job Router.retrieval_mode=dummy`다. 더미 모드에서는 모든 retrieval job이 `07.dummy_jobs`로만 나가고 실제 Oracle/H-API/Datalake/Goodocs branch는 빈 작업을 받는다. 실제 Oracle 조회를 실행하려면 `07 Retrieval Job Router.retrieval_mode=live`로 바꾸고 `09 Oracle Query Retriever.oracle_config` 입력 또는 `.env`의 `ORACLE_CONFIG_JSON`에 db_key별 접속 정보를 넣는다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 16 | `06 Retrieval Job Validator.payload_out` | `07 Retrieval Job Router.payload` |
| 17 | `06 Retrieval Job Validator.payload_out` | `13 Source Retrieval Merger.main_payload` |
| 18 | `07 Retrieval Job Router.dummy_jobs` | `08 Dummy Data Retriever.payload` |
| 19 | `08 Dummy Data Retriever.retrieval_payload` | `13 Source Retrieval Merger.dummy_retrieval` |
| 20 | `13 Source Retrieval Merger.payload_out` | `14 Retrieval Payload Adapter.payload` |

## Optional Live Retrieval Branches

아래 연결은 실제 live adapter를 사용하고 `07 Retrieval Job Router.retrieval_mode=live`일 때만 사용한다.

| From node.output | To node.input |
| --- | --- |
| `07 Retrieval Job Router.oracle_jobs` | `09 Oracle Query Retriever.payload` |
| `09 Oracle Query Retriever.retrieval_payload` | `13 Source Retrieval Merger.oracle_retrieval` |
| `07 Retrieval Job Router.h_api_jobs` | `10 H-API Retriever.payload` |
| `10 H-API Retriever.retrieval_payload` | `13 Source Retrieval Merger.h_api_retrieval` |
| `07 Retrieval Job Router.datalake_jobs` | `11 Datalake Retriever.payload` |
| `11 Datalake Retriever.retrieval_payload` | `13 Source Retrieval Merger.datalake_retrieval` |
| `07 Retrieval Job Router.goodocs_jobs` | `12 Goodocs Retriever.payload` |
| `12 Goodocs Retriever.retrieval_payload` | `13 Source Retrieval Merger.goodocs_retrieval` |

## Required Connections: Pandas

| # | From node.output | To node.input |
| --- | --- | --- |
| 21 | `14 Retrieval Payload Adapter.payload_out` | `15 Pandas Variables Builder.payload` |
| 22 | `15 Pandas Variables Builder.intent_plan_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.intent_plan_json` |
| 23 | `15 Pandas Variables Builder.source_schema_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.source_schema_json` |
| 24 | `15 Pandas Variables Builder.source_preview_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.source_preview_json` |
| 25 | `15 Pandas Variables Builder.output_contract_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.output_contract_json` |
| 26 | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 27 | `14 Retrieval Payload Adapter.payload_out` | `17 Pandas Code Executor.payload` |
| 28 | `Langflow Agent/LLM.output` | `17 Pandas Code Executor.llm_response` |
| 29 | `17 Pandas Code Executor.payload_out` | `23 MongoDB Result Store.payload` |

If result store is not used:

| From node.output | To node.input |
| --- | --- |
| `17 Pandas Code Executor.payload_out` | `18 Answer Variables Builder.payload` |
| `17 Pandas Code Executor.payload_out` | `20 Answer Response Builder.payload` |

## Required Connections: Answer

Result store를 사용할 때는 아래처럼 `23 MongoDB Result Store.payload_out`을 기준으로 답변을 만든다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 30 | `23 MongoDB Result Store.payload_out` | `18 Answer Variables Builder.payload` |
| 31 | `18 Answer Variables Builder.question` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.question` |
| 32 | `18 Answer Variables Builder.result_summary_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.result_summary_json` |
| 33 | `18 Answer Variables Builder.applied_scope_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.applied_scope_json` |
| 34 | `18 Answer Variables Builder.warnings_errors_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.warnings_errors_json` |
| 35 | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 36 | `23 MongoDB Result Store.payload_out` | `20 Answer Response Builder.payload` |
| 37 | `Langflow Agent/LLM.output` | `20 Answer Response Builder.answer_text` |
| 38 | `20 Answer Response Builder.payload_out` | `21 Answer Message Adapter.payload` |
| 39 | `21 Answer Message Adapter.message` | `Chat Output.message` |

## Optional API Response

| From node.output | To node.input |
| --- | --- |
| `20 Answer Response Builder.payload_out` | `22 API Response Builder.payload` |
| `22 API Response Builder.api_response` | downstream API/Data output |

## Fixed/Manual Inputs

- `00 Analysis Request Loader`에는 `session_id` 입력 포트를 만들지 않는다. 이전 state에 `session_id`, `conversation_id`, `thread_id`가 있으면 자동으로 이어받고, 없으면 내부 기본값 `demo-session`을 사용한다.
- `00 Analysis Request Loader`에는 기준일/시간대 입력 포트를 만들지 않는다. 기준일은 실행 시점의 한국 기준 현재일 `YYYYMMDD`로 자동 계산해 `request.reference_date`에만 남긴다.
- `00 Analysis Request Loader`는 payload에 `timezone`, `reference_date_source` 같은 실행 흔적용 필드를 남기지 않는다.
- `02 Intent Variables Builder`에는 기준일/시간대 출력 포트를 만들지 않는다. 자동 기준일은 `state_summary.request_context.reference_date` 하나로 Prompt Template에 전달된다.
- `05 MongoDB Previous Result Loader`에는 `data_ref` 입력 포트를 만들지 않는다. `payload.data.data_ref`, `payload.state.current_data.data_ref`, `payload.state.data_ref` 순서로 자동 탐색한다.
- `07 Retrieval Job Router.retrieval_mode`: 기본 `dummy`. 더미 데이터를 쓰려면 이 값을 그대로 둔다. 실제 소스를 조회할 때만 `live`로 바꾼다.
- `09 Oracle Query Retriever.oracle_config`: 비워두면 `.env`의 `ORACLE_CONFIG_JSON`을 사용한다. 값은 `{"PNT_RPT": {"user": "...", "password": "...", "dsn": "(DESCRIPTION=...)"}}` 형태의 JSON이거나 `PNT_RPT: (DESCRIPTION=...)` 형태의 TNS block일 수 있다.
- `retrieval_jobs[].required_params`: table catalog/source_config가 요구하는 필수 조회 파라미터만 넣는다. 이 값만 데이터 조회 단계에서 SQL/API/template에 적용된다.
- `retrieval_jobs[].filters`: 공정/제품/상태/장비/LOT 같은 분석 조건을 넣는다. 조회기는 이 값을 `pandas_filters`로 보존하고, `17 pandas 코드 실행기`가 pandas 전처리 코드로 적용한다.
- `01A MongoDB Domain Metadata Loader.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_DOMAIN_COLLECTION`을 사용한다.
- `01B MongoDB Table Catalog Loader.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_TABLE_CATALOG_COLLECTION`을 사용한다.
- `01C MongoDB Main Variable Loader.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_MAIN_FLOW_FILTER_COLLECTION`을 사용한다.
- `01A~01C status_filter`: 기본 `active`. 전체 문서를 읽어야 할 때만 `all`로 바꾼다.
- `05 MongoDB Previous Result Loader.collection_name`과 `23 MongoDB Result Store.collection_name`: 비워두면 `MONGODB_RESULT_COLLECTION=agent_v4_result_store`를 사용한다.

## Rules

- intent prompt/answer prompt/pandas prompt는 컴포넌트 안에 넣지 않고 Langflow Prompt Template 노드에 둔다.
- LLM 실행은 custom component가 아니라 Langflow 기본 Agent/LLM 노드가 담당한다.
- `01A~01C`는 각각 `MONGODB_DATABASE=datagov`, `agent_v4_domain_items`, `agent_v4_table_catalog_items`, `agent_v4_main_flow_filters`의 `status=active` 문서를 제한 수량만 읽는다.
- `01D Metadata Candidates Builder`는 세 로더 출력을 `domain_items`, `table_catalog_items`, `main_flow_filters`로 결합하고, 이 결과만 `02 Intent Variables Builder.metadata_candidates_in`에 연결한다.
- `05 MongoDB Previous Result Loader`로 복원한 `runtime_sources`는 새 조회 결과가 없을 때 `13~14` 단계에서 유지된다.
- `23 MongoDB Result Store`는 기본적으로 `MONGODB_RESULT_COLLECTION=agent_v4_result_store`에 pandas 결과와 source rows를 저장하고 `data_ref`를 남긴다.
- retriever는 DA/WB/HBM/POP 같은 업무 용어를 직접 분기하지 않는다.
- source credential은 metadata가 아니라 환경변수/backend secret에서 읽는다.
- `runtime_sources`는 final API response에서 제거한다.
- pandas code는 `result` 변수를 만들어야 한다.
- pandas code는 import/open/eval/exec 같은 위험 동작을 사용할 수 없다.
