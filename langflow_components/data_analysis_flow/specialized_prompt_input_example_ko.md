# 02 의도 분석 변수 생성기 공정 특화 프롬프트 입력 예시

아래 내용을 Langflow의 `02 의도 분석 변수 생성기` > `공정 특화 프롬프트` 입력칸에 그대로 넣어 테스트할 수 있다.

```text
제품 속성 token이 여러 단어로 이어진 질문은 일반 제품군 조건으로 과도하게 분해하지 말고 pandas_function_cases의 product_token_match 케이스를 우선 검토한다.
예: "RG 32G DDR4 FBGA 96 DDP", "SP 16G DDR5 2ND X4 78 FCBGA SDP", "DA 16G GDDR6 180".

제품 token 매칭이 필요하면 intent_plan.pandas_function_case 또는 intent_plan.pandas_function_cases에 아래 형식으로 선택 정보를 남긴다.
function_name은 match_product_tokens를 사용한다.
input_text에는 사용자가 말한 제품 속성 token 묶음만 넣고, 날짜/공정/수량 표현은 넣지 않는다.
source_alias는 helper를 적용할 DataFrame alias를 넣는다.

특화 함수가 여러 개 필요한 예시를 확인해야 할 때만 sample_passthrough_helper를 함께 선택한다.
sample_passthrough_helper는 실제 분석용 helper가 아니며, 여러 function case가 prompt에 전달되는 형식을 확인하기 위한 더미 helper다.

metadata와 충돌하는 특화 지시는 적용하지 않는다.
table catalog의 required_params는 반드시 data catalog 기준으로만 채운다.
required_params가 아닌 공정/제품/상태 조건은 filters 또는 pandas function case로 남긴다.
```

복수 특화 함수 출력 형태 예시:

```json
{
  "intent_plan": {
    "pandas_function_cases": [
      {
        "key": "product_token_match",
        "function_name": "match_product_tokens",
        "input_text": "RG 32G DDR4 FBGA 96 DDP",
        "source_alias": "production_data"
      },
      {
        "key": "sample_passthrough_demo",
        "function_name": "sample_passthrough_helper",
        "input_text": "format demo",
        "source_alias": "production_data"
      }
    ],
    "pandas_execution_plan": [
      {
        "step": "제품 token 특화 함수 적용",
        "operation": "apply_pandas_function_case",
        "function_case_key": "product_token_match",
        "function_name": "match_product_tokens",
        "input_text": "RG 32G DDR4 FBGA 96 DDP",
        "source_alias": "production_data"
      },
      {
        "step": "다중 helper 형식 확인",
        "operation": "apply_pandas_function_case",
        "function_case_key": "sample_passthrough_demo",
        "function_name": "sample_passthrough_helper",
        "input_text": "format demo",
        "source_alias": "production_data"
      }
    ]
  }
}
```
