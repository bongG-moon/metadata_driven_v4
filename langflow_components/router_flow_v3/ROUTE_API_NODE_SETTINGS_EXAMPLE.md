# Router Flow v3 Route별 01 노드 설정 예시

Smart Router가 route별 output port를 따로 제공하는 환경에서는 route마다 `01 Route API 요청 생성기`를 하나씩 둔다.
각 `01`에는 아래 값을 직접 입력한다.

| Route branch | `Route 이름` | `선택 Flow 이름` | `하위 Flow API URL` | `입력 종류` |
| --- | --- | --- | --- | --- |
| `data_analysis` | `data_analysis` | `data_analysis_flow` | `http://127.0.0.1:7860/api/v1/run/<data_analysis_flow_id>` | `question` |
| `metadata_qa` | `metadata_qa` | `metadata_qa_flow` | `http://127.0.0.1:7860/api/v1/run/<metadata_qa_flow_id>` | `question` |
| `domain_saving` | `domain_saving` | `domain_saving_flow` | `http://127.0.0.1:7860/api/v1/run/<domain_saving_flow_id>` | `raw_text` |
| `table_catalog_saving` | `table_catalog_saving` | `table_catalog_saving_flow` | `http://127.0.0.1:7860/api/v1/run/<table_catalog_saving_flow_id>` | `raw_text` |
| `main_flow_filter_saving` | `main_flow_filter_saving` | `main_flow_filters_saving_flow` | `http://127.0.0.1:7860/api/v1/run/<main_flow_filters_saving_flow_id>` | `raw_text` |
| `dummy_data_analysis` | `dummy_data_analysis` | `dummy_data_analysis_flow` | `http://127.0.0.1:7860/api/v1/run/<dummy_data_analysis_flow_id>` | `question` |
| `dummy_metadata_qa` | `dummy_metadata_qa` | `dummy_metadata_qa_flow` | `http://127.0.0.1:7860/api/v1/run/<dummy_metadata_qa_flow_id>` | `question` |
| `dummy_domain_saving` | `dummy_domain_saving` | `dummy_domain_saving_flow` | `http://127.0.0.1:7860/api/v1/run/<dummy_domain_saving_flow_id>` | `raw_text` |
| `dummy_table_catalog_saving` | `dummy_table_catalog_saving` | `dummy_table_catalog_saving_flow` | `http://127.0.0.1:7860/api/v1/run/<dummy_table_catalog_saving_flow_id>` | `raw_text` |
| `dummy_main_flow_filter_saving` | `dummy_main_flow_filter_saving` | `dummy_main_flow_filter_saving_flow` | `http://127.0.0.1:7860/api/v1/run/<dummy_main_flow_filter_saving_flow_id>` | `raw_text` |

## 공통 연결

각 branch마다 아래 연결을 반복한다.

```text
Chat Input.message
  -> 01 Route API 요청 생성기.original_input

Smart Router.<route output>
  -> 01 Route API 요청 생성기.route_signal

01 Route API 요청 생성기.route_request
  -> 02 선택 Flow API 호출기.route_request

02 선택 Flow API 호출기.api_call_result
  -> 03 Router API 응답 정리기.api_call_result
```

`direct_answer`, `clarification`은 하위 flow API를 호출하지 않으므로 route별 API URL 설정 대상에서 제외하고, Smart Router Route Message를 바로 Chat Output으로 연결한다.
