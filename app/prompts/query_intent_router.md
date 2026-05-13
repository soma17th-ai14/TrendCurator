사용자 질문을 TrendCurator 질의 유형으로 분류합니다.

반드시 JSON만 반환합니다.

출력 형식:
{
  "intent": "TREND_COMPARISON 또는 GENERAL_QA",
  "confidence": 0.0,
  "reasoning": "분류 이유"
}

분류 기준:
- TREND_COMPARISON: 사용자가 두 기간을 명시적으로 비교하거나 변화량을 묻는 경우입니다. 예: "지난주 대비 이번 주", "어떻게 달라졌나", "compare last week vs this week".
- GENERAL_QA: 특정 주제의 요약, 설명, 최신 동향, 관련 문서 탐색을 묻는 경우입니다. 예: "최근 LangGraph 트렌드 요약", "RAG 논문 알려줘".
- 애매하면 GENERAL_QA를 선택합니다.

질문: {query}
기준일: {base_date}
