# Metadata Driven V3 Rebuild Functional Design

작성일: 2026-07-01
대상: `C:\Users\qkekt\Desktop\metadata_driven_v3`
참고 채팅: `019f025d-f16c-7f40-8ad6-5b99069c006d`

## 1. 목적

이 문서는 `metadata_driven_v3`를 처음부터 다시 구현하기 위한 기능 설계도다.

기존 구현은 메타데이터 기반으로 제조 데이터를 유연하게 조회하고 분석하는 방향은 맞았지만, 실제 운영자가 쓰기에는 다음 문제가 커졌다.

- 중간 payload가 너무 크고 같은 정보가 여러 위치에 반복된다.
- prompt, fallback, repair, executor 보정 로직이 쌓이면서 어느 기능이 어디에서 동작하는지 읽기 어렵다.
- 특정 공정/제품/질문을 처리하기 위한 예외가 공통 노드 안으로 들어갈 위험이 커졌다.
- 현업 작업자가 metadata를 자연어로 등록해야 하는데 내부 key, JSON 구조, function-case 이름을 알아야 할 것처럼 보이는 구간이 있다.
- 검증이 숫자 정답 중심으로 흐르면 dataset, filter scope, group_by, metric, result schema가 틀린 문제를 놓칠 수 있다.

새 구현의 목표는 단순하다.

> 어느 제조 공정에도 공통으로 쓸 수 있는 Langflow 기반 metadata-driven flow를 만들고, 공정 특화 내용은 코드가 아니라 metadata, prompt contract, explicit function case로 분리한다.

## 2. 반드시 지켜야 할 원칙

### 2.1 Langflow standalone component 원칙

모든 Langflow custom component는 standalone 파일이어야 한다.

- numbered component 하나를 Langflow Desktop에 그대로 붙여 넣어도 동작해야 한다.
- sibling helper import, project-local helper import에 의존하지 않는다.
- rebuild v1의 배포 모드는 paste-in standalone이다.
- 허용 import는 Python standard library, Langflow/LFX public API, 명시적으로 설치된 third-party package만이다.
- package mode는 v1 범위가 아니다. 나중에 허용하려면 package manifest, version, install gate, parser gate를 별도 설계 문서로 만든다.
- input 이름과 output 이름은 같은 component 안에서 겹치지 않는다. 예: input `payload`, output `payload_out`.
- component parser 검증, import allowlist 검증, sample payload 실행 검증을 release gate에 포함한다.

### 2.2 공통 노드에는 공정 특화 내용을 넣지 않는다

공통 노드는 어떤 제조 공정에서도 같은 의미로 동작해야 한다.

공통 노드에 넣어도 되는 것:

- payload normalization
- metadata loading
- route normalization
- generic filter application
- source retriever dispatch
- generic pandas step primitive 실행
- answer/API response shaping
- validation/error/warning normalization

공통 노드에 넣으면 안 되는 것:

- DA/WB/HBM/POP/MOBILE 같은 특정 업무 용어의 직접 분기
- 특정 질문 하나를 맞추기 위한 executor branch
- 특정 recipe 이름에만 반응하는 숨은 fallback
- 예시 문장에 나온 조건을 실제 질문에 강하게 주입하는 로직
- product token이 애매한데 POP류 제품 조건을 임의로 연결하는 로직

### 2.3 특화 지식의 위치

특화 지식은 아래 순서로 둔다.

1. `domain_items`: 공정 그룹, 제품 조건, 수량 용어, metric, status, analysis recipe.
2. `table_catalog`: dataset family, source type, query/API config, filter mapping, standard column alias.
3. `main_flow_filters`: DATE, OPER_NAME, MODE, MCP_NO 같은 표준 filter 개념과 후보 컬럼.
4. `pandas_function_cases`: 공통 primitive로 표현하기 어려운 pandas helper 사용 안내.
5. prompt contract: LLM이 plan/code를 만들 때 지켜야 할 규칙.
6. generic primitive 확장: 여러 업무에서 재사용되는 operation일 때만 추가.

특정 현장만의 처리라도 공통 노드를 수정하기 전에 metadata로 표현할 수 있는지 먼저 판단한다.

### 2.4 특화 정보 배치 결정표

특화 정보를 어디에 둘지 애매하면 아래 순서로 판단한다. 이 표는 구현자가 prompt나 executor에 임시 예외를 넣지 않도록 막는 기준이다.

| 판단 질문 | 위치 | 넣는 예 | 넣으면 안 되는 예 |
| --- | --- | --- | --- |
| 업무 사실인가? | DB `domain_items` | DA 공정 그룹, HBM 조건, hold 상태 정의, lot count 의미, 생산달성률 공식 | LLM 말투, prompt 예시, 임시 튜닝 문장 |
| source/table/column 연결인가? | DB `table_catalog` | dataset family, source type, query template, filter mappings, standard aliases | 공정 의미 설명, 질문별 분석 순서 |
| 질문에서 추출할 표준 filter 개념인가? | DB `main_flow_filters` | DATE, OPER_NAME, MODE, MCP_NO, LOT_ID, EQP_MODEL | dataset별 실제 컬럼 mapping |
| 여러 dataset/step을 어떤 순서로 분석할지인가? | DB `analysis_recipes` | WIP rank 후 생산량 join, 생산/재공/목표 달성률 계산 순서 | pandas 코드 조각, 특정 질문 하나의 예외 branch |
| LLM이 metadata를 어떻게 읽고 JSON을 어떻게 낼지인가? | Prompt contract | 출력 schema, 금지 행동, 예시는 weak hint, scope reset 규칙 | DA/WB/HBM 조건 자체, POP 조건, table/query 정보 |
| generic primitive로 표현하기 어려운 row-level 탐색/매칭 규칙인가? | `pandas_function_cases` draft/active | 여러 제품 속성 컬럼에서 token 후보를 찾아 product list 구성 | executor가 import할 helper 경로, 숨은 runtime 함수 |
| 여러 현장에서 반복되는 deterministic operation인가? | Generic primitive/code | filter, aggregate, rank, join, derive_metric, nunique | 공정명/제품명/recipe 이름에 직접 반응하는 code |
| 특정 질문 하나만 맞추기 위한 것인가? | 구현 금지 | clarification, metadata 보강, regression 추가로 처리 | prompt hard trigger, executor fallback, hidden branch |

핵심 규칙:

- DB에는 오래 유지되는 업무 사실과 source 계약을 둔다.
- Prompt에는 DB의 사실을 해석하는 절차와 출력 형식만 둔다.
- Function case에는 특수 분석의 I/O 계약과 pseudocode만 둔다.
- 실제 실행 code는 generic primitive 또는 검증된 versioned code artifact로만 둔다.
- Prompt와 function case는 DB에 없는 업무 조건을 새로 만들어내면 안 된다.
- Executor는 recipe name, product term, output column name만 보고 숨은 동작을 실행하면 안 된다.

### 2.5 예시는 약한 힌트다

예시는 LLM이 형식을 이해하도록 돕는 soft prior일 뿐이다.

- 예시의 제품 조건을 실제 질문에 자동 적용하지 않는다.
- 유사한 product token이 있더라도 metadata에 명시된 고신뢰 mapping이 없으면 일반 product lookup 또는 확인 요청으로 보낸다.
- "POP제품 조건" 같은 도메인 조건은 사용자가 명시했거나 metadata matching이 명확할 때만 적용한다.

### 2.5 fallback은 숨은 기능 구현 장소가 아니다

fallback은 서비스가 멈추지 않도록 최소 안전 동작을 제공하는 장치다.

허용 fallback:

- LLM JSON parsing 실패 시 명확한 오류와 보충 요청 반환.
- 누락된 optional field의 schema 기본값 보정.
- generic step primitive로 표현된 plan 실행.
- pandas code 실패 시 repair route로 넘김.
- 안전하게 답할 수 없으면 "필요 정보 부족"으로 종료.

금지 fallback:

- 특정 질문을 맞추기 위해 executor가 domain rule을 새로 해석.
- result column 이름만 보고 숨은 업무 분석을 실행.
- plan 없이 특정 dataset 조합을 임의 조회.
- LLM 실수를 조용히 덮어 성공처럼 보이게 하는 fallback.

## 3. 목표 사용자와 사용 시나리오

### 3.1 제조 현업 사용자

현업 사용자는 자연어 질문만 입력한다.

예:

- `오늘 DA, WB공정에서 각각 재공 상위 3개 제품을 뽑아주고 해당 제품들의 오늘 생산량도 보여줘`
- `T1234567GEN1 LOT의 HOLD이력 알려줘`
- `현재 MODE값이 LPDDR5인 제품의 W/B공정에서 생산량과 재공 수량 알려줘`
- `어제 생산량과 오늘 생산계획의 차이수량을 제품별로 알려줘`

현업 사용자는 아래를 몰라도 된다.

- dataset key
- collection name
- JSON schema
- pandas function case 이름
- internal route 이름
- result store key

### 3.2 Metadata 관리자

Metadata 관리자는 자연어로 공정/데이터/필터 규칙을 등록한다.

예:

```text
W/B공정은 W/B1부터 W/B6까지야.
재공 수량은 WIP 컬럼을 합산해서 보면 되고, 오늘 재공 데이터는 wip_today를 써.
DATE는 WORK_DT랑 연결돼.
```

시스템은 이 설명을 정제하고, 저장 후보 JSON으로 바꾸고, 부족하면 한국어로 보충 요청을 해야 한다.

관리자는 내부 key를 직접 만들지 않아도 된다. LLM이 key를 만들지 못해도 normalizer가 `display_name`, alias, 설명에서 안정적인 snake_case key를 만들 수 있어야 한다.

### 3.3 운영/개발 관리자

운영자는 아래를 확인한다.

- 어떤 flow가 선택됐는지
- 어떤 metadata가 사용됐는지
- 어떤 source와 filter scope가 적용됐는지
- LLM plan과 pandas code가 어떤 검증을 통과했는지
- fallback 또는 repair가 발생했는지
- final answer가 어떤 data_ref를 기반으로 생성됐는지

개발자용 trace는 있어야 하지만, 현업 응답 payload와 session state를 무겁게 만들면 안 된다.

## 4. 전체 구조

권장 구조는 split runtime이다. 하나의 거대한 canvas에 모든 기능을 몰아넣지 않는다.

```text
Web/API or Chat
-> router_flow
-> selected subflow API runner
-> metadata_qa_flow | data_analysis_flow | report_generation_flow | operations_diagnosis_flow
-> final message/API response
```

### 4.1 Router Flow

역할:

- 질문 유형 분류
- metadata QA, data analysis, report, diagnosis 중 하나 선택
- 선택된 subflow 호출 정보 생성
- 선택된 하나의 subflow만 실행

필수 요구사항:

- router는 subflow 내부 payload를 조립하지 않는다.
- 여러 native Run Flow output을 동시에 기다리는 구조를 만들지 않는다.
- selected flow 하나만 API runner가 호출한다.
- route LLM 결과는 normalizer가 허용 route 목록으로 검증한다.

Router와 selected subflow 사이의 표준 envelope:

```json
{
  "route": "data_analysis_flow",
  "flow_id": "LANGFLOW_DATA_ANALYSIS_FLOW_ID",
  "api_url": "http://localhost:7860/api/v1/run/<flow_id>",
  "session_id": "session-001",
  "input": {
    "question": "현재 DA공정 재공 수량 알려줘",
    "previous_state": {},
    "request_meta": {
      "reference_date": "2026-07-01"
    }
  },
  "timeout_seconds": 120
}
```

Subflow response는 반드시 아래 shape로 정규화한다.

```json
{
  "response_type": "data_analysis",
  "status": "ok",
  "message": "현재 DA공정 재공 수량은 ...",
  "data": {},
  "applied_scope": {},
  "state": {},
  "developer": {},
  "errors": [],
  "warnings": []
}
```

API runner는 호출 전 `route`, `api_url`, `session_id`, `input.question`을 검증하고, 호출 후 `response_type`, `status`, `message`, `state`를 검증한다. timeout, connection error, invalid response는 selected subflow의 성공으로 위장하지 않고 `status=error`, `response_type=flow_error`로 반환한다.

### 4.2 Data Analysis Flow

실제 데이터 조회, pandas 분석, 결과 저장, 답변 생성을 담당한다.

권장 stage:

```text
00 Analysis Request Loader
-> 01 Metadata Context Loader
-> 02 Intent Prompt Builder
-> Intent LLM
-> 04 Intent Plan Normalizer
-> 04 Previous Result Restore Router
-> optional 05 MongoDB Data Loader
-> 06 Previous Result Restore Merger
-> Source Retrieval Block
   -> Retrieval Job Router
   -> Source Adapters
   -> Source Result Normalizer
   -> Source Retrieval Merger
-> Retrieval Payload Adapter
-> 14 Pandas Prompt Builder
-> Pandas Code LLM
-> Pandas Code Normalizer
-> 15 Pandas Code Executor
-> 16A/16B Repair Branch
-> optional second 15 Pandas Code Executor
-> 17 Result Store
-> 18 Answer Prompt Builder
-> Answer LLM
-> 19 Answer Response Builder
-> 20 Message Adapter
-> 21 API Response Builder
```

번호와 component 구성은 기존 v3와 달라도 된다. 특히 Data Retriever Flow는 기존 구조를 그대로 복제하는 것이 목표가 아니다. 더 효과적인 구조가 있으면 새로 설계한다. 다만 retrieval job routing, source별 실행, result normalization, merge, pandas용 payload adapter의 책임 경계는 유지하고, 이 모든 것을 하나의 거대한 component로 합치지 않는다.

### 4.3 Metadata QA Flow

역할:

- 어떤 데이터가 있는지 설명
- 사용 가능한 공정/제품/수량/metric/filter 안내
- 자연어 metadata 등록 방법 안내
- 일반 help/greeting 처리

요구사항:

- 실제 분석 flow를 실행하지 않는다.
- metadata summary만 사용한다.
- direct response와 API response를 구분한다.

### 4.4 Metadata Authoring Flows

세 authoring flow를 분리한다.

- `domain_authoring_flow`: 업무 용어, 공정 그룹, 제품 조건, 수량/metric, analysis recipe, function case.
- `table_catalog_authoring_flow`: dataset, source type, query/API config, filter mapping, standard column alias.
- `main_flow_filters_authoring_flow`: DATE, OPER_NAME, 제품 속성, 설비, LOT 등 표준 filter 개념.

운영 UI/API는 세 flow 이름을 현업 관리자에게 노출하지 않는다. 관리자는 하나의 "메타데이터 등록" 진입점에 자연어를 입력하고, 시스템이 내부적으로 target type을 분류한다.

관리자용 단일 authoring entrypoint:

```text
자연어 입력
-> authoring router가 domain/table/filter/special-analysis-draft 분류
-> 해당 authoring flow 실행
-> 한국어 검토 카드 표시
-> 저장/보강/중복 처리 선택
```

검토 카드에는 내부 `section`, `key`, `payload`, `source_config`, function-case 이름을 먼저 보여주지 않는다. 대신 아래를 보여준다.

- 등록하려는 의미
- 적용될 데이터/필터/공정/제품 조건
- 부족한 정보
- 비슷한 기존 항목
- 이 변경으로 영향을 받을 수 있는 예시 질문
- 저장 선택지

공통 pattern:

```text
raw natural language
-> text refinement
-> authoring JSON generation
-> normalization
-> duplicate/similarity check
-> review
-> MongoDB writer
-> user-friendly response
```

요구사항:

- 부족한 입력은 저장하지 않고 보충 요청한다.
- 중복/유사 항목은 내부 action `merge`, `replace`, `skip`, `create_new`로 처리하되, 사용자에게는 `기존 항목에 합치기`, `기존 항목 대체`, `저장하지 않기`, `새 항목으로 저장`으로 보여준다.
- writer는 review 통과 전 MongoDB에 쓰지 않는다.
- prompt 전문과 기존 collection 전체를 payload에 계속 싣지 않는다.
- domain writer는 source/query config를 거부한다.
- table catalog writer만 source/query config를 저장한다.
- function-case authoring은 일반 현업 관리자 flow와 분리하고, 개발/고급 관리자 검토와 실행 테스트를 통과해야 active가 된다.

### 4.5 Report / Diagnosis Flow

초기 재구현에서는 최소 skeleton만 둔다.

- report flow는 data_analysis 결과 또는 별도 분석 결과를 받아 structured report를 만든다.
- diagnosis flow는 병목, 목표 대비 저조, hold 증가 등 운영 진단을 담당한다.
- 두 flow 모두 data_analysis 공통 노드 안에 진단 전용 분기를 넣는 방식으로 구현하지 않는다.

## 5. Metadata 모델

### 5.1 Domain Items

Domain collection은 제조 업무의 의미를 담는다.

허용 section:

- `process_groups`
- `product_terms`
- `quantity_terms`
- `metric_terms`
- `analysis_recipes`
- `status_terms`
- `product_key_columns`
- `pandas_function_cases`

요구사항:

- `section + key`가 저장 기준이다.
- 사용자가 key를 몰라도 authoring normalizer가 생성할 수 있어야 한다.
- `gbn`은 legacy 호환으로 읽을 수 있지만 신규 문서/응답에는 `section`을 우선한다.
- source 조회 방식, SQL, API endpoint는 domain에 넣지 않는다.

### 5.2 Table Catalog

Table catalog는 source 조회 가능성을 정의한다.

주요 field:

- `dataset_key`
- `dataset_family`
- `source_type`
- `source_config`
- `required_params`
- `required_param_mappings`
- `filter_mappings`
- `standard_column_aliases`
- `primary_quantity_column`
- `default_detail_columns`
- `columns`

요구사항:

- 실제 credential은 저장하지 않는다.
- SQL/query template을 LLM이 `...`로 축약하면 저장하지 않는다.
- 표준 filter key와 물리 컬럼 mapping은 table catalog가 가진다.
- `main_flow_filters`에 dataset별 mapping을 넣지 않는다.

### 5.3 Main Flow Filters

Main flow filter는 질문에서 추출 가능한 표준 filter 개념이다.

예:

- `DATE`
- `OPER_NAME`
- `MODE`
- `TECH`
- `DEN`
- `PKG_TYPE1`
- `PKG_TYPE2`
- `MCP_NO`
- `LOT_ID`
- `EQP_ID`
- `EQP_MODEL`
- `RECIPE_ID`

요구사항:

- filter key는 표준 의미다.
- 실제 dataset 컬럼은 table catalog의 `filter_mappings`가 결정한다.
- operator, value shape, semantic role은 명확히 둔다.

### 5.4 Pandas Function Cases

`pandas_function_cases`는 generic primitive만으로 표현하기 어려운 분석 보조 규칙의 안내다. 일반 현업 관리자는 "특수 분석 설명"을 자연어로 등록하고, 시스템은 이를 draft metadata로 저장한다. 실제 executable function case는 개발/고급 관리자가 검토한 뒤 active로 승격한다.

허용 내용:

- 적용 조건
- 필요한 source/dataset family
- 필요한 입력 컬럼
- 출력 컬럼
- pseudocode
- self-contained code snippet 예시
- LLM이 따라야 할 I/O contract

금지 내용:

- executor가 import해서 실행할 helper module 경로
- executor namespace에 주입되는 숨은 함수
- 특정 case 이름으로 실행되는 hardcoded branch

사용 방식:

1. metadata에 function case를 등록한다.
2. intent normalizer가 질문과 metadata를 보고 후보를 고른다.
3. 선택 결과는 `intent_plan.pandas_function_cases` 배열에 compact하게 남기고, 실행 순서는 `pandas_execution_plan`의 `apply_pandas_function_case` step으로 표현한다.
4. pandas prompt builder가 선택된 case만 LLM prompt에 `Specialized Functions` block으로 전달한다.
5. pandas executor는 LLM이 생성한 self-contained code와 runtime source만 실행한다.

금지:

- executor가 metadata에서 helper code를 몰래 불러와 실행하지 않는다.
- function case 이름 하나로 executor가 별도 hardcoded branch를 타지 않는다.
- 일반 제품 질문을 product-token function case로 과하게 라우팅하지 않는다.
- executor namespace 검증에서 case-specific 함수가 없어야 한다.

## 6. Canonical Payload Contract

중간 payload는 "현재 stage가 다음 stage에 넘길 최소 정보"만 담는다.

특히 metadata는 MongoDB에서 많이 읽을 수 있지만, flow 전체가 그 전체 object를 들고 다니면 안 된다. 의도 분석 이후 downstream payload에는 실제 의도 분석에 사용된 metadata ref와 compact evidence만 남긴다. 정상 runtime payload의 top-level key는 10개 내외로 유지한다.

### 6.1 허용 top-level key

| Key | 설명 | 유지 기간 |
| --- | --- | --- |
| `request` | session id, question, reference date | 전체 |
| `state` | compact previous context, product key summary, data refs | 전체 |
| `metadata_refs` | 실제 사용된 metadata key 목록 | plan 이후 |
| `intent_plan` | route, analysis kind, retrieval jobs, step plan, output contract | plan 이후 |
| `source_results` | source별 compact trace, preview, filters, params | retrieval 이후 |
| `runtime_sources` | pandas 실행용 full rows | pandas 실행 전후까지만 |
| `analysis` | pandas status, row_count, columns, rows preview, code/debug refs | pandas 이후 |
| `data` | 사용자/API 표시용 rows preview, columns, data_ref | answer 이후 |
| `answer_message` | 최종 한국어 응답 | final |
| `trace` | applied_scope, warnings, errors, debug refs, metadata_evidence, inspection | 필요 stage |

허용 top-level key는 위 10개를 기준으로 한다. `metadata`, `metadata_candidates`, `prompt_payload`, `developer`, `debug`, `errors`, `warnings`, `applied_scope`는 canonical top-level key가 아니다. 필요한 경우 stage-local 변수로만 쓰거나 `trace` 아래에 compact하게 넣는다.

### 6.2 의도 분석 이후 metadata 전달 규칙

MongoDB metadata는 다음 흐름으로만 전달한다.

1. `Metadata Loader`는 MongoDB에서 domain/table/filter/recipe/function-case metadata를 읽을 수 있다.
2. `Metadata Candidate Builder`는 질문, 이전 state, route hint를 기준으로 의도 분석 후보만 추린다.
3. `Intent Prompt Builder`는 full metadata가 아니라 `metadata_candidates`만 prompt에 넣는다.
4. `Intent Normalizer`는 LLM JSON을 정규화하면서 `intent_plan`, `metadata_refs`, `trace.metadata_evidence`, `trace.inspection.intent`만 남긴다.
5. `Intent Normalizer` 이후 payload에서는 `metadata`와 `metadata_candidates`를 삭제한다.
6. downstream node가 추가 metadata detail이 필요하면 `metadata_refs`로 필요한 document만 재조회하거나 clarification/safe failure로 보낸다. full MongoDB collection을 다시 payload에 싣지 않는다.

`trace.metadata_evidence`는 사용자가 신뢰할 수 있도록 "왜 이 metadata가 쓰였는지"를 설명하는 최소 근거다. MongoDB 원문 전체가 아니라 다음 정도만 허용한다.

```json
{
  "metadata_evidence": [
    {
      "ref": "domain_items:process_group:da",
      "label": "DA 공정 그룹",
      "matched_terms": ["DA", "D/A"],
      "used_for": "process_scope"
    }
  ]
}
```

제한:

- `metadata_candidates`는 intent prompt 직전 stage-local data이며 최대 20개 item 또는 32KB 중 작은 값을 넘기지 않는다.
- `trace.metadata_evidence`는 최대 10개 item 또는 8KB 중 작은 값을 넘기지 않는다.
- evidence item은 `ref`, `label`, `matched_terms`, `used_for`, `confidence` 정도로 제한한다.
- table schema 전체, recipe 원문 전체, function-case 설명 전체는 evidence에 넣지 않는다.
- `metadata_refs`는 id/key list다. 사람이 읽는 설명은 `trace.metadata_evidence`로 분리한다.

### 6.3 Payload Inspection Contract

payload를 작게 만들더라도 운영/개발자가 component output에서 "현재 결과가 무엇이고 왜 그렇게 됐는지"를 바로 확인할 수 있어야 한다. 단, inspection block의 형태를 억지로 동일하게 맞추지 않는다. 의도 분석, 데이터 조회, pandas 실행은 서로 다른 정보를 봐야 하므로 stage별로 다른 shape를 허용한다.

고정 위치:

```json
{
  "trace": {
    "inspection": {
      "intent": {},
      "data_retrieval": {},
      "pandas_execution": {}
    }
  }
}
```

필수 inspection:

| 위치 | 만드는 component | 반드시 보여줄 내용 |
| --- | --- | --- |
| `trace.inspection.intent` | `Intent Plan Normalizer` | 정리된 의도, 판단 이유, selected route, analysis kind, pandas 처리 계획, retrieval jobs 요약, filter/date scope, used metadata refs, scope reset 여부 |
| `trace.inspection.data_retrieval` | `Source Result Normalizer` 또는 `Source Retrieval Merger` | 조회된 source별 데이터 요약, 컬럼 정보, raw data preview/ref, required/applied params, missing params, row_count, empty/error 이유 |
| `trace.inspection.pandas_execution` | `Pandas Executor` | 생성된 pandas code, 실행 status, 실행 결과 preview, output columns, row_count, 실패 시 error type/message/traceback summary, repair 필요 여부 |

의도 분석 inspection 예시:

```json
{
  "trace": {
    "inspection": {
      "intent": {
        "stage": "04_intent_plan_normalizer",
        "status": "ok",
        "normalized_intent": {
          "route": "data_analysis",
          "analysis_kind": "current_wip_count",
          "target_process": "DA",
          "metric": "wip_quantity"
        },
        "decision_reason": [
          "질문에 'DA공정'과 '재공 수량'이 포함됨",
          "domain_items:process_groups/da metadata와 매칭됨",
          "이전 follow-up scope보다 현재 질문의 명시 scope를 우선함"
        ],
        "pandas_plan": [
          "1. wip_today 데이터를 source alias wip_data로 조회한다.",
          "2. OPER_NAME을 DA 공정 그룹에 포함되는 값으로 필터링한다.",
          "3. 필요하면 OPER_NAME 기준으로 그룹화한다.",
          "4. LOT_ID 기준 중복 여부를 확인한 뒤 QTY 합계 또는 row count를 계산한다.",
          "5. output contract에 맞춰 wip_count 컬럼을 만든다."
        ],
        "retrieval_jobs_summary": [
          {
            "source_alias": "wip_data",
            "dataset_key": "wip_today",
            "source_type": "oracle",
            "required_params": ["reference_date", "process_group"]
          }
        ],
        "metadata_refs_used": ["domain_items:process_groups:da"],
        "warnings": []
      }
    }
  }
}
```

데이터 조회 inspection 예시:

```json
{
  "trace": {
    "inspection": {
      "data_retrieval": {
        "stage": "source_retrieval_merger",
        "status": "ok",
        "executed_job_count": 1,
        "sources": [
          {
            "source_alias": "wip_data",
            "dataset_key": "wip_today",
            "source_type": "oracle",
            "status": "ok",
            "row_count": 120,
            "columns": ["LOT_ID", "OPER_NAME", "QTY"],
            "required_params": {"reference_date": "2026-07-01"},
            "applied_params": {"reference_date": "2026-07-01"},
            "pandas_filters": {"OPER_NAME": ["DA1", "DA2"]},
            "raw_data_preview": [{"LOT_ID": "L001", "OPER_NAME": "DA1", "QTY": 1}],
            "raw_data_ref": "result_store://source/wip_data/..."
          }
        ]
      }
    }
  }
}
```

pandas executor inspection 예시:

```json
{
  "trace": {
    "inspection": {
      "pandas_execution": {
        "stage": "15_pandas_code_executor",
        "status": "ok",
        "generated_code": "result = sources['wip_data'].groupby('OPER_NAME').size().reset_index(name='wip_count')",
        "execution_result": {
          "row_count": 3,
          "columns": ["OPER_NAME", "wip_count"],
          "preview_rows": [{"OPER_NAME": "DA1", "wip_count": 40}]
        },
        "error": null,
        "repair_required": false
      }
    }
  }
}
```

제한:

- inspection block은 사람이 읽는 확인 화면에 가까워야 하며, stage별로 필요한 정보가 다를 수 있다.
- `intent` block은 의도/판단 이유/처리 계획 중심이다. full metadata와 prompt 원문을 넣지 않는다.
- `data_retrieval` block은 source별 컬럼, raw data preview, required/applied params를 보여준다. raw data 전체가 크면 `raw_data_preview`는 최대 20 rows만 두고 전체는 `raw_data_ref`로 연결한다.
- `pandas_execution` block은 executor에서 실제 실행한 code, 실행 결과, 실패 시 error를 보여준다. code가 4KB를 넘으면 `generated_code_preview`와 `code_ref`로 나눈다.
- `trace.inspection` 전체는 기본 16KB 이하를 목표로 하고, 32KB를 넘으면 release blocker다.
- full metadata, full prompt, full source rows 전체 dump는 inspection에 넣지 않는다.
- inspection은 final 현업 응답에 그대로 노출하지 않는다. 운영/debug API나 Langflow component output에서 확인하는 용도다.
- inspection이 payload bloat를 유발하면 release blocker다.

### 6.4 제거해야 할 중복

새 구현에서는 아래 중복을 만들지 않는다.

- top-level `retrieval_jobs` mirror. canonical 위치는 `intent_plan.retrieval_jobs`.
- `runtime_sources`, `source_results.preview_rows`, `analysis.rows`, `data.rows`, `state.current_data.rows`에 같은 rows를 반복 저장.
- prompt builder가 만든 `prompt_payload` wrapper를 downstream 실행 payload로 전달.
- API response에 `developer`, `debug`, `trace`를 같은 값으로 중복 저장.
- session state에 full source rows 저장.
- answer LLM prompt 전문을 final API payload에 저장.
- MongoDB full metadata object와 `metadata_candidates`를 intent 이후 payload에 저장.
- `applied_scope`, `warnings`, `errors`를 top-level과 `trace`에 동시에 저장.
- `trace.inspection`에 full prompt/full metadata/full source rows 전체를 복사해 저장.

### 6.5 측정 가능한 payload 기준

구현은 stage별 schema fixture를 둔다.

필수 기준:

- 각 stage payload는 허용 top-level key 목록을 벗어나면 실패한다.
- `Intent Normalizer` 이후 top-level key count는 10개 이하가 아니면 실패한다.
- prompt text는 prompt node output에만 존재하고 downstream payload에는 `prompt_preview` 최대 1,000자만 허용한다.
- `metadata_candidates`는 prompt builder 이후 downstream payload에 남으면 실패한다.
- preview rows는 stage별 최대 50 rows다.
- session state JSON은 기본 64KB 이하를 목표로 하고, 128KB를 넘으면 release blocker다.
- `runtime_sources`는 pandas executor/result store 이후 final API response에 남으면 실패한다.
- 같은 full row list가 두 개 이상의 top-level key에 존재하면 실패한다.
- `developer`, `debug`, `errors`, `warnings`, `applied_scope`가 top-level에 존재하면 실패한다. canonical 위치는 `trace`.
- `metadata` full object는 `Intent Normalizer` 이후 payload, answer/API response, session state 어디에도 남으면 실패한다.
- intent/data retrieval/pandas executor stage는 해당 `trace.inspection.*` block을 만들지 않으면 실패한다.
- `trace.inspection` 전체가 32KB를 넘거나 full prompt/full metadata/full source rows 전체를 포함하면 실패한다.

### 6.6 Stage별 payload 책임

| Stage | 입력 | 출력 |
| --- | --- | --- |
| Request Loader | question, previous state | `request`, compact `state` |
| Metadata Loader | request payload | stage-local raw metadata, load summary |
| Metadata Candidate Builder | request/state + raw metadata | stage-local `metadata_candidates` |
| Intent Prompt Builder | request/state + `metadata_candidates` | prompt text only, optional prompt preview |
| Intent Normalizer | payload + LLM JSON | `intent_plan`, `metadata_refs`, `trace.metadata_evidence`, `trace.inspection.intent`, `trace.warnings` |
| Restore Router | payload | restore decision only |
| Source Retrievers | payload | source-specific `source_results` |
| Source Merger | source results | merged `source_results`, `trace.inspection.data_retrieval` |
| Retrieval Adapter | main payload + retrieval payload | `runtime_sources`, compact `source_results` |
| Pandas Prompt Builder | payload | prompt text only |
| Pandas Code Normalizer | payload + code LLM JSON | validated code payload |
| Pandas Executor | payload + code JSON | `analysis`, `trace.inspection.pandas_execution` |
| Repair Branch | failed analysis | stage-local repair prompt or pass-through |
| Result Store | payload | `data.data_ref`, compact rows/refs |
| Answer Prompt Builder | compact payload | prompt text only |
| Answer Response Builder | payload + answer LLM | `data`, `trace.applied_scope`, `answer_message`, next `state` |
| API Builder | final payload | API response |

## 7. 기능 요구사항

### 7.1 질문 라우팅

기능:

- 질문을 `metadata_qa`, `data_analysis`, `report_generation`, `operations_diagnosis`, `clarification`으로 분류한다.
- rule candidate와 LLM classifier를 같이 쓸 수 있다.
- route LLM이 허용 route 밖을 반환하면 normalizer가 fallback route 또는 clarification으로 정리한다.

Acceptance:

- metadata help 질문은 data analysis source 조회를 하지 않는다.
- 실제 수량/목록/비교 질문은 data analysis로 간다.
- report/diagnosis는 별도 subflow로 간다.

### 7.2 Intent Planning

기능:

- 질문에서 intent type, analysis kind, required datasets, source별 filter/date scope, group_by, metric, output contract를 만든다.
- `analysis_recipes`가 있으면 recipe 기반 step plan을 우선 고려한다.
- recipe가 없더라도 generic single-source 또는 multi-source plan을 만들 수 있다.
- LLM 결과는 normalizer가 metadata와 대조해 정리한다.
- `Intent Plan Normalizer`는 `intent_plan.pandas_execution_plan`에 pandas가 따라야 할 순차 실행 계획을 남긴다.
- `Intent Plan Normalizer`는 `trace.inspection.intent`에 현재 정리된 의도, 판단 이유, retrieval job 요약, pandas 처리 계획을 남긴다.

Pandas 실행 계획 계약:

`pandas_execution_plan`은 pandas code LLM에 넘기는 핵심 지시다. pandas prompt에 source schema와 preview만 주고 "알아서 분석하라"고 맡기지 않는다. 의도 분석 단계가 어떤 데이터를 조회하고, 어떤 조건을 적용하고, 어떤 기준으로 그룹화/결합/계산할지를 순서대로 제공해야 한다.

권장 shape:

```json
{
  "pandas_execution_plan": [
    {
      "step": 1,
      "operation": "load_source",
      "source_alias": "wip_data",
      "description": "현재 기준일의 WIP 데이터를 사용한다."
    },
    {
      "step": 2,
      "operation": "filter_rows",
      "source_alias": "wip_data",
      "condition": "OPER_NAME is in DA process group",
      "description": "DA 공정 그룹에 해당하는 row만 남긴다."
    },
    {
      "step": 3,
      "operation": "group_by",
      "keys": ["PRODUCT_CODE"],
      "description": "제품 기준으로 재공 데이터를 그룹화한다."
    },
    {
      "step": 4,
      "operation": "left_join",
      "left": "wip_grouped",
      "right": "production_today",
      "join_keys": ["PRODUCT_CODE"],
      "description": "동일 제품 기준으로 오늘 생산량을 결합한다."
    },
    {
      "step": 5,
      "operation": "derive_metric",
      "formula": "achievement_rate = production_qty / target_qty",
      "description": "목표 대비 달성률을 계산한다."
    }
  ]
}
```

규칙:

- 각 step은 순서, operation, 대상 source 또는 intermediate result, 조건/키/공식, 사람이 읽는 설명을 포함한다.
- 조회 계획은 `retrieval_jobs`에, pandas 처리 계획은 `pandas_execution_plan`에 둔다.
- pandas code generator는 이 순서를 기본 실행 순서로 따라야 하며, 임의로 분석 순서를 재해석하지 않는다.
- source schema와 실제 columns 때문에 계획을 그대로 실행할 수 없으면 code에서 조용히 우회하지 말고 warning, repair, clear failure로 보낸다.
- generic primitive fallback도 가능한 경우 `pandas_execution_plan`의 operation 순서를 기준으로 실행한다.

대표 질문별 plan pattern:

| 질문 유형 | 필요한 plan 순서 |
| --- | --- |
| 현재 공정 재공 수량 | `select_source` -> `filter_rows` -> `aggregate` 또는 `count_rows` |
| DA/WB 공정별 재공 top N + 오늘 생산량 | `select_source(wip)` -> `filter_rows(process group)` -> `group_by(product)` -> `rank_top_n` -> `select_source(production)` -> `group_by(product)` -> `left_join` |
| 특정 LOT HOLD 이력 | `select_source(hold_history)` -> `filter_rows(lot_id)` -> `sort_rows(time desc)` -> `select_columns` |
| 생산/재공/목표/달성률 | `select_source(production)` -> `select_source(wip)` -> `select_source(target)` -> `group_by(product)` -> `left_join` -> `left_join` -> `derive_metric` |
| "이 제품" follow-up | `resolve_followup_reference` -> `select_source` -> `filter_rows(product key)` -> `select_columns` |
| 목표 대비 저조 제품 | `select_source(production)` -> `select_source(target)` -> `group_by(product)` -> `left_join` -> `derive_metric` -> `filter_rows(under target)` -> `rank_top_n` |

대표 pattern 예시:

```json
{
  "case": "da_wb_wip_top3_with_today_production",
  "pandas_execution_plan": [
    {"step": 1, "operation": "select_source", "source_alias": "wip_data", "output": "wip_df"},
    {
      "step": 2,
      "operation": "filter_rows",
      "input": "wip_df",
      "output": "target_wip_df",
      "conditions": [{"column": "OPER_NAME", "operator": "in", "value_ref": "metadata.process_groups.DA_WB"}]
    },
    {
      "step": 3,
      "operation": "group_by",
      "input": "target_wip_df",
      "output": "wip_by_product",
      "keys": ["PRODUCT_CODE"],
      "aggregations": [{"column": "LOT_ID", "function": "nunique", "as": "wip_lot_count"}]
    },
    {"step": 4, "operation": "rank_top_n", "input": "wip_by_product", "output": "top_wip_products", "sort_by": "wip_lot_count", "n": 3},
    {"step": 5, "operation": "select_source", "source_alias": "production_today", "output": "prod_df"},
    {
      "step": 6,
      "operation": "group_by",
      "input": "prod_df",
      "output": "prod_by_product",
      "keys": ["PRODUCT_CODE"],
      "aggregations": [{"column": "QTY", "function": "sum", "as": "today_production_qty"}]
    },
    {"step": 7, "operation": "left_join", "left": "top_wip_products", "right": "prod_by_product", "output": "result_df", "join_keys": ["PRODUCT_CODE"]}
  ]
}
```

`pandas_execution_plan`을 안정적으로 만들기 위해 필요한 metadata:

- `table_catalog`: 어떤 질문이 어떤 dataset/source를 조회해야 하는지, source별 column alias와 filter mapping.
- `domain_items.process_groups`: DA/WB/HBM 같은 업무 용어가 어떤 실제 filter 값으로 확장되는지.
- `domain_items.metric_terms`: 재공, 생산량, 목표, 달성률 같은 metric의 계산 의미.
- `domain_items.product_key_columns`: source 간 join/follow-up에 사용할 제품 key 후보.
- `analysis_recipes`: multi-source join, 목표 대비 달성률, top N 후 상세 조회처럼 순서가 중요한 대표 분석 recipe.

Acceptance:

- DA/WB는 공정 그룹 metadata로 확장한다.
- "D/A1"은 DA 전체 그룹이 아니라 단일 공정으로 유지한다.
- `전체 재공 수량` 같은 scope reset 질문은 이전 DA filter를 상속하지 않는다.
- source별 date scope가 다르면 섞지 않는다.
- component payload에서 `trace.inspection.intent.normalized_intent`, `decision_reason`, `pandas_plan`만 봐도 왜 해당 route/dataset/filter가 선택됐고 이후 pandas가 어떤 순서로 처리할 예정인지 이해할 수 있어야 한다.
- `intent_plan.pandas_execution_plan`이 없는 data analysis plan은 single-source 단순 조회를 제외하면 실패 또는 clarification 대상이다.

### 7.3 Source Retrieval

기능:

- `intent_plan.retrieval_jobs`를 source type별 retriever가 처리한다.
- 지원 source type은 `dummy`, `oracle`, `h_api`, `datalake`, `goodocs`.
- 기존 Data Retriever Flow의 component 수, 번호, wiring을 그대로 구현할 필요는 없다.
- 권장 구현은 selected job이 있는 retriever만 실행하는 것이다.
- Langflow wiring 때문에 모든 retriever를 병렬 연결해야 하면, non-matching retriever의 skipped payload는 stage-local artifact로만 존재하고 merger 이후 payload에 남기지 않는다.
- merger는 skipped payload를 버리고 실제 source results만 합친다.

권장 구조:

```text
Retrieval Job Router
-> Source Adapter Dispatcher
-> Source Adapter: dummy | oracle | h_api | datalake | goodocs
-> Source Result Normalizer
-> Source Retrieval Merger
-> Retrieval Payload Adapter
```

구조 선택 원칙:

- `Intent Normalizer`가 만든 `intent_plan.retrieval_jobs`를 입력 계약으로 삼고, retriever가 사용자 질문을 다시 해석하지 않는다.
- `Retrieval Job Router`는 실행할 job과 source type만 결정한다.
- Source Adapter는 source별 connection/query/API 호출과 raw result 수집만 담당한다.
- Source Result Normalizer는 source별 raw result를 표준 `source_results[]` item으로 바꾸고 source별 조회 결과 요약을 만든다.
- Source Retrieval Merger는 source result를 합치기만 하고 업무 분석이나 pandas step을 실행하지 않는다. 병합 후 `trace.inspection.data_retrieval`에 source별 status, row_count, columns, raw data preview/ref, required/applied params, skipped reason을 남긴다.
- Retrieval Payload Adapter는 pandas가 사용할 `runtime_sources`와 compact `source_results`만 만든다.
- source별 query template, filter mapping, required params는 `table_catalog`와 source adapter 계약으로 처리하고 공통 노드에 숨기지 않는다.
- 성능이나 유지보수성을 위해 dispatcher/adapter 구조, selected-source subflow 호출, source별 독립 component 중 하나를 선택할 수 있다.
- 단, retrieval routing, source execution, result normalization, pandas prompt building, analysis execution을 하나의 component로 합치지 않는다.

`source_results[]` 표준 item:

```json
{
  "source_alias": "wip_data",
  "dataset_key": "wip_today",
  "source_type": "oracle",
  "status": "ok",
  "row_count": 120,
  "preview_rows": [],
  "pandas_filters": {},
  "applied_params": {},
  "data_ref": "",
  "source_execution": {
    "used_dummy_data": false,
    "elapsed_ms": 0
  },
  "warnings": [],
  "errors": []
}
```

Acceptance:

- dummy mode에서도 실제 source shape와 filter scope를 검증할 수 있어야 한다.
- live source retrieval은 env flag로 켜고, credential 없는 기본 상태에서는 dummy path가 안전하게 동작한다.
- retriever output은 rows와 trace를 분리한다.
- 기존 v3 retriever 구조와 달라도 `source_results[]`, `runtime_sources`, payload bloat gate 계약을 만족하면 허용한다.
- source adapter 추가 시 기존 공통 노드 수정 없이 adapter contract와 table catalog metadata 추가로 확장 가능해야 한다.
- component payload에서 `trace.inspection.data_retrieval`만 봐도 어떤 source가 실행됐고, 어떤 컬럼과 원본 preview가 왔고, 필수 parameter와 실제 적용 parameter가 무엇인지 확인할 수 있어야 한다.

### 7.4 Pandas Code Generation and Execution

기능:

- pandas prompt builder는 `intent_plan.pandas_execution_plan`, schema, source preview, output contract, selected function cases만 LLM에 준다.
- LLM은 JSON으로 code, output_columns, reasoning_steps를 반환한다.
- Pandas Code Normalizer는 LLM JSON의 code/output_columns/reasoning_steps schema를 검증한다.
- code는 self-contained이고 `sources` dict의 DataFrame만 사용한다.
- executor는 AST/security guard를 수행하고, 실제 실행한 code와 실행 결과를 `trace.inspection.pandas_execution`에 남긴다.

Acceptance:

- generated code가 missing column을 사용하면 repair 또는 clear failure로 간다.
- output columns가 plan contract와 다르면 warning 또는 repair를 남긴다.
- function case는 prompt 안내로만 들어가며 executor hidden branch가 아니다.
- generated code는 `pandas_execution_plan`의 step 순서를 reasoning_steps와 code 구조에서 추적 가능해야 한다.
- pandas LLM이 source 전체 정보를 보고 분석 순서를 새로 만들어내면 실패로 본다.
- component payload에서 `trace.inspection.pandas_execution`만 봐도 생성된 pandas code, 실행 status, 결과 columns/row_count/preview, 실패 시 error type/message/traceback summary를 확인할 수 있어야 한다.

### 7.5 Generic Step Primitive

기능:

LLM code가 실패하거나 deterministic execution이 필요한 경우, plan에 명시된 generic primitive를 실행할 수 있다.

초기 primitive:

- `filter_rows`
- `aggregate`
- `aggregate_by_group`
- `rank_top_n`
- `left_join`
- `derive_metric`
- `count_rows`
- `nunique`
- `lookup_detail`
- `compare_presence`

확장 원칙:

- 새 primitive는 recipe 이름이 아니라 operation semantics로 추가한다.
- 최소 두 개 이상의 업무/질문에 재사용 가능해야 한다.
- input/output contract를 테스트 payload로 고정한다.
- primitive fallback은 `intent_plan.step_plan`에 명시된 operation만 실행한다.
- recipe 이름, product term, output column 이름만 보고 operation을 추론하지 않는다.

### 7.6 Pandas Repair

기능:

- pandas 실행 실패 시 repair payload를 만든다.
- repair prompt에는 실패 code, error, schema, source preview, intent_plan, output contract만 포함한다.
- repair 성공 시 기존 analysis를 대체하고 repair trace를 남긴다.

Acceptance:

- repair가 필요 없는 성공 경로에서는 repair context가 커지지 않는다.
- repair 실패는 성공으로 위장하지 않는다.

### 7.7 Result Store와 Session State

기능:

- full rows는 result store에 저장하고 payload/session에는 preview와 `data_ref`만 남긴다.
- follow-up에 필요한 product key summary는 `state.current_data.product_key_values`에 유지한다.
- full previous result restore는 recalculation/detail/sort/filter가 필요한 follow-up에서만 수행한다.

Acceptance:

- "이 제품" 질문은 product key summary만으로 처리 가능해야 한다.
- full restore가 필요 없는 질문은 MongoDB loader branch를 타지 않는다.
- session state에 full rows가 반복 저장되지 않는다.

### 7.8 Final Answer와 API Response

기능:

- 현업 응답은 한국어로 간단히 제공한다.
- 결과 표는 deterministic message adapter가 `data.rows`에서 만든다.
- LLM answer는 설명 문장 중심이며, 표를 임의로 재작성하지 않는다.
- API response는 `response_type`, `data`, `applied_scope`, `state`, `developer`를 명확히 나눈다.

현업 답변 표준 shape:

```text
결론: ...

결과:
<deterministic table>

적용 조건:
- 기준일: ...
- 공정: ...
- 제품/상태 조건: ...
- 사용 데이터: ...

주의/누락 데이터:
- ...

다음에 물어볼 수 있는 질문:
- ...
```

`주의/누락 데이터`는 partial source failure, stale data, empty result reason, fallback/repair 발생 여부를 현업 언어로 짧게 설명한다. 내부 key는 숨긴다.

Acceptance:

- answer와 API response가 서로 다른 데이터를 말하지 않는다.
- applied filters/date/dataset이 trace에 남는다.
- 사용자에게 내부 key나 function case 이름을 강요하지 않는다.

### 7.9 Natural Language Metadata Authoring

기능:

- 현업 설명을 refined text로 정리한다.
- refined text를 저장 후보 item으로 변환한다.
- normalizer가 key, section, payload, condition, source_config를 정규화한다.
- duplicate/similarity checker가 기존 item과 충돌을 찾는다.
- review가 통과한 item만 writer가 upsert한다.

Acceptance:

- key가 빠진 domain item은 normalizer가 가능한 key를 backfill한다.
- source query가 빠진 Oracle table catalog는 저장하지 않고 보충 요청한다.
- duplicate action이 `ask`이면 저장하지 않는다.
- 최종 응답은 "저장했습니다" 또는 "아직 저장하지 않았습니다. 아래 정보를 더 알려주세요"처럼 현업 친화적으로 말한다.

Source onboarding 상태:

- `draft`: 자연어 등록 후보. 실제 분석에는 사용하지 않는다.
- `reviewed`: 필수 field와 중복 검토를 통과했다.
- `validated`: dry-run 또는 preview validation을 통과했다.
- `active`: main/data-analysis flow가 사용할 수 있다.

Source type별 최소 체크리스트:

| Source | 필수 입력 | Active 전 검증 |
| --- | --- | --- |
| Oracle | sample query, date column, required params, filter mappings, owner/contact | query placeholder 없음, preview rows, column mapping |
| H-API | endpoint, required params, auth placeholder, sample response schema | dry-run/mock response, timeout/error mapping |
| Datalake | query or notebook/cluster path, user id placeholder, required params | preview rows, execution timeout |
| Goodocs | doc id, sheet/table range, required columns | preview rows, column mapping |
| Dummy | fixture generator rule, dataset shape | deterministic sample rows |

## 8. Prompt 설계 정책

Prompt는 stage별로 작고 명확해야 한다.

### 8.1 Intent Prompt

포함:

- question
- compact state summary
- relevant metadata summary
- allowed intent/analysis kinds
- output JSON schema
- examples as weak guidance

제외:

- source full rows
- previous full payload
- 모든 metadata 원본
- 특정 key 이름에 대한 hard dependency

### 8.2 Pandas Prompt

포함:

- intent_plan
- intent_plan.pandas_execution_plan
- source schema and row preview
- output contract
- selected function cases only
- safety rules

제외:

- hidden helper import
- unrelated function cases
- answer-writing instruction
- domain authoring instruction
- "주어진 데이터를 자유롭게 분석해서 알아서 답을 만들라"는 open-ended instruction
- 의도 분석에서 확정하지 않은 join/filter/group/metric을 pandas prompt에서 새로 만들게 하는 instruction

규칙:

- pandas prompt의 최상위 지시는 `pandas_execution_plan`을 순서대로 실행하는 것이다.
- source preview와 schema는 code 작성에 필요한 재료일 뿐이며, 분석 순서 결정의 주체가 아니다.
- `pandas_execution_plan`과 source schema가 충돌하면 code LLM은 임의 보정 대신 conflict를 반환하도록 유도한다.

### 8.3 Answer Prompt

포함:

- compact result summary
- rows preview
- applied scope
- warnings/errors

제외:

- full runtime_sources
- pandas code 전문
- source credential/config

## 9. Fallback/Clarification 정책

Fallback priority:

1. LLM output normalization.
2. Metadata-backed plan correction.
3. Generic primitive execution.
4. Pandas repair.
5. Clarification request.
6. Safe failure response.

Clarification이 필요한 경우:

- product token이 여러 컬럼/제품군에 걸쳐 애매하다.
- "이 제품" follow-up인데 이전 product key summary가 없다.
- source query/API config가 등록되지 않았다.
- 필수 filter value가 빠졌다.
- 보안상 credential이나 secret이 자연어 입력에 포함됐다.

Clarification response contract:

```text
바로 조회하기 전에 한 가지만 확인할게요.

제가 이해한 조건:
- ...

확인이 필요한 부분:
- ...

선택:
1. ...
2. ...
3. ...
```

규칙:

- 한 번에 하나의 핵심 결정만 묻는다.
- 내부 key, dataset key, function-case 이름을 보여주지 않는다.
- 가능한 선택지를 2~4개로 제시한다.
- 사용자가 답하면 기존 session state와 합쳐 다시 route/plan을 만든다.

## 10. 검증 설계

검증은 숫자 정답만 보지 않는다.

대표 질문 기준은 `docs/VALIDATION_QUESTIONS_AND_EXPECTED_BEHAVIOR.md`를 canonical matrix로 사용한다. 모든 regression case는 final answer text보다 먼저 plan/scope/schema를 assertion해야 한다.

검증해야 하는 항목:

- route
- intent type
- analysis kind
- dataset selection
- retrieval job count and source type
- date scope
- filters by source
- group_by
- metric formula
- step plan order
- pandas_execution_plan completeness and order
- pandas code JSON validity
- result columns
- row count
- applied scope
- fallback/repair 발생 여부
- session state compactness
- final API contract
- intent/data retrieval/pandas execution inspection 존재 여부와 가독성

### 10.1 Local Gate

```powershell
python -m compileall -q reference_runtime langflow_components tools tests
python -m pytest tests -q
python tools\validate_regression.py
python tools\upload_json_to_mongodb.py --dry-run
python tools\validate_service_readiness.py --skip-live-llm
```

### 10.2 Representative Question Gate

최소 smoke set:

- DA/WB 공정별 재공 top 3 + 오늘 생산량 join
- 특정 LOT HOLD 이력
- 현재 hold lot list
- DA 재공 top product
- "이 제품" 설비 현황 follow-up
- LPDDR5 W/B 생산량 + 재공
- 생산/재공/목표/달성률
- 목표 대비 저조 제품
- 작업대기 Lot 수량
- 어제 생산량 vs 오늘 계획 차이

각 질문은 결과 숫자보다 먼저 plan과 scope가 맞아야 한다. `7.2 Intent Planning`의 대표 질문별 plan pattern은 regression expected contract의 seed로 사용한다.

각 질문별 expected contract는 별도 matrix에 최소 아래를 포함한다.

- expected route
- expected datasets
- expected source filters/date scope
- expected step order
- expected pandas_execution_plan
- expected group_by
- expected output columns
- expected state behavior
- forbidden fallback/repair

### 10.3 Live Gate

운영 환경에서만 실행한다.

```powershell
python tools\validate_env.py
python tools\validate_gemini_connection.py
python tools\validate_component_llm_flow.py
python tools\validate_llm_in_loop.py --limit 1
python tools\validate_llm_in_loop.py
```

live source system은 별도 flag로 활성화한다.

```dotenv
RUN_LIVE_SOURCE_RETRIEVAL=true
```

### 10.4 Payload Bloat Gate

대표 질문마다 stage payload를 capture하고 아래를 검사한다.

- prompt wrapper가 downstream payload로 흐르지 않는가.
- rows가 2곳 이상 full copy되지 않는가.
- `runtime_sources`가 answer/API 이후 제거 또는 ref화되는가.
- top-level `retrieval_jobs` mirror가 없는가.
- session state가 compact한가.
- developer trace가 현업 response와 분리되어 있는가.
- `trace.inspection.intent`, `trace.inspection.data_retrieval`, `trace.inspection.pandas_execution`이 존재하는가.
- intent inspection이 normalized intent, 판단 이유, pandas 처리 계획을 포함하는가.
- data retrieval inspection이 source별 컬럼, raw data preview/ref, required/applied params를 포함하는가.
- pandas execution inspection이 generated code, execution result, 실패 시 error summary를 포함하는가.
- inspection block이 full prompt/full metadata/full source rows 전체 dump를 포함하지 않는가.

Payload report contract:

```json
{
  "case_id": "multi_step_wip_rank_production_join",
  "status": "pass",
  "stage_reports": [
    {
      "stage": "13_retrieval_payload_adapter",
      "byte_size": 24000,
      "top_level_keys": ["request", "state", "intent_plan", "source_results", "runtime_sources"],
      "full_row_locations": ["runtime_sources.wip_data"],
      "prompt_payload_leaked": false,
      "duplicate_row_copy_count": 0,
      "inspection_paths": ["trace.inspection.data_retrieval"],
      "inspection_bytes": 1800,
      "violations": []
    }
  ],
  "session_state_bytes": 12000,
  "violations": []
}
```

Release blocker:

- `prompt_payload_leaked=true`
- `duplicate_row_copy_count > 0`
- final API에 `runtime_sources` 존재
- session state 128KB 초과
- top-level `retrieval_jobs` mirror 존재
- `developer/debug` duplicate 존재
- required `trace.inspection.*` 누락
- `trace.inspection` 32KB 초과 또는 full prompt/full metadata/full source rows 전체 포함

### 10.5 UX and Negative Regression Gate

현업/관리자 UX regression:

- key 없이 자연어 domain 등록이 가능하다.
- 중복 항목은 한국어 검토 카드와 선택지를 반환한다.
- Oracle query가 빠진 table catalog는 저장하지 않고 보충 요청한다.
- secret/token/password가 입력되면 저장하지 않고 redaction warning을 반환한다.
- "이 제품" 질문인데 이전 context가 없으면 내부 key 없이 확인 요청을 반환한다.
- ambiguous product token은 POP류 조건을 임의 주입하지 않고 확인 요청 또는 generic lookup으로 간다.

Negative regression:

- ambiguous product token must not inject POP/product-domain filters.
- registered product terms must not be routed into function-case matching unless explicitly required.
- output column names alone must not trigger domain fallback.
- recipe name alone must not trigger executor behavior without explicit `step_plan`.
- pandas code generation must not ignore `pandas_execution_plan`.
- examples must not act as hard triggers.

### 10.6 Requirement Coverage Table

| Requirement | Expected contract | Test/tool | Gate | Blocker |
| --- | --- | --- | --- | --- |
| Standalone component | no sibling import, unique IO, parser init, sample payload run | component contract tests | local/staging | yes |
| Router envelope | valid route/api/session/input and normalized response | router contract tests | local/staging | yes |
| Payload compactness | no prompt leak, no duplicate rows, bounded state | payload bloat report | local/staging/prod | yes |
| Metadata authoring | natural-language in, review before write | authoring flow tests | local/staging | yes |
| Product-token safety | no unrelated POP/filter injection | negative regression | local/staging/prod | yes |
| Primitive fallback | only explicit step_plan operations | primitive fixture tests | local/staging | yes |
| Regression questions | plan/scope/schema before answer text | validation matrix | local/staging/prod | yes |
| Live LLM | intent/code/answer paths work with real model | `--require-live-llm` | staging/prod | prod yes |
| Live source | source credentials and timeout/error behavior verified | source live validation | prod | prod yes |

### 10.7 Release Gate Matrix

| Gate | 목적 | 필수 명령/증거 | Live 허용 범위 | Production blocker |
| --- | --- | --- | --- | --- |
| Local preflight | 구조/계약/로컬 회귀 확인 | compileall, pytest, regression, Mongo dry-run, payload bloat report | `--skip-live-llm` 허용 | local only |
| Staging release | 실제 LLM과 대표 source 검증 | `validate_service_readiness.py --require-live-llm`, representative LLM, source mock/live preview | live LLM 필수, source는 representative | yes |
| Production cutover | 운영 환경에서 서비스 준비 확인 | full regression, live source validation, env validation, Mongo collection/index check, rollback plan | live LLM/source 필수 | yes |

`--skip-live-llm`은 local preflight에서만 허용한다. staging 또는 production에서 "서비스 준비 완료"라고 말하려면 `--require-live-llm`과 live source validation evidence가 필요하다.

## 11. 구현 단계

### Phase 0. Rebuild 기준 확정

산출물:

- 이 기능 설계도
- canonical payload schema 초안
- validation question matrix
- component boundary checklist

완료 조건:

- 설계 문서가 architecture, usability, QA 관점 검토를 통과한다.

### Phase 1. Minimal Runtime Skeleton

구현:

- router flow
- session state loader/writer
- metadata QA minimal
- data analysis request/response skeleton
- API response contract

완료 조건:

- standalone component parser 통과
- metadata QA와 data analysis route 분리 검증

### Phase 2. Metadata Loading and Authoring

구현:

- domain/table/filter metadata loader
- natural-language authoring flows
- duplicate/similarity/review/writer
- key backfill

완료 조건:

- 사용자가 key를 쓰지 않아도 domain item 저장 가능
- 부족 입력은 저장하지 않고 보충 요청
- MongoDB dry-run shape 통과

### Phase 3. Data Retrieval

구현:

- `intent_plan.retrieval_jobs`
- dummy/oracle/h_api/datalake/goodocs retrievers
- source merger and retrieval adapter

완료 조건:

- dummy path에서 source별 filter/date scope 검증
- skipped source branch가 downstream을 막지 않음

### Phase 4. Intent + Pandas Runtime

구현:

- intent prompt/normalizer
- recipe matching
- pandas prompt/executor
- generic primitive executor
- repair branch

완료 조건:

- 대표 regression 질문 plan/scope/result contract 통과
- specialized function case가 prompt block으로만 주입됨
- executor에 새 domain-specific branch 없음

### Phase 5. Result Store + Follow-Up

구현:

- result store
- data_ref
- product key summary
- previous result restore mode
- follow-up scope reset

완료 조건:

- "이 제품" follow-up 가능
- "전체 재공 수량"은 이전 DA filter를 상속하지 않음
- session state full row copy 없음

### Phase 6. Service Hardening

구현:

- validation service script
- payload capture report
- live LLM gate
- source live gate
- operator/developer docs

완료 조건:

- local gate 통과
- representative live gate 통과
- 운영자가 읽을 수 있는 wiring guide 완성

## 12. 금지 패턴

아래 패턴이 보이면 재구현 품질 실패로 본다.

- 하나의 거대한 main canvas에 모든 기능을 다시 몰아넣음.
- 공통 노드가 DA/WB/HBM/POP 같은 단어로 직접 분기함.
- 특정 질문 하나를 executor fallback으로 맞춤.
- LLM prompt가 예시를 hard trigger처럼 사용함.
- payload에 같은 rows가 여러 key로 반복됨.
- answer LLM이 표를 임의 생성하고 deterministic adapter가 검증하지 않음.
- pandas code LLM에 source 정보만 주고 분석 순서와 처리 계획을 알아서 만들게 함.
- `intent_plan.pandas_execution_plan` 없이 join/filter/group/metric logic을 pandas prompt나 executor에서 새로 해석함.
- metadata authoring에서 사용자가 internal key를 알아야 저장됨.
- review 실패나 ambiguity를 조용히 성공으로 처리함.
- validation이 final Korean answer 문자열만 검사함.

## 13. 서비스 준비 완료 기준

문서 기준으로 "서비스 구현 가능"이라고 판단하려면 아래가 모두 가능해야 한다. 실제 release 판단은 `10.7 Release Gate Matrix`를 따른다.

| 영역 | 기준 |
| --- | --- |
| Architecture | router/subflow split이 명확하고 common/specialized 경계가 분리됨 |
| Payload | canonical key와 stage별 소유자가 명확함 |
| Metadata | 현업 자연어 authoring으로 domain/table/filter/function-case 등록 가능 |
| Analysis | metadata recipe + generic primitive 중심으로 plan 실행 가능 |
| Fallback | 숨은 hardcode가 아니라 clarification/repair/safe failure 중심 |
| UX | 현업 사용자가 key/schema/function-case를 몰라도 사용 가능 |
| Validation | local, regression, payload bloat, live gate가 분리됨 |
| Operations | env, MongoDB, source retrieval, result store, session state가 문서화됨 |

운영 증거 checklist:

- required env vars와 secret redaction 정책
- MongoDB database/collection/index 목록
- MongoDB metadata dry-run document counts
- result store retention/cleanup 정책
- source별 timeout/retry/error mapping
- live source validation report path
- LLM validation report path
- payload bloat report path
- rollback 또는 feature flag plan
- 알려진 residual risk 목록

## 14. Sub-Agent Review Log

역할별 sub-agent 검토와 반영 상태다.

| Role | Focus | Result |
| --- | --- | --- |
| Architecture Reviewer | Langflow split, standalone, payload contract, common/specialized boundary | Revised: standalone deployment mode, router envelope, retriever drop rule, function-case boundary, payload thresholds added |
| Manufacturing UX Reviewer | 현업 자연어 사용성, authoring friction, answer/clarification 품질 | Revised: single authoring entrypoint, review card, duplicate labels, clarification contract, answer trust cues added |
| QA Reviewer | acceptance criteria, validation gates, regression coverage, release risk | Revised: validation matrix reference, payload report contract, UX/negative regression, coverage table, release gate matrix, ops checklist added |

## 15. 다음 구현자가 가장 먼저 볼 체크리스트

- 공통 노드를 만들기 전에 "이 로직이 다른 제조 공정에도 그대로 맞는가"를 확인한다.
- 특화 조건은 metadata로 먼저 표현한다.
- metadata로 어렵다면 function case로 표현하고 prompt input으로만 주입한다.
- 그래도 어렵고 여러 업무에서 재사용될 때만 generic primitive를 추가한다.
- payload에 rows를 추가할 때는 "언제 제거되거나 ref로 바뀌는가"를 같이 설계한다.
- fallback을 추가할 때는 "이 fallback이 실패를 숨기는가"를 테스트한다.
- 검증 질문은 final answer보다 plan/scope/schema를 먼저 검사한다.
