# Domain Authoring Flow Connection Guide

이 flow는 domain metadata를 자연어로 등록하기 위한 Langflow flow다. 기본 동작은 dry-run이다. 실제 MongoDB 저장은 `dry_run=false`이고 `MONGODB_URI`가 있으면 실행된다. 데이터베이스와 컬렉션은 입력값이 없을 때 `MONGODB_DATABASE=datagov`, `MONGODB_DOMAIN_COLLECTION=agent_v4_domain_items`를 기본값으로 사용한다.

## Required Connections

아래 표의 `output -> input`을 그대로 연결한다. Langflow 기본 Prompt Template/Agent 노드는 사용 중인 Langflow 버전에 따라 포트 표시명이 조금 다를 수 있으나, 연결 의미는 `Prompt Template output -> Agent/LLM prompt/input`, `Agent/LLM message/text output -> 다음 component llm_response`다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 1 | `Text Input.message` 또는 `Chat Input.message` | `00 Domain Authoring Request Loader.raw_text` |
| 2 | `00 Domain Existing Items Loader.existing_items` | `00 Domain Authoring Request Loader.existing_items` |
| 3 | `00 Domain Authoring Request Loader.payload_out` | `01 Domain Text Refinement Variables Builder.payload` |
| 4 | `01 Domain Text Refinement Variables Builder.raw_text` | `Langflow Prompt Template: 01_text_refinement_prompt_template_ko.md.raw_text` |
| 5 | `Langflow Prompt Template: 01_text_refinement_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 6 | `00 Domain Authoring Request Loader.payload_out` | `02 Domain Text Refinement Normalizer.payload` |
| 7 | `Langflow Agent/LLM.output` | `02 Domain Text Refinement Normalizer.llm_response` |
| 8 | `02 Domain Text Refinement Normalizer.payload_out` | `03 Domain Authoring Variables Builder.payload` |
| 9 | `03 Domain Authoring Variables Builder.refined_text` | `Langflow Prompt Template: 03_authoring_prompt_template_ko.md.refined_text` |
| 10 | `03 Domain Authoring Variables Builder.existing_metadata_summary` | `Langflow Prompt Template: 03_authoring_prompt_template_ko.md.existing_metadata_summary` |
| 11 | `Langflow Prompt Template: 03_authoring_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 12 | `02 Domain Text Refinement Normalizer.payload_out` | `04 Domain Authoring Result Normalizer.payload` |
| 13 | `Langflow Agent/LLM.output` | `04 Domain Authoring Result Normalizer.llm_response` |
| 14 | `04 Domain Authoring Result Normalizer.payload_out` | `05 Domain Similarity Checker.payload` |
| 15 | `05 Domain Similarity Checker.payload_out` | `06 Domain Review Variables Builder.payload` |
| 16 | `06 Domain Review Variables Builder.review_input_json` | `Langflow Prompt Template: 06_review_prompt_template_ko.md.review_input_json` |
| 17 | `Langflow Prompt Template: 06_review_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 18 | `05 Domain Similarity Checker.payload_out` | `07 Domain Review Writer.payload` |
| 19 | `Langflow Agent/LLM.output` | `07 Domain Review Writer.review_response` |
| 20 | `07 Domain Review Writer.payload_out` | `08 Domain Authoring Response Builder.payload` |
| 21 | `08 Domain Authoring Response Builder.message` | `Chat Output.message` |

## Optional Connections

| From node.output | To node.input | When to use |
| --- | --- | --- |
| `00 Domain Existing Items Loader.existing_items` | `05 Domain Similarity Checker.existing_items` | 중복 검사를 명시적으로 연결하고 싶을 때 사용한다. 2번 연결을 했다면 payload에 기존 항목이 포함되므로 필수는 아니다. |
| `08 Domain Authoring Response Builder.api_response` | downstream API/Data output | Web/API에서 구조화 응답을 받을 때 사용한다. |

## Fixed/Manual Inputs

- `00 Domain Authoring Request Loader.duplicate_action`: 기본은 `ask`. 중복 처리 재실행 때 `merge`, `replace`, `skip`, `create_new` 중 하나로 바꾼다.
- `00 Domain Authoring Request Loader.dry_run`: 실제 저장 전에는 `true`, 검수 후 저장할 때만 `false`.
- `00 Domain Existing Items Loader.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_DOMAIN_COLLECTION`을 사용한다.
- `07 Domain Review Writer.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 같은 env 기본값을 사용한다.

## Rules

- `raw_text` 원문은 임의로 JSON 변환해 직접 저장하지 않는다.
- `review` 전에는 writer가 저장 성공을 만들지 않는다.
- `duplicate_action=ask` 상태에서 같은 key가 있으면 저장하지 않는다.
- domain item에는 `source_config`, SQL, API endpoint, credential을 넣지 않는다.
- 프롬프트 본문은 custom component 안에 넣지 않고 Langflow Prompt Template 노드에 둔다.
- LLM 실행은 custom component가 아니라 Langflow 기본 Agent/LLM 노드가 담당한다.
- 실제 저장 시 `registration_trace.raw_text`로 원문을 보존한다.
