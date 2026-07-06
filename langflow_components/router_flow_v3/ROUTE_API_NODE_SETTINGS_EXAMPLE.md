# Router Flow v3 Route별 API URL 설정 예시

각 route branch마다 `01 선택 Flow API 메시지 호출기`를 하나씩 둡니다.
각 노드에서 직접 입력하는 주요 값은 `하위 Flow API URL`입니다.

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

```text
Chat Input.message
  -> Smart Router.input

Smart Router.<route output>
  -> 01 선택 Flow API 메시지 호출기.flow_input

01 선택 Flow API 메시지 호출기.message
  -> Chat Output.input
```

## Smart Router Route Message 설정

API 호출 route의 Route Message는 비워둡니다.
`direct_answer`, `clarification`처럼 하위 flow를 호출하지 않는 route에만 사용자에게 보여줄 메시지를 입력합니다.
