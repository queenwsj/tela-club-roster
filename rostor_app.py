"""
테라클럽 회원 명부 - Streamlit Cloud + Google Sheets 버전
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실행: streamlit run tela_club_streamlit.py
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date

st.set_page_config(
    page_title="테라클럽 회원 명부",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────
#  상수
# ─────────────────────────────────────────────────────────
ADMIN_PASSWORD = "1223"
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
OFFICER_CATS = ["마스터", "고문", "회장", "총무", "경기이사", "홍보이사"]

# ─────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif !important; }

.app-header {
    background: linear-gradient(135deg, #1a2e4a 0%, #2563eb 100%);
    border-radius: 16px; padding: 22px 28px; margin-bottom: 20px;
    display: flex; align-items: center; gap: 16px;
    box-shadow: 0 8px 32px rgba(37,99,235,.25);
}
.app-header h1 { color:#fff; margin:0; font-size:22px; font-weight:800; letter-spacing:-0.5px; }
.app-header p  { color:rgba(255,255,255,.65); margin:2px 0 0; font-size:13px; }

.stat-card {
    background:#fff; border-radius:12px; padding:14px 16px;
    box-shadow:0 2px 12px rgba(0,0,0,.08); border-left:4px solid #2563eb;
}
.stat-card.officer { border-color:#f59e0b; }
.stat-card.regular { border-color:#2563eb; }
.stat-card.dormant { border-color:#ca8a04; }
.stat-card.left    { border-color:#dc2626; }
.stat-card.total   { border-color:#1a2e4a; background:#1a2e4a; }
.stat-label       { font-size:11px; font-weight:700; color:#6b7280; text-transform:uppercase; letter-spacing:.5px; }
.stat-label.white { color:rgba(255,255,255,.7); }
.stat-num         { font-size:26px; font-weight:900; color:#1a2e4a; line-height:1.1; }
.stat-num.white   { color:#fff; }
.stat-sub         { font-size:11px; color:#9ca3af; margin-top:1px; }
.stat-sub.white   { color:rgba(255,255,255,.55); }

.badge { display:inline-block; padding:2px 9px; border-radius:20px; font-size:11px; font-weight:700; white-space:nowrap; }
.b-master    { background:#fef3c7; color:#92400e; }
.b-advisor   { background:#fde68a; color:#78350f; }
.b-president { background:#d1fae5; color:#065f46; }
.b-secretary { background:#a7f3d0; color:#064e3b; }
.b-sports    { background:#bfdbfe; color:#1e40af; }
.b-pr        { background:#c7d2fe; color:#3730a3; }
.b-regular   { background:#e0f2fe; color:#0369a1; }
.b-dormant   { background:#fef9c3; color:#854d0e; }
.b-left      { background:#fee2e2; color:#991b1b; }

.stButton > button {
    border-radius:8px !important;
    font-family:'Noto Sans KR', sans-serif !important;
    font-weight:600 !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  세션 상태 초기화
# ─────────────────────────────────────────────────────────
defaults = {
    "edit_id": None,
    "show_form": False,
    "filter_cat": "전체",
    "search_q": "",
    "search_active": "",
    "admin_verified": False,
    "pending_action": None,   # {"type":"edit"|"delete", "id":int, "name":str}
    "pw_error": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────
#  Google Sheets 연결
# ─────────────────────────────────────────────────────────
@st.cache_resource(ttl=0)
def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open_by_key(st.secrets["SHEET_ID"]).sheet1
    if sheet.row_count == 0 or sheet.cell(1, 1).value != "id":
        sheet.insert_row(COLUMNS, 1)
    return sheet

def load_df() -> pd.DataFrame:
    sheet = get_sheet()
    records = sheet.get_all_records(expected_headers=COLUMNS)
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(records)
    df["id"]         = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce")
    return df

def save_row(df: pd.DataFrame, row: dict, is_new: bool):
    sheet = get_sheet()
    row["updated_at"] = datetime.today().strftime("%Y-%m-%d")
    values = [str(row.get(c, "") or "") for c in COLUMNS]
    if is_new:
        sheet.append_row(values, value_input_option="USER_ENTERED")
    else:
        all_ids = sheet.col_values(1)
        try:
            row_idx = all_ids.index(str(row["id"])) + 1
            sheet.update(f"A{row_idx}:{chr(64+len(COLUMNS))}{row_idx}",
                         [values], value_input_option="USER_ENTERED")
        except ValueError:
            sheet.append_row(values, value_input_option="USER_ENTERED")

def delete_row(member_id: int):
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
#  헬퍼
# ─────────────────────────────────────────────────────────
BADGE_CLS = {
    "마스터":"b-master","고문":"b-advisor","회장":"b-president",
    "총무":"b-secretary","경기이사":"b-sports","홍보이사":"b-pr",
    "정회원":"b-regular","휴면":"b-dormant","탈퇴":"b-left",
}
def badge(cat):
    return f'<span class="badge {BADGE_CLS.get(cat,"b-regular")}">{cat}</span>'

GENDER_COLOR = {"남":"#2563eb","여":"#db2777"}
def gender_html(g):
    return f'<span style="color:{GENDER_COLOR.get(g,"#374151")};font-weight:700">{g}</span>'

# ─────────────────────────────────────────────────────────
#  헤더
# ─────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <span style="font-size:36px">🎾</span>
  <div>
    <h1>테라클럽 회원 명부</h1>
    <p>TELA CLUB Member Roster · Google Sheets 연동</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  데이터 로드
# ─────────────────────────────────────────────────────────
with st.spinner("📡 구글 시트에서 데이터 불러오는 중…"):
    try:
        df = load_df()
    except Exception as e:
        st.error(f"⚠️ Google Sheets 연결 오류: {e}")
        st.info("Streamlit Secrets에 gcp_service_account 와 SHEET_ID 가 올바르게 설정되어 있는지 확인해주세요.")
        st.stop()

# ─────────────────────────────────────────────────────────
#  통계 카드 — 운영진(마스터+고문+임원) 합산
# ─────────────────────────────────────────────────────────
def stat_counts(cats):
    sub = df[df["category"].isin(cats)] if not df.empty else pd.DataFrame()
    m = len(sub[sub["gender"]=="남"]) if not sub.empty else 0
    f = len(sub[sub["gender"]=="여"]) if not sub.empty else 0
    return m, f

groups = [
    ("운영진", OFFICER_CATS, "officer"),
    ("정회원", ["정회원"],   "regular"),
    ("휴면",   ["휴면"],     "dormant"),
    ("탈퇴",   ["탈퇴"],     "left"),
]

stat_cols = st.columns(len(groups) + 1)
for col, (label, cats, cls) in zip(stat_cols[:-1], groups):
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
with stat_cols[-1]:
    st.markdown(f"""
    <div class="stat-card total">
      <div class="stat-label white">총 회원수</div>
      <div class="stat-num white">{total_m+total_f}</div>
      <div class="stat-sub white">남 {total_m} · 여 {total_f}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  툴바 — 검색창 + 검색버튼 + 회원등록버튼
# ─────────────────────────────────────────────────────────
col_search, col_search_btn, col_add = st.columns([4, 0.8, 1.2])
with col_search:
    search_q = st.text_input(
        "검색",
        value=st.session_state.search_q,
        placeholder="이름 / 카페ID / 연락처 입력 후 검색 버튼 클릭",
        label_visibility="collapsed",
    )
    st.session_state.search_q = search_q

with col_search_btn:
    if st.button("🔍 검색", use_container_width=True):
        st.session_state.search_active = search_q.strip()
        st.rerun()

with col_add:
    if st.button("＋ 회원 등록", type="primary", use_container_width=True):
        st.session_state.edit_id        = None
        st.session_state.show_form      = True
        st.session_state.admin_verified = False
        st.session_state.pending_action = None

# 검색어 비어있으면 초기화
if not search_q.strip():
    st.session_state.search_active = ""

# 필터 라디오
FILTER_OPTIONS = ["전체", "운영진", "정회원", "휴면", "탈퇴"]
if st.session_state.filter_cat not in FILTER_OPTIONS:
    st.session_state.filter_cat = "전체"

filter_cat = st.radio(
    "구분 필터", FILTER_OPTIONS,
    index=FILTER_OPTIONS.index(st.session_state.filter_cat),
    horizontal=True, label_visibility="collapsed",
)
st.session_state.filter_cat = filter_cat

sort_col_w, _ = st.columns([1, 5])
with sort_col_w:
    sort_by = st.selectbox("정렬", ["No.순","구분순","이름순","입회일순","탈퇴일순","생년순","성별순"],
                           label_visibility="collapsed")

# ─────────────────────────────────────────────────────────
#  필터링 & 정렬
# ─────────────────────────────────────────────────────────
def apply_filters(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data
    if filter_cat == "운영진":
        data = data[data["category"].isin(OFFICER_CATS)]
    elif filter_cat != "전체":
        data = data[data["category"] == filter_cat]

    q = st.session_state.search_active.lower()
    if q:
        mask = (
            data["name"].str.lower().str.contains(q, na=False) |
            data["cafe_id"].astype(str).str.lower().str.contains(q, na=False) |
            data["phone"].astype(str).str.contains(q, na=False)
        )
        data = data[mask]

    if sort_by == "구분순":
        data = data.copy()
        data["_ord"] = data["category"].map(CAT_ORDER).fillna(99)
        data = data.sort_values("_ord").drop(columns="_ord")
    elif sort_by == "이름순":
        data = data.sort_values("name")
    elif sort_by == "입회일순":
        data = data.sort_values("join_date")
    elif sort_by == "탈퇴일순":
        data = data.sort_values("leave_date")
    elif sort_by == "생년순":
        data = data.sort_values("birth_year")
    elif sort_by == "성별순":
        data = data.sort_values("gender")
    else:
        data = data.sort_values("id")
    return data.reset_index(drop=True)

view_df = apply_filters(df.copy())
st.caption(f"검색 결과 **{len(view_df)}명** / 전체 {len(df)}명")

# ─────────────────────────────────────────────────────────
#  회원 목록 테이블 — 메모 컬럼 포함
# ─────────────────────────────────────────────────────────
COL_W = [0.3, 0.7, 0.85, 0.9, 0.5, 0.4, 1.0, 0.8, 1.1, 0.8, 1.2, 0.75]
HDR   = ["No.","구분","성명","카페ID","생년","성별","연락처","입회일","휴면기간","탈퇴일","메모","관리"]

if view_df.empty:
    st.info("🎾 해당 조건의 회원이 없습니다.")
else:
    hcols = st.columns(COL_W)
    for col, txt in zip(hcols, HDR):
        col.markdown(
            f"<div style='font-size:11px;font-weight:700;color:#6b7280;"
            f"padding:6px 0 4px;border-bottom:2px solid #e2e8f0'>{txt}</div>",
            unsafe_allow_html=True,
        )

    for idx, row in view_df.iterrows():
        rcols = st.columns(COL_W)
        memo_txt     = str(row.get("memo","") or "").strip()
        memo_display = (memo_txt[:22] + "…") if len(memo_txt) > 22 else (memo_txt or "—")

        rcols[0].markdown(f"<div style='padding:8px 0;font-size:12px;color:#9ca3af'>{idx+1}</div>", unsafe_allow_html=True)
        rcols[1].markdown(f"<div style='padding:6px 0'>{badge(row.get('category',''))}</div>", unsafe_allow_html=True)
        rcols[2].markdown(f"<div style='padding:8px 0;font-weight:600;color:#1a2e4a'>{row.get('name','')}</div>", unsafe_allow_html=True)
        rcols[3].markdown(f"<div style='padding:8px 0;font-size:12px;color:#6b7280'>{row.get('cafe_id','') or '—'}</div>", unsafe_allow_html=True)
        rcols[4].markdown(f"<div style='padding:8px 0;font-size:12px'>{int(row['birth_year']) if pd.notna(row.get('birth_year')) and row.get('birth_year') else '—'}</div>", unsafe_allow_html=True)
        rcols[5].markdown(f"<div style='padding:6px 0'>{gender_html(str(row.get('gender','')))}</div>", unsafe_allow_html=True)
        rcols[6].markdown(f"<div style='padding:8px 0;font-size:12px'>{row.get('phone','') or '—'}</div>", unsafe_allow_html=True)
        rcols[7].markdown(f"<div style='padding:8px 0;font-size:12px;color:#6b7280'>{row.get('join_date','') or '—'}</div>", unsafe_allow_html=True)
        rcols[8].markdown(f"<div style='padding:8px 0;font-size:11px;color:#ca8a04'>{row.get('dormant_period','') or '—'}</div>", unsafe_allow_html=True)
        rcols[9].markdown(f"<div style='padding:8px 0;font-size:12px;color:#dc2626'>{row.get('leave_date','') or '—'}</div>", unsafe_allow_html=True)
        rcols[10].markdown(f"<div style='padding:8px 0;font-size:12px;color:#4b5563' title='{memo_txt}'>{memo_display}</div>", unsafe_allow_html=True)

        btn_c1, btn_c2 = rcols[11].columns(2)
        if btn_c1.button("수정", key=f"edit_{row['id']}", use_container_width=True):
            st.session_state.pending_action = {"type":"edit","id":int(row["id"]),"name":row["name"]}
            st.session_state.admin_verified = False
            st.session_state.pw_error       = False
            st.session_state.show_form      = False
            st.rerun()
        if btn_c2.button("삭제", key=f"del_{row['id']}", use_container_width=True):
            st.session_state.pending_action = {"type":"delete","id":int(row["id"]),"name":row["name"]}
            st.session_state.admin_verified = False
            st.session_state.pw_error       = False
            st.session_state.show_form      = False
            st.rerun()

        st.markdown("<div style='border-bottom:1px solid #f1f5f9'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  관리자 비밀번호 확인
# ─────────────────────────────────────────────────────────
if st.session_state.pending_action and not st.session_state.admin_verified:
    action = st.session_state.pending_action
    action_label = "수정" if action["type"] == "edit" else "삭제"

    st.markdown("---")
    st.markdown(f"### 🔐 관리자 인증 — [{action['name']}] {action_label}")

    with st.form("pw_form"):
        pw_input = st.text_input("관리자 비밀번호", type="password", placeholder="비밀번호 입력")
        col_ok, col_cancel, _ = st.columns([1, 1, 4])
        ok     = col_ok.form_submit_button("확인", type="primary", use_container_width=True)
        cancel = col_cancel.form_submit_button("취소", use_container_width=True)

    if ok:
        if pw_input == ADMIN_PASSWORD:
            st.session_state.admin_verified = True
            if action["type"] == "edit":
                st.session_state.edit_id   = action["id"]
                st.session_state.show_form = True
            st.rerun()
        else:
            st.error("❌ 비밀번호가 틀렸습니다.")

    if cancel:
        st.session_state.pending_action = None
        st.session_state.pw_error       = False
        st.rerun()

# ─────────────────────────────────────────────────────────
#  삭제 최종 확인 (인증 완료 후)
# ─────────────────────────────────────────────────────────
if (st.session_state.pending_action and
        st.session_state.admin_verified and
        st.session_state.pending_action["type"] == "delete"):

    action = st.session_state.pending_action
    st.markdown("---")
    st.warning(f"⚠️ **[{action['name']}]** 회원을 정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
    col_yes, col_no, _ = st.columns([1, 1, 4])
    if col_yes.button("🗑️ 삭제 확인", type="primary", use_container_width=True):
        with st.spinner("삭제 중…"):
            delete_row(action["id"])
        st.success(f"✅ {action['name']} 회원이 삭제되었습니다.")
        st.session_state.pending_action = None
        st.session_state.admin_verified = False
        st.cache_resource.clear()
        st.rerun()
    if col_no.button("취소", use_container_width=True):
        st.session_state.pending_action = None
        st.session_state.admin_verified = False
        st.rerun()

# ─────────────────────────────────────────────────────────
#  회원 등록 / 수정 폼
# ─────────────────────────────────────────────────────────
if st.session_state.show_form:
    edit_id  = st.session_state.edit_id
    existing = None
    if edit_id is not None and not df.empty:
        rows = df[df["id"] == edit_id]
        if not rows.empty:
            existing = rows.iloc[0].to_dict()

    st.markdown("---")
    st.markdown(f"### {'✏️ 회원 정보 수정' if existing else '➕ 새 회원 등록'}")

    with st.form("member_form", clear_on_submit=True):

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            cat = st.selectbox("구분 *", CATEGORIES,
                index=CATEGORIES.index(existing["category"]) if existing else 6)
        with c2:
            name = st.text_input("성명 *",
                value=existing["name"] if existing else "", placeholder="홍길동")
        with c3:
            gender = st.selectbox("성별 *", ["남","여"],
                index=0 if not existing else (0 if existing["gender"]=="남" else 1))

        c4, c5, c6 = st.columns([1, 1, 1])
        with c4:
            cafe_id = st.text_input("카페ID",
                value=existing["cafe_id"] if existing else "", placeholder="cafe_id")
        with c5:
            by_val = ""
            if existing and existing.get("birth_year"):
                try:
                    by_val = str(int(existing["birth_year"]))
                except Exception:
                    by_val = ""
            birth_year = st.text_input("생년 (YYYY)", value=by_val, placeholder="1990", max_chars=4)
        with c6:
            phone = st.text_input("연락처",
                value=existing["phone"] if existing else "", placeholder="010-0000-0000")

        c7, c8 = st.columns([1, 2])
        with c7:
            join_date_val = None
            if existing and existing.get("join_date"):
                try:
                    join_date_val = datetime.strptime(str(existing["join_date"]), "%Y-%m-%d").date()
                except Exception:
                    pass
            join_date = st.date_input("입회일", value=join_date_val or date.today())
        with c8:
            email = st.text_input("이메일",
                value=existing["email"] if existing else "", placeholder="example@email.com")

        c9, c10 = st.columns([1, 1])
        with c9:
            dormant = st.text_input("휴면 기간",
                value=existing["dormant_period"] if existing else "",
                placeholder="예: 2024-01-01~2024-12-31")
        with c10:
            leave_date_val = None
            if existing and existing.get("leave_date"):
                try:
                    leave_date_val = datetime.strptime(str(existing["leave_date"]), "%Y-%m-%d").date()
                except Exception:
                    pass
            leave_date = st.date_input("탈퇴일 (탈퇴 시만)", value=leave_date_val)

        memo = st.text_area("메모",
            value=existing["memo"] if existing else "",
            placeholder="특이사항, 역할 등 자유 기재", height=80)

        btn_save, btn_cancel, _ = st.columns([1, 1, 4])
        submitted = btn_save.form_submit_button("💾 저장", type="primary", use_container_width=True)
        cancelled = btn_cancel.form_submit_button("✕ 취소", use_container_width=True)

    if cancelled:
        st.session_state.show_form      = False
        st.session_state.pending_action = None
        st.session_state.admin_verified = False
        st.rerun()

    if submitted:
        if not name.strip():
            st.error("❗ 성명은 필수입니다.")
        else:
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
            st.session_state.show_form      = False
            st.session_state.pending_action = None
            st.session_state.admin_verified = False
            st.cache_resource.clear()
            st.rerun()
