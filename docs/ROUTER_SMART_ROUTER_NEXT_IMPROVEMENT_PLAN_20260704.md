# Router Smart Router 추가 개선 계획 2026-07-04

## 1. 목표와 전제

이번 개선은 `router_flow`를 API 라우터가 아니라 **Langflow Smart Router 중심의 분기 flow**로 구체화하는 작업이다.

반드시 지킬 전제는 아래와 같다.

- Router는 사용자의 질문을 보고 어떤 flow로 보낼지만 판단한다.
- 제품 token 매핑, pandas function case 선택, 공정별 제조 해석은 `data_analysis_flow` 안에서 처리한다.
- `Run Flow`는 flow 이름을 변수로 받아 실행하는 방식이 아니므로, route마다 대상 flow가 미리 선택된 `Run Flow` 노드를 둔다.
- 메타데이터 저장 원문은 router에서 변형하지 않는다.
- dummy flow는 빠른 연결 테스트용이지만, 실제 flow가 반환하는 응답 형태를 충분히 닮아야 한다.
- metadata QA는 저장 flow가 아니라 읽기 전용 질의응답 flow다.

참고한 Langflow 공식 문서 기준:

- Smart Router는 route table의 각 route마다 output port를 만들고, `Route Message`가 비어 있으면 원래 입력을 route output으로 전달한다.
- `Route Description`은 router가 route를 고를 때 참고하는 설명이고, `Route Message`는 route가 선택된 뒤 downstream으로 나가는 메시지다.
- If-Else 예시는 branch마다 별도 처리 체인과 `Chat Output`을 두는 방식을 보여준다.
- `Chat Output`은 `Message`, `JSON`, `Table` 입력을 받을 수 있다.
- `Run Flow`는 대상 flow를 선택하면 그 flow 구조를 기준으로 입력/출력 포트가 동적으로 열린다.
- `Notify/Listen`은 단일 최종 출력으로 branch 결과를 모아야 할 때 후보가 될 수 있으나, 실제 Langflow Desktop 버전에서 사용 가능 여부를 확인해야 한다.

## 2. 서브에이전트별 초안

| 담당 | 제안 요약 | 핵심 근거 |
| --- | --- | --- |
| Router/Smart Router 담당 | direct answer, clarification, error를 별도 flow로 만들지 않는다. direct/clarification은 Smart Router message branch로 처리하고, error는 route가 아니라 실행 결과 상태로 다룬다. | Router가 런타임 오류를 사용자 의도처럼 분기하면 의미가 섞인다. flow route의 `Route Message`를 채우면 원문 질문이 Run Flow로 가지 않는다. |
| Dummy Flow 담당 | dummy는 질문 echo가 아니라 실제 data analysis/metadata QA/saving flow의 응답 계약을 닮은 fixture형 응답을 반환한다. | 단순 echo로는 Router 연결만 확인되고 Web/Playground 표, developer 진단, state, API 계약 검증이 안 된다. |
| Metadata QA 담당 | `metadata_qa_flow`를 새로 만들고 MongoDB의 domain/table catalog/main filter 3 collection만 읽어 서비스형 답변을 만든다. | data analysis flow를 재사용하면 retrieval/pandas/result-store까지 불필요하게 탄다. 전체 metadata/raw trace를 LLM에 넣으면 token 낭비와 노출 위험이 크다. |

## 3. 상호 비판과 최종 판단

### 3.1 Router 담당이 Dummy/Metadata QA 설계에 제기한 비판

- dummy flow가 실제 분석 로직까지 흉내 내면 개발용 fast route의 목적을 잃는다.
- metadata QA가 Router 안에서 metadata를 직접 해석하기 시작하면 Router boundary가 무너진다.
- Router는 “metadata_qa로 보낼지”만 판단하고, metadata 해석과 답변 품질은 `metadata_qa_flow`가 책임져야 한다.

### 3.2 Dummy 담당이 Router 설계에 제기한 비판

- Router가 공통 응답 flow를 만들면 각 subflow가 이미 가진 `message`/`api_response` 계약과 중복된다.
- dummy flow는 Router가 아니라 각 원본 flow의 응답 형태를 닮아야 실제 Run Flow 연결 검증에 도움이 된다.

### 3.3 Metadata QA 담당이 Router/Dummy 설계에 제기한 비판

- metadata QA dummy도 실제 QA 응답처럼 `metadata_qa.items`, `data.rows`, `source_refs`를 보여줘야 route 연결 검증이 된다.
- metadata QA route description에 생산량/재공 같은 단어가 들어가더라도 “실제 데이터 값을 물어보는 질문”은 `data_analysis`로 가야 한다.

### 3.4 최종 판단

1. direct answer, clarification, error는 **별도 flow로 만들지 않는다**.
2. direct/clarification은 Smart Router의 `Route Message` 또는 `Else Message`로 처리한다.
3. Web/API 구조화 응답은 Router가 새로 감싸지 않고, 실제 실행된 각 subflow의 기존 `message`/`api_response` 계약을 그대로 사용한다.
4. `flow_error`는 Smart Router route table에 넣지 않는다. 각 subflow가 `status=error`, `errors`, `message`를 반환하고 Web/Playground에서 그대로 보여준다.
5. saving route는 이미 domain/table catalog/main filter flow가 분리되어 있으므로, 이 구조를 유지한다.
6. 단일 Chat Output이 꼭 필요할 때만 `Notify/Listen` 또는 별도 collector를 검토한다. 기본은 branch별 Chat Output이다.

## 4. 항목별 개선 계획

## 4.1 Direct Answer / Clarification / Error 응답 구조

### 추천 구조

direct/clarification/error용 별도 flow는 만들지 않는다.
이유는 이미 실제 실행 대상 flow들이 `message`와 `api_response` 형식을 책임지고 있고, Router에서 다시 공통 응답 flow로 감싸면 계약이 중복되기 때문이다.

Router는 아래 역할만 가진다.

| 구분 | 처리 방식 | 비고 |
| --- | --- | --- |
| direct_answer | Smart Router `Route Message`를 Chat Output으로 바로 연결 | 인사, 사용 범위 안내처럼 별도 flow 실행이 필요 없는 경우 |
| clarification | Smart Router `Else Message` 또는 `clarification` route message를 Chat Output으로 바로 연결 | 질문이 분석/QA/등록 중 무엇인지 불명확한 경우 |
| flow_error | route로 만들지 않음 | 실행된 subflow의 오류 응답을 그대로 표시 |

Web/API에서 direct/clarification을 구조화해서 보여줘야 하는 경우에도 Router flow 안에 새 component를 추가하지 않는다.
필요하면 Web parser 또는 호출 계층에서 `route=clarification`, `message=<텍스트>`를 `response_type=clarification`처럼 얇게 해석한다.
실제 flow 응답의 구조화는 각 flow 끝단의 API 응답 생성기가 책임진다.

### Router canvas 연결

기본 연결:

```text
Chat Input
  -> Smart Router.Input

Smart Router.direct_answer
  -> Chat Output(direct)

Smart Router.clarification 또는 Else
  -> Chat Output(clarification)
```

direct/clarification은 Route Message/Else Message를 반드시 채운다.
반대로 실제 flow를 실행해야 하는 route는 Route Message를 비워 원문 질문이 Run Flow로 그대로 전달되게 한다.

### Error 처리

`flow_error`는 Smart Router route가 아니다.
오류는 아래 위치에서 처리한다.

- `data_analysis_flow`: 기존 `status=error`, `trace.errors`, `message` 계약 사용
- `metadata_qa_flow`: 새 flow의 API 응답 생성기에서 `status=error`, `trace.errors`, `message` 반환
- saving flows: 기존 authoring API adapter의 오류 응답 사용
- dummy flows: 실제 저장/조회 실패처럼 보이지 않도록 `status=ok` 또는 `status=skipped`와 경고만 사용

## 4.2 Dummy Flow 응답 개선

### 현재 문제

현재 dummy flow는 `response_type`, `status`, `message` 같은 최소 키는 있으나 실제 flow의 답변 형태와 차이가 있다.

보완해야 할 부분:

- 대표 질문별 실제 답변처럼 보이는 `answer_message`
- Playground용 `display_message` 또는 `message`의 markdown 구조
- 결과 테이블 `data.columns`, `data.rows`, `data.row_count`
- `intent_plan.retrieval_jobs`
- `intent_plan.pandas_execution_plan`
- `analysis.status`, `analysis.row_count`, `analysis.columns`
- `trace.inspection.intent`
- `trace.inspection.data_retrieval`
- `trace.inspection.pandas_execution`
- `state.current_data`

### 구현 방향

dummy는 실제 LLM/pandas를 실행하지 않는다.
대신 대표 질문별 fixture를 둔다.

우선 fixture 후보:

1. `RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘`
2. `전일 L-218K8H 제품의 SBM공정에서 생산 실적 알려줘`
3. `등록된 생산량 관련 도메인 정보 보여줘`
4. `POP 제품 도메인 정보가 어떻게 등록되어 있어?`
5. `테이블 카탈로그 더미 등록 요청`

`dummy_data_analysis_flow`는 질문에 핵심 token이 매칭되면 해당 fixture를 반환하고, 매칭되지 않으면 generic fixture를 반환한다.

예상 응답 구조:

```json
{
  "response_type": "data_analysis",
  "status": "ok",
  "answer_message": "RG 32G DDR4 FBGA 96 DDP 제품의 BG공정 기준 생산량은 18.4K, 재공수량은 9,850입니다.",
  "display_message": "### 답변\nRG 32G DDR4 FBGA 96 DDP 제품의 BG공정 기준 생산량은 18.4K, 재공수량은 9,850입니다.\n\n### 결과 테이블\n| 제품 | 공정 | 생산량 | 재공수량 |\n| --- | --- | ---: | ---: |\n| RG 32G DDR4 FBGA 96 DDP | BG | 18.4K | 9,850 |",
  "intent_plan": {
    "analysis_kind": "production_wip_by_product_process",
    "retrieval_jobs": [
      {"dataset_key": "production_today", "source_alias": "production_data"},
      {"dataset_key": "wip_today", "source_alias": "wip_data"}
    ],
    "pandas_execution_plan": [
      {"step": "제품 token 매핑 조건 적용"},
      {"step": "BG 공정 필터 적용"},
      {"step": "생산량과 재공수량 집계"}
    ]
  },
  "data": {
    "columns": ["제품", "공정", "생산량", "재공수량"],
    "rows": [
      {"제품": "RG 32G DDR4 FBGA 96 DDP", "공정": "BG", "생산량": 18400, "재공수량": 9850}
    ],
    "row_count": 1
  }
}
```

주의:

- dummy가 실제 MongoDB에 저장했다고 표현하지 않는다.
- dummy data_ref는 클릭 가능한 실제 링크처럼 속이지 않는다.
- `trace.inspection.result_store.status=skipped`처럼 명확히 남긴다.
- saving dummy는 `dry_run=true`, `saved_count=0`, `would_save_count`를 사용한다.

## 4.3 Metadata QA Flow 구현 계획

### 새 flow 위치

```text
langflow_components/
  metadata_qa_flow/
    00_metadata_qa_request_loader.py
    01a_mongodb_domain_metadata_loader.py
    01b_mongodb_table_catalog_loader.py
    01c_mongodb_main_filter_loader.py
    02_metadata_qa_context_builder.py
    03_metadata_qa_variables_builder.py
    03_metadata_qa_prompt_template_ko.md
    04_metadata_qa_response_normalizer.py
    05_metadata_qa_message_adapter.py
    06_metadata_qa_api_response_builder.py
    CONNECTION_GUIDE.md
```

### 노드별 역할

| 번호 | 노드 | 역할 |
| --- | --- | --- |
| 00 | 메타데이터 QA 요청 로더 | 질문과 state를 payload로 만든다. 쓰기 동작 없음 |
| 01A | 도메인 메타데이터 로더 | `agent_v4_domain_items` 읽기 |
| 01B | 테이블 카탈로그 로더 | `agent_v4_table_catalog_items` 읽기 |
| 01C | 메인 필터 로더 | `agent_v4_main_flow_filters` 읽기 |
| 02 | QA 컨텍스트 생성기 | 질문에 관련된 metadata만 선별하고 raw trace 제거 |
| 03 | 프롬프트 변수 생성기 | Prompt Template에 넣을 변수 생성 |
| 03P | Prompt Template | 한국어 기반 metadata QA 지시문 |
| LLM | Langflow Agent/LLM | 답변 JSON 생성 |
| 04 | 응답 정규화기 | JSON 파싱, 없는 정보 제거, 표 데이터 정리 |
| 05 | 메시지 어댑터 | Playground용 markdown 메시지 생성 |
| 06 | API 응답 생성기 | Web/API용 `api_response` 생성 |

### MongoDB 읽기 대상

```text
MONGODB_DATABASE=datagov
MONGODB_DOMAIN_COLLECTION=agent_v4_domain_items
MONGODB_TABLE_CATALOG_COLLECTION=agent_v4_table_catalog_items
MONGODB_MAIN_FLOW_FILTER_COLLECTION=agent_v4_main_flow_filters
```

`MONGODB_RESULT_COLLECTION`은 사용하지 않는다.
metadata QA는 조회/답변 flow이므로 result store에 쓰지 않는다.

### LLM에 전달할 context

전체 문서를 그대로 넣지 않는다.
아래 값만 압축해서 전달한다.

```json
{
  "load_summary": {},
  "matched_domain_items": [],
  "matched_datasets": [],
  "matched_filters": [],
  "source_refs": []
}
```

제외할 값:

- `raw_trace`
- `registration_trace.raw_text`
- `llm_response`
- `write_result`
- `existing_matches`
- 전체 MongoDB dump
- API key, password, token, Mongo URI

### 지원할 대표 질문

| 질문 유형 | 답변 방식 |
| --- | --- |
| 생산량 관련 도메인 정보 보여줘 | 생산량 metric/domain item 요약 + aliases/table |
| 등록된 계산 로직 list 보여줘 | `analysis_recipes`, `metric_terms`, `pandas_function_cases` 표 |
| 생산량 데이터 관련 query SQL 알려줘 | 관련 dataset의 `query_template` 코드 블록 + 필수 파라미터 표 |
| 조회 가능한 데이터와 연결 방식/필수 조건 알려줘 | dataset list table |
| POP 제품 도메인 정보 보여줘 | domain item 조건을 말로 설명 + 조건 표 |

### 응답 계약

```json
{
  "response_type": "metadata_qa",
  "status": "ok",
  "direct_response_ready": true,
  "message": "한국어 답변 markdown",
  "answer_message": "한국어 답변 markdown",
  "metadata_route": {
    "route": "metadata_qa",
    "answer_mode": "dataset_sql",
    "confidence": "high"
  },
  "metadata_qa": {
    "summary": "요약",
    "items": [],
    "source_refs": []
  },
  "data": {
    "columns": [],
    "rows": [],
    "row_count": 0
  },
  "state": {},
  "trace": {
    "warnings": [],
    "errors": []
  }
}
```

### Router 연결

```text
Smart Router.metadata_qa
  -> Run Flow(metadata_qa_flow).질문 입력
  -> Run Flow(metadata_qa_flow).message
  -> Chat Output(metadata_qa)
```

Web/API에서 구조화 응답을 확인해야 한다면 `metadata_qa_flow.06 API 응답 생성기.api_response`도 output으로 노출한다.

### Metadata QA dummy flow

metadata QA도 다른 flow들과 마찬가지로 실제 flow와 dummy flow를 분리해서 둔다.

```text
langflow_components/
  dummy_metadata_qa_flow/
    00_dummy_metadata_qa_request_loader.py
    01_dummy_metadata_qa_response_builder.py
    CONNECTION_GUIDE.md
```

현재 `dummy_metadata_qa_flow`가 있으면 새로 중복 생성하지 않고, 실제 `metadata_qa_flow`의 응답 계약과 맞게 보강한다.
없다면 위 구조로 생성한다.

dummy metadata QA는 MongoDB를 읽지 않는다.
대신 아래 질문에 대해 실제 metadata QA가 반환할 법한 markdown 답변, `metadata_qa.items`, `data.rows`, `source_refs`를 fixture로 반환한다.

- `생산량과 관련해서 등록된 도메인 정보들 보여줄래?`
- `지금 등록된 계산 로직들이 어떤 것들이 있는지 list 보여줘.`
- `생산량 데이터 관련 쿼리문은 어떤 건지 알려줘.`
- `지금 조회 가능한 데이터들이 뭐가 있고 각 데이터의 연결방식과 필수 조건은 뭐야?`
- `POP 제품은 도메인 정보가 어떻게 등록되어 있어?`

Router 연결:

```text
Smart Router.dummy_metadata_qa
  -> Run Flow(dummy_metadata_qa_flow).질문 입력
  -> Run Flow(dummy_metadata_qa_flow).message
  -> Chat Output(dummy_metadata_qa)
```

## 4.4 Chat Output 연결 방식

### 기본 추천: branch별 Chat Output

Smart Router 또는 If-Else 계열 분기는 선택된 branch만 실행되는 구조이므로, 가장 단순한 연결은 branch마다 Chat Output을 두는 것이다.

```text
Run Flow(data_analysis_flow).message
  -> Chat Output(data_analysis)

Run Flow(metadata_qa_flow).message
  -> Chat Output(metadata_qa)

Smart Router.direct_answer
  -> Chat Output(direct)

Smart Router.clarification 또는 Else
  -> Chat Output(clarification)
```

장점:

- 연결이 눈에 잘 보인다.
- 선택되지 않은 branch와 merge 대기 문제가 없다.
- Langflow 예시와 가장 유사하다.
- route 추가 시 `Run Flow + Chat Output`만 추가하면 된다.

### 단일 Chat Output이 꼭 필요한 경우

우선순위:

1. Langflow 버전에서 `Notify/Listen`이 안정적으로 동작하면 branch 끝을 `Notify`로 보내고 `Listen -> Chat Output`으로 모은다.
2. `Notify/Listen`이 없거나 불안정하면 branch별 Chat Output을 유지한다.
3. custom collector는 마지막 선택지로 둔다. 선택되지 않은 branch 입력을 기다리는 문제가 생길 수 있으므로, 실제 canvas에서 smoke test 후에만 사용한다.

단일 Chat Output 후보 연결:

```text
Run Flow(data_analysis_flow).message
  -> Notify(router_response, status=data_analysis)

Run Flow(metadata_qa_flow).message
  -> Notify(router_response, status=metadata_qa)

Smart Router.direct_answer
  -> Notify(router_response, status=direct_answer)

Smart Router.clarification 또는 Else
  -> Notify(router_response, status=clarification)

Listen(router_response)
  -> Chat Output
```

## 5. 순차 구현 계획

### Phase 0. 현재 기준 고정

1. `router_flow/CONNECTION_GUIDE.md`를 route-flow map까지 포함한 단일 기준 문서로 UTF-8 정리한다.
2. Smart Router routes table 기준을 확정한다.
3. `Run Flow` 대상 flow는 변수 입력이 아니라 노드 설정에서 미리 선택한다는 내용을 다시 명시한다.

검증:

```powershell
python -m pytest -q tests\test_langflow_components.py tests\test_web_app_v4_contracts.py
python -m compileall -q langflow_components web_app tests
```

### Phase 1. Router direct/clarification 연결 정리

1. `router_system_response_flow`는 만들지 않는다.
2. `direct_answer`는 Smart Router `Route Message -> Chat Output`으로 바로 연결한다.
3. `clarification`은 Smart Router `Else Message` 또는 `clarification Route Message -> Chat Output`으로 바로 연결한다.
4. `flow_error`는 Router route table에 넣지 않고, 실행된 subflow의 오류 응답을 그대로 표시한다.
5. `CONNECTION_GUIDE.md`에 direct/clarification branch 연결을 그림처럼 서술한다.

검증:

- direct answer 질문이 별도 Run Flow 없이 안내 메시지를 반환한다.
- 모호한 질문이 별도 Run Flow 없이 추가 질문 요청 메시지를 반환한다.
- subflow error는 router가 다른 route로 바꾸지 않고 원래 error를 보여준다.

### Phase 2. Dummy flow 응답 현실화

1. `dummy_data_analysis_flow`에 대표 질문 fixture를 추가한다.
2. `dummy_metadata_qa_flow`는 실제 metadata QA 답변 형태 fixture를 반환하도록 보강한다.
3. dummy saving flows는 저장 성공처럼 보이지 않도록 `dry_run/skipped/would_save_count`를 명확히 한다.

검증:

- dummy flow가 question echo가 아니라 markdown 답변과 표를 반환한다.
- Web parser가 `display_message`, `data`, `developer` 정보를 정상 표시한다.
- MongoDB collection count가 변하지 않는다.

### Phase 3. Metadata QA flow 구현

1. `metadata_qa_flow` 폴더를 새로 만든다.
2. Mongo loader 3종을 읽기 전용으로 구현한다.
3. context builder에서 관련 metadata만 선별한다.
4. Prompt Template + Langflow Agent/LLM 연결을 기준으로 변수 생성기를 만든다.
5. 응답 정규화기, 메시지 어댑터, API 응답 생성기를 추가한다.
6. `dummy_metadata_qa_flow`와 출력 계약을 맞춰 Router에서 실제/더미 route를 교체해도 Chat Output과 Web/API 표시가 깨지지 않게 한다.

검증 질문:

```text
생산량과 관련해서 등록된 도메인 정보들 보여줄래?
지금 등록된 계산 로직들이 어떤 것들이 있는지 list 보여줘.
생산량 데이터 관련 쿼리문은 어떤 건지 알려줘.
지금 조회 가능한 데이터들이 뭐가 있고 각 데이터의 연결방식과 필수 조건은 뭐야?
POP 제품은 도메인 정보가 어떻게 등록되어 있어?
```

### Phase 4. Smart Router canvas 연결 문서 보강

1. `router_flow/CONNECTION_GUIDE.md`에 route별 정확한 연결을 적는다.
2. 각 route output이 어떤 `Run Flow`의 어떤 input으로 들어가는지 표로 적는다.
3. branch별 Chat Output 방식과 단일 Chat Output 대안을 둘 다 적는다.
4. Route Description과 Route Message 차이를 문서에 명시한다.

### Phase 5. 통합 검증

검증 시나리오:

| 입력 | 기대 route | 기대 결과 |
| --- | --- | --- |
| 오늘 DA공정 생산량 알려줘 | data_analysis | data analysis flow 실행 |
| 생산량 관련 도메인 정보 보여줘 | metadata_qa | metadata QA 답변 |
| POP 제품 조건 등록해줘 | domain_saving | domain 저장 flow 실행 |
| 더미 분석으로 연결 테스트 | dummy_data_analysis | 빠른 dummy 응답 |
| 무슨 말인지 모르겠어 | clarification | 추가 질문 요청 |

자동 검증:

```powershell
python -m pytest -q
python -m compileall -q langflow_components web_app tests
git diff --check
```

수동 검증:

- Langflow Playground에서 각 route branch가 하나만 실행되는지 확인한다.
- branch별 Chat Output에서 중복 답변이 나오지 않는지 확인한다.
- metadata QA 답변이 실제 metadata에 없는 정보를 만들어내지 않는지 확인한다.
- dummy route가 실제 저장을 하지 않는지 확인한다.

## 6. 구현 중 금지할 것

- Router에서 제품 token 매핑을 수행하지 않는다.
- Router에서 pandas function case를 선택하지 않는다.
- `flow_error`를 Smart Router route로 넣지 않는다.
- dummy route를 일반 질문에서 자동 선택하지 않는다. 명시적으로 dummy 테스트를 요청한 경우에만 선택한다.
- metadata QA에서 raw trace, 전체 MongoDB dump, credential 성격 값을 응답 또는 prompt에 넣지 않는다.
- metadata QA가 data retrieval/pandas/result-store를 타지 않는다.
- Run Flow 대상 flow를 변수처럼 전달하려고 하지 않는다.

## 7. 최종 결론

이번 개선의 최종 형태는 아래가 가장 균형이 좋다.

```text
Chat Input
  -> Smart Router
     -> data_analysis route -> Run Flow(data_analysis_flow) -> Chat Output
     -> metadata_qa route -> Run Flow(metadata_qa_flow) -> Chat Output
     -> domain_saving route -> Run Flow(domain_saving_flow) -> Chat Output
     -> table_catalog_saving route -> Run Flow(table_catalog_saving_flow) -> Chat Output
     -> main_flow_filter_saving route -> Run Flow(main_flow_filters_saving_flow) -> Chat Output
     -> dummy_data_analysis route -> Run Flow(dummy_data_analysis_flow) -> Chat Output
     -> dummy_metadata_qa route -> Run Flow(dummy_metadata_qa_flow) -> Chat Output
     -> dummy_domain_saving route -> Run Flow(dummy_domain_saving_flow) -> Chat Output
     -> dummy_table_catalog_saving route -> Run Flow(dummy_table_catalog_saving_flow) -> Chat Output
     -> dummy_main_flow_filter_saving route -> Run Flow(dummy_main_flow_filter_saving_flow) -> Chat Output
     -> direct/clarification route -> Smart Router Message -> Chat Output
```

direct/clarification/error는 별도 flow로 만들지 않고 Smart Router message 또는 실행된 subflow의 기존 응답 계약으로 처리한다.
authoring은 이미 분리된 domain/table catalog/main filter flow 구조를 유지한다.
metadata QA는 새로 구현하되, MongoDB의 기존 metadata 구조를 바꾸지 않고 읽기/압축/답변만 담당한다.
metadata QA dummy도 별도 route로 유지해 실제 flow와 같은 응답 계약을 빠르게 검증할 수 있게 한다.
dummy flow는 빠르게 실행되지만 실제 응답 계약을 닮게 만들어 Router 연결 검증에 쓸 수 있게 한다.
