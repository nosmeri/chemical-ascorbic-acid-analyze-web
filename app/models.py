from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    file_id: Optional[str] = Field(None, description="업로드된 파일 고유 ID (없으면 기본 샘플 데이터 사용)")
    target_run: str = Field("실행 1", description="분석 대상 실행 (예: '실행 1')")
    start_time: float = Field(60.0, description="분석 시작 시간 (초)")
    end_time: float = Field(400.0, description="분석 종료 시간 (초)")
    window_len: int = Field(3501, description="Savitzky-Golay 필터 윈도우 크기 (반드시 홀수)")
    poly_order: int = Field(3, description="다항식 차수 (기본 3)")
    downsample_points: int = Field(2500, description="시각화 차트 렌더링용 다운샘플링 포인트 수 (0이면 전체)")

    @field_validator("window_len")
    @classmethod
    def validate_window_len(cls, v: int) -> int:
        if v < 3:
            raise ValueError("window_len은 최소 3 이상이어야 합니다.")
        if v % 2 == 0:
            raise ValueError(
                f"window_len({v})은 홀수여야 합니다. "
                f"Savitzky-Golay 필터는 중심점을 기준으로 좌우 대칭인 윈도우를 계산하여 "
                f"시간 위상 왜곡(Phase shift)을 방지하므로 짝수를 사용할 수 없습니다. "
                f"(추천값: {v + 1})"
            )
        return v

    @field_validator("poly_order")
    @classmethod
    def validate_poly_order(cls, v: int) -> int:
        if v < 1:
            raise ValueError("poly_order는 1 이상이어야 합니다.")
        return v


class RunDetail(BaseModel):
    name: str
    time_col: str
    voltage_col: str
    ph_col: Optional[str] = None
    min_time: float
    max_time: float
    total_points: int
    recommended_window: int


class UploadResponse(BaseModel):
    status: str = "success"
    file_id: str
    filename: str
    runs: List[str]
    run_details: Dict[str, RunDetail]


class MetricData(BaseModel):
    endpoint_time: float
    endpoint_voltage: float
    endpoint_slope: float
    total_points: int
    start_time: float
    end_time: float
    window_len: int
    poly_order: int
    elapsed_ms: float


class ChartSeries(BaseModel):
    raw_x: List[float]
    raw_y: List[float]
    smooth_x: List[float]
    smooth_y: List[float]
    deriv_x: List[float]
    deriv_y: List[float]
    endpoint_time: float
    endpoint_voltage: float
    endpoint_slope: float


class AnalysisResponse(BaseModel):
    status: str = "success"
    target_run: str
    metrics: MetricData
    chart_data: ChartSeries
    message: Optional[str] = None
