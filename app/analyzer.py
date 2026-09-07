import re
import time
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from app.models import AnalysisRequest, AnalysisResponse, ChartSeries, MetricData, RunDetail


def parse_runs_from_df(df: pd.DataFrame) -> Tuple[List[str], Dict[str, RunDetail]]:
    """
    DataFrame의 컬럼명에서 실행(Run) 패턴을 감지하고 세부 정보를 분석합니다.
    패턴 1: '시간 (s) [실행명]', '전압 (mV) [실행명]'
    패턴 2: 'Time [실행명]', 'Voltage [실행명]'
    패턴 3: 단일 실행 데이터셋 ('시간', '전압' 또는 'Time', 'Voltage')
    """
    runs: List[str] = []
    run_details: Dict[str, RunDetail] = {}

    # 컬럼 문자열 앞뒤 공백 및 BOM 정리
    clean_columns = [col.strip().lstrip("\ufeff") for col in df.columns]
    col_map = dict(zip(clean_columns, df.columns))

    # 패턴 1: '시간 (s)' 패턴 탐색
    time_pattern = re.compile(r"^(?:시간\s*(?:\(s\)|\[s\])?|Time\s*(?:\(s\)|\[s\])?)\s*(.*)$", re.IGNORECASE)
    
    candidate_runs = {}
    for col in clean_columns:
        m = time_pattern.match(col)
        if m:
            run_name = m.group(1).strip()
            if not run_name:
                run_name = "실행 1"
            candidate_runs[run_name] = col_map[col]

    # 각 후보 실행에 대응하는 전압 컬럼 찾기
    for run_name, t_col in candidate_runs.items():
        v_col = None
        ph_col = None
        
        # 전압 컬럼 후보 탐색
        v_candidates = [
            f"전압 (mV) {run_name}".strip(),
            f"전압 (mV){run_name}".strip(),
            f"전압 {run_name}".strip(),
            f"Voltage (mV) {run_name}".strip(),
            f"Voltage {run_name}".strip(),
            "전압 (mV)",
            "전압",
            "Voltage (mV)",
            "Voltage",
        ]
        for vc in v_candidates:
            if vc in col_map:
                v_col = col_map[vc]
                break
        
        # pH 컬럼 탐색 (있으면)
        ph_candidates = [
            f"pH {run_name}".strip(),
            "pH",
        ]
        for pc in ph_candidates:
            if pc in col_map:
                ph_col = col_map[pc]
                break

        if v_col:
            # 유효 데이터 확인
            sub_df = df[[t_col, v_col]].dropna()
            try:
                times = pd.to_numeric(sub_df[t_col], errors="coerce").dropna()
                if len(times) > 10:
                    min_t = float(times.min())
                    max_t = float(times.max())
                    total_pts = len(times)
                    
                    # 기본 window_len은 3501로 고정 (데이터 수가 부족할 경우에만 최대 홀수로 안전 조정)
                    if total_pts > 3501:
                        rec_win = 3501
                    else:
                        rec_win = total_pts - 1 if (total_pts - 1) % 2 != 0 else total_pts - 2
                        rec_win = max(3, rec_win)

                    runs.append(run_name)
                    run_details[run_name] = RunDetail(
                        name=run_name,
                        time_col=t_col,
                        voltage_col=v_col,
                        ph_col=ph_col,
                        min_time=round(min_t, 2),
                        max_time=round(max_t, 2),
                        total_points=total_pts,
                        recommended_window=rec_win,
                    )
            except Exception:
                continue

    # 만약 패턴으로 못 찾았을 경우, 첫 2개 컬럼을 시간/전압으로 매핑
    if not runs and len(clean_columns) >= 2:
        t_col = df.columns[0]
        v_col = df.columns[1]
        run_name = "실행 1"
        try:
            sub_df = df[[t_col, v_col]].dropna()
            times = pd.to_numeric(sub_df[t_col], errors="coerce").dropna()
            min_t = float(times.min())
            max_t = float(times.max())
            total_pts = len(times)
            if total_pts > 3501:
                rec_win = 3501
            else:
                rec_win = total_pts - 1 if (total_pts - 1) % 2 != 0 else total_pts - 2
                rec_win = max(3, rec_win)
            runs.append(run_name)
            run_details[run_name] = RunDetail(
                name=run_name,
                time_col=t_col,
                voltage_col=v_col,
                ph_col=None,
                min_time=round(min_t, 2),
                max_time=round(max_t, 2),
                total_points=total_pts,
                recommended_window=rec_win,
            )
        except Exception:
            pass

    return runs, run_details


def perform_titration_analysis(
    df: pd.DataFrame,
    req: AnalysisRequest,
    run_details: Dict[str, RunDetail]
) -> AnalysisResponse:
    """
    지정된 실행 대상과 파라미터로 Savitzky-Golay 필터링 및 1차 미분 기반 종말점을 산출합니다.
    """
    t_start = time.perf_counter()

    target_run = req.target_run
    if target_run not in run_details:
        # 첫 번째 사용 가능한 run으로 대체
        if not run_details:
            raise ValueError("분석 가능한 실행(Run) 데이터를 찾을 수 없습니다.")
        target_run = list(run_details.keys())[0]

    detail = run_details[target_run]
    time_col = detail.time_col
    voltage_col = detail.voltage_col

    # 1. 데이터 전처리
    data = df[[time_col, voltage_col]].dropna()
    data[time_col] = pd.to_numeric(data[time_col], errors="coerce")
    data[voltage_col] = pd.to_numeric(data[voltage_col], errors="coerce")
    data = data.dropna().sort_values(by=time_col)

    # 2. 시간 범위 필터링
    mask = (data[time_col] >= req.start_time) & (data[time_col] <= req.end_time)
    filtered_data = data[mask]

    n_points = len(filtered_data)
    if n_points < req.poly_order + 3:
        raise ValueError(
            f"선택한 시간 구간({req.start_time}s ~ {req.end_time}s) 내의 유효 데이터가 "
            f"{n_points}개로 너무 적습니다. 다항식 차수({req.poly_order})보다 충분히 많은 데이터가 필요합니다."
        )

    x = filtered_data[time_col].values
    y = filtered_data[voltage_col].values

    # 3. 윈도우 길이 검증 및 자동 조정 (데이터 수보다 작아야 함)
    window_len = req.window_len
    if window_len >= n_points:
        adjusted_win = n_points - 1 if (n_points - 1) % 2 != 0 else n_points - 2
        adjusted_win = max(req.poly_order + 2 if (req.poly_order + 2) % 2 != 0 else req.poly_order + 3, adjusted_win)
        window_len = adjusted_win

    # 4. Savitzky-Golay 계산
    poly_order = req.poly_order
    dx = float(np.mean(np.diff(x)))
    if dx <= 0:
        dx = 0.02  # 기본 샘플 간격 안전장치

    # (1) 평활화 곡선
    y_smooth = savgol_filter(y, window_length=window_len, polyorder=poly_order)

    # (2) 1차 미분 (dV/dt)
    dy_dx = savgol_filter(y, window_length=window_len, polyorder=poly_order, deriv=1, delta=dx)

    # 5. 종말점 탐색 (1차 미분 dV/dt 최댓값 피크)
    search_indices = np.arange(len(x))
    peak_idx = int(np.argmax(dy_dx))

    endpoint_time = float(x[peak_idx])
    endpoint_voltage = float(y_smooth[peak_idx])
    endpoint_slope = float(dy_dx[peak_idx])

    # 6. 시각화용 데이터 다운샘플링 (브라우저 차트 렌더링 최적화)
    if req.downsample_points > 0 and n_points > req.downsample_points:
        step = max(1, n_points // req.downsample_points)
        sample_indices = set(range(0, n_points, step))
        # 종말점 및 시작/끝점 인덱스는 반드시 포함
        sample_indices.add(0)
        sample_indices.add(n_points - 1)
        sample_indices.add(peak_idx)
        sorted_indices = sorted(list(sample_indices))
        
        plot_x = [round(float(x[i]), 3) for i in sorted_indices]
        plot_raw_y = [round(float(y[i]), 3) for i in sorted_indices]
        plot_smooth_y = [round(float(y_smooth[i]), 3) for i in sorted_indices]
        plot_deriv_y = [round(float(dy_dx[i]), 4) for i in sorted_indices]
    else:
        plot_x = [round(float(v), 3) for v in x]
        plot_raw_y = [round(float(v), 3) for v in y]
        plot_smooth_y = [round(float(v), 3) for v in y_smooth]
        plot_deriv_y = [round(float(v), 4) for v in dy_dx]

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

    return AnalysisResponse(
        status="success",
        target_run=target_run,
        metrics=MetricData(
            endpoint_time=round(endpoint_time, 2),
            endpoint_voltage=round(endpoint_voltage, 2),
            endpoint_slope=round(endpoint_slope, 4),
            total_points=n_points,
            start_time=round(float(x[0]), 2),
            end_time=round(float(x[-1]), 2),
            window_len=window_len,
            poly_order=poly_order,
            elapsed_ms=elapsed_ms,
        ),
        chart_data=ChartSeries(
            raw_x=plot_x,
            raw_y=plot_raw_y,
            smooth_x=plot_x,
            smooth_y=plot_smooth_y,
            deriv_x=plot_x,
            deriv_y=plot_deriv_y,
            endpoint_time=round(endpoint_time, 2),
            endpoint_voltage=round(endpoint_voltage, 2),
            endpoint_slope=round(endpoint_slope, 4),
        ),
        message=f"윈도우 크기 {window_len} 적용 (계산 소요: {elapsed_ms}ms)",
    )
