# Implementation Checkpoints

Date: 2026-07-01

이 문서는 구현 단위마다 핵심 지시사항 준수 여부를 확인하기 위한 작업 로그다.

## Checkpoint 1. Shared Runtime Contracts

Implemented:

- `pyproject.toml`
- `reference_runtime/__init__.py`
- `reference_runtime/contracts.py`

Instruction check:

- txt 원문 변경 없음: pass
- MongoDB write 없음: pass
- v4 독립 구현: pass
- 공정/제품 특화 hardcode 없음: pass

## Checkpoint 2. Metadata Storage Dry-Run Core

Implemented:

- `reference_runtime/metadata_authoring.py`
- `langflow_components/domain_authoring_flow/*_prompt_template_ko.md`
- `langflow_components/table_catalog_authoring_flow/*_prompt_template_ko.md`
- `langflow_components/main_flow_filters_authoring_flow/*_prompt_template_ko.md`
- `tools/metadata_authoring_dry_run.py`

Instruction check:

- default dry-run, MongoDB write 없음: pass
- review 전 write 차단: pass
- `duplicate_action=ask` 저장 차단: pass
- secret/token/password 저장 차단: pass
- SQL 축약 저장 차단: pass
- prompt 한국어 기반: pass
- txt 원문을 임의 JSON으로 직접 저장하지 않음: pass

Verification:

- `python -m pytest tests -q` -> 12 passed
- `python tools\metadata_authoring_dry_run.py --workspace .`
  - `written_to_mongodb=false`
  - domain blocks: 51
  - table catalog blocks: 42
  - main flow filter blocks: 6

## Checkpoint 3. Data Retriever Dummy-First Core

Implemented:

- `reference_runtime/dummy_data.py`
- `reference_runtime/retrieval.py`
- `langflow_components/data_analysis_flow/06_retrieval_job_validator.py`
- `langflow_components/data_analysis_flow/07_retrieval_job_router.py`
- `langflow_components/data_analysis_flow/08_dummy_data_retriever.py`
- `langflow_components/data_analysis_flow/09_oracle_query_retriever.py`
- `langflow_components/data_analysis_flow/10_h_api_retriever.py`
- `langflow_components/data_analysis_flow/11_datalake_retriever.py`
- `langflow_components/data_analysis_flow/12_goodocs_retriever.py`
- `langflow_components/data_analysis_flow/13_source_retrieval_merger.py`
- `langflow_components/data_analysis_flow/14_retrieval_payload_adapter.py`

Instruction check:

- retriever가 사용자 질문을 재해석하지 않음: pass
- 입력은 `intent_plan.retrieval_jobs`와 table catalog 계약: pass
- source credential 저장 없음: pass
- dummy mode에서도 source type 경계와 `used_dummy_data` trace 보존: pass
- final/API 응답 전 `22 API Response Builder`에서 `runtime_sources` 제거: pass
- DA/WB/HBM/POP 등 업무 단어 기반 adapter 분기 없음: pass

Verification:

- `python -m compileall -q reference_runtime tools tests` -> pass
- `python -m pytest tests -q` -> 12 passed

## Checkpoint 4. Langflow Metadata Storage Components

Implemented:

- domain authoring flow numbered components: `00`, `01`, `02`, `03`, `04`, `05`, `06`, `07`, `08`
- table catalog authoring flow numbered components: `00`, `01`, `02`, `03`, `04`, `05`, `06`, `07`, `08`
- main flow filter authoring flow numbered components: `00`, `01`, `02`, `03`, `04`, `05`, `06`, `07`, `08`
- connection guides for all three authoring flows

Instruction check:

- prompt templates are Korean-first: pass
- prompt bodies are kept in Langflow Prompt Template files, not embedded in custom components: pass
- LLM execution is delegated to Langflow Agent/LLM nodes in the connection guide: pass
- components are standalone and do not import project helpers: pass
- default behavior is dry-run: pass
- actual MongoDB writer is gated by `dry_run=false` plus explicit `mongo_uri`, `mongo_database`, and `collection_name`: pass
- actual write preserves `registration_trace.raw_text`: pass
- domain blocks `source_config` and query metadata: pass
- table catalog blocks truncated query templates: pass
- table catalog allows SQL line comments such as `--쿼리 작성`: pass
- table catalog allows `WITH` CTE query templates: pass
- main flow filter requires standard filter execution fields: pass

Verification:

- `python -m compileall -q reference_runtime tools tests langflow_components` -> pass
- `python -m pytest tests -q` -> 24 passed
- `python tools\metadata_authoring_dry_run.py --workspace .`
  - `written_to_mongodb=false`
  - domain blocks: 51
  - table catalog blocks: 14
  - main flow filter blocks: 6

## Checkpoint 5. Langflow Data Analysis Flow

Implemented:

- `langflow_components/data_analysis_flow/00_analysis_request_loader.py`
- `langflow_components/data_analysis_flow/03_intent_prompt_template_ko.md`
- `langflow_components/data_analysis_flow/02_intent_variables_builder.py`
- `langflow_components/data_analysis_flow/04_intent_plan_normalizer.py`
- `langflow_components/data_analysis_flow/06_retrieval_job_validator.py`
- `langflow_components/data_analysis_flow/07_retrieval_job_router.py`
- `langflow_components/data_analysis_flow/08_dummy_data_retriever.py`
- `langflow_components/data_analysis_flow/09_oracle_query_retriever.py`
- `langflow_components/data_analysis_flow/10_h_api_retriever.py`
- `langflow_components/data_analysis_flow/11_datalake_retriever.py`
- `langflow_components/data_analysis_flow/12_goodocs_retriever.py`
- `langflow_components/data_analysis_flow/13_source_retrieval_merger.py`
- `langflow_components/data_analysis_flow/14_retrieval_payload_adapter.py`
- `langflow_components/data_analysis_flow/15_pandas_variables_builder.py`
- `langflow_components/data_analysis_flow/16_pandas_prompt_template_ko.md`
- `langflow_components/data_analysis_flow/17_pandas_code_executor.py`
- `langflow_components/data_analysis_flow/18_answer_variables_builder.py`
- `langflow_components/data_analysis_flow/19_answer_prompt_template_ko.md`
- `langflow_components/data_analysis_flow/20_answer_response_builder.py`
- `langflow_components/data_analysis_flow/21_answer_message_adapter.py`
- `langflow_components/data_analysis_flow/22_api_response_builder.py`
- `langflow_components/data_analysis_flow/CONNECTION_GUIDE.md`

Instruction check:

- `의도분석 -> 데이터 조회 -> pandas code 실행 -> 답변/API response` flow exists: pass
- intent/pandas/answer prompt bodies are Korean-first Prompt Template files: pass
- LLM execution is delegated to Langflow Agent/LLM nodes: pass
- custom components only build variables, normalize LLM output, execute guarded pandas code, and shape responses: pass
- `runtime_sources` is removed from final API response: pass
- pandas executor blocks import/open/eval/exec and requires generated code to set `result`: pass
- live Oracle/H-API/Datalake/Goodocs adapters are implemented as environment-gated adapters; real external service validation is still environment-dependent: pending

Verification:

- `python -m compileall -q reference_runtime tools tests langflow_components` -> pass
- `python -m pytest tests -q` -> 25 passed
- dummy path integration test reaches API response with `status=ok`: pass

## Checkpoint 6. Korean-First Langflow Component Labels

Implemented:

- 모든 Langflow custom component의 `display_name`을 한글 기준으로 변경
- 모든 Langflow custom component의 `description`을 한글 기준으로 변경
- input/output port의 `display_name`도 한글 기준으로 변경
- 기술 식별자(`API`, `LLM`, `JSON`, `Oracle`, `Goodocs`, `MongoDB`, `pandas`)는 유지하되 한글 설명 문맥을 붙임

Instruction check:

- Langflow 화면에 보이는 컴포넌트 이름은 한글 기준: pass
- Langflow 화면에 보이는 컴포넌트 설명은 한글 기준: pass
- Langflow 화면에 보이는 input/output 포트명은 한글 기준: pass
- 내부 `name=` 값은 flow 연결 계약 보존을 위해 변경하지 않음: pass

Verification:

- `python -m compileall -q reference_runtime tools tests langflow_components` -> pass
- `python -m pytest tests -q` -> 25 passed
- `test_langflow_component_visible_labels_are_korean_first` 추가: pass

## Checkpoint 7. Direct Langflow `lfx` Imports

Implemented:

- 모든 Langflow custom component 파일에서 `try/except` 기반 local fallback class 제거
- `from lfx.custom.custom_component.component import Component` 직접 import로 통일
- 각 컴포넌트가 실제 사용하는 `DataInput`, `MessageTextInput`, `DropdownInput`, `Output`, `Data`, `Message`를 직접 import
- 로컬 테스트에서만 `lfx` test stub을 주입하도록 변경

Instruction check:

- 컴포넌트 파일 내부에 local `Component` fallback 없음: pass
- 컴포넌트 파일 내부에 local `DataInput`/`Output` fallback 없음: pass
- Langflow 런타임 기준 직접 import 방식 사용: pass
- 테스트용 stub은 `tests/test_langflow_components.py`에만 존재: pass

Verification:

- `python -m compileall -q reference_runtime tools tests langflow_components` -> pass
- `python -m pytest tests -q` -> 26 passed
- `test_langflow_components_use_direct_lfx_imports_without_fallback_stubs` 추가: pass

## Checkpoint 8. Unified Data Analysis Flow Folder

Implemented:

- 기존 조회 전용 폴더의 조회 컴포넌트를 `langflow_components/data_analysis_flow/`로 이동
- 별도 조회 전용 폴더 제거
- 테스트와 문서의 조회 컴포넌트 경로를 `data_analysis_flow` 단일 경로로 갱신
- `data_analysis_flow/CONNECTION_GUIDE.md`에 조회 단계 `07~15`를 통합 표기

Instruction check:

- data analysis와 data retrieval 컴포넌트가 하나의 Langflow flow 폴더에 있음: pass
- 별도 조회 전용 폴더 없음: pass
- custom component 내부 sibling import 없음: pass
- 기존 `intent -> retrieval -> pandas -> answer/API` 테스트 경로 유지: pass

Verification:

- `python -m compileall -q reference_runtime tools tests langflow_components` -> pass
- `python -m pytest tests -q` -> 26 passed
- old retrieval-only folder existence check -> `False`
