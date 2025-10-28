"""
GMIS Agent v4 자동 테스트 스크립트 (배치 모드)

복합 문장 쿼리 60개를 자동으로 실행하고 결과를 기록합니다.

[배치 모드 최적화]
- agent_v4_batch.py 사용 (원본과 분리)
- 각 테스트 간 상태 독립성 보장
- 외부 라이브러리 로그 최소화
"""

import json
import os
from datetime import datetime
from agent_v4_batch import GmisAgentV4

# 테스트 질문 목록 (1-60번)
TEST_QUERIES = [
    # A. 다중 회사 + 다중 지표 (1-20)
    "LS 전선과 MnM의 2023년 매출액과 영업이익을 비교해줘",
    "제조4사의 2023년 매출액, 영업이익, 순이익을 모두 보여줘",
    "ELECTRIC과 엠트론의 2022년과 2023년 매출액 변화를 알려줘",
    "LS 전선, MnM, ELECTRIC 3개사의 2023년 상반기 영업이익과 하반기 영업이익을 비교해줘",
    "제조4사 중에서 2023년 매출액이 가장 높은 회사와 영업이익이 가장 높은 회사를 찾아줘",
    "MnM과 엠트론의 2023년 자산총계와 부채총계, 그리고 부채비율을 계산해줘",
    "LS 전선의 2023년 1분기부터 4분기까지 매출액과 각 분기별 영업이익률을 보여줘",
    "ELECTRIC과 MnM의 2023년 국내매출액과 해외매출액 비중을 비교해줘",
    "제조4사의 2023년 EBITDA와 당기순이익, 그리고 이자보상배율을 모두 조회해줘",
    "LS 전선과 ELECTRIC의 2022년 대비 2023년 매출액 성장률과 영업이익 성장률을 계산해줘",
    
    # 11-20
    "MnM과 엠트론의 2023년 월별 매출액 추이와 분기별 영업이익 합계를 보여줘",
    "제조4사의 2023년 유동자산과 비유동자산, 그리고 자기자본비율을 비교해줘",
    "LS 전선의 2023년 매출총이익과 판매관리비, 그리고 조정영업이익을 조회해줘",
    "ELECTRIC과 MnM의 2023년 영업외손익과 세전이익, 법인세를 모두 보여줘",
    "엠트론과 LS 전선의 2023년 현금성자산과 차입금, 순차입금을 비교해줘",
    "제조4사의 2023년 3분기 매출액과 영업이익, 그리고 전년 동기 대비 증감률을 계산해줘",
    "MnM과 ELECTRIC의 2023년 재고자산과 매출채권, 운전자본회전일을 조회해줘",
    "LS 전선과 엠트론의 2023년 연구개발비와 감가상각비, 그리고 매출액 대비 비중을 보여줘",
    "제조4사 중 2023년 ROE가 가장 높은 회사와 ROA가 가장 높은 회사를 찾아줘",
    "ELECTRIC과 MnM의 2023년 영업활동현금흐름과 투자활동현금흐름을 비교해줘",
    
    # B. 시계열 + 다중 조건 (21-40)
    "LS 전선의 2022년과 2023년 매출액을 비교하고, 월별 증감 패턴을 분석해줘",
    "MnM의 2023년 1월부터 12월까지 영업이익 추이와 최고점, 최저점을 찾아줘",
    "ELECTRIC의 2023년 분기별 순이익과 전분기 대비 증감률, 전년 동기 대비 증감률을 계산해줘",
    "엠트론의 2022년 하반기와 2023년 상반기 매출액을 비교하고 성장률을 구해줘",
    "제조4사의 2023년 각 월별 매출액과 3개월 이동평균을 계산해줘",
    "LS 전선의 2023년 상반기 영업이익과 하반기 영업이익, 그리고 연간 목표 달성률을 보여줘",
    "MnM의 2023년 1분기부터 4분기까지 자산총계 변화와 분기별 증감률을 분석해줘",
    "ELECTRIC의 2022년 4분기와 2023년 1분기, 2분기 매출액 연속 변화를 추적해줘",
    "엠트론의 2023년 월별 부채비율 변화와 연중 최고, 최저 시점을 찾아줘",
    "제조4사의 2023년 반기별 영업이익률과 전년 동기 대비 개선폭을 계산해줘",
    
    # 31-40
    "LS 전선의 2023년 각 분기 매출액과 누적 매출액, 그리고 연간 목표 대비 진척률을 보여줘",
    "MnM의 2023년 월별 영업이익과 6개월 이동평균, 그리고 계절성 패턴을 분석해줘",
    "ELECTRIC의 2022년과 2023년 각 분기별 순이익 비교와 개선된 분기를 찾아줘",
    "엠트론의 2023년 상반기와 하반기 EBITDA 비교, 그리고 월별 변동성을 계산해줘",
    "제조4사의 2023년 3분기 매출액과 전분기, 전년 동분기 대비 증감률을 모두 구해줘",
    "LS 전선의 2023년 월별 이자보상배율과 연중 안정성 지표를 분석해줘",
    "MnM의 2023년 분기별 자기자본비율 변화와 재무안정성 추이를 평가해줘",
    "ELECTRIC의 2023년 반기별 운전자본과 전년 동기 대비 효율성 개선도를 측정해줘",
    "엠트론의 2023년 월별 현금흐름과 분기별 누적 현금흐름을 추적해줘",
    "제조4사의 2023년 각 월 매출액 대비 영업이익률과 연간 평균 대비 편차를 계산해줘",
    
    # C. 조건부 + 비교 분석 (41-60)
    "제조4사 중 2023년 매출액이 1조원 이상인 회사들의 영업이익률을 비교해줘",
    "2023년 영업이익이 전년 대비 증가한 회사들과 감소한 회사들을 분류해줘",
    "LS 전선과 MnM 중 2023년 부채비율이 더 낮은 회사의 재무안정성을 분석해줘",
    "제조4사 중 2023년 ROE가 10% 이상인 회사들의 수익성 지표를 모두 보여줘",
    "2023년 상반기 대비 하반기 매출액이 증가한 회사들과 그 증가율을 찾아줘",
    "ELECTRIC과 엠트론 중 2023년 이자보상배율이 더 높은 회사의 안정성을 평가해줘",
    "제조4사 중 2023년 영업이익률이 업계 평균(5%) 이상인 회사들을 선별해줘",
    "2023년 자산총계가 전년 대비 10% 이상 증가한 회사들의 성장 동력을 분석해줘",
    "MnM과 LS 전선 중 2023년 현금성자산이 더 많은 회사의 유동성을 비교해줘",
    "제조4사 중 2023년 순이익이 양수인 회사들의 수익성 순위를 매겨줘",
    
    # 51-60
    "2023년 해외매출 비중이 50% 이상인 회사들의 글로벌 경쟁력을 평가해줘",
    "ELECTRIC과 MnM 중 2023년 매출액 성장률이 더 높은 회사의 성장 요인을 분석해줘",
    "제조4사 중 2023년 EBITDA 마진이 15% 이상인 회사들의 운영 효율성을 비교해줘",
    "2023년 차입금 대비 EBITDA 배수가 3배 미만인 회사들의 재무 건전성을 평가해줘",
    "LS 전선과 엠트론 중 2023년 운전자본회전일이 더 짧은 회사의 효율성을 분석해줘",
    "제조4사 중 2023년 분기별 매출액 변동성이 가장 낮은 회사를 찾아줘",
    "2023년 영업활동현금흐름이 순이익보다 높은 회사들의 현금 창출 능력을 평가해줘",
    "MnM과 ELECTRIC 중 2023년 자기자본수익률이 더 높은 회사의 주주가치 창출을 분석해줘",
    "제조4사 중 2023년 매출액 대비 연구개발비 비중이 3% 이상인 회사들을 찾아줘",
    "2023년 영업레버리지 효과가 가장 큰 회사와 그 요인을 분석해줘",
]

def run_batch_test(start_idx=0, end_idx=60, output_dir="test_results", auto_sequential=False):
    """
    배치 테스트 실행
    
    Args:
        start_idx: 시작 인덱스 (0부터)
        end_idx: 종료 인덱스 (60까지)
        output_dir: 결과 저장 디렉토리
        auto_sequential: True면 5개씩 자동 순차 실행
    """
    # [자동 순차 모드] 5개씩 나누어 실행
    if auto_sequential and (end_idx - start_idx) > 5:
        auto_start_time = datetime.now()
        
        print("="*70)
        print(f"  🔄 자동 순차 모드")
        print(f"  {start_idx+1}번 ~ {end_idx}번을 5개씩 나누어 자동 실행합니다")
        print(f"  시작: {auto_start_time.strftime('%H:%M:%S')}")
        print("="*70)
        print()
        
        all_results = []
        
        for chunk_start in range(start_idx, end_idx, 5):
            chunk_end = min(chunk_start + 5, end_idx)
            
            print(f"\n{'='*70}")
            print(f"  🚀 {chunk_start+1}번 ~ {chunk_end}번 실행 중...")
            print(f"{'='*70}\n")
            
            # 5개 단위로 실행 (재귀 호출, auto_sequential=False로)
            chunk_results = run_batch_test(chunk_start, chunk_end, output_dir, auto_sequential=False)
            all_results.extend(chunk_results)
            
            # 진행 상황 출력
            completed = len(all_results)
            total = end_idx - start_idx
            print(f"\n[진행 상황] {completed}/{total} 완료 ({completed/total*100:.1f}%)")
            
            # 다음 청크 전 대기 (API 쿨다운)
            if chunk_end < end_idx:
                print("\n⏸️  다음 그룹 준비 중... (3초 대기)")
                import time
                time.sleep(3)
        
        auto_end_time = datetime.now()
        auto_duration = auto_end_time - auto_start_time
        auto_duration_seconds = auto_duration.total_seconds()
        auto_duration_minutes = int(auto_duration_seconds / 60)
        auto_duration_secs = int(auto_duration_seconds % 60)
        
        print("\n" + "="*70)
        print("  ✅ 자동 순차 실행 완료!")
        print(f"  ⏱️  총 소요 시간: {auto_duration_minutes}분 {auto_duration_secs}초")
        print(f"     평균: {auto_duration_seconds/len(all_results):.1f}초/테스트")
        print("="*70)
        
        # 통합 리포트 생성 (소요 시간 포함)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_results_file = os.path.join(output_dir, f"batch_test_auto_{timestamp}.json")
        final_report_file = os.path.join(output_dir, f"batch_test_report_auto_{timestamp}.md")
        
        with open(final_results_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        
        generate_report(all_results, final_report_file, auto_start_time, auto_end_time, auto_duration)
        
        print(f"\n최종 결과: {final_results_file}")
        print(f"최종 리포트: {final_report_file}\n")
        
        return all_results
    
    # [일반 모드] 단일 범위 실행
    # 결과 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 결과 저장 파일
    results_file = os.path.join(output_dir, f"batch_test_{timestamp}.json")
    report_file = os.path.join(output_dir, f"batch_test_report_{timestamp}.md")
    
    results = []
    
    # 시작 시간 기록
    start_time = datetime.now()
    
    print("="*70)
    print(f"  GMIS Agent v4 배치 테스트")
    print(f"  테스트 범위: {start_idx+1}번 ~ {end_idx}번")
    print(f"  시작 시간: {start_time.strftime('%H:%M:%S')}")
    print("="*70)
    print()
    
    # Agent 초기화 (배치 테스트 최적화)
    with GmisAgentV4(max_iterations=10) as agent:
        # 배치 테스트용 설정
        agent.max_history_turns = 100  # 자동 요약 사실상 비활성화
        
        # 배치 테스트 플래그 설정
        agent._batch_test_mode = True
        
        for idx in range(start_idx, min(end_idx, len(TEST_QUERIES))):
            query = TEST_QUERIES[idx]
            test_number = idx + 1
            
            print("\n" + "="*70)
            print(f"테스트 #{test_number}/{end_idx}")
            print(f"질문: {query}")
            print("="*70)
            
            # 결과 기록 시작
            result = {
                "test_number": test_number,
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "status": "unknown",
                "error": None,
                "response_length": 0,
                "response_preview": ""  # 답변 미리보기 추가
            }
            
            try:
                # Agent 실행 (출력은 그대로 표시)
                agent.run(query)
                
                # 답변 내용 확인 및 저장
                last_response = ""
                if agent.chat_history and len(agent.chat_history) > 0:
                    last_response = agent.chat_history[-1].get("content", "")
                    result["response_length"] = len(last_response)
                    result["response_preview"] = last_response[:300]  # 처음 300자 저장
                
                # [수정] "데이터 없음" 메타 정보만 추가 (상태는 success 유지)
                no_data_keywords = [
                    "데이터가 없습니다",
                    "데이터를 찾을 수 없습니다",
                    "조회 결과가 없습니다",
                    "Query returned no data",
                    "해당하는 정보가 없습니다",
                    "재무제표에 포함되어 있지 않습니다",
                    "데이터가 누락되어",
                    "포함되어 있지 않아",
                    "값이 포함되어 있지 않아",
                    "계산할 수 없습니다",
                    "조회할 수 없습니다",
                    "제공된 데이터에는",  # "제공된 데이터에는 X가 포함되어..." 패턴
                    "현재 조회 가능한",     # "현재 조회 가능한 계정 목록에..."
                    "누락되어 있습니다"     # "데이터가 누락되어 있습니다"
                ]
                
                result["has_data"] = not any(keyword in last_response for keyword in no_data_keywords)
                result["status"] = "success"
                
                # 사용자에게 알림
                if not result["has_data"]:
                    print(f"\n[테스트 #{test_number}] ✅ 완료 (⚠️ 답변: 데이터 없음)")
                else:
                    print(f"\n[테스트 #{test_number}] ✅ 완료 (데이터 응답)")
                
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                result["has_data"] = False
                print(f"\n[테스트 #{test_number}] ❌ 오류: {e}")
            
            results.append(result)
            
            # [배치 최적화] 5개 테스트마다 상태 초기화
            if test_number % 5 == 0:
                print(f"\n{'='*70}")
                print(f"[시스템] {test_number}개 테스트 완료 - Agent 상태 초기화 중...")
                print(f"{'='*70}")
                agent.reset_for_new_test()
                print(f"[OK] 상태 초기화 완료. 다음 테스트 준비됨.\n")
            
            # 중간 저장 (5개마다)
            if (test_number % 5 == 0) or test_number == end_idx:
                with open(results_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"\n[진행상황] {test_number}/{end_idx} 완료 → {results_file} 저장됨")
    
    # 종료 시간 기록
    end_time = datetime.now()
    duration = end_time - start_time
    duration_seconds = duration.total_seconds()
    duration_minutes = duration_seconds / 60
    
    # 최종 리포트 생성 (소요 시간 포함)
    generate_report(results, report_file, start_time, end_time, duration)
    
    print("\n" + "="*70)
    print("  배치 테스트 완료!")
    print("="*70)
    print(f"결과 파일: {results_file}")
    print(f"리포트: {report_file}")
    print()
    
    # 요약 통계
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    no_data = sum(1 for r in results if r.get("has_data") == False and r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    
    print(f"총 테스트: {total}개")
    print(f"✅ 성공: {success}개 ({success/total*100:.1f}%)")
    print(f"⚠️ 데이터 없음: {no_data}개 ({no_data/total*100:.1f}%)")
    print(f"❌ 오류: {errors}개 ({errors/total*100:.1f}%)")
    print(f"\n⏱️  소요 시간: {int(duration_minutes)}분 {int(duration_seconds % 60)}초")
    print(f"   평균: {duration_seconds/total:.1f}초/테스트")
    
    return results  # 결과 리턴 (자동 순차 모드용)

def generate_report(results, report_file, start_time=None, end_time=None, duration=None):
    """테스트 결과 리포트 생성"""
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    
    # 데이터 존재 여부 통계
    with_data = sum(1 for r in results if r.get("has_data", False))
    no_data = sum(1 for r in results if r.get("has_data") == False and r["status"] == "success")
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# GMIS Agent v4 배치 테스트 리포트\n\n")
        f.write(f"**실행 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 소요 시간 추가
        if start_time and end_time and duration:
            duration_seconds = duration.total_seconds()
            duration_minutes = int(duration_seconds / 60)
            duration_secs = int(duration_seconds % 60)
            avg_per_test = duration_seconds / total if total > 0 else 0
            
            f.write(f"**시작**: {start_time.strftime('%H:%M:%S')}\n")
            f.write(f"**종료**: {end_time.strftime('%H:%M:%S')}\n")
            f.write(f"**소요 시간**: {duration_minutes}분 {duration_secs}초\n")
            f.write(f"**평균**: {avg_per_test:.1f}초/테스트\n\n")
        
        f.write("## 📊 요약 통계\n\n")
        f.write(f"- 총 테스트: {total}개\n")
        f.write(f"- ✅ 성공: {success}개 ({success/total*100:.1f}%)\n")
        f.write(f"  - 데이터 응답: {with_data}개\n")
        f.write(f"  - 데이터 없음 응답: {no_data}개 (GDB에 데이터 미존재)\n")
        f.write(f"- ❌ 오류: {errors}개 ({errors/total*100:.1f}%)\n\n")
        
        f.write("## 📋 상세 결과\n\n")
        f.write("| # | 상태 | 데이터 | 질문 | 답변 미리보기 |\n")
        f.write("|:---|:---:|:---:|:---|:---|\n")
        
        for r in results:
            if r["status"] == "success":
                status_icon = "✅"
                data_icon = "📊" if r.get("has_data", False) else "⚠️"
            else:
                status_icon = "❌"
                data_icon = "-"
            
            preview = r.get("response_preview", "")[:80] if r.get("response_preview") else "-"
            f.write(f"| {r['test_number']} | {status_icon} | {data_icon} | {r['query'][:50]}... | {preview}... |\n")
        
        f.write("\n## ⚠️ 데이터 없음 케이스\n\n")
        no_data_tests = [r for r in results if r.get("has_data") == False and r["status"] == "success"]
        if no_data_tests:
            f.write("다음 질문들은 Knowledge Graph에 데이터가 존재하지 않아 '데이터 없음' 응답을 받았습니다:\n\n")
            for r in no_data_tests:
                f.write(f"- **테스트 #{r['test_number']}**: {r['query']}\n")
                f.write(f"  - 답변: {r.get('response_preview', '')[:150]}...\n\n")
        else:
            f.write("모든 질문에서 데이터를 찾았습니다.\n\n")
        
        f.write("\n## 🚨 오류 상세\n\n")
        error_tests = [r for r in results if r["status"] == "error"]
        if error_tests:
            for r in error_tests:
                f.write(f"### 테스트 #{r['test_number']}\n")
                f.write(f"**질문**: {r['query']}\n\n")
                f.write(f"**오류**: {r.get('error', 'Unknown')}\n\n")
        else:
            f.write("오류 없음\n")
    
    print(f"[리포트 생성] {report_file}")

if __name__ == "__main__":
    import sys
    
    # 명령행 인자로 범위 지정 가능
    # python test_agent_batch.py 0 20         → 1-20번 테스트 (일반)
    # python test_agent_batch.py 0 60 auto   → 1-60번 자동 순차 (5개씩)
    
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    auto = sys.argv[3].lower() == 'auto' if len(sys.argv) > 3 else False
    
    print(f"\n시작 인덱스: {start}, 종료 인덱스: {end}")
    print(f"테스트할 질문 수: {end - start}개")
    
    if auto:
        print(f"모드: 🔄 자동 순차 (5개씩 자동 진행)\n")
    else:
        print(f"모드: 일반 (한 번에 실행)\n")
    
    confirm = input("계속하시겠습니까? (y/n): ")
    if confirm.lower() != 'y':
        print("테스트를 취소합니다.")
        sys.exit(0)
    
    run_batch_test(start, end, auto_sequential=auto)

