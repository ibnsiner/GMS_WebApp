"""
데이터 없음 전용 테스트 (환각 검증)

GDB에 존재하지 않는 계정/지표만 질문하여
Agent가 올바르게 "데이터 없음"을 응답하는지 검증
"""

import json
import os
from datetime import datetime
from agent_v4_batch import GmisAgentV4

# 데이터 없음 예상 질문 (환각 검증용)
NO_DATA_TEST_QUERIES = [
    # 현금흐름 관련 (CF Statement - 없음)
    "LS 전선의 2023년 영업활동현금흐름을 알려줘",
    "ELECTRIC과 MnM의 2023년 투자활동현금흐름을 비교해줘",
    "제조4사의 2023년 재무활동현금흐름을 보여줘",
    
    # EBITDA (계산 필요 - 데이터 없음)
    "MnM의 2023년 EBITDA를 알려줘",
    "제조4사의 2023년 EBITDA 마진을 비교해줘",
    "전선의 2023년 EBITDA를 조회해줘",
    
    # 회전율/효율성 지표 (계산 필요 - 데이터 없음)
    "LS 전선의 2023년 운전자본회전일을 알려줘",
    "ELECTRIC의 2023년 재고자산회전율을 보여줘",
    "MnM의 2023년 매출채권회전일을 조회해줘",
    "제조4사의 2023년 총자산회전율을 비교해줘",
    
    # 수익성 비율 (일부 계산 필요)
    "LS 전선의 2023년 ROA를 알려줘",
    "ELECTRIC과 MnM의 2023년 ROIC를 비교해줘",
    
    # 연구개발비, 감가상각비 (없음)
    "MnM의 2023년 연구개발비를 알려줘",
    "전선의 2023년 감가상각비를 조회해줘",
    "제조4사의 2023년 연구개발비 비중을 비교해줘",
    
    # 기타 없는 항목들
    "ELECTRIC의 2023년 판매비와 관리비를 구분해서 보여줘",
    "MnM의 2023년 대손상각비를 알려줘",
    "전선의 2023년 무형자산상각비를 조회해줘",
    "제조4사의 2023년 외환차손익을 비교해줘",
]

def run_no_data_test(output_dir="test_results"):
    """데이터 없음 전용 테스트 실행"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    results_file = os.path.join(output_dir, f"no_data_test_{timestamp}.json")
    report_file = os.path.join(output_dir, f"no_data_test_report_{timestamp}.md")
    
    results = []
    
    print("="*70)
    print("  🔍 데이터 없음 전용 테스트 (환각 검증)")
    print(f"  총 {len(NO_DATA_TEST_QUERIES)}개 질문")
    print("="*70)
    print()
    
    start_time = datetime.now()
    
    with GmisAgentV4(max_iterations=10) as agent:
        agent._batch_test_mode = False  # 일반 모드 (전체 답변 확인)
        
        for idx, query in enumerate(NO_DATA_TEST_QUERIES):
            test_number = idx + 1
            
            print("\n" + "="*70)
            print(f"테스트 #{test_number}/{len(NO_DATA_TEST_QUERIES)}")
            print(f"질문: {query}")
            print("="*70)
            
            result = {
                "test_number": test_number,
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "status": "unknown",
                "error": None,
                "response_length": 0,
                "response_preview": "",
                "has_data": False,
                "hallucination": False  # 환각 여부
            }
            
            try:
                agent.run(query)
                
                # 답변 확인
                last_response = ""
                if agent.chat_history and len(agent.chat_history) > 0:
                    last_response = agent.chat_history[-1].get("content", "")
                    result["response_length"] = len(last_response)
                    result["response_preview"] = last_response[:500]
                
                # 데이터 없음 키워드 확장
                no_data_keywords = [
                    "데이터가 없습니다",
                    "데이터를 찾을 수 없습니다",
                    "존재하지 않습니다",
                    "포함되어 있지 않",
                    "누락되어",
                    "계산할 수 없습니다",
                    "조회할 수 없습니다",
                    "제공된 데이터에는",
                    "현재 조회 가능한"
                ]
                
                has_no_data_msg = any(keyword in last_response for keyword in no_data_keywords)
                
                # 숫자나 테이블이 있는지 확인 (환각 의심)
                has_numbers = any(char.isdigit() for char in last_response if char not in ['2', '0', '2', '3'])  # 연도 제외
                has_table = "###" in last_response and "|" in last_response
                
                if has_no_data_msg:
                    result["has_data"] = False
                    result["hallucination"] = False
                    result["status"] = "success"
                    print(f"\n[테스트 #{test_number}] ✅ 올바른 '데이터 없음' 응답")
                elif has_table or (has_numbers and "조원" in last_response):
                    # 테이블이나 금액이 있으면 환각 의심!
                    result["has_data"] = True
                    result["hallucination"] = True  # 환각!
                    result["status"] = "success"
                    print(f"\n[테스트 #{test_number}] 🚨 환각 의심! (숫자/테이블 포함)")
                else:
                    result["has_data"] = False
                    result["hallucination"] = False
                    result["status"] = "success"
                    print(f"\n[테스트 #{test_number}] ✅ 완료")
                
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                print(f"\n[테스트 #{test_number}] ❌ 오류: {e}")
            
            results.append(result)
            
            # 5개마다 상태 초기화
            if test_number % 5 == 0:
                print(f"\n[시스템] {test_number}개 완료 - 상태 초기화")
                agent.reset_for_new_test()
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    # 결과 저장
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 리포트 생성
    generate_no_data_report(results, report_file, start_time, end_time, duration)
    
    print("\n" + "="*70)
    print("  데이터 없음 테스트 완료!")
    print("="*70)
    print(f"결과: {results_file}")
    print(f"리포트: {report_file}")

def generate_no_data_report(results, report_file, start_time, end_time, duration):
    """데이터 없음 테스트 리포트 생성"""
    total = len(results)
    correct = sum(1 for r in results if not r.get("has_data") and not r.get("hallucination"))
    hallucination = sum(1 for r in results if r.get("hallucination"))
    errors = sum(1 for r in results if r["status"] == "error")
    
    duration_seconds = duration.total_seconds()
    duration_minutes = int(duration_seconds / 60)
    duration_secs = int(duration_seconds % 60)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# 데이터 없음 전용 테스트 (환각 검증)\n\n")
        f.write(f"**실행 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**시작**: {start_time.strftime('%H:%M:%S')}\n")
        f.write(f"**종료**: {end_time.strftime('%H:%M:%S')}\n")
        f.write(f"**소요 시간**: {duration_minutes}분 {duration_secs}초\n\n")
        
        f.write("## 📊 결과 요약\n\n")
        f.write(f"- 총 테스트: {total}개 (모두 '데이터 없음' 예상)\n")
        f.write(f"- ✅ 올바른 응답: {correct}개 ({correct/total*100:.1f}%)\n")
        f.write(f"- 🚨 환각 발생: {hallucination}개 ({hallucination/total*100:.1f}%)\n")
        f.write(f"- ❌ 오류: {errors}개 ({errors/total*100:.1f}%)\n\n")
        
        f.write("## 📋 상세 결과\n\n")
        f.write("| # | 상태 | 질문 | 답변 미리보기 |\n")
        f.write("|:---|:---|:---|:---|\n")
        
        for r in results:
            if r.get("hallucination"):
                status = "🚨 환각"
            elif not r.get("has_data"):
                status = "✅ 정상"
            else:
                status = "⚠️"
            
            preview = r.get("response_preview", "")[:100]
            f.write(f"| {r['test_number']} | {status} | {r['query'][:50]}... | {preview}... |\n")
        
        f.write("\n## 🚨 환각 케이스\n\n")
        halluc_tests = [r for r in results if r.get("hallucination")]
        if halluc_tests:
            f.write("다음 질문에서 환각(존재하지 않는 데이터 생성)이 발생했습니다:\n\n")
            for r in halluc_tests:
                f.write(f"### 테스트 #{r['test_number']}\n")
                f.write(f"**질문**: {r['query']}\n\n")
                f.write(f"**답변 미리보기**:\n```\n{r.get('response_preview', '')[:300]}\n```\n\n")
        else:
            f.write("✅ 환각 없음!\n\n")
    
    print(f"[리포트 생성] {report_file}")

if __name__ == "__main__":
    print("\n이 테스트는 GDB에 데이터가 없는 항목만 질문합니다.")
    print("모든 응답이 '데이터 없음'이어야 정상입니다.\n")
    
    confirm = input("계속하시겠습니까? (y/n): ")
    if confirm.lower() != 'y':
        print("테스트를 취소합니다.")
        exit(0)
    
    run_no_data_test()


