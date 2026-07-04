# Router Flow 최종 구현 계획 2026-07-04

## 1. 다시 정한 전제

이번 계획은 **라우팅 방식이 API일 필요는 없다**는 조건에서 다시 작성한다. API 방식은 v3에서 사용했던 방식일 뿐이며, v4 router의 기본 전제로 두지 않는다.

라우터에서 반드시 지켜야 할 것은 실행 방식이 아니라 아래 계약이다.

- 사용자의 입력을 받아 적절한 route를 판단한다.
- 선택된 flow는 하나만 실행한다.
- Langflow Playground와 Web에서 같은 최종 응답 형태를 볼 수 있어야 한다.
- 신규 flow가 추가되어도 route registry와 연결 가이드만 확장하면 된다.
- 메타데이터 등록 원문은 router에서 변형하지 않는다.
- 제품 token 매핑, 공정별 특화 로직, pandas 특화 함수 선택 로직은 router가 아니라 `data_analysis_flow` 내부의 특화 입력/메타데이터 위치에 둔다.

## 2. 공식 문서 기준 비교

Langflow 공식 문서를 기준으로 라우팅 후보를 다시 비교했다.

| 방식 | 공식 문서상 성격 | 장점 | 위험/한계 | 최종 판단 |
| --- | --- | --- | --- | --- |
| Smart Router | LLM 기반 If-Else. route table로 output route를 만든다. | Langflow-native 분기 느낌이 가장 강하고 시각적으로 이해하기 쉽다. | route 판단에는 좋지만 selected flow 실행, error wrapping, output contract 정규화까지 맡기기 어렵다. | route classifier 후보 |
| If-Else | 문자열 비교 기반 conditional router. equals/contains/regex 등을 지원한다. | 명시 route hint, developer dummy route, authoring type 선택처럼 결정적 조건에 좋다. | 자연어 분석/등록 의도 분류에는 부족하다. | deterministic gate로 사용 |
| Structured Output / Agent Structured Response | LLM 결과를 JSON schema로 정규화한다. | route 판단 결과를 `route`, `confidence`, `reason` 형태로 안정화하기 좋다. | branch 실행 자체는 별도 component가 필요하다. | route decision 기본 후보 |
| Native Run Flow | 다른 flow를 현재 flow의 subprocess로 실행한다. 대상 flow를 노드에서 먼저 선택하면 그 flow 기준의 입력/출력 포트가 열린다. | API 없이 Langflow 내부에서 subflow를 실행할 수 있다. Playground 친화적이다. | flow 이름을 런타임 변수로 넘겨 동적 선택하는 방식은 맞지 않는다. route별 Run Flow 노드가 필요하다. | route별 고정 Run Flow branch로 채택 |
| Agent Tool Calling | agent가 tool 호출 여부를 판단한다. | agent형 멀티툴 UX에는 자연스럽다. | 반드시 하나의 selected flow를 실행해야 하는 router 계약과 맞지 않는다. | 운영 router 방식 제외 |
| API Adapter | `/v1/run/{FLOW_ID}`로 subflow를 호출한다. | timeout/error/trace 통제와 웹 연동이 쉽다. | Langflow 내부에서 다시 Langflow를 HTTP 호출하는 구조가 된다. | 현재 단순화 범위에서는 제외 |

참고 문서:

- [Smart Router](https://docs.langflow.org/smart-router)
- [If-Else](https://docs.langflow.org/if-else)
- [Run Flow](https://docs.langflow.org/run-flow)
- [Structured Output](https://docs.langflow.org/structured-output)
- [Agent Tools](https://docs.langflow.org/agents-tools)
- [Langflow API 실행](https://docs.langflow.org/concepts-publish)

## 3. 서브에이전트 재검토 결과

이번에는 세 서브에이전트에게 API 우선 가정을 제거하고 다시 검토시켰다.

| 역할 | 핵심 의견 | 최종 반영 |
| --- | --- | --- |
| Langflow-native routing 전문가 | Smart Router/Structured Output으로 route를 판단하고, Native Run Flow로 subflow 실행 가능성을 먼저 검증해야 한다. 여러 Run Flow output을 한 노드로 병합하는 구조는 위험하다. | native-first spike 채택 |
| Web/API/운영 계약 전문가 | Web은 외부에서 router flow를 호출해야 하지만, router 내부 subflow 실행이 API일 필요는 없다. 중요한 것은 router가 selected flow 응답을 동일한 envelope로 반환하는 것이다. | external API와 internal routing 분리 |
| 제조 도메인/검증 전문가 | router는 제조 분석을 해석하지 말고 분석/등록/QA/dummy/direct 정도만 분류해야 한다. raw text 보존과 특화 로직 위치 분리가 중요하다. | domain boundary 채택 |

토론 결과 최종 방향은 다음과 같다.

> `API router`가 아니라 **Smart Router route output + route별 고정 Native Run Flow** 구조로 설계한다. 현재 구현 범위에서는 router 내부 API 호출 방식을 제외하고 Native Run Flow 연결만 사용한다.

## 4. 최종 아키텍처

```text
Web / Langflow Playground / 외부 API
  -> router_flow
     Smart Router route outputs
  -> route별로 미리 선택된 Run Flow
     data_analysis_flow
     dummy_data_analysis_flow
     dummy_metadata_qa_flow
     domain_authoring_flow
     dummy_domain_authoring_flow
     table_catalog_authoring_flow
     dummy_table_catalog_authoring_flow
     main_flow_filters_authoring_flow
     dummy_main_flow_filter_authoring_flow
     future flows...
```

중요한 구분:

- Web이 router flow를 호출하는 외부 경계는 API일 수밖에 없다.
- 하지만 router flow 내부에서 subflow를 실행하는 방식은 API로 고정하지 않는다.
- 현재 router 내부 실행 방식은 Native Run Flow만 사용한다.
- Native Run Flow의 대상 flow는 변수로 선택하지 않고, route별 Run Flow 노드 설정에서 미리 선택한다.

## 5. Route 판단 방식

### 5.1 1순위: deterministic gate

명시 입력은 LLM으로 보내지 않는다.

- `route_hint=dummy_*`이면 해당 dummy route
- `authoring_type=domain`이면 domain authoring
- `authoring_type=table_catalog`이면 table catalog authoring
- `authoring_type=main_flow_filter`이면 main flow filter authoring
- 운영자가 명시적으로 direct/help route를 준 경우 direct answer

### 5.2 2순위: Structured route decision

명시 route가 없을 때만 Langflow Prompt Template + LLM Structured Output 또는 Agent Structured Response를 사용한다.

출력 schema는 아래처럼 작게 유지한다.

```json
{
  "route": "data_analysis",
  "confidence": "high",
  "reason": "제조 데이터 분석 질문입니다.",
  "needs_clarification": false,
  "clarification_question": ""
}
```

### 5.3 Smart Router의 위치

Smart Router는 Langflow-only router canvas의 기본 분기 노드로 사용한다.

- Langflow Desktop/서버 환경에서 Smart Router 컴포넌트가 안정적으로 제공된다.
- route별 output port가 실제 canvas에서 관리 가능하다.
- Route Message를 비워 원래 사용자 입력을 선택된 route output으로 그대로 통과시킨다.

Web/API 응답은 선택된 subflow의 최종 Message/API output을 그대로 사용한다. 별도 00~07 custom router chain은 최종 구조에서 사용하지 않는다.

## 6. Native Run Flow 연결 방식

Native Run Flow는 route별 branch로만 연결한다.
단일 Run Flow 노드에 flow 이름을 변수로 넣어 실행 대상을 바꾸는 방식은 채택하지 않는다.

### 6.1 route별 Run Flow branch

목표:

- Smart Router가 선택된 route output만 활성화하고, 선택되지 않은 Run Flow는 실행되지 않는지 확인한다.
- downstream에서 여러 branch output을 무리하게 merge하지 않고도 Playground/Web 응답을 만들 수 있는지 확인한다.

채택 조건:

- 선택되지 않은 branch 때문에 flow가 대기하지 않는다.
- Web API 응답에서 선택 branch 결과만 안정적으로 추출된다.
- branch별 Chat Output 또는 branch별 response builder가 사용자에게 중복 출력되지 않는다.

### 6.2 현재 단순화 결정

현재 구현에서는 API adapter fallback을 두지 않는다.

- Smart Router는 route를 정하고 원래 입력 text를 해당 route output으로 보낸다.
- 각 route output은 대상 flow가 미리 선택된 Native Run Flow 노드로 연결된다.
- 선택된 subflow의 최종 Message/API output을 router flow의 최종 출력으로 사용한다.

## 7. Route Taxonomy

| route | selected_flow | 입력 mode | 용도 | output contract |
| --- | --- | --- | --- | --- |
| `data_analysis` | `data_analysis_flow` | `question` | 제조 데이터 분석 | `response_type=data_analysis` |
| `dummy_data_analysis` | `dummy_data_analysis_flow` | `question` | 개발/스모크 테스트 | `response_type=data_analysis` |
| `domain_authoring` | `domain_authoring_flow` | `raw_text` | domain metadata 등록 | `response_type=metadata_authoring`, `metadata_type=domain` |
| `dummy_domain_authoring` | `dummy_domain_authoring_flow` | `raw_text` | 개발/스모크 테스트용 domain metadata 등록 | `response_type=metadata_authoring`, `metadata_type=domain` |
| `table_catalog_authoring` | `table_catalog_authoring_flow` | `raw_text` | table catalog 등록 | `response_type=metadata_authoring`, `metadata_type=table_catalog` |
| `dummy_table_catalog_authoring` | `dummy_table_catalog_authoring_flow` | `raw_text` | 개발/스모크 테스트용 table catalog 등록 | `response_type=metadata_authoring`, `metadata_type=table_catalog` |
| `main_flow_filter_authoring` | `main_flow_filters_authoring_flow` | `raw_text` | main filter 등록 | `response_type=metadata_authoring`, `metadata_type=main_flow_filter` |
| `dummy_main_flow_filter_authoring` | `dummy_main_flow_filter_authoring_flow` | `raw_text` | 개발/스모크 테스트용 main filter 등록 | `response_type=metadata_authoring`, `metadata_type=main_flow_filter` |
| `metadata_qa` | `metadata_qa_flow` | `question` | 저장된 metadata 조회/설명 | `response_type=metadata_qa` |
| `dummy_metadata_qa` | `dummy_metadata_qa_flow` | `question` | 개발/스모크 테스트용 metadata QA | `response_type=metadata_qa` |
| `direct_answer` | router direct | `question` | 인사, 도움말, 사용법 | `response_type=direct_answer` |
| `clarification` | router direct | `question/raw_text` | route 불명확 | `status=needs_more_input` |
| `flow_error` | router direct | error payload | selected flow 실행 실패 | `status=error` |

## 8. Router Output Contract

router는 별도 envelope를 만들지 않고, 선택된 subflow의 최종 응답을 그대로 반환한다.
따라서 각 subflow는 기존 응답 계약을 유지해야 한다.

| route family | 최종 응답 기준 |
| --- | --- |
| data analysis | `response_type=data_analysis`, `message/answer_message`, `data`, `state`, `trace` |
| metadata QA | `response_type=metadata_qa`, `message/answer_message`, `metadata_route`, `state` |
| metadata authoring | `response_type=metadata_authoring`, `metadata_type`, `message`, `write_result`, `trace` |
| dummy routes | 실제 대응 flow와 같은 `response_type` shape |

Web parser는 선택된 subflow의 `api_response` 또는 Message를 직접 읽는다.

불필요한 payload는 넣지 않는다.

- raw LLM 전문
- 긴 metadata 원문
- raw_trace 전체
- 중복 `pandas_function_case` / `pandas_function_cases`
- 대용량 preview rows

## 9. Dummy Flow 계획

`dummy_data_analysis_flow`는 기존 data retriever의 dummy mode와 다르다.

- 목적: router, Web parser, Playground 출력, session, 다운로드 링크를 빠르게 검증
- 출력: 실제 `data_analysis_flow`와 같은 `response_type=data_analysis` shape
- 실행 시간: LLM/DB 없이 즉시 반환
- 선택 조건: `route_hint=dummy_data_analysis`, developer test, smoke test

예상 구성:

| 파일 | 역할 |
| --- | --- |
| `00_dummy_request_loader.py` | 질문/session/options를 payload로 정리 |
| `01_dummy_data_analysis_response_builder.py` | data_analysis와 같은 API response shape 생성 |
| `CONNECTION_GUIDE.md` | Chat Input -> dummy response -> Chat Output 연결 설명 |

메타데이터 계열 더미 flow도 같은 목적을 가진다.

| 폴더 | 역할 |
| --- | --- |
| `dummy_metadata_qa_flow/` | metadata QA와 같은 `response_type=metadata_qa` 더미 응답 |
| `dummy_domain_authoring_flow/` | domain authoring과 같은 `metadata_authoring` 더미 응답 |
| `dummy_table_catalog_authoring_flow/` | table catalog authoring과 같은 `metadata_authoring` 더미 응답 |
| `dummy_main_flow_filter_authoring_flow/` | main flow filter authoring과 같은 `metadata_authoring` 더미 응답 |

더미 authoring flow는 MongoDB에 저장하지 않고, `raw_text` 보존과 응답 계약만 검증한다.

## 10. Metadata Authoring 포함 방식

metadata authoring flow도 router route에 포함한다.

원칙:

- 사용자가 UI에서 `domain/table_catalog/main_flow_filter`를 명시 선택하면 route classifier를 타지 않는다.
- 단일 자연어 입력창에서 들어온 경우에만 route classifier가 authoring type을 판단한다.
- `raw_text`는 절대 합치거나 재작성하지 않는다.
- `review_notes`, `dry_run`, `duplicate_action`은 별도 field로 전달한다.
- MongoDB 저장은 기존 authoring flow writer만 수행한다.

router가 하지 않는 일:

- domain item 생성
- table catalog query 수정
- main filter 값 보정
- 메타데이터 원문 요약 저장

## 11. 제조 분석 경계

router는 아래를 판단하지 않는다.

- `DA`가 공정인지 제품 token인지
- `match_product_tokens` 사용 여부
- pandas function case 선택
- 공정/제품/상태 filter 분해
- 필수 parameter와 pandas filter 구분

이 내용은 `data_analysis_flow`의 intent prompt, metadata, specialized prompt/function input에서 처리한다.

router는 오직 아래 수준만 판단한다.

- 분석 질문인가
- metadata 등록인가
- metadata 조회/설명인가
- dummy 테스트인가
- 단순 안내인가
- 더 물어봐야 하는가

## 12. 구현 파일 계획

### 12.1 `langflow_components/router_flow/`

| 파일 | 역할 |
| --- | --- |
| `CONNECTION_GUIDE.md` | 최종 canvas 연결 가이드, Smart Router route와 Run Flow 대상 flow 매핑표 |

### 12.2 `langflow_components/dummy_data_analysis_flow/`

| 파일 | 역할 |
| --- | --- |
| `00_dummy_request_loader.py` | dummy 요청 정리 |
| `01_dummy_data_analysis_response_builder.py` | data_analysis 호환 응답 생성 |
| `CONNECTION_GUIDE.md` | dummy flow 연결 설명 |

### 12.3 `langflow_components/dummy_*metadata*_flow/`

| 폴더 | 역할 |
| --- | --- |
| `dummy_metadata_qa_flow/` | metadata QA 호환 더미 응답 생성 |
| `dummy_domain_authoring_flow/` | domain authoring 호환 더미 응답 생성 |
| `dummy_table_catalog_authoring_flow/` | table catalog authoring 호환 더미 응답 생성 |
| `dummy_main_flow_filter_authoring_flow/` | main flow filter authoring 호환 더미 응답 생성 |

이 flow들은 개발/스모크 테스트용이며 MongoDB 저장이나 원본 메타데이터 변형을 하지 않는다.

## 13. Web 적용 원칙

Web은 계속 router flow 하나를 호출한다. 이것은 외부 진입점이므로 API 호출일 수 있다. 하지만 Web이 selected subflow를 직접 호출하지 않는다.

router 내부는 Smart Router와 Native Run Flow로 실행하고, Web이 보는 응답은 선택된 subflow의 최종 응답이다.

Web parser는 다음 우선순위로 응답을 찾는다.

1. 선택된 Run Flow의 `api_response` Data output
2. 선택된 Run Flow의 최종 Message output
3. 기존 호환용 router envelope가 있으면 그 안의 `selected_flow_response`

현재 authoring 화면이 각 authoring flow를 직접 호출하는 구조는 migration 기간 동안 유지할 수 있다. 최종 목표는 router에서도 authoring route를 실행할 수 있게 하는 것이다.

## 14. 검증 계획

### 14.1 Native Run Flow spike 검증

- Smart Router route output이 원래 입력 text를 선택된 route branch로 전달하는가
- route별 고정 Run Flow branch가 선택되지 않은 Run Flow를 실행하지 않는가
- branch output을 merge하지 않아도 Web/Playground가 같은 최종 메시지를 볼 수 있는가
- selected flow 응답을 router response builder가 읽을 수 있는가

### 14.2 Route 검증

대표 분석 질문 13개는 모두 `data_analysis`로 가야 한다.

- `오늘 투입된 제품중 MCP NO가 L-267로 시작하는 제품의 INPUT 수량 알려줘`
- `어제 DA공정 차수별 생산량 알려줘`
- `어제 Mobile제품의 PKG OUT실적을 제품별로 알려줘`
- `HBM제품의 WB공정에서 오늘 아침재공 제품별로 알려줘`
- `6/27일 W/B공정에서 세부 공정별 생산실적과 아침재공 수량 알려줘`
- `HBM제품 FCB공정에서 오늘 아침재공 제품별로 알려줘`
- `6월 30일 FCB/H 공정 실적이 있는 Device 알려줘`
- `RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘`
- `FCB 공정에서 SP 16G DDR5 2ND X4 78 FCBGA SDP 제품의 전일 생산량 알려줘`
- `6/24일 투입 실적 대비 D/S1, DA1공정에서 WIP 많은 제품 알려줘`
- `7/1 현시간 기준 Input 실적은 있으나 D/A 공정 WIP 없는 제품 확인해줘`
- `전일 L-218K8H 제품의 SBM공정에서 생산 실적 알려줘`
- `오늘 아침 07시 기준 DA 16G GDDR6 180 제품 재공 수량 알려줘`

metadata 등록 문장은 authoring type별 route로 가야 하고, raw text가 변형되지 않아야 한다.

### 14.3 Contract 검증

- route별로 미리 선택된 Run Flow 중 하나만 실행된다.
- dummy flow는 실제 data analysis와 같은 response shape를 반환한다.
- 불명확한 route는 임의 fallback이 아니라 `clarification`을 반환한다.
- selected flow 실패는 `flow_error`로 정규화된다.
- router trace는 간결해야 하며 raw_trace/긴 원문을 포함하지 않는다.

## 15. 구현 순서

1. 이 계획 문서를 기준으로 `router_flow/CONNECTION_GUIDE.md` 초안을 만든다.
2. `dummy_data_analysis_flow`를 먼저 구현한다.
3. Smart Router route output과 route별 고정 Run Flow branch를 실제 Langflow canvas에서 검증한다.
4. data analysis route를 연결한다.
5. metadata authoring 3종 route를 연결한다.
6. Web parser가 선택된 subflow의 API/Data output 또는 Message output을 해석하는지 검증한다.
7. 대표 질문과 metadata 등록 sample로 회귀 검증한다.

## 16. 결론

최종 방향은 **API router가 아니다.**

최종 방향은 **Smart Router route output + route별 고정 Native Run Flow**다. 내부 subflow 실행은 Native Run Flow만 사용하고, API adapter는 현재 단순화 범위에서 제외한다.
