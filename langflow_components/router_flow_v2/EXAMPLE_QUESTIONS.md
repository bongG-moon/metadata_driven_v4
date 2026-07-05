# Router Flow v2 예시 질문셋 - Tool Call 기반

이 문서는 `router_flow_v2`에서 Agent가 어떤 tool action을 호출해야 하는지 검증하기 위한 예시 질문셋이다.
기존 `router_flow`의 Smart Router route 대신, v2에서는 기대값을 `expected tool`로 확인한다.

## 1. 실제 분석 Tool

| 예시 질문 | Expected tool | 확인 포인트 |
| --- | --- | --- |
| 오늘 DA공정 생산량 알려줘 | `run_data_analysis` | 제조 데이터 분석 질문은 분석 tool 호출 |
| 어제 DA공정 차수별 생산량 알려줘 | `run_data_analysis` | 날짜/공정/차수 해석은 data_analysis_flow 내부 처리 |
| RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘 | `run_data_analysis` | 제품 token 매칭은 router agent가 직접 처리하지 않음 |
| 전일 L-218K8H 제품의 SBM공정에서 생산 실적 알려줘 | `run_data_analysis` | MCP/공정 조건은 분석 flow 내부 처리 |
| 현재 재공이 가장 많은 제품기준으로 장비 ASSIGN대수 알려줘, 세부 공정별로 | `run_data_analysis` | 단계적 pandas 분석은 분석 flow 내부 처리 |

## 2. Metadata QA Tool

| 예시 질문 | Expected tool | 확인 포인트 |
| --- | --- | --- |
| 지금 조회 가능한 데이터셋 목록과 각 데이터셋의 연결 방식, 필수 조건을 표로 보여줘 | `run_metadata_qa` | 데이터셋 목록 질문은 QA tool 호출 |
| 생산량과 관련해서 등록된 도메인 정보 보여줘 | `run_metadata_qa` | 도메인 설명 질문 |
| production_today 데이터셋의 쿼리문은 어떻게 등록되어 있어? | `run_metadata_qa` | query_template 조회 |
| 등록된 계산 로직들이 어떤 것들이 있는지 list 보여줘 | `run_metadata_qa` | 계산/특화 함수 metadata 조회 |
| ORG 필터는 어떻게 등록되어 있어? | `run_metadata_qa` | main flow filter 조회 |

## 3. Metadata Saving Tools

| 예시 입력 | Expected tool | 확인 포인트 |
| --- | --- | --- |
| DA 공정 그룹은 D/A1, D/A2, D/A3, D/A4, D/A5, D/A6로 등록해줘 | `save_domain_metadata` | 공정 그룹 등록 |
| 생산량은 PRODUCTION 컬럼을 sum 집계하는 지표로 등록해줘 | `save_domain_metadata` | 수량 용어 등록 |
| 제품 token 매칭 helper 설명을 domain metadata로 등록해줘 | `save_domain_metadata` | 특화 함수 설명 등록 |
| production_today 데이터셋을 등록해줘. source_type은 oracle이고 required_params는 DATE야. | `save_table_catalog_metadata` | 데이터셋 등록 |
| 아래 SQL을 production_history query_template으로 table catalog에 저장해줘 | `save_table_catalog_metadata` | SQL 원문 보존 |
| DATE는 기준일을 YYYYMMDD로 변환해서 eq 조건으로 쓰는 필터로 등록해줘 | `save_main_flow_filter_metadata` | 공통 날짜 필터 등록 |
| ORG는 x16, X8 표현에서 x를 제외하고 숫자로 매칭하는 필터로 등록해줘 | `save_main_flow_filter_metadata` | ORG 필터 등록 |

## 4. Dummy Tools

dummy tool은 명시적 테스트 요청에서만 호출한다.

| 예시 질문 | Expected tool | 확인 포인트 |
| --- | --- | --- |
| route_hint=dummy_data_analysis 오늘 DA공정 생산량 알려줘 | `run_dummy_data_analysis` | 더미 분석 명시 |
| 더미 metadata qa 테스트로 조회 가능한 데이터셋 알려줘 | `run_dummy_metadata_qa` | 더미 QA 명시 |
| route_hint=dummy_domain_saving DA 공정 그룹 등록 테스트 | `run_dummy_domain_saving` | 더미 domain saving 명시 |
| route_hint=dummy_table_catalog_saving production_today 등록 테스트 | `run_dummy_table_catalog_saving` | 더미 table catalog saving 명시 |
| route_hint=dummy_main_flow_filter_saving DATE 필터 등록 테스트 | `run_dummy_main_flow_filter_saving` | 더미 main filter saving 명시 |

## 5. Tool 호출 없이 직접 답변

| 예시 질문 | Expected tool | 기대 동작 |
| --- | --- | --- |
| 안녕 | 없음 | 기능 범위와 대표 예시를 함께 안내 |
| 이 챗봇으로 뭘 할 수 있어? | 없음 | 분석/QA/등록 가능 범위와 입력 예시 안내 |
| 사용법 알려줘 | 없음 | 분석 질문, 메타데이터 조회, 등록 원문 입력 방식을 예시와 함께 안내 |

## 6. Clarification

| 예시 입력 | Expected tool | 기대 동작 |
| --- | --- | --- |
| 이거 확인해줘 | 없음 | 분석/QA/등록 중 어떤 요청인지와 추가로 필요한 정보를 선택지로 되묻기 |
| 데이터 좀 봐줘 | 없음 | 어떤 데이터/기준일/지표인지 예시를 들어 되묻기 |
| 등록해줘 | 없음 | 등록할 원문과 metadata 종류를 되묻기 |

## 7. 빠른 Smoke Test 순서

1. `안녕`
2. `지금 조회 가능한 데이터셋 목록과 각 데이터셋의 연결 방식, 필수 조건을 표로 보여줘`
3. `오늘 DA공정 생산량 알려줘`
4. `DA 공정 그룹은 D/A1, D/A2, D/A3, D/A4, D/A5, D/A6로 등록해줘`
5. `production_today 데이터셋을 등록해줘. source_type은 oracle이고 required_params는 DATE야.`
6. `DATE는 기준일을 YYYYMMDD로 변환해서 eq 조건으로 쓰는 필터로 등록해줘`
7. `route_hint=dummy_data_analysis RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘`
8. `이거 확인해줘`

## 8. 기대 실패 기준

| 잘못된 결과 | 확인할 설정 |
| --- | --- |
| 일반 분석 질문이 dummy tool로 감 | dummy tool description과 system prompt의 명시 조건 확인 |
| 저장 요청에서 SQL/WITH/주석이 사라짐 | saving tool 입력 원문 보존 지시 확인 |
| 메타데이터 목록 질문이 분석 tool로 감 | `run_metadata_qa` description 강화 |
| Agent가 tool 결과 표를 짧게 요약함 | system prompt의 tool 결과 원문 유지 지시 확인 |
| 모호한 요청에서 임의 tool을 호출함 | clarification 규칙 강화 |
