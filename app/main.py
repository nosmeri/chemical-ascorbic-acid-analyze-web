import asyncio
import io
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.analyzer import parse_runs_from_df, perform_titration_analysis
from app.models import AnalysisRequest, AnalysisResponse, RunDetail, UploadResponse

from contextlib import asynccontextmanager

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_CSV_PATH = BASE_DIR / "sample_data" / "data2.csv"
STATIC_DIR = BASE_DIR / "app" / "static"

# 업로드된 데이터 캐시 저장소 (file_id -> (DataFrame, runs, run_details))
DATA_STORE: Dict[str, Tuple[pd.DataFrame, List[str], Dict[str, RunDetail]]] = {}


def load_csv_data(content: bytes) -> pd.DataFrame:
    """CSV 바이트 데이터를 판다스 데이터프레임으로 변환 (인코딩 자동 감지)"""
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except (UnicodeDecodeError, Exception):
            continue
    # 최종 시도
    return pd.read_csv(io.BytesIO(content), errors="replace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 기동 시 샘플 데이터가 있으면 미리 메모리에 로드"""
    if SAMPLE_CSV_PATH.exists():
        try:
            with open(SAMPLE_CSV_PATH, "rb") as f:
                content = f.read()
            df = await asyncio.to_thread(load_csv_data, content)
            runs, run_details = await asyncio.to_thread(parse_runs_from_df, df)
            DATA_STORE["sample"] = (df, runs, run_details)
        except Exception as e:
            print(f"[Warning] Failed to preload sample data: {e}")
    yield


# FastAPI 앱 생성
app = FastAPI(
    title="ChemTitrate Analytics",
    description="FastAPI 기반 전위차 적정(Potentiometric Titration) 비동기 분석 플랫폼",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/upload", response_model=UploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """
    CSV 파일을 비동기로 수신하고 헤더를 분석하여
    분석 가능한 실행(Run) 목록과 시간 범위를 반환합니다.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")

    try:
        content = await file.read()
        df = await asyncio.to_thread(load_csv_data, content)
        runs, run_details = await asyncio.to_thread(parse_runs_from_df, df)

        if not runs:
            raise HTTPException(
                status_code=400,
                detail="CSV 파일에서 적합한 시간 및 전압 컬럼을 감지하지 못했습니다. 컬럼명을 확인해 주세요.",
            )

        file_id = f"file_{uuid.uuid4().hex[:8]}"
        DATA_STORE[file_id] = (df, runs, run_details)

        return UploadResponse(
            status="success",
            file_id=file_id,
            filename=file.filename,
            runs=runs,
            run_details=run_details,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류가 발생했습니다: {str(e)}")


@app.get("/api/sample", response_model=UploadResponse)
async def get_sample_data():
    """
    미리 준비된 전위차 적정 샘플 데이터를 반환합니다.
    """
    if "sample" not in DATA_STORE:
        if SAMPLE_CSV_PATH.exists():
            with open(SAMPLE_CSV_PATH, "rb") as f:
                content = f.read()
            df = await asyncio.to_thread(load_csv_data, content)
            runs, run_details = await asyncio.to_thread(parse_runs_from_df, df)
            DATA_STORE["sample"] = (df, runs, run_details)
        else:
            raise HTTPException(status_code=404, detail="샘플 데이터 파일이 서버에 존재하지 않습니다.")

    df, runs, run_details = DATA_STORE["sample"]
    return UploadResponse(
        status="success",
        file_id="sample",
        filename="data2.csv (공식 적정 샘플)",
        runs=runs,
        run_details=run_details,
    )


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_data(req: AnalysisRequest):
    """
    선택된 실행과 파라미터(시작시간, 끝시간, window_len)를 기반으로
    Savitzky-Golay 평활화 및 1차 미분 종말점을 비동기로 분석합니다.
    """
    file_id = req.file_id or "sample"

    if file_id not in DATA_STORE:
        raise HTTPException(
            status_code=404,
            detail=f"데이터 세션('{file_id}')을 찾을 수 없습니다. CSV 파일을 먼저 업로드해 주세요.",
        )

    df, runs, run_details = DATA_STORE[file_id]

    try:
        # 비차단(Non-blocking) 비동기 스레드 풀에서 분석 연산 수행
        response = await asyncio.to_thread(
            perform_titration_analysis, df, req, run_details
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")


# 정적 파일 서빙
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"message": "ChemTitrate Analytics API Running"})
