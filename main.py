import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router as chat_router

app = FastAPI(
    title="RAG AI-Tutor API",
    description="LangGraph 기반 RAG 파이프라인 서빙 API",
    version="1.0.0"
)

# 프론트엔드 통신을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 실무에서는 실제 프론트엔드 도메인으로 제한할 것
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is running."}

if __name__ == "__main__":
    # uvicorn을 통해 ASGI 비동기 서버 구동
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)