# Router Flow v3 예시 질문셋

아래 질문으로 Smart Router route와 v3 API 호출 계약을 확인한다.

| 질문 | 기대 route | 확인할 점 |
| --- | --- | --- |
| 오늘 DA공정 생산량 알려줘 | `data_analysis` | 원문이 `data_analysis_flow` API의 `input_value`로 그대로 전달된다. |
| L-114제품 생산량 알려줘 | `data_analysis` | router가 제품 token을 해석하지 않고 data analysis flow로 보낸다. |
| 현재 조회 가능한 dataset list와 필수 para정보를 알려줘 | `metadata_qa` | metadata QA flow API가 호출된다. |
| 생산량 데이터 관련 쿼리문은 어떤 건지 알려줘 | `metadata_qa` | router가 SQL/metadata 질문을 data analysis로 보내지 않는다. |
| DA 공정 그룹을 D/A1~D/A6로 등록해줘 | `domain_saving` | 저장 원문이 raw text로 그대로 전달된다. |
| production_today 데이터셋을 등록해줘 | `table_catalog_saving` | query template, WITH, -- 주석이 손상되지 않아야 한다. |
| DATE 필터를 YYYYMMDD 형식 필수 파라미터로 등록해줘 | `main_flow_filter_saving` | main flow filter saving flow가 선택된다. |
| route_hint=dummy_data_analysis 오늘 DA공정 생산량 알려줘 | `dummy_data_analysis` | 명시적 dummy 요청에서만 dummy 분석 flow가 선택된다. |
| route_hint=dummy_metadata_qa 현재 조회 가능한 데이터 알려줘 | `dummy_metadata_qa` | dummy metadata QA 응답 shape를 확인한다. |
| 안녕 | `direct_answer` | 하위 flow API를 호출하지 않고 기능 안내를 반환한다. |
| 이거 확인해줘 | `clarification` | 하위 flow API를 호출하지 않고 추가 정보를 요청한다. |

## API 호출 검증 포인트

`02 선택 Flow API 호출기`의 결과에서 아래 항목을 확인한다.

- `route`
- `selected_flow`
- `subflow_call.api_url`
- `request.input_length`
- `trace.execution.http_status`
- `selected_flow_response.response_type`

## 원문 보존 검증 예시

저장 flow는 아래처럼 줄바꿈과 SQL 주석이 포함된 텍스트를 그대로 받아야 한다.

```sql
-- production today 등록
WITH base AS (
  SELECT *
  FROM PROD_TABLE
)
SELECT *
FROM base
WHERE WORK_DATE = {DATE}
```

이 텍스트가 router v3를 지나도 `subflow_call.input_value`에서 동일해야 한다.
