import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from src.rag.plugins.openrouter_generator import OpenRouterGenerator

async def test_openrouter_direct():
    # 1. 환경 변수 강제 로드
    current_dir = Path(__file__).resolve().parent
    env_path = current_dir / "settings" / ".env.poc"
    
    print(f"1. .env.poc 파일 경로 확인: {env_path.exists()} ({env_path})")
    load_dotenv(dotenv_path=env_path, override=True)
    
    # 2. 로드된 API 키 값 확인 (보안을 위해 앞 10자리만 출력)
    raw_key = os.getenv("OPENROUTER_API_KEY", "")
    masked_key = raw_key[:10] + "..." if len(raw_key) > 10 else "없음 또는 너무 짧음!"
    print(f"2. 로드된 API Key 확인: {masked_key}")
    
    if not raw_key:
        print(" 실패: 환경 변수에서 키를 읽어오지 못했습니다.")
        return

    # 3. 플러그인 단독 호출 테스트
    print("\n3. OpenRouter 직접 호출 테스트 시작...")
    generator = OpenRouterGenerator(default_model="google/gemini-2.5-flash")
    
    test_prompt = "대한민국의 수도는 어디인가요? 아주 짧게 단답형으로 대답해 주세요."
    try:
        response = await generator.forward(prompt=test_prompt)
        print("\n 통신 성공! AI의 답변:")
        print(response)
    except Exception as e:
        print(f"\n 통신 실패! 상세 에러: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter_direct())