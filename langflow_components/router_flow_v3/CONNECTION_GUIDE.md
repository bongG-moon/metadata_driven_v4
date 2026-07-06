# Router Flow v3 연결 가이드 - Smart Router + Langflow API 호출

`router_flow_v3`는 Smart Router의 route별 output port마다 별도의 API 호출 branch를 두는 방식입니다.
이 방식에서는 route별로 `01 -> 02 -> 03` 노드 묶음을 하나씩 배치하고, 각 `01` 노드에는 해당 하위 flow의 Langflow Run API URL만 입력합니다.

```text
Smart Router.<route output>
-> 01 Route API 요청 생성기
-> 02 선택 Flow API 호출기
-> 03 Router API 응답 정리기
-> Chat Output 또는 Data Output
```

## 1. 기본 구조

예를 들어 `data_analysis`, `metadata_qa`, `domain_saving` route를 사용한다면 아래 branch를 각각 하나씩 만듭니다.

```text
Chat Input.message
  -> Smart Router.input

Chat Input.message
  -> 각 route의 01 Route API 요청 생성기.original_input

Smart Router.data_analysis
  -> 01 Data Analysis Route API 요청 생성기.route_signal
  -> 02 Data Analysis 선택 Flow API 호출기
  -> 03 Data Analysis Router API 응답 정리기
  -> Chat Output

Smart Router.metadata_qa
  -> 01 Metadata QA Route API 요청 생성기.route_signal
  -> 02 Metadata QA 선택 Flow API 호출기
  -> 03 Metadata QA Router API 응답 정리기
  -> Chat Output
```

## 2. Smart Router 설정

Smart Router route table에는 아래처럼 route message를 JSON으로 넣습니다. `01` 노드는 이 route message에서 route를 자동으로 읽습니다.

| Route Name | Route Description | Route Message |
| --- | --- | --- |
| `data_analysis` | 생산량, 재공, 투입, 장비 ASSIGN 등 실제 제조 데이터 조회/분석 질문 | `{"route":"data_analysis"}` |
| `metadata_qa` | 등록된 데이터셋, 필수 파라미터, 쿼리, 도메인 용어, 계산 로직을 확인하는 질문 | `{"route":"metadata_qa"}` |
| `domain_saving` | 도메인 용어, 공정 그룹, 제품 그룹, 분석 규칙, 특화 함수 설명 저장 요청 | `{"route":"domain_saving"}` |
| `table_catalog_saving` | 데이터셋, source type, query template, required params, 컬럼 정보 저장 요청 | `{"route":"table_catalog_saving"}` |
| `main_flow_filter_saving` | DATE, OPER_NAME, ORG 같은 공통 필터 정의 저장 요청 | `{"route":"main_flow_filter_saving"}` |
| `dummy_data_analysis` | 개발 검증용 dummy data analysis flow 호출 | `{"route":"dummy_data_analysis"}` |
| `dummy_metadata_qa` | 개발 검증용 dummy metadata QA flow 호출 | `{"route":"dummy_metadata_qa"}` |
| `dummy_domain_saving` | 개발 검증용 dummy domain saving flow 호출 | `{"route":"dummy_domain_saving"}` |
| `dummy_table_catalog_saving` | 개발 검증용 dummy table catalog saving flow 호출 | `{"route":"dummy_table_catalog_saving"}` |
| `dummy_main_flow_filter_saving` | 개발 검증용 dummy main filter saving flow 호출 | `{"route":"dummy_main_flow_filter_saving"}` |

`direct_answer`, `clarification`은 하위 flow API를 호출하지 않는 route입니다. 이 둘은 Smart Router route message를 바로 Chat Output에 연결하거나 별도 응답 노드로 처리합니다.

## 3. 01 노드 입력

`01 Route API 요청 생성기`에서 사용자가 직접 입력해야 하는 값은 `하위 Flow API URL` 하나입니다.

| 01 입력 | 연결/입력 방식 |
| --- | --- |
| `원문 입력` | `Chat Input.message`를 연결합니다. 사용자가 입력한 문장/저장 원문을 그대로 보존합니다. |
| `선택 Route 신호` | Smart Router의 해당 route output을 연결합니다. route message는 `{"route":"..."}` 형식이어야 합니다. |
| `하위 Flow API URL` | 해당 하위 flow의 Langflow Run API URL을 직접 입력합니다. 예: `http://127.0.0.1:7860/api/v1/run/<flow_id>` |

`Route 이름`, `선택 Flow 이름`, `입력 종류`는 더 이상 화면에서 입력하지 않습니다.
route는 Smart Router route message에서 자동으로 읽고, flow 이름과 입력 종류는 route 기준으로 내부에서 자동 추론합니다.

## 4. 정확한 연결

route branch마다 아래 연결을 반복합니다.

| From output | To input |
| --- | --- |
| `Chat Input.message` | `01 Route API 요청 생성기.original_input` |
| `Smart Router.<route output>` | `01 Route API 요청 생성기.route_signal` |
| `01 Route API 요청 생성기.route_request` | `02 선택 Flow API 호출기.route_request` |
| `02 선택 Flow API 호출기.api_call_result` | `03 Router API 응답 정리기.api_call_result` |
| `03 Router API 응답 정리기.display_message` | route별 `Chat Output.input` |
| `03 Router API 응답 정리기.api_response` | route별 `Data Output.input` 또는 Web/API 응답 확인용 output |

채팅 화면에서 하위 flow가 반환한 답변을 그대로 보려면 `03 Router API 응답 정리기.display_message`를 `Chat Output.input`에 연결합니다.

## 5. 02 노드 역할

`02 선택 Flow API 호출기`는 실제 Langflow Run API를 호출하는 노드입니다.

호출 payload는 내부에서 아래 형태로 고정합니다.

```json
{
  "input_value": "사용자 원문",
  "input_type": "chat",
  "output_type": "chat"
}
```

하위 flow가 구조화된 `api_response`를 반환하면 그 값을 우선 추출합니다.
하위 flow가 Chat Output 메시지만 반환하면 Langflow Run API 응답의 nested `outputs/results/message/text`, `artifacts/message` 등에서 표시 메시지를 찾아 `03`으로 넘깁니다.

## 6. 03 노드 출력

`03 Router API 응답 정리기`는 최종 연결용 노드입니다. 출력은 두 개만 사용합니다.

| 03 출력 | 용도 | 연결 대상 |
| --- | --- | --- |
| `API 응답` | Web/API에서 읽을 구조화된 router 응답입니다. route, status, 하위 flow 응답, trace를 포함합니다. | Data Output 또는 Web/API 확인용 |
| `채팅 표시 메시지` | Langflow Playground/Chat에서 사용자에게 보여줄 최종 텍스트입니다. | Chat Output |

기존의 `API 메시지` 출력은 JSON을 문자열 Message로 중복 제공하는 용도라 제거했습니다.

## 7. 직접 응답과 구체화 응답

아래 route는 하위 flow를 호출하지 않습니다.

```text
Smart Router.direct_answer
  -> Chat Output

Smart Router.clarification
  -> Chat Output
```

이 route들은 `01 -> 02 -> 03` branch를 만들 필요가 없습니다.

## 8. 점검 기준

- 각 route branch의 `01`에는 해당 flow의 Run API URL만 직접 입력한다.
- 사용자 원문은 `Chat Input.message -> 01.original_input`으로 들어간다.
- Smart Router route message는 `{"route":"..."}` JSON 형식으로 넣는다.
- 하위 flow 답변을 채팅에서 보려면 `03.display_message`를 Chat Output에 연결한다.
- Web/API에서 구조화 응답을 보고 싶으면 `03.api_response`를 Data Output으로 연결한다.
- `route_signal`이 비어 있거나 API URL이 없으면 `02`는 HTTP 호출을 하지 않고 오류 응답을 반환한다.
