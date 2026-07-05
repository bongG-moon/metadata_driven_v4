# Router Flow 예시 질문셋

이 문서는 `router_flow`를 Playground 또는 Web/API에서 검증할 때 사용할 대표 입력 예시다.
각 질문은 Smart Router가 어떤 route를 선택해야 하는지 확인하는 용도이며, 실제 의도 분석과 pandas 생성 품질은 선택된 하위 flow에서 검증한다.

## 사용 원칙

- 실제 분석/QA/저장 route는 `Route Message`를 비우고 원래 사용자 입력을 Run Flow로 그대로 전달한다.
- dummy route는 사용자가 명시적으로 더미 테스트를 요청했거나 `route_hint=...` 성격의 입력을 준 경우에만 선택한다.
- router는 제품 token 매칭, pandas function case 선택, 공정/제품 조건 분해를 하지 않는다.
- 저장 route로 보내는 원문은 router에서 요약하거나 수정하지 않는다.
- 애매한 요청은 임의로 분석 route로 보내지 말고 `clarification` 또는 Else 안내 branch로 보낸다.

## 1. 실제 Data Analysis Route

제조 데이터를 조회하거나 pandas 분석이 필요한 질문은 `data_analysis`로 보낸다.

| 예시 질문 | 기대 route | 대상 flow | 확인 포인트 |
| --- | --- | --- | --- |
| 오늘 DA공정 생산량 알려줘 | `data_analysis` | `data_analysis_flow` | 생산량/공정/오늘 조건이 실제 분석 flow로 전달되는지 확인 |
| 어제 DA공정 차수별 생산량 알려줘 | `data_analysis` | `data_analysis_flow` | 날짜 표현과 차수별 groupby는 하위 flow에서 처리 |
| RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘 | `data_analysis` | `data_analysis_flow` | 제품 token 매칭은 router가 아니라 분석 flow에서 처리 |
| 전일 L-218K8H 제품의 SBM공정에서 생산 실적 알려줘 | `data_analysis` | `data_analysis_flow` | MCP/제품/공정 조건이 분석 flow로 전달되는지 확인 |
| 7/1 현시간 기준 Input 실적은 있으나 D/A 공정 WIP 없는 제품 확인해줘 | `data_analysis` | `data_analysis_flow` | 복합 분석 요청도 단일 분석 route로 전달 |
| 현재 재공이 가장 많은 제품기준으로 장비 ASSIGN대수 알려줘, 세부 공정별로 | `data_analysis` | `data_analysis_flow` | 단계적 분석은 하위 flow의 pandas 계획에서 처리 |

## 2. 실제 Metadata QA Route

저장된 메타데이터의 의미, 목록, 규칙, 쿼리, 필수 조건을 묻는 질문은 `metadata_qa`로 보낸다.

| 예시 질문 | 기대 route | 대상 flow | 확인 포인트 |
| --- | --- | --- | --- |
| 지금 조회 가능한 데이터셋 목록과 각 데이터셋의 연결 방식, 필수 조건을 표로 보여줘 | `metadata_qa` | `metadata_qa_flow` | 데이터셋 목록 질문이 분석 route로 가지 않는지 확인 |
| 생산량과 관련해서 등록된 도메인 정보 보여줘 | `metadata_qa` | `metadata_qa_flow` | 도메인 metadata 설명으로 분기 |
| production_today 데이터셋의 쿼리문은 어떻게 등록되어 있어? | `metadata_qa` | `metadata_qa_flow` | query_template 질문은 metadata QA에서 처리 |
| 등록된 계산 로직들이 어떤 것들이 있는지 list 보여줘 | `metadata_qa` | `metadata_qa_flow` | pandas function case/recipe 목록 설명 |
| POP제품은 도메인 정보가 어떻게 등록되어 있어? | `metadata_qa` | `metadata_qa_flow` | 제품군 조건 조회 |
| DATE 필터는 어떤 main flow filter로 등록되어 있어? | `metadata_qa` | `metadata_qa_flow` | 메인 필터 metadata 조회 |

## 3. 실제 Metadata Saving Routes

메타데이터를 새로 등록하거나 수정하라는 요청은 저장 route로 보낸다.
저장 route는 원문 전체를 `Raw Text` 입력으로 받으므로, router에서 내용을 변형하지 않는다.

### 3.1 Domain Saving

| 예시 입력 | 기대 route | 대상 flow | 확인 포인트 |
| --- | --- | --- | --- |
| DA 공정 그룹은 D/A1, D/A2, D/A3, D/A4, D/A5, D/A6로 등록해줘 | `domain_saving` | `domain_saving_flow` | 업무 용어/공정 그룹 등록 |
| 생산량은 PRODUCTION 컬럼을 sum 집계하는 지표로 등록해줘 | `domain_saving` | `domain_saving_flow` | 용어/지표 정의 등록 |
| 제품 token 매칭 helper 설명을 domain metadata로 등록해줘 | `domain_saving` | `domain_saving_flow` | 특화 함수 설명 등록 |

### 3.2 Table Catalog Saving

| 예시 입력 | 기대 route | 대상 flow | 확인 포인트 |
| --- | --- | --- | --- |
| production_today 데이터셋을 등록해줘. source_type은 oracle이고 required_params는 DATE야. query_template은 아래 SQL을 사용해. | `table_catalog_saving` | `table_catalog_saving_flow` | 데이터셋/source/query/필수 조건 등록 |
| wip_today 데이터셋의 컬럼과 query_template을 table catalog로 저장해줘 | `table_catalog_saving` | `table_catalog_saving_flow` | 테이블 카탈로그 저장 요청 |
| Goodocs 계획 데이터셋을 source_type goodocs로 등록해줘 | `table_catalog_saving` | `table_catalog_saving_flow` | Goodocs source 등록 |

### 3.3 Main Flow Filter Saving

| 예시 입력 | 기대 route | 대상 flow | 확인 포인트 |
| --- | --- | --- | --- |
| DATE는 기준일, 날짜 표현을 YYYYMMDD로 변환해서 eq 조건으로 쓰는 필터로 등록해줘 | `main_flow_filter_saving` | `main_flow_filters_saving_flow` | 공통 날짜 필터 등록 |
| OPER_NAME은 공정명, 세부공정 alias를 처리하는 main filter로 등록해줘 | `main_flow_filter_saving` | `main_flow_filters_saving_flow` | 공정 필터 정의 등록 |
| ORG는 x16, X8처럼 x를 제외하고 숫자 기준으로 매칭할 수 있는 필터로 등록해줘 | `main_flow_filter_saving` | `main_flow_filters_saving_flow` | ORG 필터 정의 등록 |

## 4. Dummy Routes

dummy route는 개발 중 router wiring, Web parser, Chat Output 표시 형식을 빠르게 확인할 때만 사용한다.
운영성 질문에 dummy route가 선택되면 안 된다.

| 예시 질문 | 기대 route | 대상 flow | 확인 포인트 |
| --- | --- | --- | --- |
| route_hint=dummy_data_analysis RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘 | `dummy_data_analysis` | `dummy_data_analysis_flow` | 더미 분석 응답의 `data_analysis` 계약 확인 |
| dummy_data_analysis 테스트로 오늘 DA공정 생산량 알려줘 | `dummy_data_analysis` | `dummy_data_analysis_flow` | 명시적 더미 분석 요청 |
| route_hint=dummy_metadata_qa 조회 가능한 데이터셋 알려줘 | `dummy_metadata_qa` | `dummy_metadata_qa_flow` | 더미 Metadata QA 응답 계약 확인 |
| route_hint=dummy_domain_saving DA 공정 그룹 등록 테스트 | `dummy_domain_saving` | `dummy_domain_saving_flow` | 더미 domain saving 응답 계약 확인 |
| route_hint=dummy_table_catalog_saving production_today 데이터셋 등록 테스트 | `dummy_table_catalog_saving` | `dummy_table_catalog_saving_flow` | 더미 table catalog saving 응답 계약 확인 |
| route_hint=dummy_main_flow_filter_saving DATE 필터 등록 테스트 | `dummy_main_flow_filter_saving` | `dummy_main_flow_filter_saving_flow` | 더미 main filter saving 응답 계약 확인 |

## 5. Direct Answer Route

하위 flow 실행 없이 짧은 안내로 끝낼 수 있는 입력은 `direct_answer`로 보낸다.

| 예시 질문 | 기대 route | Route Message 예시 |
| --- | --- | --- |
| 안녕 | `direct_answer` | 안녕하세요. 제조 데이터 분석, 메타데이터 QA, 메타데이터 등록을 도와드릴 수 있습니다.<br><br>예를 들어 이렇게 물어볼 수 있습니다.<br>- 데이터 분석: 오늘 DA공정 생산량 알려줘<br>- 메타데이터 QA: 지금 조회 가능한 데이터셋과 필수 조건을 보여줘<br>- 메타데이터 등록: DA 공정 그룹은 D/A1~D/A6로 등록해줘<br><br>원하는 내용을 자연어로 입력해 주세요. |
| 이 챗봇으로 뭘 할 수 있어? | `direct_answer` | 제조 데이터 분석, 메타데이터 QA, 메타데이터 등록을 처리할 수 있습니다. 분석 질문은 자연어로 입력하고, 등록 요청은 원문을 그대로 붙여넣으면 됩니다. |
| 사용법 알려줘 | `direct_answer` | 분석은 기준일/공정/제품/지표를 자연어로 물어보면 됩니다. 메타데이터 조회는 데이터셋/컬럼/계산 로직을 물어보고, 등록은 원문과 metadata 종류를 함께 입력해 주세요. |

## 6. Clarification 또는 Else Branch

분석/QA/저장 중 어느 요청인지 판단하기 어려운 입력은 `clarification` 또는 Else 안내 branch로 보낸다.

| 예시 입력 | 기대 route | Route Message 예시 |
| --- | --- | --- |
| 이거 확인해줘 | `clarification` | 무엇을 확인하면 될지 조금만 더 알려주세요.<br><br>아래 중 어떤 요청인지 알려주시면 바로 이어서 처리하겠습니다.<br>- 데이터 분석: 기준일, 공정, 제품, 보고 싶은 지표를 알려주세요. 예: 오늘 DA공정 생산량 알려줘<br>- 메타데이터 QA: 확인할 데이터셋, 컬럼, 계산 로직, 등록 규칙을 알려주세요. 예: production_today 필수 조건 보여줘<br>- 메타데이터 등록: 등록할 원문과 metadata 종류를 알려주세요. 예: DA 공정 그룹을 domain metadata로 등록해줘 |
| 데이터 좀 봐줘 | `clarification` | 어떤 데이터와 기준일, 지표를 보고 싶은지 알려주세요. 예: 오늘 DA공정 생산량, 어제 WB공정 재공, 6/27 공정별 생산실적처럼 입력하면 됩니다. |
| 등록해줘 | `clarification` | 어떤 메타데이터를 등록할지 원문과 대상 유형을 알려주세요. 예: domain metadata, table catalog metadata, main flow filter 중 하나를 함께 적어 주세요. |

## 7. 빠른 Smoke Test 순서

아래 순서로 입력하면 주요 route가 모두 한 번씩 검증된다.

1. `안녕`
2. `지금 조회 가능한 데이터셋 목록과 각 데이터셋의 연결 방식, 필수 조건을 표로 보여줘`
3. `오늘 DA공정 생산량 알려줘`
4. `DA 공정 그룹은 D/A1, D/A2, D/A3, D/A4, D/A5, D/A6로 등록해줘`
5. `production_today 데이터셋을 등록해줘. source_type은 oracle이고 required_params는 DATE야.`
6. `DATE는 기준일을 YYYYMMDD로 변환해서 eq 조건으로 쓰는 필터로 등록해줘`
7. `route_hint=dummy_data_analysis RG 32G DDR4 FBGA 96 DDP 제품 BG공정에서 생산량과 재공수량 알려줘`
8. `이거 확인해줘`

## 8. 기대 실패 기준

아래처럼 분기되면 router 설정을 다시 확인한다.

| 잘못된 결과 | 확인할 설정 |
| --- | --- |
| `오늘 DA공정 생산량 알려줘`가 `metadata_qa`로 감 | `data_analysis` Route Description이 너무 약하거나 metadata 설명이 과도함 |
| `조회 가능한 데이터셋 목록`이 `data_analysis`로 감 | `metadata_qa` Route Description에 데이터셋 목록/필수 조건 설명 추가 필요 |
| 일반 분석 질문이 dummy route로 감 | dummy route 설명을 “명시적 route_hint가 있을 때만”으로 제한 |
| saving route에서 원문이 사라짐 | 해당 route의 `Route Message`가 비어 있는지 확인 |
| direct/clarification에서 사용자 입력이 그대로 출력됨 | direct/clarification의 `Route Message` 또는 Else Message 확인 |
