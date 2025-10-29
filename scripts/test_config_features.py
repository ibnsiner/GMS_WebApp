"""
Config.json 기능 활용 테스트 스크립트
각 Phase별 구현 완료 후 회귀 테스트용
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from agent import GmisAgentV4

# 테스트 케이스 정의
TEST_CASES = {
    "PLAN_VS_ACTUAL": [
        {
            "query": "2023년 MnM 매출액 계획 대비 실적을 알려줘",
            "expected_keywords": ["계획", "실적", "달성", "%"],
            "description": "계획-실적 비교 기능"
        },
        {
            "query": "일렉트릭의 1분기 목표 달성률은?",
            "expected_keywords": ["목표", "달성", "Q1"],
            "description": "분기별 목표 달성률"
        }
    ],
    "YTD": [
        {
            "query": "2023년 9월까지 전선 매출액 누계",
            "expected_keywords": ["누계", "9월"],
            "description": "YTD 누계 조회"
        },
        {
            "query": "올해 연초부터 영업이익 누적은?",
            "expected_keywords": ["연초", "누적"],
            "description": "YTD 키워드 변형"
        }
    ],
    "CALCULATED_RATIOS": [
        {
            "query": "MnM의 2023년 ROE를 계산해줘",
            "expected_keywords": ["ROE", "%", "자기자본"],
            "description": "ROE 자동 계산"
        },
        {
            "query": "전선의 매출채권회전율은?",
            "expected_keywords": ["회전율", "회"],
            "description": "회전율 자동 계산"
        }
    ],
    "DEFINITIONS": [
        {
            "query": "영업이익이 뭐야?",
            "expected_keywords": ["판매관리비", "매출총이익"],
            "description": "계정 정의 조회"
        },
        {
            "query": "ROE 의미는?",
            "expected_keywords": ["자기자본", "수익률"],
            "description": "비율 정의 조회"
        }
    ],
    "VIEWPOINTS": [
        {
            "query": "수익성 지표를 모두 보여줘",
            "expected_keywords": ["영업이익률", "ROE"],
            "description": "관점별 비율 목록"
        },
        {
            "query": "안정성 관련 비율들은?",
            "expected_keywords": ["부채비율"],
            "description": "안정성 관점 비율"
        }
    ],
    "QUARTERLY": [
        {
            "query": "2023년 1분기부터 4분기까지 매출액",
            "expected_keywords": ["Q1", "Q2", "Q3", "Q4"],
            "description": "분기별 데이터 조회"
        }
    ]
}

def run_single_test(agent, test_case):
    """단일 테스트 케이스 실행"""
    print(f"\n{'='*70}")
    print(f"테스트: {test_case['description']}")
    print(f"질문: {test_case['query']}")
    print(f"{'='*70}")
    
    try:
        # Agent 실행
        result = agent.run_and_get_structured_output(test_case['query'])
        
        # 결과를 문자열로 변환
        result_str = str(result).lower()
        
        # 키워드 체크
        passed_keywords = []
        failed_keywords = []
        
        for keyword in test_case['expected_keywords']:
            if keyword.lower() in result_str:
                passed_keywords.append(keyword)
            else:
                failed_keywords.append(keyword)
        
        # 결과 출력
        if len(failed_keywords) == 0:
            print(f"✅ PASS - 모든 키워드 확인됨: {passed_keywords}")
            return True
        else:
            print(f"⚠️ PARTIAL - 일부 키워드 누락: {failed_keywords}")
            print(f"   확인된 키워드: {passed_keywords}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR - {str(e)}")
        return False

def run_all_tests():
    """전체 테스트 스위트 실행"""
    print("\n" + "="*70)
    print("  Config.json 기능 활용 테스트")
    print("="*70)
    
    # Agent 초기화
    try:
        agent = GmisAgentV4()
        print("\n✅ Agent 초기화 성공")
    except Exception as e:
        print(f"\n❌ Agent 초기화 실패: {e}")
        return
    
    # 각 Phase별 테스트
    total_tests = 0
    passed_tests = 0
    
    for phase_name, test_cases in TEST_CASES.items():
        print(f"\n{'#'*70}")
        print(f"# {phase_name}")
        print(f"{'#'*70}")
        
        for test_case in test_cases:
            total_tests += 1
            if run_single_test(agent, test_case):
                passed_tests += 1
    
    # 최종 결과
    print(f"\n{'='*70}")
    print(f"  테스트 결과")
    print(f"{'='*70}")
    print(f"전체: {total_tests}개")
    print(f"성공: {passed_tests}개 ({passed_tests/total_tests*100:.1f}%)")
    print(f"실패: {total_tests - passed_tests}개")
    print(f"{'='*70}\n")
    
    # Agent 정리
    agent.close()

if __name__ == "__main__":
    run_all_tests()

