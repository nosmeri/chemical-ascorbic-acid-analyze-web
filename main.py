import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

# 한글 폰트 설정
plt.rcParams['font.family'] = ['Noto Sans CJK JP', 'DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# 1. CSV 데이터 불러오기
file_path = "data2.csv"  # 파일 경로 지정
df = pd.read_csv(file_path)

# 분석 대상 실행 선택
target_run = "실행 1"
time_col = f"시간 (s) {target_run}"
voltage_col = f"전압 (mV) {target_run}"

# 2. 데이터 전처리 (결측치 제거 및 초반 노이즈 마스킹)
data = df[[time_col, voltage_col]].dropna()
data[time_col] = pd.to_numeric(data[time_col])
data[voltage_col] = pd.to_numeric(data[voltage_col])
data = data.sort_values(by=time_col)

# 65초 이전 노이즈 제외
mask = (data[time_col] <= 400) & (data[time_col] >= 60)
data = data[mask]

x = data[time_col].values
y = data[voltage_col].values

# 3. Savitzky-Golay 필터 계산
# ※ 데이터 샘플 수보다 window_len이 작고 홀수여야 합니다. (예: 501, 701, 1001 등)
window_len = 3501
poly_order = 3
dx = np.mean(np.diff(x))

# (1) 평활화 곡선
y_smooth = savgol_filter(y, window_length=window_len, polyorder=poly_order)

# (2) 1차 미분 (dV/dt)
dy_dx = savgol_filter(
    y, window_length=window_len, polyorder=poly_order, deriv=1, delta=dx
)

# 4. 종말점 탐색 (1차 미분 dV/dt 최댓값 지점)
# 탐색 구간 마스크
search_mask = x >= 0  # (x >= 100) & (x <= 140)
search_indices = np.where(search_mask)[0]

# 1차 미분 피크 지점 (dV/dt 최댓값)
peak_1st_sub_idx = np.argmax(dy_dx[search_mask])
idx_endpoint = search_indices[peak_1st_sub_idx]
time_endpoint = x[idx_endpoint]
voltage_endpoint = y_smooth[idx_endpoint]
slope_endpoint = dy_dx[idx_endpoint]

print(f"[{target_run} 분석 결과]")
print(
    f"- [종말점] 1차 미분 최댓값 (dV/dt 피크) : {time_endpoint:.2f} s (전압: {voltage_endpoint:.2f} mV, 기울기: {slope_endpoint:.4f} mV/s)"
)

# 5. 2단 시각화 플롯
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

# 1) 원본 데이터 및 평활화
ax1.plot(
    x,
    y,
    color="lightgreen",
    marker="o",
    markersize=2,
    linestyle="",
    alpha=0.5,
    label="Raw Data",
)
ax1.plot(
    x,
    y_smooth,
    color="darkgreen",
    lw=2,
    label=f"Smoothed (win={window_len})",
)
# 종말점 표시 (오렌지색 점선 및 원형 마커)
ax1.axvline(
    time_endpoint,
    color="darkorange",
    linestyle="--",
    lw=1.5,
    label=f"Endpoint ({time_endpoint:.1f} s, {voltage_endpoint:.1f} mV)",
)
ax1.scatter(
    [time_endpoint],
    [voltage_endpoint],
    color="darkorange",
    s=60,
    zorder=5,
)
ax1.set_ylabel("Voltage (mV)")
ax1.set_title(f"Potentiometric Titration Analysis ({target_run})")
ax1.legend(loc="lower right")
ax1.grid(True, linestyle=":", alpha=0.6)

# 2) 1차 도함수 (dV/dt)
ax2.plot(x, dy_dx, color="blue", lw=1.5, label="1st Derivative (dV/dt)")
ax2.axvline(
    time_endpoint,
    color="darkorange",
    linestyle="--",
    lw=1.5,
    label=f"Max dV/dt ({time_endpoint:.1f} s)",
)
ax2.scatter(
    [time_endpoint],
    [slope_endpoint],
    color="darkorange",
    s=50,
    zorder=5,
)
ax2.set_xlabel("Time (s)")
ax2.set_ylabel("dV/dt (mV/s)")
ax2.set_title("1st Derivative (Max Slope: Endpoint)")
ax2.legend(loc="upper right")
ax2.grid(True, linestyle=":", alpha=0.6)

plt.tight_layout()
plt.savefig("graph_1.png", dpi=300, bbox_inches="tight")
plt.show()