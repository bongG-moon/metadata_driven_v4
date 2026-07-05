# Router Flow v2 Tool Descriptions

이 문서는 `Run Flow` 컴포넌트에서 Tool Mode를 켠 뒤 `Edit Tool Actions`에 넣을 action slug, 이름, 설명을 정리한 것이다.
Agent가 tool을 고르는 기준은 대부분 이 설명에서 결정되므로, 아래 문구를 가능한 그대로 사용한다.

## 공통 설정

- Tool Mode는 각 `Run Flow` 컴포넌트에서 켠다.
- action slug는 영문 snake_case로 고정한다.
- description에는 호출 조건과 금지 조건을 함께 적는다.
- saving tool의 입력은 `raw_text`이며, 원문 보존이 가장 중요하다.
- analysis/QA tool의 입력은 `question`이며, 사용자 질문 전체를 전달한다.

## Tool Action Table

| Action Slug | Display Name | 대상 flow | 입력 의미 |
| --- | --- | --- | --- |
| `run_data_analysis` | 제조 데이터 분석 실행 | `data_analysis_flow` | `question` |
| `run_metadata_qa` | 메타데이터 QA 실행 | `metadata_qa_flow` | `question` |
| `save_domain_metadata` | 도메인 메타데이터 저장 | `domain_saving_flow` | `raw_text` |
| `save_table_catalog_metadata` | 테이블 카탈로그 메타데이터 저장 | `table_catalog_saving_flow` | `raw_text` |
| `save_main_flow_filter_metadata` | 메인 플로우 필터 저장 | `main_flow_filters_saving_flow` | `raw_text` |
| `run_dummy_data_analysis` | 더미 제조 데이터 분석 실행 | `dummy_data_analysis_flow` | `question` |
| `run_dummy_metadata_qa` | 더미 메타데이터 QA 실행 | `dummy_metadata_qa_flow` | `question` |
| `run_dummy_domain_saving` | 더미 도메인 저장 실행 | `dummy_domain_saving_flow` | `raw_text` |
| `run_dummy_table_catalog_saving` | 더미 테이블 카탈로그 저장 실행 | `dummy_table_catalog_saving_flow` | `raw_text` |
| `run_dummy_main_flow_filter_saving` | 더미 메인 필터 저장 실행 | `dummy_main_flow_filter_saving_flow` | `raw_text` |

## Copy-Paste Descriptions

### run_data_analysis

제조 데이터 조회와 pandas 분석이 필요한 질문을 처리한다.
생산량, 생산실적, 재공, WIP, 투입, INPUT, PKG OUT, 공정별/제품별 집계, 장비 ASSIGN, 기준일 분석, 제품 token이 포함된 제조 데이터 질문에 사용한다.
제품 token 매칭, pandas function case 선택, 공정/제품/상태 조건 해석은 이 tool 내부에서 처리하므로 router agent가 직접 분해하지 않는다.
입력에는 사용자 질문 전체를 그대로 전달한다.

### run_metadata_qa

저장된 메타데이터에 대한 질문을 처리한다.
등록된 데이터셋 목록, 연결 방식, 필수 조건, query_template, 컬럼 의미, 도메인 정보, 공정 그룹, 제품 조건, 계산 로직, main flow filter, 저장된 규칙 설명을 묻는 질문에 사용한다.
실제 수량 계산이나 데이터 조회를 요구하는 질문에는 사용하지 않는다.
입력에는 사용자 질문 전체를 그대로 전달한다.

### save_domain_metadata

domain metadata 저장 요청을 처리한다.
업무 용어, 공정 그룹, 제품 그룹, 수량 용어, 분석 규칙, 특화 함수 설명, pandas function case 설명을 등록하거나 수정하라는 요청에 사용한다.
사용자 원문을 요약하거나 정리하지 말고 raw_text로 그대로 전달한다.
데이터셋 query_template이나 required_params 등록 요청에는 사용하지 않는다.

### save_table_catalog_metadata

table catalog metadata 저장 요청을 처리한다.
데이터셋 이름, dataset_key, dataset_family, source_type, db_key, query_template, required_params, columns, source_config를 등록하거나 수정하라는 요청에 사용한다.
SQL에 `WITH`문이나 `--` 주석이 포함되어도 원문을 그대로 raw_text로 전달한다.
업무 용어나 공통 필터 정의 등록에는 사용하지 않는다.

### save_main_flow_filter_metadata

main flow filter metadata 저장 요청을 처리한다.
DATE, WORK_DATE, OPER_NAME, ORG, DEVICE, MCP_NO처럼 분석 flow 전반에서 공통으로 쓰는 필터 정의, alias, operator, value_type, value_shape 등록 요청에 사용한다.
사용자 원문을 그대로 raw_text로 전달한다.
데이터셋 자체 또는 query_template 등록에는 사용하지 않는다.

### run_dummy_data_analysis

개발/스모크 테스트용 더미 제조 데이터 분석 tool이다.
사용자가 명시적으로 dummy, 더미, route_hint=dummy_data_analysis를 요청한 경우에만 사용한다.
일반 제조 분석 질문에는 절대 사용하지 않는다.

### run_dummy_metadata_qa

개발/스모크 테스트용 더미 metadata QA tool이다.
사용자가 명시적으로 dummy, 더미, route_hint=dummy_metadata_qa를 요청한 경우에만 사용한다.
일반 metadata QA 질문에는 절대 사용하지 않는다.

### run_dummy_domain_saving

개발/스모크 테스트용 더미 domain saving tool이다.
사용자가 명시적으로 dummy, 더미, route_hint=dummy_domain_saving을 요청한 경우에만 사용한다.
일반 domain 저장 요청에는 절대 사용하지 않는다.

### run_dummy_table_catalog_saving

개발/스모크 테스트용 더미 table catalog saving tool이다.
사용자가 명시적으로 dummy, 더미, route_hint=dummy_table_catalog_saving을 요청한 경우에만 사용한다.
일반 table catalog 저장 요청에는 절대 사용하지 않는다.

### run_dummy_main_flow_filter_saving

개발/스모크 테스트용 더미 main flow filter saving tool이다.
사용자가 명시적으로 dummy, 더미, route_hint=dummy_main_flow_filter_saving을 요청한 경우에만 사용한다.
일반 main flow filter 저장 요청에는 절대 사용하지 않는다.
