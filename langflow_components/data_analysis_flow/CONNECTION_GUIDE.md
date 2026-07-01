# Data Analysis Flow Connection Guide

이 flow는 `의도분석 -> 데이터 조회 -> pandas code 실행 -> 답변/API response`를 연결하는 skeleton이다. Prompt와 LLM/Agent 실행은 Langflow 기본 Prompt Template과 Agent/LLM 노드를 사용한다.

## Required Connections: Intent

| # | From node.output | To node.input |
| --- | --- | --- |
| 1 | `Chat Input.message` 또는 `Text Input.message` | `00 Analysis Request Loader.question` |
| 2 | optional previous state Data | `00 Analysis Request Loader.previous_state` |
| 3 | `04 MongoDB Metadata Loader.metadata_candidates` | `02 Intent Variables Builder.metadata_candidates` |
| 4 | `00 Analysis Request Loader.payload_out` | `02 Intent Variables Builder.payload` |
| 5 | `02 Intent Variables Builder.question` | `Langflow Prompt Template: 01_intent_prompt_template_ko.md.question` |
| 6 | `02 Intent Variables Builder.state_summary` | `Langflow Prompt Template: 01_intent_prompt_template_ko.md.state_summary` |
| 7 | `02 Intent Variables Builder.metadata_candidates` | `Langflow Prompt Template: 01_intent_prompt_template_ko.md.metadata_candidates` |
| 8 | `02 Intent Variables Builder.output_schema` | `Langflow Prompt Template: 01_intent_prompt_template_ko.md.output_schema` |
| 9 | `Langflow Prompt Template: 01_intent_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 10 | `00 Analysis Request Loader.payload_out` | `03 Intent Plan Normalizer.payload` |
| 11 | `Langflow Agent/LLM.output` | `03 Intent Plan Normalizer.llm_response` |

## Optional Previous Result Restore

이전 turn의 `data_ref`로 전체 rows를 복원해야 할 때만 넣는다. 필요 없으면 `03 Intent Plan Normalizer.payload_out`을 바로 `07 Retrieval Job Validator.payload`에 연결한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 12A | `03 Intent Plan Normalizer.payload_out` | `05 MongoDB Previous Result Loader.payload` |
| 12B | optional data ref text | `05 MongoDB Previous Result Loader.data_ref` |
| 12C | `05 MongoDB Previous Result Loader.payload_out` | `07 Retrieval Job Validator.payload` |

Skip restore path:

| From node.output | To node.input |
| --- | --- |
| `03 Intent Plan Normalizer.payload_out` | `07 Retrieval Job Validator.payload` |

## Required Connections: Retrieval

로컬 검증 기본값은 `RUN_LIVE_SOURCE_RETRIEVAL=false`이므로 더미 branch만 연결하는 것을 권장한다. live adapter는 현재 skeleton에서 명시적 미구현 오류를 반환한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 13 | `07 Retrieval Job Validator.payload_out` | `08 Retrieval Job Router.payload` |
| 14 | `07 Retrieval Job Validator.payload_out` | `14 Source Retrieval Merger.main_payload` |
| 15 | `08 Retrieval Job Router.dummy_jobs` | `09 Dummy Data Retriever.payload` |
| 16 | `09 Dummy Data Retriever.retrieval_payload` | `14 Source Retrieval Merger.dummy_retrieval` |
| 17 | `14 Source Retrieval Merger.payload_out` | `15 Retrieval Payload Adapter.payload` |

## Optional Live Retrieval Branches

아래 연결은 실제 live adapter를 구현하고 `RUN_LIVE_SOURCE_RETRIEVAL=true`일 때만 사용한다.

| From node.output | To node.input |
| --- | --- |
| `08 Retrieval Job Router.oracle_jobs` | `10 Oracle Query Retriever.payload` |
| `10 Oracle Query Retriever.retrieval_payload` | `14 Source Retrieval Merger.oracle_retrieval` |
| `08 Retrieval Job Router.h_api_jobs` | `11 H-API Retriever.payload` |
| `11 H-API Retriever.retrieval_payload` | `14 Source Retrieval Merger.h_api_retrieval` |
| `08 Retrieval Job Router.datalake_jobs` | `12 Datalake Retriever.payload` |
| `12 Datalake Retriever.retrieval_payload` | `14 Source Retrieval Merger.datalake_retrieval` |
| `08 Retrieval Job Router.goodocs_jobs` | `13 Goodocs Retriever.payload` |
| `13 Goodocs Retriever.retrieval_payload` | `14 Source Retrieval Merger.goodocs_retrieval` |

## Required Connections: Pandas

| # | From node.output | To node.input |
| --- | --- | --- |
| 18 | `15 Retrieval Payload Adapter.payload_out` | `16 Pandas Variables Builder.payload` |
| 19 | `16 Pandas Variables Builder.intent_plan_json` | `Langflow Prompt Template: 17_pandas_prompt_template_ko.md.intent_plan_json` |
| 20 | `16 Pandas Variables Builder.source_schema_json` | `Langflow Prompt Template: 17_pandas_prompt_template_ko.md.source_schema_json` |
| 21 | `16 Pandas Variables Builder.source_preview_json` | `Langflow Prompt Template: 17_pandas_prompt_template_ko.md.source_preview_json` |
| 22 | `16 Pandas Variables Builder.output_contract_json` | `Langflow Prompt Template: 17_pandas_prompt_template_ko.md.output_contract_json` |
| 23 | `Langflow Prompt Template: 17_pandas_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 24 | `15 Retrieval Payload Adapter.payload_out` | `18 Pandas Code Executor.payload` |
| 25 | `Langflow Agent/LLM.output` | `18 Pandas Code Executor.llm_response` |
| 26 | `18 Pandas Code Executor.payload_out` | `24 MongoDB Result Store.payload` |

If result store is not used:

| From node.output | To node.input |
| --- | --- |
| `18 Pandas Code Executor.payload_out` | `19 Answer Variables Builder.payload` |
| `18 Pandas Code Executor.payload_out` | `21 Answer Response Builder.payload` |

## Required Connections: Answer

Result store를 사용할 때는 아래처럼 `24 MongoDB Result Store.payload_out`을 기준으로 답변을 만든다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 27 | `24 MongoDB Result Store.payload_out` | `19 Answer Variables Builder.payload` |
| 28 | `19 Answer Variables Builder.question` | `Langflow Prompt Template: 20_answer_prompt_template_ko.md.question` |
| 29 | `19 Answer Variables Builder.result_summary_json` | `Langflow Prompt Template: 20_answer_prompt_template_ko.md.result_summary_json` |
| 30 | `19 Answer Variables Builder.applied_scope_json` | `Langflow Prompt Template: 20_answer_prompt_template_ko.md.applied_scope_json` |
| 31 | `19 Answer Variables Builder.warnings_errors_json` | `Langflow Prompt Template: 20_answer_prompt_template_ko.md.warnings_errors_json` |
| 32 | `Langflow Prompt Template: 20_answer_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 33 | `24 MongoDB Result Store.payload_out` | `21 Answer Response Builder.payload` |
| 34 | `Langflow Agent/LLM.output` | `21 Answer Response Builder.answer_text` |
| 35 | `21 Answer Response Builder.payload_out` | `22 Answer Message Adapter.payload` |
| 36 | `22 Answer Message Adapter.message` | `Chat Output.message` |

## Optional API Response

| From node.output | To node.input |
| --- | --- |
| `21 Answer Response Builder.payload_out` | `23 API Response Builder.payload` |
| `23 API Response Builder.api_response` | downstream API/Data output |

## Fixed/Manual Inputs

- `00 Analysis Request Loader.session_id`: 세션 식별자가 있으면 입력한다. 비워두면 `demo-session`.
- `00 Analysis Request Loader.reference_date`: 기준일이 필요한 검증에서 `YYYYMMDD` 등으로 입력한다.
- `00 Analysis Request Loader.timezone`: 기본 `Asia/Seoul`.
- `04 MongoDB Metadata Loader.mongo_uri`, `mongo_database`, collection inputs: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_DOMAIN_COLLECTION`, `MONGODB_TABLE_CATALOG_COLLECTION`, `MONGODB_MAIN_FLOW_FILTER_COLLECTION`을 사용한다.
- `04 MongoDB Metadata Loader.status_filter`: 기본 `active`.
- `05 MongoDB Previous Result Loader.collection_name`과 `24 MongoDB Result Store.collection_name`: 비워두면 `MONGODB_RESULT_COLLECTION=agent_v4_result_store`를 사용한다.

## Rules

- intent prompt/answer prompt/pandas prompt는 컴포넌트 안에 넣지 않고 Langflow Prompt Template 노드에 둔다.
- LLM 실행은 custom component가 아니라 Langflow 기본 Agent/LLM 노드가 담당한다.
- `04 MongoDB Metadata Loader`는 기본적으로 `MONGODB_DATABASE=datagov`, `agent_v4_domain_items`, `agent_v4_table_catalog_items`, `agent_v4_main_flow_filters`의 `status=active` 문서를 제한 수량만 읽는다.
- `05 MongoDB Previous Result Loader`로 복원한 `runtime_sources`는 새 조회 결과가 없을 때 `14~15` 단계에서 유지된다.
- `24 MongoDB Result Store`는 기본적으로 `MONGODB_RESULT_COLLECTION=agent_v4_result_store`에 pandas 결과와 source rows를 저장하고 `data_ref`를 남긴다.
- retriever는 DA/WB/HBM/POP 같은 업무 용어를 직접 분기하지 않는다.
- source credential은 metadata가 아니라 환경변수/backend secret에서 읽는다.
- `runtime_sources`는 final API response에서 제거한다.
- pandas code는 `result` 변수를 만들어야 한다.
- pandas code는 import/open/eval/exec 같은 위험 동작을 사용할 수 없다.
