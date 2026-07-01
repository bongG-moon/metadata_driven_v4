# Table Catalog Authoring Flow Connection Guide

이 flow는 dataset/source/table catalog metadata를 자연어로 등록하기 위한 Langflow flow다. 기본 동작은 dry-run이다. 실제 MongoDB 저장은 `dry_run=false`이고 `MONGODB_URI`가 있으면 실행된다. 데이터베이스와 컬렉션은 입력값이 없을 때 `MONGODB_DATABASE=datagov`, `MONGODB_TABLE_CATALOG_COLLECTION=agent_v4_table_catalog_items`를 기본값으로 사용한다.

## Required Connections

| # | From node.output | To node.input |
| --- | --- | --- |
| 1 | `Text Input.message` 또는 `Chat Input.message` | `00 Table Catalog Authoring Request Loader.raw_text` |
| 2 | `00 Table Catalog Existing Items Loader.existing_items` | `00 Table Catalog Authoring Request Loader.existing_items` |
| 3 | `00 Table Catalog Authoring Request Loader.payload_out` | `01 Table Catalog Text Refinement Variables Builder.payload` |
| 4 | `01 Table Catalog Text Refinement Variables Builder.raw_text` | `Langflow Prompt Template: 01_text_refinement_prompt_template_ko.md.raw_text` |
| 5 | `Langflow Prompt Template: 01_text_refinement_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 6 | `00 Table Catalog Authoring Request Loader.payload_out` | `02 Table Catalog Text Refinement Normalizer.payload` |
| 7 | `Langflow Agent/LLM.output` | `02 Table Catalog Text Refinement Normalizer.llm_response` |
| 8 | `02 Table Catalog Text Refinement Normalizer.payload_out` | `03 Table Catalog Authoring Variables Builder.payload` |
| 9 | `03 Table Catalog Authoring Variables Builder.refined_text` | `Langflow Prompt Template: 03_authoring_prompt_template_ko.md.refined_text` |
| 10 | `03 Table Catalog Authoring Variables Builder.existing_metadata_summary` | `Langflow Prompt Template: 03_authoring_prompt_template_ko.md.existing_metadata_summary` |
| 11 | `Langflow Prompt Template: 03_authoring_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 12 | `02 Table Catalog Text Refinement Normalizer.payload_out` | `04 Table Catalog Authoring Result Normalizer.payload` |
| 13 | `Langflow Agent/LLM.output` | `04 Table Catalog Authoring Result Normalizer.llm_response` |
| 14 | `04 Table Catalog Authoring Result Normalizer.payload_out` | `05 Table Catalog Similarity Checker.payload` |
| 15 | `05 Table Catalog Similarity Checker.payload_out` | `06 Table Catalog Review Variables Builder.payload` |
| 16 | `06 Table Catalog Review Variables Builder.review_input_json` | `Langflow Prompt Template: 06_review_prompt_template_ko.md.review_input_json` |
| 17 | `Langflow Prompt Template: 06_review_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 18 | `05 Table Catalog Similarity Checker.payload_out` | `07 Table Catalog Review Writer.payload` |
| 19 | `Langflow Agent/LLM.output` | `07 Table Catalog Review Writer.review_response` |
| 20 | `07 Table Catalog Review Writer.payload_out` | `08 Table Catalog Authoring Response Builder.payload` |
| 21 | `08 Table Catalog Authoring Response Builder.message` | `Chat Output.message` |

## Optional Connections

| From node.output | To node.input | When to use |
| --- | --- | --- |
| `00 Table Catalog Existing Items Loader.existing_items` | `05 Table Catalog Similarity Checker.existing_items` | 중복 검사를 명시적으로 연결하고 싶을 때 사용한다. 2번 연결을 했다면 payload에 기존 항목이 포함되므로 필수는 아니다. |
| `08 Table Catalog Authoring Response Builder.api_response` | downstream API/Data output | Web/API에서 구조화 응답을 받을 때 사용한다. |

## Fixed/Manual Inputs

- `00 Table Catalog Authoring Request Loader.duplicate_action`: 기본은 `ask`. 중복 처리 재실행 때 `merge`, `replace`, `skip`, `create_new` 중 하나로 바꾼다.
- `00 Table Catalog Authoring Request Loader.dry_run`: 실제 저장 전에는 `true`, 검수 후 저장할 때만 `false`.
- `00 Table Catalog Existing Items Loader.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_TABLE_CATALOG_COLLECTION`을 사용한다.
- `07 Table Catalog Review Writer.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 같은 env 기본값을 사용한다.

## Rules

- SQL `query_template`은 원문 그대로 보존한다.
- `...`, `생략`, `omitted`, `truncated`로 축약된 query는 저장하지 않는다.
- credential, token, password는 metadata에 저장하지 않는다.
- `filter_mappings` 왼쪽은 표준 filter key, 오른쪽은 실제 source column이다.
- `equipment_assign` vs `equipment_status` 같은 dataset naming 차이는 조용히 변경하지 않고 review에서 드러낸다.
- 프롬프트 본문은 custom component 안에 넣지 않고 Langflow Prompt Template 노드에 둔다.
- LLM 실행은 custom component가 아니라 Langflow 기본 Agent/LLM 노드가 담당한다.
- 실제 저장 시 `registration_trace.raw_text`로 원문을 보존한다.
