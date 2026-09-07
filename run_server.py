import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("ChemTitrate Pro - FastAPI 비동기 전위차 적정 분석 웹 애플리케이션")
    print("웹 브라우저 접속 주소: http://localhost:8000")
    print("API 문서(Swagger): http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
