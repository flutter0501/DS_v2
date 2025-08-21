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
# 데이터 업로드/로드 (Streamlit Cloud 친화형)
# -----------------------
import os
import io
import requests

st.sidebar.header("데이터 업로드 (필요 시)")
uploaded = st.sidebar.file_uploader("CSV 파일 업로드", type=["csv"])

# 1) 레포에 포함된 CSV (app.py와 같은 폴더) 를 우선 시도
LOCAL_CSV_PATH = "KPI_Master_Small_12M_KR.csv"

# 2) (선택) GitHub Raw URL fallback - 본인 레포 경로로 교체
# 예시: https://raw.githubusercontent.com/<USER>/<REPO>/main/KPI_Master_Small_12M_KR.csv
GITHUB_RAW_URL = "https://raw.githubusercontent.com/<YOUR_ID>/<YOUR_REPO>/main/KPI_Master_Small_12M_KR.csv"

def _try_read_csv_any_encoding_from_buffer(buf):
    for enc in ["utf-8", "utf-8-sig", "cp949", "euc-kr"]:
        try:
            buf.seek(0)
            return pd.read_csv(buf, encoding=enc)
        except Exception:
            continue
    raise RuntimeError("CSV 인코딩 자동 판별 실패")

def _load_local_csv_if_exists(path):
    if os.path.exists(path):
        # 파일 핸들로 읽을 때는 인코딩 루프를 위해 메모리로 올려두는 게 안전
        with open(path, "rb") as f:
            raw = f.read()
        return _try_read_csv_any_encoding_from_buffer(io.BytesIO(raw))
    return None

def _load_csv_from_github_raw(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return _try_read_csv_any_encoding_from_buffer(io.BytesIO(resp.content))
    except Exception:
        return None

df = None
load_log = []

# A) 로컬(레포 포함) CSV 시도
df = _load_local_csv_if_exists(LOCAL_CSV_PATH)
if df is not None:
    load_log.append(f"✅ 로컬 CSV 로드 성공: {LOCAL_CSV_PATH}")
else:
    load_log.append(f"❌ 로컬 CSV 없음/로드 실패: {LOCAL_CSV_PATH}")

# B) 로컬 실패 시 GitHub Raw URL 시도 (원하시면 끄셔도 됩니다)
if df is None and GITHUB_RAW_URL and "<YOUR_ID>" not in GITHUB_RAW_URL:
    df = _load_csv_from_github_raw(GITHUB_RAW_URL)
    if df is not None:
        load_log.append(f"✅ GitHub Raw에서 CSV 로드 성공")
    else:
        load_log.append(f"❌ GitHub Raw에서 CSV 로드 실패")

# C) 그래도 실패하면 업로드 위젯 사용
if df is None and uploaded is not None:
    try:
        # 업로드 파일을 메모리에서 인코딩 루프 처리
        file_bytes = uploaded.read()
        df = _try_read_csv_any_encoding_from_buffer(io.BytesIO(file_bytes))
        load_log.append("✅ 업로드 CSV 로드 성공")
    except Exception as e:
        load_log.append(f"❌ 업로드 CSV 로드 실패: {e}")

# 최종 실패 시 에러 안내
if df is None:
    st.error("CSV를 불러오지 못했습니다. 아래 로그를 참고하세요.")
    for m in load_log:
        st.write("•", m)
    st.info("방법 1) 레포에 CSV를 app.py와 같은 폴더에 넣고 커밋/배포 다시하기")
    st.info("방법 2) GitHub Raw URL을 GITHUB_RAW_URL 변수에 올바르게 설정")
    st.info("방법 3) 사이드바에서 CSV 업로드")
    st.stop()

# 이후 파싱/전처리(월 컬럼/숫자형/파생지표) — 기존 함수 재사용
def coerce_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# '월' 파싱
if "월" in df.columns:
    try:
        df["월"] = pd.to_datetime(df["월"])
    except Exception:
        df["월"] = pd.to_datetime(df["월"].astype(str) + "-01", errors="coerce")

num_cols = ["매출액","매출원가","매출총이익","마케팅비용","운영비용","영업이익","NPS","CSAT"]
df = coerce_numeric(df, num_cols)

with np.errstate(divide='ignore', invalid='ignore'):
    if {"매출액","영업이익"}.issubset(df.columns):
        df["영업이익률(%)"] = (df["영업이익"] / df["매출액"] * 100).replace([np.inf, -np.inf], np.nan)
    if {"매출액","매출총이익"}.issubset(df.columns):
        df["매출총이익률(%)"] = (df["매출총이익"] / df["매출액"] * 100).replace([np.inf, -np.inf], np.nan)

# 디버그 보기
with st.expander("데이터 로딩 로그/미리보기"):
    for m in load_log:
        st.write("•", m)
    st.write("shape:", df.shape)
    st.write("columns:", list(df.columns))
    st.dataframe(df.head(10), use_container_width=True)

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

# =======================
# PDF Export (한글 폰트 포함)
# =======================
import io
import os
from fpdf import FPDF
import plotly.io as pio
import streamlit as st

# Plotly Figure -> PNG 바이트 (kaleido 필요)
def fig_to_png_bytes(fig, scale=2.0, width=1400, height=800):
    return pio.to_image(fig, format="png", scale=scale, width=width, height=height, engine="kaleido")

def build_pdf_bytes(
    kpi_total_sales, kpi_total_gross, kpi_opm,
    filters_text, selected_cat_text, axis_metric, trend_metric,
    bar_fig, wf_fig, scatter_fig, line_fig
):
    # 1) 차트 PNG 변환
    bar_png     = fig_to_png_bytes(bar_fig)
    wf_png      = fig_to_png_bytes(wf_fig)
    scatter_png = fig_to_png_bytes(scatter_fig)
    line_png    = fig_to_png_bytes(line_fig)

    # 2) PDF 생성
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)

    # ✅ NotoSansKR 폰트 등록 (없으면 기본 폰트로 대체)
    font_path = "NotoSansKR-Regular.ttf"
    use_korean_font = False
    if os.path.exists(font_path):
        try:
            pdf.add_font("NotoSansKR", "", font_path, uni=True)
            use_korean_font = True
        except Exception:
            use_korean_font = False

    def set_font(size=11, bold=False):
        if use_korean_font:
            pdf.set_font("NotoSansKR", "", size)
        else:
            # 한글 폰트가 없으면 기본 폰트(영문)로 대체
            pdf.set_font("Helvetica", "B" if bold else "", size)

    # 3) 커버/요약
    pdf.add_page()
    set_font(16, bold=True)
    pdf.cell(0, 10, "제품 카테고리별 수익성 대시보드", ln=1)

    set_font(11)
    pdf.multi_cell(0, 6, filters_text)
    pdf.ln(2)
    pdf.cell(0, 6, f"선택 카테고리: {selected_cat_text}", ln=1)
    pdf.cell(0, 6, f"산점도 Y축: {axis_metric} | 추세 지표: {trend_metric}", ln=1)

    pdf.ln(2)
    set_font(12, bold=True)
    pdf.cell(0, 7, "KPI 요약", ln=1)
    set_font(11)
    pdf.cell(0, 6, f"총 매출액: {kpi_total_sales:,.0f}", ln=1)
    pdf.cell(0, 6, f"총 매출총이익: {kpi_total_gross:,.0f}", ln=1)
    if pd.notna(kpi_opm):
        pdf.cell(0, 6, f"영업이익률: {kpi_opm:.2f}%", ln=1)
    else:
        pdf.cell(0, 6, "영업이익률: -", ln=1)

    # 4) 차트 페이지(각 차트 1페이지)
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    img_w = page_w
    img_h = 160  # mm 단위 대략적 비율

    def add_chart_page(title, png_bytes):
        pdf.add_page()
        set_font(12, bold=True)
        pdf.cell(0, 8, title, ln=1)
        pdf.image(io.BytesIO(png_bytes), x=pdf.l_margin, y=None, w=img_w, h=img_h)

    add_chart_page("카테고리별 영업이익률 (Bar)", bar_png)
    add_chart_page("선택 카테고리 수익 구조 (Waterfall)", wf_png)
    add_chart_page("수익성 vs 고객경험 (Scatter)", scatter_png)
    add_chart_page("시간 추세 (Line)", line_png)

    # 5) PDF 바이트 반환
    pdf_bytes = pdf.output(dest="S").encode("latin1")
    return pdf_bytes

# ===== 버튼 노출 (현재 필터/선택 상태를 캡처) =====
filters_text = (
    f"필터 -> 사업부: {biz or '(전체)'} | 지역: {reg or '(전체)'} | "
    f"채널: {ch or '(전체)'} | 세그먼트: {seg or '(전체)'}"
)
selected_cat_text = sel_cat
kpi_total_sales = fil["매출액"].sum()
kpi_total_gross = fil["매출총이익"].sum()
kpi_opm = (fil["영업이익"].sum() / kpi_total_sales * 100) if kpi_total_sales else np.nan

st.download_button(
    label="📄 PDF로 내보내기",
    data=build_pdf_bytes(
        kpi_total_sales, kpi_total_gross, kpi_opm,
        filters_text, selected_cat_text, axis_metric, trend_metric,
        bar_fig, wf_fig, scatter_fig, line_fig
    ),
    file_name="dashboard_report.pdf",
    mime="application/pdf",
    use_container_width=True
)

# 폰트가 없을 때 안내
if not os.path.exists("NotoSansKR-Regular.ttf"):
    st.info("한글이 깨지면 레포에 NotoSansKR-Regular.ttf를 넣어주세요. (app.py와 같은 폴더)")
