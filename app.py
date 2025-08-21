# app.py
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------
# 페이지/스타일
# -----------------------
st.set_page_config(page_title="제품 카테고리별 수익성 대시보드", layout="wide", page_icon="📊")

BASE_COLOR = "#FFC8A2"   # 기본 톤
HL_COLOR   = "#ff968a"   # 집중(핵심) 톤 - Waterfall 등

# 트렌디 파스텔 팔레트 (카테고리 구분용)
CATEGORY_COLORS = [
    "#FF9AA2", "#FFDAC1", "#E2F0CB", "#B5EAD7",
    "#C7CEEA", "#F3C5FF", "#FFD6E0", "#A2E1DB",
    "#FDE2E4", "#BEE1E6", "#E2ECE9", "#F6EAC2"  # 여유 색상
]

st.markdown("""
<style>
.big-number {font-size: 28px; font-weight: 700;}
.subtle {color: #666;}
</style>
""", unsafe_allow_html=True)

# -----------------------
# 유틸
# -----------------------
REQUIRED_COLS = [
    "월","사업부","지역","채널","제품카테고리","고객세그먼트",
    "매출액","매출원가","매출총이익","마케팅비용","운영비용","영업이익",
    "NPS","CSAT"
]

def coerce_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _try_read_csv_any_encoding(path_or_buf):
    """
    인코딩 문제 대비: 여러 인코딩으로 순차 시도
    """
    tried = []
    for enc in ["utf-8", "utf-8-sig", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(path_or_buf, encoding=enc)
        except Exception as e:
            tried.append(f"{enc}: {e}")
    raise RuntimeError("CSV 인코딩 자동 탐지 실패\n" + "\n".join(tried))

@st.cache_data
def load_csv_safe(path_or_buf):
    # 파일 포인터(uploaded)든 경로든 모두 허용
    df_local = _try_read_csv_any_encoding(path_or_buf)

    # '월' 파싱
    if "월" in df_local.columns:
        try:
            df_local["월"] = pd.to_datetime(df_local["월"])
        except:
            df_local["월"] = pd.to_datetime(df_local["월"].astype(str) + "-01", errors="coerce")

    # 숫자형 강제 변환
    num_cols = ["매출액","매출원가","매출총이익","마케팅비용","운영비용","영업이익","NPS","CSAT"]
    df_local = coerce_numeric(df_local, num_cols)

    with np.errstate(divide='ignore', invalid='ignore'):
        if "매출액" in df_local.columns and "영업이익" in df_local.columns:
            df_local["영업이익률(%)"] = (df_local["영업이익"] / df_local["매출액"] * 100).replace([np.inf, -np.inf], np.nan)
        if "매출액" in df_local.columns and "매출총이익" in df_local.columns:
            df_local["매출총이익률(%)"] = (df_local["매출총이익"] / df_local["매출액"] * 100).replace([np.inf, -np.inf], np.nan)

    return df_local

def check_required_columns(df):
    return [c for c in REQUIRED_COLS if c not in df.columns]

def kpi_card(title, value, suffix="", help_text=None):
    st.markdown(f"**{title}**")
    try:
        st.markdown(f"<div class='big-number'>{value:,.0f}{suffix}</div>", unsafe_allow_html=True)
    except:
        st.markdown(f"<div class='big-number'>{value}{suffix}</div>", unsafe_allow_html=True)
    if help_text:
        st.markdown(f"<span class='subtle'>{help_text}</span>", unsafe_allow_html=True)

def number_card(title, value, fmt="{:,.2f}", suffix=""):
    st.markdown(f"**{title}**")
    try:
        st.markdown(f"<div class='big-number'>{fmt.format(value)}{suffix}</div>", unsafe_allow_html=True)
    except:
        st.markdown(f"<div class='big-number'>{value}{suffix}</div>", unsafe_allow_html=True)

def build_color_map(all_categories, palette=CATEGORY_COLORS):
    """
    카테고리 -> 고정 색상 매핑(그래프 간 일관성 유지)
    """
    color_map = {}
    n = len(palette)
    for i, cat in enumerate(sorted(all_categories)):
        color_map[cat] = palette[i % n]
    return color_map

# -----------------------
# 데이터 업로드/로드
# -----------------------
st.sidebar.header("데이터 업로드")
uploaded = st.sidebar.file_uploader("CSV 파일을 업로드하세요", type=["csv"])

# ⚠️ 본인 경로로 변경하세요(또는 업로드 사용)
# 예) "/Users/내계정/Desktop/데이터 스토리텔링 대시보드/KPI_Master_Small_12M_KR.csv"
default_path = "/User/juyubin//Desktop/데이터 스토리텔링 대시보드/KPI_Master_Small_12M_KR.csv"

df = None
load_errors = []

if uploaded is not None:
    try:
        df = load_csv_safe(uploaded)
        st.sidebar.success("업로드한 CSV를 성공적으로 불러왔습니다.")
    except Exception as e:
        load_errors.append(f"업로드 파일 읽기 실패: {e}")

# 업로드가 없거나 실패하면 기본 경로 시도
if df is None:
    try:
        df = load_csv_safe(default_path)
        st.sidebar.info("업로드가 없어 기본 경로 CSV를 불러왔습니다.")
    except Exception as e:
        load_errors.append(f"기본 경로 읽기 실패: {e}")

# 최종 점검: 여전히 실패하면 즉시 중단
if df is None:
    st.error("CSV를 불러오지 못했습니다. 아래 원인을 확인하세요:")
    for msg in load_errors:
        st.code(msg)
    st.stop()

# 파일이 로드되었으면 컬럼 미리보기 제공(디버깅에 유용)
with st.expander("데이터 로딩 확인 (디버그)"):
    st.write("shape:", df.shape)
    st.write("columns:", list(df.columns))
    st.dataframe(df.head(10), use_container_width=True)

# 필수 컬럼 확인
missing = check_required_columns(df)
if missing:
    st.error(f"필수 컬럼이 없습니다: {missing}")
    st.stop()

# -----------------------
# 필터
# -----------------------
st.sidebar.header("필터")
col1, col2 = st.sidebar.columns(2)
with col1:
    biz = st.selectbox("사업부", ["(전체)"] + sorted(df["사업부"].dropna().unique().tolist()))
    reg = st.selectbox("지역", ["(전체)"] + sorted(df["지역"].dropna().unique().tolist()))
with col2:
    ch  = st.selectbox("채널", ["(전체)"] + sorted(df["채널"].dropna().unique().tolist()))
    seg = st.selectbox("고객세그먼트", ["(전체)"] + sorted(df["고객세그먼트"].dropna().unique().tolist()))

fil = df.copy()
if biz != "(전체)": fil = fil[fil["사업부"] == biz]
if reg != "(전체)": fil = fil[fil["지역"] == reg]
if ch  != "(전체)": fil = fil[fil["채널"] == ch]
if seg != "(전체)": fil = fil[fil["고객세그먼트"] == seg]

if fil.empty:
    st.warning("선택한 필터에 해당하는 데이터가 없습니다.")
    st.stop()

# 카테고리-색상 매핑(대시보드 전역 일관성)
all_cats = df["제품카테고리"].dropna().unique().tolist()
COLOR_MAP = build_color_map(all_cats, CATEGORY_COLORS)

# -----------------------
# 상단 KPI
# -----------------------
st.title("📊 제품 카테고리별 수익성 대시보드")

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("총 매출액", fil["매출액"].sum())
with k2:
    kpi_card("총 매출총이익", fil["매출총이익"].sum())
with k3:
    total_sales = fil["매출액"].sum()
    total_op = fil["영업이익"].sum()
    opm = (total_op / total_sales * 100) if total_sales else np.nan
    number_card("영업이익률(%)", opm, fmt="{:,.2f}")
with k4:
    cat_profit = fil.groupby("제품카테고리").agg(매출액=("매출액","sum"),
                                             영업이익=("영업이익","sum")).reset_index()
    st.markdown("**최고 수익성 카테고리**")
    if cat_profit["매출액"].sum() > 0 and not cat_profit.empty:
        cat_profit["영업이익률(%)"] = cat_profit["영업이익"] / cat_profit["매출액"] * 100
        top_row = cat_profit.sort_values("영업이익률(%)", ascending=False).iloc[0]
        st.markdown(f"<div class='big-number'>{top_row['제품카테고리']}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='subtle'>영업이익률 {top_row['영업이익률(%)']:.2f}%</span>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='big-number'>-</div>", unsafe_allow_html=True)
        st.markdown("<span class='subtle'>영업이익률 계산 불가</span>", unsafe_allow_html=True)

st.divider()

# -----------------------
# (집중) 그래프 1: 카테고리별 영업이익률 비교 (Bar)
# -----------------------
st.subheader("카테고리별 영업이익률 비교")
cat = fil.groupby("제품카테고리").agg(
    매출액=("매출액","sum"),
    매출총이익=("매출총이익","sum"),
    영업이익=("영업이익","sum")
).reset_index()
cat["영업이익률(%)"]   = np.where(cat["매출액"]>0, cat["영업이익"]/cat["매출액"]*100, np.nan)
cat["매출총이익률(%)"] = np.where(cat["매출액"]>0, cat["매출총이익"]/cat["매출액"]*100, np.nan)

bar_fig = px.bar(
    cat.sort_values("영업이익률(%)", ascending=False),
    x="제품카테고리", y="영업이익률(%)",
    hover_data=["매출액","매출총이익","영업이익","매출총이익률(%)"],
    color="제품카테고리",
    color_discrete_map=COLOR_MAP  # ✅ 카테고리별 고정색
)
bar_fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
st.plotly_chart(bar_fig, use_container_width=True)

# -----------------------
# (집중) 그래프 2: Waterfall (선택 카테고리) - HL_COLOR 유지
# -----------------------
st.subheader("선택 카테고리 수익 구조 (Waterfall)")
cat_list = ["(전체합계)"] + sorted(fil["제품카테고리"].dropna().unique().tolist())
sel_cat = st.selectbox("카테고리 선택", cat_list)

wf_src = fil.copy()
if sel_cat != "(전체합계)":
    wf_src = wf_src[wf_src["제품카테고리"] == sel_cat]

agg = wf_src[["매출액","매출원가","매출총이익","마케팅비용","운영비용","영업이익"]].sum()

x = ["매출액","매출원가","매출총이익","마케팅비용","운영비용","영업이익"]
measure = ["relative","relative","total","relative","relative","total"]
vals = [
    agg["매출액"],
    -agg["매출원가"],
    agg["매출총이익"],
    -agg["마케팅비용"],
    -agg["운영비용"],
    agg["영업이익"]
]

wf_fig = go.Figure(go.Waterfall(
    name="수익 구조",
    orientation="v",
    measure=measure,
    x=x,
    text=[f"{v:,.0f}" for v in vals],
    y=vals,
    connector={"line":{"color":HL_COLOR}},
    decreasing={"marker":{"color":HL_COLOR}},
    increasing={"marker":{"color":HL_COLOR}},
    totals={"marker":{"color":HL_COLOR}}
))
wf_fig.update_layout(showlegend=False, margin=dict(l=10,r=10,t=40,b=10))
st.plotly_chart(wf_fig, use_container_width=True)

st.divider()

# -----------------------
# (기본) 그래프 3: 수익성 vs 고객경험 (Scatter)
# -----------------------
st.subheader("수익성 vs 고객경험 (버블 크기=매출액)")
sc = fil.groupby("제품카테고리").agg(
    매출액=("매출액","sum"),
    영업이익=("영업이익","sum"),
    NPS=("NPS","mean"),
    CSAT=("CSAT","mean")
).reset_index()
sc["영업이익률(%)"] = np.where(sc["매출액"]>0, sc["영업이익"]/sc["매출액"]*100, np.nan)

axis_metric = st.radio("Y축 선택", ["NPS","CSAT"], horizontal=True)
scatter_fig = px.scatter(
    sc, x="영업이익률(%)", y=axis_metric,
    size="매출액", color="제품카테고리",
    color_discrete_map=COLOR_MAP,  # ✅ 카테고리별 고정색
    hover_data=["매출액","영업이익","NPS","CSAT"]
)
scatter_fig.update_traces(marker=dict(line=dict(width=1, color="black")))
scatter_fig.update_layout(margin=dict(l=10,r=10,t=40,b=10))
st.plotly_chart(scatter_fig, use_container_width=True)

st.divider()

# -----------------------
# (기본) 그래프 4: 시간 추세 (Line)
# -----------------------
st.subheader("시간에 따른 수익성 추세")
trend_metric = st.selectbox("지표 선택", ["매출액","매출총이익","영업이익","영업이익률(%)","매출총이익률(%)"])

ts = fil.copy()
ts["영업이익률(%)"]   = np.where(ts["매출액"]>0, ts["영업이익"]/ts["매출액"]*100, np.nan)
ts["매출총이익률(%)"] = np.where(ts["매출액"]>0, ts["매출총이익"]/ts["매출액"]*100, np.nan)

aggfunc = "mean" if "(%)" in trend_metric else "sum"
line_src = ts.groupby(["월","제품카테고리"]).agg({trend_metric: aggfunc}).reset_index()

line_fig = px.line(
    line_src.sort_values("월"),
    x="월", y=trend_metric, color="제품카테고리",
    color_discrete_map=COLOR_MAP  # ✅ 카테고리별 고정색
)
line_fig.update_layout(margin=dict(l=10,r=10,t=40,b=10), xaxis_title="월")
st.plotly_chart(line_fig, use_container_width=True)

st.divider()

# -----------------------
# 테이블
# -----------------------
st.subheader("카테고리별 핵심 지표 요약")
table = cat[["제품카테고리","매출액","매출총이익","영업이익","매출총이익률(%)","영업이익률(%)"]].sort_values("영업이익률(%)", ascending=False)
st.dataframe(table, use_container_width=True)

st.caption("Tip: 사이드바 필터로 사업부/지역/채널/세그먼트를 바꿔보며 비교하세요.")