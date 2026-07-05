# Data Retriever And Metadata Storage Flow Design

Date: 2026-07-01
Target workspace: `C:\Users\qkekt\Desktop\meta_driven_v4`

이 문서는 먼저 구현할 두 영역만 상세 설계한다.

1. `data retriever flow`: 확정된 `intent_plan.retrieval_jobs`를 source별로 실행하고 pandas 실행용 payload를 만든다.
2. `metadata 저장 flow`: 자연어 metadata 입력을 review 가능한 후보로 만들고, review/duplicate 결정을 통과한 경우에만 MongoDB에 저장한다.

`metadata_driven_v3`는 참고 자산이다. 구현 기준은 이 workspace의 `docs`와 루트 txt 입력이다.

## 0. Non-Negotiable Rules

- `domain_knowledge.txt`, `data_catalog.txt`, `main_variable.txt` 원문을 임의로 hand-edit JSON으로 바꿔 MongoDB에 직접 저장하지 않는다.
- txt 입력은 saving flow의 `raw_text` 입력이다. 구조화는 `refine -> saving JSON -> normalizer -> duplicate/similarity -> review -> writer`를 통과해야 한다.
- 등록 당시 원문 보존이 필요하면 MongoDB 문서에 `registration_trace.raw_text` 또는 별도 audit record로 남긴다. 단 main runtime loader가 읽는 핵심 metadata shape는 lean하게 유지한다.
- `data retriever flow`는 사용자 질문을 다시 해석하지 않는다. 입력은 `intent_plan.retrieval_jobs`와 selected table catalog 계약이다.
- source credential, token, password, MongoDB URI는 metadata에 저장하지 않는다. env/backend secret store에서만 읽는다.
- 공정/제품/수량 특화 조건은 common retriever code에 박지 않는다. 표준 filter key와 table catalog mapping으로만 적용한다.
- `D/A1`, `W/B2`, `HBM`, `POP`, `MOBILE` 같은 업무 단어가 retriever adapter 안에서 직접 분기되면 설계 실패다.
- `duplicate_action=ask`, review failure, missing required field는 저장 성공으로 위장하지 않는다.

## 1. Data Retriever Flow

### 1.1 Role Boundary

Data retriever flow의 책임:

- `intent_plan.retrieval_jobs`의 source job validation
- dataset별 table catalog 계약 확인
- source type별 adapter dispatch
- source별 raw result를 표준 `source_results[]`로 normalize
- pandas execution 직전 `runtime_sources` 구성
- `trace.inspection.data_retrieval` 작성

Data retriever flow가 하지 않는 일:

- 사용자 질문 재분석
- DA/WB/HBM 같은 domain alias 해석
- 제품 조건을 새로 추론
- pandas join/filter/group/metric 실행
- answer text 작성
- full metadata collection 전달

### 1.2 Input Contract

Data retriever는 data analysis flow 중간 stage다. 입력 payload는 아래 key를 기준으로 한다.

```json
{
  "request": {
    "session_id": "session-001",
    "question": "오늘 DA공정 재공 수량 알려줘",
    "reference_date": "2026-07-01"
  },
  "state": {},
  "metadata_refs": [
    "domain_items:process_groups:DA",
    "table_catalog:wip_today"
  ],
  "intent_plan": {
    "analysis_kind": "current_wip_quantity",
    "retrieval_jobs": [],
    "pandas_execution_plan": []
  },
  "trace": {
    "metadata_evidence": [],
    "warnings": [],
    "errors": [],
    "inspection": {}
  }
}
```

`Intent Plan Normalizer`가 만든 retrieval job은 retriever가 실행 가능한 형태여야 한다.

```json
{
  "job_id": "job_wip_today_1",
  "source_alias": "wip_data",
  "dataset_key": "wip_today",
  "dataset_family": "wip",
  "source_type": "oracle",
  "status": "ready",
  "required_params": {
    "DATE": "20260701"
  },
  "filters": {
    "OPER_NAME": {
      "operator": "in",
      "values": ["D/A1", "D/A2", "D/A3", "D/A4", "D/A5", "D/A6"],
      "source": "domain_items:process_groups:DA"
    }
  },
  "expected_columns": ["WORK_DATE", "OPER_NAME", "WIP"],
  "row_limit": 5000,
  "result_mode": "rows"
}
```

Job 생성 원칙:

- `dataset_key`, `source_alias`, `source_type`은 필수다.
- `source_type`은 table catalog의 값과 같아야 한다.
- 필수 조회 조건은 table catalog/source_config의 required param 정의를 기준으로 `required_params`에 넣는다. date가 필수인 source는 `DATE`가 들어가지만, source별로 필수 param은 달라질 수 있다.
- 공정, 제품, 상태, 장비, LOT 등 필수 param이 아닌 분석 조건은 `filters`에 넣고 pandas 전처리에서 적용한다.
- table catalog의 `filter_mappings` 왼쪽 key는 표준 filter key, 오른쪽 값은 실제 source column이다.
- `D/A1`처럼 단일 공정으로 확정된 값과 `DA` 그룹 확장값을 구분할 수 있도록 `filters.*.source` 또는 `trace.metadata_evidence`를 남긴다.
- missing required param이 있으면 adapter가 임의 default를 만들지 않고 `status=error` 또는 clarification path로 넘긴다.

### 1.3 Output Contract

Retriever 완료 후 main payload에는 compact trace와 pandas용 rows만 남긴다.

```json
{
  "source_results": [
    {
      "source_alias": "wip_data",
      "dataset_key": "wip_today",
      "source_type": "oracle",
      "status": "ok",
      "row_count": 120,
      "columns": ["WORK_DATE", "OPER_NAME", "WIP"],
      "preview_rows": [],
      "applied_params": {"DATE": "20260701"},
      "pandas_filters": {"OPER_NAME": ["D/A1", "D/A2"]},
      "data_ref": "",
      "source_execution": {
        "used_dummy_data": false,
        "filters_applied_in_retriever": false,
        "elapsed_ms": 0
      },
      "warnings": [],
      "errors": []
    }
  ],
  "runtime_sources": {
    "wip_data": []
  },
  "trace": {
    "inspection": {
      "data_retrieval": {}
    }
  }
}
```

Output rules:

- `source_results[].preview_rows`는 최대 20 rows.
- `runtime_sources`는 pandas executor 전후까지만 유지하고 final API/session에는 남기지 않는다.
- rows가 커지면 result store에 저장하고 `data_ref`를 남긴다.
- skipped source branch는 merger 이후 남기지 않는다. 단 debugging용 skipped summary는 `trace.inspection.data_retrieval.skipped_sources`에 compact하게 둘 수 있다.
- adapter error는 selected subflow 성공처럼 위장하지 않는다.

### 1.4 Node Design

권장 flow:

```text
06 Previous Result Restore Merger
-> 06 Retrieval Job Validator
-> 07 Retrieval Job Router
-> 08 Dummy Data Retriever
-> 09 Oracle Query Retriever
-> 10 H-API Retriever
-> 11 Datalake Retriever
-> 12 Goodocs Retriever
-> 13 Source Retrieval Merger
-> 14 Retrieval Payload Adapter
```

번호는 구현 중 조정 가능하지만 책임 경계는 유지한다.

| Node | Input | Output | Responsibility | Must Not Do |
| --- | --- | --- | --- | --- |
| `06 Retrieval Job Validator` | payload | payload_out | `retrieval_jobs` shape, required fields, source type allowlist, row limit 검증 | 질문 재분석, missing param 임의 생성 |
| `07 Retrieval Job Router` | payload | source별 job bundle | source type별 job 분리, no-job source는 skipped | source 실행, filter materialization |
| `08 Dummy Data Retriever` | payload/jobs | retrieval_payload | deterministic fixture로 실제 source shape 검증 | sample JSON을 운영 source로 취급 |
| `09 Oracle Query Retriever` | payload/jobs + env config | retrieval_payload | Oracle query template 실행, filter/param 적용 | credential metadata 저장, LLM SQL 생성 |
| `10 H-API Retriever` | payload/jobs + token | retrieval_payload | endpoint/request body 실행, timeout/error mapping | question 기반 endpoint 선택 |
| `11 Datalake Retriever` | payload/jobs + lake env | retrieval_payload | lake query 실행과 result 수집 | local hardcoded process branch |
| `12 Goodocs Retriever` | payload/jobs + module/token | retrieval_payload | doc/sheet rows 조회, column mapping | 계획 데이터 날짜 형식 임의 변경 |
| `13 Source Retrieval Merger` | source retrieval payloads | payload_out | ok/error source 결과 병합, skipped 제거, inspection 작성 | pandas 분석 실행 |
| `14 Retrieval Payload Adapter` | payload_out | payload_out | pandas용 `runtime_sources` dict와 compact `source_results` 구성 | final answer 작성, full rows 중복 저장 |

### 1.5 Adapter Contract

모든 source adapter는 같은 top-level shape를 반환한다.

```json
{
  "source_type": "oracle",
  "status": "ok",
  "executed_jobs": [],
  "skipped": false,
  "source_results": [],
  "warnings": [],
  "errors": []
}
```

No matching jobs일 때:

```json
{
  "source_type": "oracle",
  "status": "skipped",
  "skipped": true,
  "skip_reason": "no oracle retrieval jobs",
  "source_results": []
}
```

Error일 때:

```json
{
  "source_type": "oracle",
  "status": "error",
  "skipped": false,
  "source_results": [
    {
      "source_alias": "wip_data",
      "dataset_key": "wip_today",
      "status": "error",
      "errors": [
        {
          "type": "missing_required_param",
          "message": "DATE is required for wip_today"
        }
      ]
    }
  ]
}
```

### 1.6 Source-Specific Design

#### Dummy

- 기본 local/regression source다.
- `RUN_LIVE_SOURCE_RETRIEVAL=false`일 때 모든 source type job을 dummy rows로 처리할 수 있다.
- dummy rows는 실제 table catalog의 columns/filter mapping을 검증할 수 있어야 한다.
- fixture는 `dataset_key`별로 생성하되, runtime은 `source_type`, `source_config`, `used_dummy_data=true`를 trace에 남긴다.

#### Oracle

- metadata에는 `db_key`, `query_template`, `filter_mappings`, `required_params`, `date_format`만 둔다.
- 실제 credential은 `ORACLE_CONFIG_JSON`의 `db_key`로 찾는다.
- LLM이 SQL을 만들지 않는다. SQL은 table catalog의 `source_config.query_template`만 사용한다.
- `{DATE}`, `{LOT_ID}` 같은 placeholder는 required/applied params에서만 채운다.
- 추가 filters는 table catalog의 `filter_mappings`로 실제 column을 찾은 뒤 allowlisted condition builder로 붙인다.
- `query_template`이 `...`, `생략`, `omitted`, `truncated`면 metadata 저장 단계에서 막아야 하며, retriever에서도 blocker로 본다.
- `data_catalog.txt`의 오타 의심 mapping, 예: `EQP_MODEL -> EQPIP_MODEL`, 은 adapter가 조용히 고치지 않는다. authoring review warning 또는 validation failure로 드러내야 한다.

#### H-API

- metadata에는 endpoint id, method, required params, request schema, response schema 정도만 둔다.
- token은 env/backend secret에서 읽는다.
- timeout, 4xx/5xx, invalid JSON은 `source_results[].status=error`로 남긴다.
- response rows는 table catalog의 `standard_column_aliases`를 통해 표준 컬럼 view를 만든다.

#### Datalake

- metadata에는 query/notebook/cluster path 또는 query template, required params, expected columns만 둔다.
- user id/token/S3 key는 env에서만 읽는다.
- 긴 실행은 timeout을 명시하고, partial/timeout은 source error로 남긴다.
- Datalake adapter도 질문을 해석하지 않고 job의 dataset/query contract만 실행한다.

#### Goodocs

- metadata에는 `doc_id`, sheet/range/table name, required columns, date format을 둔다.
- Goodocs credential/module은 env에서만 읽는다.
- `target`처럼 `YYYY-MM-DD` 날짜를 쓰는 source는 job materialization 단계에서 source별 date format을 분리한다.
- plan/target 컬럼은 `INPUT_PLAN`, `OUT_PLAN` 같은 standard aliases를 반드시 제공해야 pandas 단계가 안정적이다.

### 1.7 Filter And Column Materialization

Materialization 순서:

1. `job.required_params`를 table catalog의 `required_param_mappings`로 실제 source parameter/column에 연결하고 retriever에서 적용한다.
2. `job.filters`의 표준 key를 table catalog `filter_mappings`로 실제 column list에 연결하되, retriever에서 row filter로 적용하지 않고 pandas 단계로 넘긴다.
3. 실제 rows를 받은 뒤 `standard_column_aliases`로 pandas 표준 컬럼 view를 만든다.
4. `source_results[].pandas_filters`에는 pandas 전처리에서 적용할 표준 key 기준과 실제 source column 기준을 함께 남긴다.

권장 trace:

```json
{
  "pandas_filters": {
    "standard": {"OPER_NAME": ["D/A1", "D/A2"]},
    "physical": {"OPER_NAME": ["D/A1", "D/A2"]}
  },
  "column_aliases_applied": {
    "DEN": "DENSITY",
    "PKG_TYPE1": "PKG1"
  }
}
```

### 1.8 Retrieval Inspection

`trace.inspection.data_retrieval`는 운영자가 source 실행 여부를 바로 볼 수 있어야 한다.

필수 내용:

- executed job count
- source별 status
- dataset/source type/source alias
- required params vs applied params
- standard filters vs physical filters
- columns and row count
- preview rows/ref
- skipped reason
- error type/message
- `used_dummy_data`

### 1.9 Data Retriever Validation

Local tests:

- no matching source type은 skipped 후 merger에서 제거된다.
- missing `dataset_key`, `source_alias`, `source_type`은 validation error다.
- `wip_today` job은 WIP columns와 DATE param을 요구한다.
- `target` Goodocs job은 `YYYY-MM-DD` date format을 보존한다.
- source별 date scope가 섞이지 않는다.
- `D/A1`은 DA group으로 확장되지 않는다.
- `RUN_LIVE_SOURCE_RETRIEVAL=false`에서도 `source_type` 경계와 applied filters는 검증된다.
- adapter error가 final success로 위장되지 않는다.
- final API/session에는 `runtime_sources`가 남지 않는다.

## 2. Metadata Storage Flows

### 2.1 Flow Scope

Metadata 저장 flow는 세 종류다.

| Flow | Input file/source | Mongo key | Stores |
| --- | --- | --- | --- |
| `domain_saving_flow` | `domain_knowledge.txt` blocks | `section + key` | process groups, product terms, quantity/metric/status terms, recipes, function-case drafts |
| `table_catalog_saving_flow` | `data_catalog.txt` blocks | `dataset_key` | dataset family, source type/config, query/API contract, filter/column mapping |
| `main_flow_filters_saving_flow` | `main_variable.txt` blocks | `filter_key` | DATE, OPER_NAME, product/equipment/lot standard filter concepts |

운영 UI는 세 flow를 그대로 노출하지 않는다. 사용자는 하나의 metadata 등록 화면에 자연어를 넣고, backend/router가 target flow를 선택한다.

### 2.2 Recommended MongoDB Names

현재 문서에는 v3 이름이 남아 있다. v4 구현에서는 v3 collection을 실수로 덮어쓰지 않도록 `.env`에서 명확히 분리한다.

권장 기본값:

```dotenv
MONGODB_DATABASE=datagov
MONGODB_DOMAIN_COLLECTION=agent_v4_domain_items
MONGODB_TABLE_CATALOG_COLLECTION=agent_v4_table_catalog_items
MONGODB_MAIN_FLOW_FILTER_COLLECTION=agent_v4_main_flow_filters
MONGODB_RESULT_COLLECTION=agent_v4_result_store
```

실제 구현 기본값도 위 이름을 따른다. writer/loader는 prefix 조합이 아니라 full collection name을 입력받고, 입력이 비어 있으면 같은 환경변수를 사용한다.

### 2.3 Common Saving Flow

권장 flow:

```text
00 Saving Request Loader
-> 01 Existing Metadata Loader
-> 02 Text Refinement Variables Builder
-> Text Refinement LLM
-> 03 Text Refinement Normalizer
-> 04 Saving Variables Builder
-> Authoring JSON LLM
-> 05 Saving Result Normalizer
-> 06 Duplicate/Similarity Checker
-> 07 Review Variables Builder
-> Review LLM
-> 08 Review Writer
-> 09 Saving Response Builder
```

### 2.4 Common Payload

```json
{
  "metadata_type": "domain",
  "request": {
    "raw_text": "",
    "duplicate_action": "ask",
    "operator_id": "",
    "dry_run": false
  },
  "refinement": {
    "refined_text": "",
    "needs_more_input": false,
    "missing_information": [],
    "assumptions": []
  },
  "items": [],
  "existing_matches": [],
  "conflict_warnings": [],
  "duplicate_decision": {
    "action": "ask",
    "target_key": ""
  },
  "review": {},
  "write_result": {},
  "trace": {
    "raw_text_preview": "",
    "generated_items_preview": []
  },
  "errors": [],
  "warnings": []
}
```

Payload rules:

- prompt 전문을 downstream payload에 남기지 않는다.
- existing metadata full collection을 prompt에 넣지 않는다.
- `existing_matches`는 관련 후보만 둔다.
- final user response에는 internal JSON보다 저장 여부/부족 정보/중복 선택지를 보여준다.

### 2.5 Node Details

| Node | Responsibility | Key Rejects |
| --- | --- | --- |
| `00 Saving Request Loader` | raw text, metadata type, duplicate action, dry-run flag 정리 | raw text empty, unknown metadata type |
| `01 Existing Metadata Loader` | existing item summary load for duplicate check | full collection prompt dump |
| `02 Text Refinement Variables Builder` | refinement prompt variables 구성 | schema 강제 과다 주입 |
| `03 Text Refinement Normalizer` | refined text, missing info, assumptions 추출 | LLM prose only without parseable structure |
| `04 Saving Variables Builder` | authoring context 구성 | unrelated metadata 전체 포함 |
| `05 Saving Result Normalizer` | candidate item list 정규화 | invented physical columns/query, unsupported section/source type |
| `06 Duplicate/Similarity Checker` | same key/alias/condition/source collision 탐지 | conflict 무시하고 writer 직행 |
| `07 Review Variables Builder` | review input JSON 구성 | full prompt/secret 포함 |
| `08 Review Writer` | review normalize, duplicate decision 적용, MongoDB upsert | review fail, duplicate ask, secret, missing required |
| `09 Saving Response Builder` | Korean result message/API response 생성 | 저장하지 않았는데 저장 성공 메시지 |

### 2.6 Domain Saving Flow

Allowed sections:

- `process_groups`
- `product_terms`
- `quantity_terms`
- `metric_terms`
- `analysis_recipes`
- `status_terms`
- `product_key_columns`
- `pandas_function_cases`

Domain writer required fields:

- `section`
- `key`
- `payload`
- allowed section

Domain-specific rules:

- SQL/query/API/source credential은 domain에 저장하지 않는다.
- 공정 그룹은 aliases와 실제 filter values를 보존한다.
- 제품 조건은 원문 조건을 임의 완화/강화하지 않는다.
- POP/MOBILE/HBM 같은 product terms는 사용자가 명시했거나 metadata matching이 명확할 때만 runtime에서 적용되도록 저장한다.
- `pandas_function_cases`는 draft로 저장하고, active 승격은 개발자 검토와 실행 테스트 이후에만 한다.
- 제품 token lookup 규칙은 일반 product term으로 과잉 변환하지 않는다. 원문이 function case라고 말하면 function-case draft로 둔다.

Domain examples from current raw input:

- process groups: DP, WET, DA, WB, FCB, BM, etc.
- analysis recipes: 공정 차수 표현, 공정 구간 OPER_SEQ range, BOH/EOH date rule, product key join rule.
- product terms: POP, MOBILE, AUTO, HBM/3DS/TSV, 2Hi/4Hi/8Hi.
- quantity/metric terms: WIP, PRODUCTION, INPUT, target, equipment count, wafer out, achievement rate.

주의:

- "예시는 규칙 설명을 위한 예시"라고 적힌 블록은 예시 공정을 별도 process group item으로 저장하지 않는다.
- BOH rule처럼 요청 기준일과 실제 조회 DATE가 다른 규칙은 `analysis_recipes` 또는 date-scope rule로 보존한다.

### 2.7 Table Catalog Saving Flow

Table catalog writer required fields:

- `dataset_key`
- `payload.source_type`
- `payload.source_config`
- source별 최소 정보
- `required_param_mappings` when required params exist
- `filter_mappings` when filters can be applied

Source-specific required fields:

| Source | Required |
| --- | --- |
| `oracle` | `source_config.db_key`, `source_config.query_template` |
| `goodocs` | `source_config.doc_id`, columns or expected sheet schema |
| `h_api` | endpoint/api id, method/request schema, response schema |
| `datalake` | query/notebook path or query template, execution config refs |
| `dummy` | fixture shape/generator rule |

Table-specific rules:

- SQL 원문은 보존한다. LLM이 `...`로 줄이면 저장하지 않는다.
- table catalog에는 credential을 넣지 않는다.
- `filter_mappings` 왼쪽은 standard filter key, 오른쪽은 physical source column이다.
- `standard_column_aliases`는 pandas 표준 컬럼 view를 만들기 위해 적극적으로 둔다.
- `data_catalog.txt`에 오타 또는 불일치가 있으면 review warning으로 드러낸다. writer가 조용히 보정하지 않는다.
- Goodocs `target`의 date format `YYYY-MM-DD`는 `production/wip`의 `YYYYMMDD`와 섞지 않는다.

Current raw dataset candidates:

- `production_today` / Oracle / `PROD_TABLE`
- `production` / Oracle / `PROD_TABLE2`
- `wip_today` / Oracle / `WIP_TABLE`
- `wip` / Oracle / `WIP_TABLE2`
- `target` / Goodocs / doc id `1212121212121212121212`
- `equipment_assign` or `equipment_status` / Oracle / `EQP_TABLE`
- `eqp_uph` / Oracle / `UPH`
- `lot_status` / Oracle / `WIP_STATE`
- `hold_history` / Oracle / `HOLD_HIS`

Naming decision needed:

- docs validation uses `equipment_status`, while current `data_catalog.txt` says `equipment_assign`.
- Do not silently rename. Authoring review should surface this as either alias/display name decision or dataset_key replacement decision.

### 2.8 Main Flow Filters Saving Flow

Main filter writer required fields:

- `filter_key`
- `payload`
- display name or aliases
- `column_candidates` when executable
- `value_type`
- `value_shape`
- `operator`

Main filter rules:

- `main_flow_filters` defines standard meaning only.
- Dataset-specific mapping belongs to table catalog.
- `DEVICE_DESC` should only apply when the user explicitly asks for description/product description.
- `known_values` or `value_aliases` must not be invented without raw text support.

Current raw filter candidates:

- DATE
- OPER_NAME
- OPER_NUM
- TECH
- DEN
- MODE
- PKG_TYPE1
- PKG_TYPE2
- ORG
- LEAD
- MCP_NO
- DEVICE_DESC
- TSV_DIE_TYP
- EQP_ID
- EQP_MODEL
- LOT_ID
- RECIPE_ID

### 2.9 Duplicate And Review Policy

Duplicate actions:

| Action | Writer behavior |
| --- | --- |
| `ask` | do not write; return choices |
| `merge` | deep merge into existing item; empty new values do not delete existing values |
| `replace` | replace existing document; requires explicit user choice |
| `skip` | do not write |
| `create_new` | write only if new key differs and conflict is acceptable |

Storage blockers:

- missing writer key
- empty payload
- review missing or `ready_to_save=false`
- duplicate decision still `ask`
- real secret/token/password included
- table catalog query omitted/truncated
- domain item contains only source/query config
- main flow filter has business phrase but no executable filter semantics

Warnings that may not block:

- display name missing but key can stand in
- Goodocs seed doc id placeholder
- extra columns added
- aliases partially overlap but condition does not conflict
- table catalog `filter_mappings` left standard key is not a physical column

### 2.10 Batch Onboarding From Current TXT Files

Batch onboarding should still use the saving flow; it should not be a direct JSON conversion script.

Recommended stages:

1. Split raw txt into candidate blocks using explicit headings, marker comments, and blank-line groups.
2. Send each block to the matching saving flow with `dry_run=true`.
3. Save dry-run review reports locally under `validation_runs/metadata_saving_dry_run/<timestamp>/`.
4. Group results into `ready`, `needs_more_input`, `duplicate_decision`, `blocked`.
5. Present review summary to the user.
6. Only after approval, run writer against the v4 MongoDB collections.

Block splitting rules:

- Splitting can segment text; it must not rewrite business meaning.
- SQL blocks must stay attached to their dataset description.
- `<!-- single_* -->` markers are strong boundaries.
- If a block contains multiple independent domain items, the authoring LLM may return multiple candidate items, but review must show them.

### 2.11 Metadata Storage Validation

Local tests:

- sufficient domain process group input saves candidate item in dry-run writer.
- key missing can be backfilled when safe; otherwise supplement request.
- Oracle table catalog without query is blocked.
- `query_template` containing `...` is blocked.
- Goodocs with `doc_id` and columns can pass with warning if credential is absent.
- `filter_mappings` standard key not in physical columns does not block by itself.
- duplicate same key with `ask` does not write.
- `merge` deep merges lists with dedupe.
- `replace` replaces only when explicit.
- secret/token/password is rejected.
- response says "저장하지 않았습니다" when write did not happen.

Round-trip tests:

- raw block -> candidate item -> dry-run Mongo shape -> loader assembled metadata.
- table catalog filters materialize through data retriever dummy path.
- domain product terms do not get applied unless user asks for that term.
- ambiguous product token goes to generic lookup/clarification, not POP injection.

## 3. Interaction Between Metadata Storage And Data Retriever

Runtime dependency:

```text
metadata storage flow
-> MongoDB domain/table/filter collections
-> Metadata Context Loader
-> Intent Plan Normalizer
-> intent_plan.retrieval_jobs
-> data retriever flow
```

Important boundaries:

- Data retriever does not read raw txt files.
- Data retriever does not run authoring logic.
- Intent stage may read active metadata and create compact `retrieval_jobs`.
- Data analysis Langflow의 `01A~01C MongoDB Metadata Loader`는 domain/table catalog/main variable을 각각 `status=active` 문서만 제한 수량으로 읽고, `01D Metadata Candidates Builder`가 의도분석 LLM 호출 전에 후보 JSON으로 결합한다.
- Retriever may re-read selected table catalog documents by `dataset_key` if needed, but it must not carry full metadata downstream.
- `05 MongoDB Previous Result Loader`로 복원한 이전 결과 rows는 새 retrieval 결과가 없으면 pandas 단계까지 유지한다.
- Saving flow may create draft metadata, but main runtime should load only `status=active` unless a validation mode explicitly includes draft/reviewed items.

## 4. Implementation Order

### Phase A. Shared Contracts

Deliverables:

- `reference_runtime` schema dataclasses or typed dicts for:
  - retrieval job
  - source result
  - authoring payload
  - write result
- `.env.example` updated for v4 collection names.
- dry-run Mongo writer interface.

Gate:

- schema tests pass.
- no live MongoDB write in tests.

### Phase B. Metadata Storage Flows First

Deliverables:

- three saving flow skeletons
- common writer utilities copied/adapted only where standalone-safe
- dry-run batch onboarding command for the three txt files
- review report output

Gate:

- txt dry-run produces ready/blocked/duplicate summary.
- no Mongo write without explicit non-dry-run and target collection.
- SQL/query raw text is preserved.

### Phase C. Data Retriever Flow With Dummy Path

Deliverables:

- retrieval job validator
- source router
- dummy retriever
- source merger
- retrieval payload adapter
- inspection block

Gate:

- representative jobs for `wip_today`, `production_today`, `target`, `lot_status`, `hold_history`, `equipment_status` run in dummy mode.
- expected filters/date scopes appear in inspection.

### Phase D. Live Source Adapters

Deliverables:

- Oracle adapter
- Goodocs adapter
- H-API adapter
- Datalake adapter
- source timeout/error mapping

Gate:

- live adapters disabled by default.
- adapter contract tests with mocked clients.
- live validation only when env is present.

### Phase E. Integration With Intent/Pandas

Deliverables:

- intent normalizer emits retrieval jobs with source-specific date/filter scopes.
- pandas prompt consumes `runtime_sources` and `source_results`.
- final API removes `runtime_sources`.

Gate:

- validation questions pass plan/scope/schema before answer text.
- payload bloat gate passes.

## 5. Sub-Agent Work Split

Recommended sub-agent roles for implementation:

| Role | Ownership | Output |
| --- | --- | --- |
| Metadata Storage Worker | `domain_saving_flow`, `table_catalog_saving_flow`, `main_flow_filters_saving_flow`, writer tests | dry-run saving flow and txt onboarding report |
| Data Retriever Worker | retriever validator/router/adapters/merger/payload adapter | dummy-first retriever flow and adapter tests |
| Validation Worker | regression matrix, payload bloat tests, Mongo dry-run tests | local gate scripts and expected contracts |
| Integration Reviewer | boundary review across authoring, metadata loader, retriever, pandas prompt | findings before live Mongo/LLM run |

Workers must use disjoint write scopes and must not revert changes from other workers.

## 6. Immediate Next Checklist

1. Confirm v4 MongoDB database and collection names.
2. Add `.env.example` for v4 names and live source flags.
3. Scaffold shared schema contracts.
4. Implement metadata saving dry-run path.
5. Run dry-run onboarding for `domain_knowledge.txt`, `data_catalog.txt`, `main_variable.txt`.
6. Review blocked/warning items, especially dataset naming and suspicious mappings.
7. Implement data retriever dummy path.
8. Validate representative retrieval jobs before building pandas/answer flow.
