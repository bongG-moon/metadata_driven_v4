제품 속성 token이 여러 단어로 이어진 질문은 일반 제품군 조건으로 과도하게 분해하지 말고 pandas_function_cases의 product_token_match 케이스를 우선 검토한다.
예: "RG 32G DDR4 FBGA 96 DDP", "SP 16G DDR5 2ND X4 78 FCBGA SDP", "DA 16G GDDR6 180".
예: "RG 8G DDR4 x16 96 FCBGA SDP, CP 16G DDR x8 78 FCBGA SDP"처럼 콤마로 여러 제품이 들어오면 제품 token 묶음을 그대로 input_text에 남긴다.
예: x16/X8 ORG 표현, FC+숫자/F+숫자 lead 표현, L-218/A-663 MCP_NO 부분 입력은 match_product_tokens helper가 처리하므로 별도 pandas filter로 과도하게 분해하지 않는다.
DA공정, D/A공정, WB공정, W/B공정, FCB공정, BG공정처럼 공정명 또는 공정 그룹만 말한 경우는 제품 token 매칭이 아니다.
공정 조건은 match_product_tokens에 넣지 말고 retrieval job의 filters 또는 pandas 전처리 조건으로 OPER_NAME에 적용한다.

제품 token 매칭이 필요하면 intent_plan.pandas_function_case 또는 intent_plan.pandas_function_cases에 아래 형식으로 선택 정보를 남긴다.
function_name은 match_product_tokens를 사용한다.
input_text에는 사용자가 말한 제품 속성 token 묶음만 넣고, 날짜/공정/수량 표현은 넣지 않는다.
input_text가 "DA", "D/A", "WB", "W/B", "FCB", "BG", "B/G", "SBM"처럼 공정명/공정 그룹 단독이면 product_token_match를 선택하지 않는다.
source_alias는 helper를 적용할 DataFrame alias를 넣는다.
pandas_execution_plan에는 각 case별로 operation=apply_pandas_function_case, function_case_key, function_name, input_text, source_alias를 포함한다.

제품 token case에서 "DA 16G GDDR6 180"의 DA는 공정 D/A가 아니라 제품 속성 token일 수 있다.
이런 경우 input_text에서 DA를 제거하거나 OPER_NAME=D/A... 필터를 추가하지 않는다.
"오늘 DA공정 생산량"처럼 DA 뒤에 공정이 붙거나 질문 의미가 공정 조건이면 DA는 제품 token이 아니라 공정 그룹이다. 이 경우 product_token_match를 선택하지 않는다.

특화 함수가 여러 개 필요한 예시를 확인해야 할 때만 sample_passthrough_helper를 함께 선택한다.
sample_passthrough_helper는 실제 분석용 helper가 아니며, 여러 function case가 prompt에 전달되는 형식을 확인하기 위한 더미 helper다.

PKG OUT, OUT실적, output 실적은 생산량 metric 표현이다.
metadata에 실제 OPER_NAME="PKG OUT" 공정이 없는 한 공정 필터로 만들지 말고 PRODUCTION 합계로 계산한다.
INPUT, 투입, 투입 실적만 PKG INPUT 공정으로 보며 이때는 OPER_NAME="INPUT" 필터를 사용한다.

질문에 날짜가 없고 생산량, 생산실적, 투입, 재공수량을 현재 기준으로 묻는 경우 table catalog에 당일용 dataset이 있으면 production_today 또는 wip_today를 우선 사용한다.
production 또는 wip 이력 dataset은 어제, 전일, 특정 과거일, EOH, 아침 재공/BOH처럼 이력 기준이 명시된 경우에 사용한다.

아침 재공, BOH, 07시 기준 재공은 wip 이력 데이터의 전일 DATE를 조회한다.
예를 들어 기준일이 20260701이면 오늘 아침 재공 조회 DATE는 20260630이다.
현재 재공, 현시간 기준 재공, 지금 재공은 wip_today를 사용하고 기준일 DATE를 그대로 사용한다.

metadata와 충돌하는 특화 지시는 적용하지 않는다.
table catalog의 required_params는 반드시 data catalog 기준으로만 채운다.
required_params가 아닌 공정/제품/상태 조건은 filters 또는 pandas function case로 남긴다.
