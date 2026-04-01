"""
테라클럽 회원 명부 - Streamlit Cloud + Google Sheets 버전
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
로컬 테스트:
    pip install streamlit gspread google-auth pandas
    streamlit run tela_club_streamlit.py

Streamlit Cloud 배포:
    GitHub에 올린 후 share.streamlit.io에서 연결
    Secrets에 gcp_service_account + SHEET_ID 설정 필요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date

# ─────────────────────────────────────────────────────────
#  페이지 설정 (반드시 첫 번째 st 호출)
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="테라클럽 회원 명부",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif !important; }

/* 헤더 */
.app-header {
    background: linear-gradient(135deg, #1a2e4a 0%, #2563eb 100%);
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 8px 32px rgba(37,99,235,.25);
}
.app-header h1 { color: #fff; margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }
.app-header p  { color: rgba(255,255,255,.65); margin: 2px 0 0; font-size: 13px; }

/* 통계 카드 */
.stat-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.stat-card {
    flex: 1; min-width: 110px;
    background: #fff;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
    border-left: 4px solid #2563eb;
}
.stat-card.master  { border-color: #f59e0b; }
.stat-card.officer { border-color: #16a34a; }
.stat-card.regular { border-color: #2563eb; }
.stat-card.dormant { border-color: #ca8a04; }
.stat-card.left    { border-color: #dc2626; }
.stat-card.total   { border-color: #1a2e4a; background: #1a2e4a; }
.stat-label { font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: .5px; }
.stat-label.white { color: rgba(255,255,255,.7); }
.stat-num   { font-size: 26px; font-weight: 900; color: #1a2e4a; line-height: 1.1; }
.stat-num.white { color: #fff; }
.stat-sub   { font-size: 11px; color: #9ca3af; margin-top: 1px; }
.stat-sub.white { color: rgba(255,255,255,.55); }

/* 배지 */
.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
}
.b-master    { background:#fef3c7; color:#92400e; }
.b-advisor   { background:#fde68a; color:#78350f; }
.b-president { background:#d1fae5; color:#065f46; }
.b-secretary { background:#a7f3d0; color:#064e3b; }
.b-sports    { background:#bfdbfe; color:#1e40af; }
.b-pr        { background:#c7d2fe; color:#3730a3; }
.b-regular   { background:#e0f2fe; color:#0369a1; }
.b-dormant   { background:#fef9c3; color:#854d0e; }
.b-left      { background:#fee2e2; color:#991b1b; }

/* 테이블 */
.members-table { background: #fff; border-radius: 14px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,.08); }
.tbl-header { background: #1a2e4a; color: rgba(255,255,255,.85); padding: 11px 14px; font-size: 12px; font-weight: 600; }
.tbl-row    { border-bottom: 1px solid #f1f5f9; padding: 10px 14px; font-size: 13px; }
.tbl-row:hover { background: #f8fafc; }
.row-master  { background: #fffbeb; }
.row-officer { background: #f0fdf4; }
.row-dormant { background: #fefce8; }
.row-left    { background: #fff1f2; opacity: .85; }

/* 폼 컨테이너 */
.form-section {
    background: #fff;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 2px 16px rgba(0,0,0,.08);
    margin-bottom: 20px;
}
.section-title {
    font-size: 15px; font-weight: 700; color: #1a2e4a;
    margin-bottom: 16px; padding-bottom: 10px;
    border-bottom: 2px solid #e0f2fe;
}

/* Streamlit 기본 스타일 오버라이드 */
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
.stButton > button {
    border-radius: 8px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
    font-weight: 600 !important;
}
div[data-testid="metric-container"] {
    background: #fff;
    border-radius: 12px;
    padding: 14px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  Google Sheets 연결
# ─────────────────────────────────────────────────────────
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
COLUMNS = [
    "id", "category", "name", "cafe_id", "birth_year", "gender",
    "phone", "join_date", "dormant_period", "leave_date",
    "email", "memo", "updated_at",
]
CATEGORIES = ["마스터", "고문", "회장", "총무", "경기이사", "홍보이사", "정회원", "휴면", "탈퇴"]
CAT_ORDER  = {c: i for i, c in enumerate(CATEGORIES)}

@st.cache_resource(ttl=0)
def get_sheet():
    """서비스 계정으로 Google Sheets 연결 (캐시: 앱 재시작까지 유지)"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    sheet  = client.open_by_key(st.secrets["SHEET_ID"]).sheet1

    # 헤더가 없으면 자동 삽입
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "id":
        sheet.insert_row(COLUMNS, 1)

    return sheet


def load_df() -> pd.DataFrame:
    """시트 → DataFrame"""
    sheet = get_sheet()
    records = sheet.get_all_records(expected_headers=COLUMNS)
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(records)
    # 타입 정리
    df["id"]         = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce")
    return df


def save_row(df: pd.DataFrame, row: dict, is_new: bool):
    """한 행 저장 (신규 추가 or 기존 수정)"""
    sheet = get_sheet()
    row["updated_at"] = datetime.today().strftime("%Y-%m-%d")
    values = [str(row.get(c, "") or "") for c in COLUMNS]

    if is_new:
        sheet.append_row(values, value_input_option="USER_ENTERED")
    else:
        # id로 행 위치 찾기
        all_ids = sheet.col_values(1)          # 1열 = id
        try:
            row_idx = all_ids.index(str(row["id"])) + 1   # 1-based
            sheet.update(f"A{row_idx}:{chr(64+len(COLUMNS))}{row_idx}",
                         [values], value_input_option="USER_ENTERED")
        except ValueError:
            sheet.append_row(values, value_input_option="USER_ENTERED")


def delete_row(member_id: int):
    """id로 행 삭제"""
    sheet = get_sheet()
    all_ids = sheet.col_values(1)
    try:
        row_idx = all_ids.index(str(member_id)) + 1
        sheet.delete_rows(row_idx)
    except ValueError:
        pass


def next_id(df: pd.DataFrame) -> int:
    return int(df["id"].max()) + 1 if not df.empty else 1


# ─────────────────────────────────────────────────────────
#  세션 상태 초기화
# ─────────────────────────────────────────────────────────
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None   # None = 신규, int = 수정 대상 id
if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "filter_cat" not in st.session_state:
    st.session_state.filter_cat = "전체"
if "search_q" not in st.session_state:
    st.session_state.search_q = ""


# ─────────────────────────────────────────────────────────
#  배지 HTML 헬퍼
# ─────────────────────────────────────────────────────────
BADGE_CLS = {
    "마스터":"b-master","고문":"b-advisor","회장":"b-president",
    "총무":"b-secretary","경기이사":"b-sports","홍보이사":"b-pr",
    "정회원":"b-regular","휴면":"b-dormant","탈퇴":"b-left",
}
def badge(cat):
    return f'<span class="badge {BADGE_CLS.get(cat,"b-regular")}">{cat}</span>'

GENDER_COLOR = {"남": "#2563eb", "여": "#db2777"}
def gender_html(g):
    c = GENDER_COLOR.get(g, "#374151")
    return f'<span style="color:{c};font-weight:700">{g}</span>'


# ─────────────────────────────────────────────────────────
#  메인 UI
# ─────────────────────────────────────────────────────────
# ── 헤더 ──────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <span style="font-size:36px">🎾</span>
  <div>
    <h1>테라클럽 회원 명부</h1>
    <p>TELA CLUB Member Roster · Google Sheets 연동</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 데이터 로드 ───────────────────────────────────────────
with st.spinner("📡 구글 시트에서 데이터 불러오는 중…"):
    try:
        df = load_df()
    except Exception as e:
        st.error(f"⚠️ Google Sheets 연결 오류: {e}")
        st.info("Streamlit Secrets에 `gcp_service_account`와 `SHEET_ID`가 올바르게 설정되어 있는지 확인해주세요.")
        st.stop()

# ── 통계 카드 ─────────────────────────────────────────────
def stat_counts(cats):
    sub = df[df["category"].isin(cats)] if not df.empty else pd.DataFrame()
    m = len(sub[sub["gender"] == "남"]) if not sub.empty else 0
    f = len(sub[sub["gender"] == "여"]) if not sub.empty else 0
    return m, f

groups = [
    ("마스터/고문", ["마스터","고문"],                              "master"),
    ("임원",        ["회장","총무","경기이사","홍보이사"],           "officer"),
    ("정회원",      ["정회원"],                                     "regular"),
    ("휴면",        ["휴면"],                                       "dormant"),
    ("탈퇴",        ["탈퇴"],                                       "left"),
]

cols = st.columns(len(groups) + 1)
for col, (label, cats, cls) in zip(cols[:-1], groups):
    m, f = stat_counts(cats)
    with col:
        st.markdown(f"""
        <div class="stat-card {cls}">
          <div class="stat-label">{label}</div>
          <div class="stat-num">{m+f}</div>
          <div class="stat-sub">남 {m} · 여 {f}</div>
        </div>""", unsafe_allow_html=True)

total_m = len(df[df["gender"]=="남"]) if not df.empty else 0
total_f = len(df[df["gender"]=="여"]) if not df.empty else 0
with cols[-1]:
    st.markdown(f"""
    <div class="stat-card total">
      <div class="stat-label white">총 회원수</div>
      <div class="stat-num white">{total_m+total_f}</div>
      <div class="stat-sub white">남 {total_m} · 여 {total_f}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── 툴바 ─────────────────────────────────────────────────
tb_left, tb_right = st.columns([3, 1])
with tb_left:
    search_q = st.text_input("🔍 검색 (이름 · 카페ID · 연락처)",
                             value=st.session_state.search_q,
                             placeholder="홍길동  /  hong_gd  /  010-...",
                             label_visibility="collapsed")
    st.session_state.search_q = search_q

with tb_right:
    if st.button("＋ 회원 등록", type="primary", use_container_width=True):
        st.session_state.edit_id   = None
        st.session_state.show_form = True

FILTER_OPTIONS = ["전체","마스터","고문","임원","정회원","휴면","탈퇴"]
filter_cat = st.radio("구분 필터", FILTER_OPTIONS,
                      index=FILTER_OPTIONS.index(st.session_state.filter_cat),
                      horizontal=True, label_visibility="collapsed")
st.session_state.filter_cat = filter_cat

sort_col1, sort_col2 = st.columns([1, 5])
with sort_col1:
    sort_by = st.selectbox("정렬", ["No.순","구분순","이름순","입회일순"],
                           label_visibility="collapsed")

# ── 필터링 ────────────────────────────────────────────────
OFFICER_CATS = ["회장","총무","경기이사","홍보이사"]

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # 구분 필터
    if filter_cat != "전체":
        cats = OFFICER_CATS if filter_cat == "임원" else [filter_cat]
        df = df[df["category"].isin(cats)]
    # 검색
    q = search_q.strip().lower()
    if q:
        mask = (
            df["name"].str.lower().str.contains(q, na=False) |
            df["cafe_id"].astype(str).str.lower().str.contains(q, na=False) |
            df["phone"].astype(str).str.contains(q, na=False)
        )
        df = df[mask]
    # 정렬
    if sort_by == "구분순":
        df = df.copy()
        df["_ord"] = df["category"].map(CAT_ORDER).fillna(99)
        df = df.sort_values("_ord").drop(columns="_ord")
    elif sort_by == "이름순":
        df = df.sort_values("name")
    elif sort_by == "입회일순":
        df = df.sort_values("join_date")
    else:
        df = df.sort_values("id")
    return df.reset_index(drop=True)

view_df = apply_filters(df.copy())

st.caption(f"검색 결과 **{len(view_df)}명** / 전체 {len(df)}명")

# ── 회원 목록 테이블 ──────────────────────────────────────
ROW_BG = {
    "마스터":"#fffbeb","고문":"#fffbeb",
    "회장":"#f0fdf4","총무":"#f0fdf4","경기이사":"#f0fdf4","홍보이사":"#f0fdf4",
    "정회원":"#ffffff",
    "휴면":"#fefce8",
    "탈퇴":"#fff1f2",
}

if view_df.empty:
    st.info("🎾 해당 조건의 회원이 없습니다.")
else:
    # 헤더
    hcols = st.columns([0.4, 0.8, 1, 1.2, 0.6, 0.5, 1.2, 1, 1.4, 1, 0.9])
    for col, txt in zip(hcols, ["No.","구분","성명","카페ID","생년","성별","연락처","입회일","휴면기간","탈퇴일","관리"]):
        col.markdown(f"<div style='font-size:11px;font-weight:700;color:#6b7280;padding:6px 0 4px;border-bottom:2px solid #e2e8f0'>{txt}</div>",
                     unsafe_allow_html=True)

    for idx, row in view_df.iterrows():
        bg = ROW_BG.get(row.get("category",""), "#fff")
        rcols = st.columns([0.4, 0.8, 1, 1.2, 0.6, 0.5, 1.2, 1, 1.4, 1, 0.9])

        rcols[0].markdown(f"<div style='padding:8px 0;font-size:12px;color:#9ca3af'>{idx+1}</div>", unsafe_allow_html=True)
        rcols[1].markdown(f"<div style='padding:6px 0'>{badge(row.get('category',''))}</div>", unsafe_allow_html=True)
        rcols[2].markdown(f"<div style='padding:8px 0;font-weight:600;color:#1a2e4a'>{row.get('name','')}</div>", unsafe_allow_html=True)
        rcols[3].markdown(f"<div style='padding:8px 0;font-size:12px;color:#6b7280'>{row.get('cafe_id','') or '—'}</div>", unsafe_allow_html=True)
        rcols[4].markdown(f"<div style='padding:8px 0;font-size:12px'>{row.get('birth_year','') or '—'}</div>", unsafe_allow_html=True)
        rcols[5].markdown(f"<div style='padding:6px 0'>{gender_html(str(row.get('gender','')))}</div>", unsafe_allow_html=True)
        rcols[6].markdown(f"<div style='padding:8px 0;font-size:12px'>{row.get('phone','') or '—'}</div>", unsafe_allow_html=True)
        rcols[7].markdown(f"<div style='padding:8px 0;font-size:12px;color:#6b7280'>{row.get('join_date','') or '—'}</div>", unsafe_allow_html=True)
        rcols[8].markdown(f"<div style='padding:8px 0;font-size:11px;color:#6b7280'>{row.get('dormant_period','') or '—'}</div>", unsafe_allow_html=True)
        rcols[9].markdown(f"<div style='padding:8px 0;font-size:12px;color:#dc2626'>{row.get('leave_date','') or '—'}</div>", unsafe_allow_html=True)

        btn_col1, btn_col2 = rcols[10].columns(2)
        if btn_col1.button("수정", key=f"edit_{row['id']}", use_container_width=True):
            st.session_state.edit_id   = int(row["id"])
            st.session_state.show_form = True
            st.rerun()
        if btn_col2.button("삭제", key=f"del_{row['id']}", use_container_width=True):
            delete_row(int(row["id"]))
            st.success(f"✅ {row['name']} 회원이 삭제되었습니다.")
            st.cache_resource.clear()
            st.rerun()

        st.markdown(f"<div style='border-bottom:1px solid #f1f5f9'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
#  회원 등록 / 수정 폼 (메인 화면 인라인)
# ─────────────────────────────────────────────────────────
if st.session_state.show_form:
    edit_id = st.session_state.edit_id
    existing = None
    if edit_id is not None and not df.empty:
        rows = df[df["id"] == edit_id]
        if not rows.empty:
            existing = rows.iloc[0].to_dict()

    st.markdown("---")
    st.markdown(f"### {'✏️ 회원 정보 수정' if existing else '➕ 새 회원 등록'}")

    with st.form("member_form", clear_on_submit=True):

        # ── 1행: 구분 / 성명 / 성별 ──────────────────────────
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            cat = st.selectbox(
                "구분 *",
                CATEGORIES,
                index=CATEGORIES.index(existing["category"]) if existing else 6,
            )
        with c2:
            name = st.text_input(
                "성명 *",
                value=existing["name"] if existing else "",
                placeholder="홍길동",
            )
        with c3:
            gender = st.selectbox(
                "성별 *",
                ["남", "여"],
                index=0 if not existing else (0 if existing["gender"] == "남" else 1),
            )

        # ── 2행: 카페ID / 생년 / 연락처 ──────────────────────
        c4, c5, c6 = st.columns([1, 1, 1])
        with c4:
            cafe_id = st.text_input(
                "카페ID",
                value=existing["cafe_id"] if existing else "",
                placeholder="cafe_id",
            )
        with c5:
            birth_year = st.text_input(
                "생년 (YYYY)",
                value=str(existing["birth_year"]) if existing and existing.get("birth_year") else "",
                placeholder="1990",
                max_chars=4,
            )
        with c6:
            phone = st.text_input(
                "연락처",
                value=existing["phone"] if existing else "",
                placeholder="010-0000-0000",
            )

        # ── 3행: 입회일 / 이메일 ─────────────────────────────
        c7, c8 = st.columns([1, 2])
        with c7:
            join_date_val = None
            if existing and existing.get("join_date"):
                try:
                    join_date_val = datetime.strptime(existing["join_date"], "%Y-%m-%d").date()
                except Exception:
                    pass
            join_date = st.date_input("입회일", value=join_date_val or date.today())
        with c8:
            email = st.text_input(
                "이메일",
                value=existing["email"] if existing else "",
                placeholder="example@email.com",
            )

        # ── 4행: 휴면기간 / 탈퇴일 ───────────────────────────
        c9, c10 = st.columns([1, 1])
        with c9:
            dormant = st.text_input(
                "휴면 기간",
                value=existing["dormant_period"] if existing else "",
                placeholder="예: 2024-01-01~2024-12-31",
            )
        with c10:
            leave_date_val = None
            if existing and existing.get("leave_date"):
                try:
                    leave_date_val = datetime.strptime(existing["leave_date"], "%Y-%m-%d").date()
                except Exception:
                    pass
            leave_date = st.date_input("탈퇴일 (탈퇴 시만)", value=leave_date_val)

        # ── 5행: 메모 ─────────────────────────────────────────
        memo = st.text_area(
            "메모",
            value=existing["memo"] if existing else "",
            placeholder="특이사항, 역할 등 자유 기재",
            height=80,
        )

        # ── 버튼 ──────────────────────────────────────────────
        btn_save, btn_cancel, _ = st.columns([1, 1, 4])
        submitted = btn_save.form_submit_button("💾 저장", type="primary", use_container_width=True)
        cancelled = btn_cancel.form_submit_button("✕ 취소", use_container_width=True)

    # 취소
    if cancelled:
        st.session_state.show_form = False
        st.rerun()

    # 저장
    if submitted:
        if not name.strip():
            st.error("❗ 성명은 필수입니다.")
        else:
            # 생년 숫자 변환
            by = None
            if birth_year.strip():
                try:
                    by = int(birth_year.strip())
                except ValueError:
                    by = None

            row_data = {
                "id":             existing["id"] if existing else next_id(df),
                "category":       cat,
                "name":           name.strip(),
                "cafe_id":        cafe_id.strip(),
                "birth_year":     by or "",
                "gender":         gender,
                "phone":          phone.strip(),
                "join_date":      join_date.strftime("%Y-%m-%d") if join_date else "",
                "dormant_period": dormant.strip(),
                "leave_date":     leave_date.strftime("%Y-%m-%d") if leave_date else "",
                "email":          email.strip(),
                "memo":           memo.strip(),
            }
            with st.spinner("구글 시트에 저장 중…"):
                save_row(df, row_data, is_new=(existing is None))

            st.success(f"✅ {'수정' if existing else '등록'} 완료! — {cat} {name.strip()}")
            st.session_state.show_form = False
            st.cache_resource.clear()
            st.rerun()
