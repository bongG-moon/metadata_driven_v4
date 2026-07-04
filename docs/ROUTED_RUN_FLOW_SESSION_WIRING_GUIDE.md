# Routed Run Flow + Session State Wiring Guide

> 참고: 현재 v4 router 내부에서는 하위 flow를 API로 다시 호출하지 않는다. Web/외부 시스템이 router flow를 API로 호출할 수는 있지만, router canvas 안에서는 route별로 미리 선택된 Native Run Flow 결과를 받아 표준 응답으로 합친다.
> Langflow `Run Flow`는 flow 이름을 변수로 입력받는 노드가 아니므로, 각 Run Flow 노드에서 대상 flow를 먼저 선택해야 한다.

이 문서는 main router flow와 하위 flow의 session state 연결 기준입니다. 현재 권장 구조는 단순합니다.

```text
main router flow
Chat Input
-> Smart Router
-> route별로 미리 선택된 Native Run Flow 노드 하나
-> 선택 route의 subflow 응답
-> Chat Output
```

각 subflow는 독립 실행 가능한 flow로 둡니다.

```text
subflow
Chat Input
-> 00 MongoDB Session State Loader
-> 00 Request Loader
-> subflow logic
-> Final API Response
-> 01 MongoDB Session State Writer

Final Message
-> Chat Output
```

main flow는 subflow 내부 payload를 조립하지 않습니다. main flow는 질문을 분류하고, Smart Router route output이 route별로 미리 선택된 Native Run Flow 노드 하나만 실행하게 합니다. 별도 router custom component chain은 사용하지 않습니다.

## Main Router Connections

### A. Playground/Native 권장 연결

```text
Chat Input.Chat Message
  -> Smart Router.Input

Smart Router.data_analysis output
  -> Run Flow(data_analysis_flow)의 동적 질문 입력 포트

Smart Router.metadata_qa output
  -> Run Flow(metadata_qa_flow)의 동적 질문 입력 포트

Smart Router.domain_authoring output
  -> Run Flow(domain_authoring_flow)의 동적 raw text 입력 포트

각 Run Flow의 최종 Message/API output
  -> 해당 route의 Chat Output 또는 후속 응답 어댑터
```

Smart Router의 routes table에서 Route Message를 비우면 매칭된 output으로 원래 사용자 입력이 전달됩니다.
Run Flow 노드는 대상 flow를 선택하고 refresh해야 해당 flow의 동적 입력 포트가 표시됩니다.

| Smart Router route | Run Flow 노드에서 미리 선택할 flow |
| --- | --- |
| `data_analysis` | `data_analysis_flow` |
| `dummy_data_analysis` | `dummy_data_analysis_flow` |
| `metadata_qa` | `metadata_qa_flow` |
| `dummy_metadata_qa` | `dummy_metadata_qa_flow` |
| `domain_authoring` | `domain_authoring_flow` |
| `dummy_domain_authoring` | `dummy_domain_authoring_flow` |
| `table_catalog_authoring` | `table_catalog_authoring_flow` |
| `dummy_table_catalog_authoring` | `dummy_table_catalog_authoring_flow` |
| `main_flow_filter_authoring` | `main_flow_filters_authoring_flow` |
| `dummy_main_flow_filter_authoring` | `dummy_main_flow_filter_authoring_flow` |

Run Flow 출력은 Data 또는 Message일 수 있습니다. 여러 출력이 보이면 최종 API/구조화 응답 output을 먼저 연결하고, 없으면 최종 Message output을 연결합니다.

전체 route와 flow 매핑은 `langflow_components/router_flow/CONNECTION_GUIDE.md`의 Smart Router routes table을 기준으로 확인합니다.

## Subflow Standard Connections

현재 v4에서 구현된 subflow의 시작부는 request loader가 `previous_state`를 직접 받는 패턴입니다.

```text
Chat Input.Chat Message
  -> 00 Request Loader.Question

Web/API에서 이전 상태를 주입할 때
  -> 00 Request Loader.previous_state
```

종료부는 flow별 최종 API response와 최종 Message를 분리합니다.

```text
Final API Response
  -> Web/API 구조화 응답

Final Message
  -> Chat Output
```

## Flow-Specific Ports

| Subflow | First loader | Previous state input | Final API response | Final human message |
| --- | --- | --- | --- | --- |
| `metadata_qa_flow` | `00 메타데이터 QA 요청 로더.사용자 질문` | `00 메타데이터 QA 요청 로더.이전 상태` | `06 메타데이터 QA API 응답 생성기.API 응답` | `05 메타데이터 QA 메시지 어댑터.메시지` |
| `data_analysis_flow` | `00 분석 요청 로더.사용자 질문` | `00 분석 요청 로더.이전 상태` | `22 API 응답 생성기.API 응답` | `21 답변 메시지 어댑터.메시지` |
| `report_generation_flow` | `00 Report Request Loader.Question` | `00 Report Request Loader.Previous State` | `03 Report Response Builder.API Response` | `03 Report Response Builder.Message` |
| `operations_diagnosis_flow` | `00 Diagnosis Request Loader.Question` | `00 Diagnosis Request Loader.Previous State` | `05 Diagnosis API Response Builder.API Response` | `04 Diagnosis Message Adapter.Message` |

## E2E Example Questions

`report_generation_flow`와 `operations_diagnosis_flow`는 현재 예시 기준으로 후속 질문이 아니라 신규 E2E 업무 요청을 테스트 문장으로 사용합니다.

Report generation examples:

```text
오늘 DA공정 일일 운영 리포트 만들어줘
오늘 WB공정 기준으로 생산량, 재공, 목표 달성률을 포함한 요약 리포트 만들어줘
오늘 HBM 제품군의 생산 실적, 재공 현황, 목표 대비 차이를 리포트로 정리해줘
오늘 DA/WB공정의 주요 이상 징후와 우선 확인 항목을 포함해서 운영 리포트 작성해줘
```

Operations diagnosis examples:

```text
오늘 DA공정 병목 원인을 진단해줘
오늘 WB공정에서 재공이 많이 쌓인 원인 후보를 진단해줘
오늘 목표 대비 생산량이 저조한 제품들의 원인 후보를 진단해줘
오늘 HBM 제품군 생산 저조 원인을 장비, 재공, HOLD LOT 관점으로 진단해줘
오늘 DA공정에서 재공 상위 공정의 HOLD LOT 수와 평균 IN TAT를 보고 병목 여부를 진단해줘
```

## Session Id

별도 `Session ID` 포트는 request loader와 session loader/writer에서 제거했습니다. Langflow API payload의 `session_id`가 Chat/API message에 포함되면 컴포넌트가 자동으로 읽습니다. 응답 저장 시에는 final API response의 `request.session_id`를 사용합니다.

단독 테스트에서 message에 session id가 없으면 `demo-session` fallback이 사용됩니다.

## Adding A New Routed Flow

1. 새 subflow가 질문 하나만 받아 독립 실행되도록 만듭니다.
2. 필요하면 subflow 내부에 session state loader/writer를 둡니다.
3. `router_flow/CONNECTION_GUIDE.md`의 Smart Router routes table에 새 route와 selected flow를 추가합니다.
4. Smart Router canvas routes table에도 같은 route를 추가합니다.
5. router canvas에 새 Run Flow 노드를 추가하고 대상 flow를 직접 선택한 뒤 refresh합니다.
