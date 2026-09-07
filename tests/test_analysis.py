import pytest
import pandas as pd
from app.models import AnalysisRequest
from app.analyzer import parse_runs_from_df, perform_titration_analysis
from fastapi.testclient import TestClient
from app.main import app


def test_window_len_odd_validation():
    # 짝수 입력 시 ValueError 발생 확인
    with pytest.raises(ValueError, match="홀수여야 합니다"):
        AnalysisRequest(
            target_run="실행 1",
            start_time=60.0,
            end_time=400.0,
            window_len=3500,  # 짝수
            poly_order=3,
        )

    # 홀수 입력 시 성공
    req = AnalysisRequest(
        target_run="실행 1",
        start_time=60.0,
        end_time=400.0,
        window_len=3501,  # 홀수
        poly_order=3,
    )
    assert req.window_len == 3501


def test_analyzer_with_sample_data():
    sample_path = "sample_data/data2.csv"
    df = pd.read_csv(sample_path)
    runs, run_details = parse_runs_from_df(df)

    assert "실행 1" in runs
    assert "실행 1" in run_details
    detail = run_details["실행 1"]
    assert detail.total_points > 20000

    req = AnalysisRequest(
        target_run="실행 1",
        start_time=60.0,
        end_time=400.0,
        window_len=3501,
        poly_order=3,
    )
    resp = perform_titration_analysis(df, req, run_details)

    assert resp.status == "success"
    # 기존 main.py와 동일한 종말점인지 검증
    # main.py 출력: 233.92s
    assert round(resp.metrics.endpoint_time, 2) == 233.92
    assert resp.metrics.endpoint_voltage > 160.0
    assert resp.metrics.endpoint_slope > 0.0


def test_fastapi_endpoints():
    client = TestClient(app)

    # 1. 루트 페이지 확인
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "ChemTitrate" in res_root.text

    # 2. 샘플 데이터 API 확인
    res_sample = client.get("/api/sample")
    assert res_sample.status_code == 200
    sample_data = res_sample.json()
    assert sample_data["status"] == "success"
    assert "실행 1" in sample_data["runs"]

    # 3. 분석 API 확인 (정상 홀수)
    res_analyze = client.post(
        "/api/analyze",
        json={
            "file_id": "sample",
            "target_run": "실행 1",
            "start_time": 60.0,
            "end_time": 400.0,
            "window_len": 3501,
            "poly_order": 3,
        },
    )
    assert res_analyze.status_code == 200
    result = res_analyze.json()
    assert result["status"] == "success"
    assert "endpoint_time" in result["metrics"]

    # 4. 분석 API 오류 검증 (짝수 윈도우 전송 시 422 Unprocessable Entity)
    res_err = client.post(
        "/api/analyze",
        json={
            "file_id": "sample",
            "target_run": "실행 1",
            "start_time": 60.0,
            "end_time": 400.0,
            "window_len": 3500,  # 짝수
            "poly_order": 3,
        },
    )
    assert res_err.status_code == 422  # Pydantic ValidationError
