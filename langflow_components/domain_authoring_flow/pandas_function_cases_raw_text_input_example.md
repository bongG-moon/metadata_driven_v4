# pandas_function_cases Domain Authoring 입력 예시

아래 블록은 `domain_authoring_flow`의 `00 도메인 등록 요청 로더` > `Raw Text`에 넣어 테스트할 수 있는 입력 예시다.

중요:

- 이 파일은 MongoDB에 직접 import하는 JSON이 아니다.
- 실제 저장은 domain authoring flow의 `refine -> authoring prompt -> normalizer -> review -> writer`를 통과시킨다.
- `sample_passthrough_helper`는 여러 특화 함수가 함께 전달되는 형식을 확인하기 위한 더미 함수다.

## match_product_tokens function case 등록용 raw text

```text
제품 속성 token 매칭 특화 함수 case를 등록해줘.
section은 pandas_function_cases이고 key는 product_token_match야.
display_name은 제품 속성 token 매칭이야.
function_name은 match_product_tokens야.
signature는 match_product_tokens(input_text, frame, token_columns=None, output_order=None)야.

이 case는 사용자가 "RG 32G DDR4 FBGA 96 DDP 제품", "SP 16G DDR5 2ND X4 78 FCBGA SDP 제품", "DA 16G GDDR6 180 제품"처럼 제품 속성 token을 자연어로 이어서 말했을 때 사용해.
input_text에는 날짜, 공정, 수량 표현을 제외하고 제품 속성 token 묶음만 넣어.
source_alias에는 helper를 적용할 DataFrame alias를 넣어.

helper는 TECH, DEN, DENSITY, MODE, PKG_TYPE1, PKG1, PKG_TYPE2, PKG2, LEAD, MCP_NO, DEVICE, DEVICE_DESC, TSV_DIE_TYP, TSV_DIE_TYPE, ORG, FAMILY 컬럼에서 token을 매칭해.
pseudocode는 df = match_product_tokens(input_text, sources[source_alias])야.
이 helper를 먼저 적용한 뒤 groupby, 집계, join, 정렬을 수행해.
```

## sample_passthrough_helper 더미 function case 등록용 raw text

```text
다중 특화 함수 전달 형식 확인용 더미 function case를 등록해줘.
section은 pandas_function_cases이고 key는 sample_passthrough_demo야.
display_name은 다중 helper 형식 확인 더미야.
function_name은 sample_passthrough_helper야.
signature는 sample_passthrough_helper(input_text, frame, note=None)야.

이 case는 실제 분석 로직에 사용하지 않고, 여러 pandas_function_cases가 의도 분석 결과와 pandas prompt에 어떻게 전달되는지 확인할 때만 사용해.
helper는 입력 DataFrame을 변경하지 않고 copy를 반환해.
pseudocode는 df = sample_passthrough_helper(input_text, sources[source_alias], note="format demo")야.
운영 질문에서는 명시적으로 테스트나 형식 확인을 요청한 경우에만 선택해.
```

## authoring LLM이 만들면 좋은 JSON 형태 예시

```json
{
  "items": [
    {
      "section": "pandas_function_cases",
      "key": "product_token_match",
      "status": "active",
      "payload": {
        "display_name": "제품 속성 token 매칭",
        "function_name": "match_product_tokens",
        "signature": "match_product_tokens(input_text, frame, token_columns=None, output_order=None)",
        "trigger_examples": [
          "RG 32G DDR4 FBGA 96 DDP 제품",
          "SP 16G DDR5 2ND X4 78 FCBGA SDP 제품",
          "DA 16G GDDR6 180 제품"
        ],
        "input_contract": {
          "input_text": "제품 속성 token 묶음만 입력",
          "frame": "source_alias에 해당하는 pandas DataFrame",
          "token_columns": "선택 입력. 없으면 기본 제품 속성 컬럼 사용"
        },
        "pseudocode": "df = match_product_tokens(input_text, sources[source_alias])",
        "usage_rule": "제품 token helper를 먼저 적용한 뒤 후속 집계/조인/정렬을 수행한다."
      }
    },
    {
      "section": "pandas_function_cases",
      "key": "sample_passthrough_demo",
      "status": "active",
      "payload": {
        "display_name": "다중 helper 형식 확인 더미",
        "function_name": "sample_passthrough_helper",
        "signature": "sample_passthrough_helper(input_text, frame, note=None)",
        "trigger_examples": ["특화 함수 여러 개 형식 보여줘"],
        "input_contract": {
          "input_text": "형식 확인용 문자열",
          "frame": "source_alias에 해당하는 pandas DataFrame"
        },
        "pseudocode": "df = sample_passthrough_helper(input_text, sources[source_alias], note=\"format demo\")",
        "usage_rule": "실제 분석에는 사용하지 않고 다중 helper 전달 형식 확인에만 사용한다."
      }
    }
  ],
  "missing_information": [],
  "assumptions": []
}
```
