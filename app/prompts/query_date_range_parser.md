트렌드 비교 질문에서 비교할 두 기간과 핵심 키워드를 추출합니다.

반드시 JSON만 반환합니다.

출력 형식:
{
  "period_a": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  },
  "period_b": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  },
  "focus_keywords": ["키워드"]
}

규칙:
- period_a는 더 과거의 비교 기준 기간입니다.
- period_b는 더 최근의 비교 대상 기간입니다.
- 질문에 기간이 명시되지 않으면 period_b는 기준일까지의 최근 7일, period_a는 그 직전 7일로 설정합니다.
- focus_keywords에는 검색에 필요한 기술명과 주제어를 넣습니다.

질문: {query}
기준일: {base_date}
