# Router Flow v3 Route별 01 노드 설정 예시

Smart Router가 route별 output port를 제공하는 환경에서는 route마다 `01 Route API 요청 생성기`를 하나씩 둡니다.
각 `01` 노드에서 직접 입력하는 값은 `하위 Flow API URL` 하나입니다.

| Route branch | `01 하위 Flow API URL` |
| --- | --- |
| `data_analysis` | `http://127.0.0.1:7860/api/v1/run/<data_analysis_flow_id>` |
| `metadata_qa` | `http://127.0.0.1:7860/api/v1/run/<metadata_qa_flow_id>` |
| `domain_saving` | `http://127.0.0.1:7860/api/v1/run/<domain_saving_flow_id>` |
| `table_catalog_saving` | `http://127.0.0.1:7860/api/v1/run/<table_catalog_saving_flow_id>` |
| `main_flow_filter_saving` | `http://127.0.0.1:7860/api/v1/run/<main_flow_filters_saving_flow_id>` |
| `dummy_data_analysis` | `http://127.0.0.1:7860/api/v1/run/<dummy_data_analysis_flow_id>` |
| `dummy_metadata_qa` | `http://127.0.0.1:7860/api/v1/run/<dummy_metadata_qa_flow_id>` |
| `dummy_domain_saving` | `http://127.0.0.1:7860/api/v1/run/<dummy_domain_saving_flow_id>` |
| `dummy_table_catalog_saving` | `http://127.0.0.1:7860/api/v1/run/<dummy_table_catalog_saving_flow_id>` |
| `dummy_main_flow_filter_saving` | `http://127.0.0.1:7860/api/v1/run/<dummy_main_flow_filter_saving_flow_id>` |

## 공통 연결

각 branch마다 아래 연결을 반복합니다.

```text
Chat Input.message
  -> 01 Route API 요청 생성기.original_input

Smart Router.<route output>
  -> 01 Route API 요청 생성기.route_signal

01 Route API 요청 생성기.route_request
  -> 02 선택 Flow API 호출기.route_request

02 선택 Flow API 호출기.api_call_result
  -> 03 Router API 응답 정리기.api_call_result

03 Router API 응답 정리기.display_message
  -> Chat Output.input

03 Router API 응답 정리기.api_response
  -> Data Output.input
```

## Route Message 예시

Smart Router route message는 아래처럼 넣습니다.

```json
{"route":"metadata_qa"}
```

`direct_answer`, `clarification`은 하위 flow API를 호출하지 않으므로 이 표의 URL 설정 대상에서 제외합니다.
