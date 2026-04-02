"""
테라클럽 회원 명부 - Streamlit Cloud + Google Sheets 버전
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
ADMIN_PASSWORD = "1223"
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
COLUMNS = [
    "id", "category", "name", "cafe_id", "birth_year", "gender",
    "phone", "join_date", "dormant_period", "leave_date",
    "email", "application", "memo", "updated_at",
]
CATEGORIES   = ["마스터","고문","회장","총무","경기이사","홍보이사","정회원","휴면","탈퇴"]
CAT_ORDER    = {c: i for i, c in enumerate(CATEGORIES)}
OFFICER_CATS = ["마스터","고문","회장","총무","경기이사","홍보이사"]
FS = "font-size:12px"

# ── CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
html, body, [class*="css"] { font-family:'Noto Sans KR',sans-serif !important; }
.app-header {
    background:linear-gradient(135deg,#1a2e4a 0%,#2563eb 100%);
    border-radius:16px; padding:22px 28px; margin-bottom:20px;
    display:flex; align-items:center; gap:16px;
    box-shadow:0 8px 32px rgba(37,99,235,.25);
}
.app-header h1 { color:#fff; margin:0; font-size:22px; font-weight:800; letter-spacing:-0.5px; }
.app-header p  { color:rgba(255,255,255,.65); margin:2px 0 0; font-size:13px; }
.stat-card { background:#fff; border-radius:12px; padding:14px 16px;
    box-shadow:0 2px 12px rgba(0,0,0,.08); border-left:4px solid #2563eb; }
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
.stButton > button { border-radius:8px !important; font-family:'Noto Sans KR',sans-serif !important; font-weight:600 !important; }
/* 다이얼로그 너비 확장 */
div[data-testid="stDialog"] > div { max-width: 780px !important; width: 90vw !important; }
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 ─────────────────────────────────────────────
for k, v in {
    "filter_cat":    "전체",
    "search_q":      "",
    "search_active": "",
    "open_dialog":   None,   # None | "add" | "edit" | "pw_edit" | "pw_delete"
    "edit_target":   None,   # 수정/삭제 대상 {"id":int,"name":str,"type":str}
    "pw_verified_id": None,  # 비번 인증 완료된 id
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Google Sheets ─────────────────────────────────────────
@st.cache_resource(ttl=0)
def get_sheet():
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet  = client.open_by_key(st.secrets["SHEET_ID"]).sheet1
    if sheet.row_count == 0 or sheet.cell(1,1).value != "id":
        sheet.insert_row(COLUMNS, 1)
    return sheet

def load_df():
    records = get_sheet().get_all_records(expected_headers=COLUMNS)
    if not records:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(records)
    df["id"]         = pd.to_numeric(df["id"],         errors="coerce").fillna(0).astype(int)
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce")
    return df

def save_row(df, row, is_new):
    sheet = get_sheet()
    row["updated_at"] = datetime.today().strftime("%Y-%m-%d")
    values = [str(row.get(c,"") or "") for c in COLUMNS]
    if is_new:
        sheet.append_row(values, value_input_option="USER_ENTERED")
    else:
        all_ids = sheet.col_values(1)
        try:
            ri = all_ids.index(str(row["id"])) + 1
            sheet.update(f"A{ri}:{chr(64+len(COLUMNS))}{ri}", [values], value_input_option="USER_ENTERED")
        except ValueError:
            sheet.append_row(values, value_input_option="USER_ENTERED")

def delete_row(mid):
    sheet   = get_sheet()
    all_ids = sheet.col_values(1)
    try:
        sheet.delete_rows(all_ids.index(str(mid)) + 1)
    except ValueError:
        pass

def next_id(df):
    return int(df["id"].max()) + 1 if not df.empty else 1

# ── 헬퍼 ──────────────────────────────────────────────────
BADGE_CLS = {
    "마스터":"b-master","고문":"b-advisor","회장":"b-president","총무":"b-secretary",
    "경기이사":"b-sports","홍보이사":"b-pr","정회원":"b-regular","휴면":"b-dormant","탈퇴":"b-left",
}
def badge(cat):
    return f'<span class="badge {BADGE_CLS.get(cat,"b-regular")}">{cat}</span>'

def gender_html(g):
    c = {"남":"#2563eb","여":"#db2777"}.get(g,"#374151")
    return f'<span style="color:{c};font-weight:700;{FS}">{g}</span>'

def cell(txt, color="#374151", extra=""):
    return f"<div style='padding:7px 0;{FS};color:{color};{extra}'>{txt}</div>"

# ─────────────────────────────────────────────────────────
#  팝업 다이얼로그: 관리자 비밀번호
# ─────────────────────────────────────────────────────────
@st.dialog("🔐 관리자 인증")
def dialog_pw(target):
    action_label = "수정" if target["type"] == "edit" else "삭제"
    st.markdown(f"**[{target['name']}]** 회원 {action_label}을 위해 비밀번호를 입력하세요.")
    pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
    col_ok, col_cancel = st.columns(2)
    if col_ok.button("✅ 확인", type="primary", use_container_width=True):
        if pw == ADMIN_PASSWORD:
            # 인증 성공 → 다음 다이얼로그로 이동
            st.session_state.pw_verified_id = target["id"]
            if target["type"] == "edit":
                st.session_state.open_dialog = "edit"
            else:
                st.session_state.open_dialog = "delete_confirm"
            st.session_state.edit_target = target
            st.rerun()
        else:
            st.error("❌ 비밀번호가 틀렸습니다.")
    if col_cancel.button("취소", use_container_width=True):
        st.session_state.open_dialog  = None
        st.session_state.edit_target  = None
        st.session_state.pw_verified_id = None
        st.rerun()

# ─────────────────────────────────────────────────────────
#  팝업 다이얼로그: 삭제 확인
# ─────────────────────────────────────────────────────────
@st.dialog("🗑️ 삭제 확인")
def dialog_delete(target):
    st.warning(f"**[{target['name']}]** 회원을 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.")
    cy, cn = st.columns(2)
    if cy.button("삭제 확인", type="primary", use_container_width=True):
        with st.spinner("삭제 중…"):
            delete_row(target["id"])
        st.session_state.open_dialog   = None
        st.session_state.edit_target   = None
        st.session_state.pw_verified_id = None
        st.cache_resource.clear()
        st.rerun()
    if cn.button("취소", use_container_width=True):
        st.session_state.open_dialog   = None
        st.session_state.edit_target   = None
        st.session_state.pw_verified_id = None
        st.rerun()

# ─────────────────────────────────────────────────────────
#  팝업 다이얼로그: 회원 등록 / 수정 폼
# ─────────────────────────────────────────────────────────
@st.dialog("회원 정보", width="large")
def dialog_form(existing=None):
    title = "✏️ 회원 정보 수정" if existing else "➕ 새 회원 등록"
    st.markdown(f"#### {title}")

    with st.form("member_form", clear_on_submit=False):
        # 행1: 구분 / 성명 / 성별
        c1,c2,c3 = st.columns([1,1,1])
        with c1:
            cat = st.selectbox("구분 *", CATEGORIES,
                index=CATEGORIES.index(existing["category"]) if existing else 6)
        with c2:
            name = st.text_input("성명 *",
                value=existing["name"] if existing else "", placeholder="홍길동")
        with c3:
            gender = st.selectbox("성별 *", ["남","여"],
                index=0 if not existing else (0 if existing["gender"]=="남" else 1))

        # 행2: 카페ID / 생년 / 연락처
        c4,c5,c6 = st.columns([1,1,1])
        with c4:
            cafe_id = st.text_input("카페ID",
                value=existing["cafe_id"] if existing else "", placeholder="cafe_id")
        with c5:
            by_v = ""
            if existing and existing.get("birth_year"):
                try: by_v = str(int(existing["birth_year"]))
                except: pass
            birth_year = st.text_input("생년 (YYYY)", value=by_v, placeholder="1990", max_chars=4)
        with c6:
            phone = st.text_input("연락처",
                value=existing["phone"] if existing else "", placeholder="010-0000-0000")

        # 행3: 입회일 / 이메일
        c7,c8 = st.columns([1,2])
        with c7:
            jd_val = None
            if existing and existing.get("join_date"):
                try: jd_val = datetime.strptime(str(existing["join_date"]),"%Y-%m-%d").date()
                except: pass
            join_date = st.date_input("입회일", value=jd_val or date.today())
        with c8:
            email = st.text_input("이메일",
                value=existing["email"] if existing else "", placeholder="example@email.com")

        # 행4: 휴면기간 / 탈퇴일
        c9,c10 = st.columns([1,1])
        with c9:
            dormant = st.text_input("휴면 기간",
                value=existing["dormant_period"] if existing else "",
                placeholder="예: 2024-01-01~2024-12-31")
        with c10:
            ld_val = None
            if existing and existing.get("leave_date"):
                try: ld_val = datetime.strptime(str(existing["leave_date"]),"%Y-%m-%d").date()
                except: pass
            leave_date = st.date_input("탈퇴일 (입력 시 구분 자동→탈퇴)", value=ld_val)

        # 행5: 입회신청서 / 메모
        c11,c12 = st.columns([1,2])
        with c11:
            app_opts = ["—","Yes","No"]
            app_idx  = 0
            if existing:
                av = existing.get("application","")
                if av in app_opts: app_idx = app_opts.index(av)
            application = st.selectbox("입회신청서", app_opts, index=app_idx)
        with c12:
            memo = st.text_area("메모",
                value=existing["memo"] if existing else "",
                placeholder="특이사항, 역할 등 자유 기재", height=80)

        bs, bc = st.columns([1,1])
        submitted = bs.form_submit_button("💾 저장", type="primary", use_container_width=True)
        cancelled = bc.form_submit_button("✕ 취소",  use_container_width=True)

    if cancelled:
        st.session_state.open_dialog   = None
        st.session_state.edit_target   = None
        st.session_state.pw_verified_id = None
        st.rerun()

    if submitted:
        if not name.strip():
            st.error("❗ 성명은 필수입니다.")
        else:
            by = None
            if birth_year.strip():
                try: by = int(birth_year.strip())
                except: pass

            ld_str     = leave_date.strftime("%Y-%m-%d") if leave_date else ""
            final_cat  = "탈퇴" if ld_str else cat

            row_data = {
                "id":             existing["id"] if existing else next_id(df),
                "category":       final_cat,
                "name":           name.strip(),
                "cafe_id":        cafe_id.strip(),
                "birth_year":     by or "",
                "gender":         gender,
                "phone":          phone.strip(),
                "join_date":      join_date.strftime("%Y-%m-%d") if join_date else "",
                "dormant_period": dormant.strip(),
                "leave_date":     ld_str,
                "email":          email.strip(),
                "application":    "" if application=="—" else application,
                "memo":           memo.strip(),
            }
            with st.spinner("구글 시트에 저장 중…"):
                save_row(df, row_data, is_new=(existing is None))

            st.success(f"✅ {'수정' if existing else '등록'} 완료! — {final_cat} {name.strip()}")
            st.session_state.open_dialog   = None
            st.session_state.edit_target   = None
            st.session_state.pw_verified_id = None
            st.cache_resource.clear()
            st.rerun()

# ─────────────────────────────────────────────────────────
#  헤더
# ─────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <span style="font-size:36px">🎾</span>
  <div><h1>테라클럽 회원 명부</h1>
  <p>TELA CLUB Member Roster · Google Sheets 연동</p></div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  데이터 로드
# ─────────────────────────────────────────────────────────
with st.spinner("📡 구글 시트에서 데이터 불러오는 중…"):
    try:
        df = load_df()
    except Exception as e:
        st.error(f"⚠️ Google Sheets 연결 오류: {e}")
        st.stop()

# ─────────────────────────────────────────────────────────
#  다이얼로그 라우터 — 렌더링 최상단에서 처리
# ─────────────────────────────────────────────────────────
od = st.session_state.open_dialog
et = st.session_state.edit_target

if od == "add":
    dialog_form(existing=None)

elif od == "edit" and et and st.session_state.pw_verified_id == et["id"]:
    existing_row = None
    if not df.empty:
        rows = df[df["id"] == et["id"]]
        if not rows.empty:
            existing_row = rows.iloc[0].to_dict()
    dialog_form(existing=existing_row)

elif od == "delete_confirm" and et and st.session_state.pw_verified_id == et["id"]:
    dialog_delete(et)

elif od in ("pw_edit", "pw_delete") and et:
    dialog_pw(et)

# ─────────────────────────────────────────────────────────
#  통계 카드
# ─────────────────────────────────────────────────────────
def stat_counts(cats):
    sub = df[df["category"].isin(cats)] if not df.empty else pd.DataFrame()
    m   = len(sub[sub["gender"]=="남"]) if not sub.empty else 0
    f   = len(sub[sub["gender"]=="여"]) if not sub.empty else 0
    return m, f

groups = [
    ("운영진", OFFICER_CATS, "officer"),
    ("정회원", ["정회원"],   "regular"),
    ("휴면",   ["휴면"],     "dormant"),
    ("탈퇴",   ["탈퇴"],     "left"),
]
sc = st.columns(len(groups)+1)
for col,(label,cats,cls) in zip(sc[:-1],groups):
    m,f = stat_counts(cats)
    col.markdown(f'<div class="stat-card {cls}"><div class="stat-label">{label}</div>'
                 f'<div class="stat-num">{m+f}</div><div class="stat-sub">남 {m} · 여 {f}</div></div>',
                 unsafe_allow_html=True)
tm = len(df[df["gender"]=="남"]) if not df.empty else 0
tf = len(df[df["gender"]=="여"]) if not df.empty else 0
sc[-1].markdown(f'<div class="stat-card total"><div class="stat-label white">총 회원수</div>'
                f'<div class="stat-num white">{tm+tf}</div><div class="stat-sub white">남 {tm} · 여 {tf}</div></div>',
                unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  툴바
# ─────────────────────────────────────────────────────────
c_s, c_sb, c_add = st.columns([4, 0.8, 1.2])
with c_s:
    search_q = st.text_input("검색", value=st.session_state.search_q,
        placeholder="이름 / 카페ID / 연락처 입력 후 검색 버튼 클릭",
        label_visibility="collapsed")
    st.session_state.search_q = search_q
with c_sb:
    if st.button("🔍 검색", use_container_width=True):
        st.session_state.search_active = search_q.strip()
        st.rerun()
with c_add:
    if st.button("＋ 회원 등록", type="primary", use_container_width=True):
        st.session_state.open_dialog  = "add"
        st.session_state.edit_target  = None
        st.session_state.pw_verified_id = None
        st.rerun()

if not search_q.strip():
    st.session_state.search_active = ""

FILTER_OPTIONS = ["전체","운영진","정회원","휴면","탈퇴"]
if st.session_state.filter_cat not in FILTER_OPTIONS:
    st.session_state.filter_cat = "전체"
filter_cat = st.radio("필터", FILTER_OPTIONS,
    index=FILTER_OPTIONS.index(st.session_state.filter_cat),
    horizontal=True, label_visibility="collapsed")
st.session_state.filter_cat = filter_cat

sc2,_ = st.columns([1,5])
with sc2:
    sort_by = st.selectbox("정렬",
        ["No.순","구분순","이름순","입회일순","탈퇴일순","생년순","성별순"],
        label_visibility="collapsed")

# ─────────────────────────────────────────────────────────
#  필터링 & 정렬
# ─────────────────────────────────────────────────────────
def apply_filters(data):
    if data.empty: return data
    if filter_cat == "운영진":
        data = data[data["category"].isin(OFFICER_CATS)]
    elif filter_cat != "전체":
        data = data[data["category"] == filter_cat]
    q = st.session_state.search_active.lower()
    if q:
        mask = (data["name"].str.lower().str.contains(q,na=False) |
                data["cafe_id"].astype(str).str.lower().str.contains(q,na=False) |
                data["phone"].astype(str).str.contains(q,na=False))
        data = data[mask]
    if   sort_by=="구분순":   data=data.copy(); data["_o"]=data["category"].map(CAT_ORDER).fillna(99); data=data.sort_values("_o").drop(columns="_o")
    elif sort_by=="이름순":   data=data.sort_values("name")
    elif sort_by=="입회일순": data=data.sort_values("join_date")
    elif sort_by=="탈퇴일순": data=data.sort_values("leave_date")
    elif sort_by=="생년순":   data=data.sort_values("birth_year")
    elif sort_by=="성별순":   data=data.sort_values("gender")
    else:                     data=data.sort_values("id")
    return data.reset_index(drop=True)

view_df = apply_filters(df.copy())
st.caption(f"검색 결과 **{len(view_df)}명** / 전체 {len(df)}명")

# ─────────────────────────────────────────────────────────
#  회원 목록 테이블
# ─────────────────────────────────────────────────────────
CW  = [0.28, 0.68, 0.85, 0.88, 0.48, 0.4, 1.0, 0.78, 1.05, 0.75, 0.72, 1.15, 0.72]
HDR = ["No.","구분","성명","카페ID","생년","성별","연락처","입회일","휴면기간","탈퇴일","입회신청서","메모","관리"]

if view_df.empty:
    st.info("🎾 해당 조건의 회원이 없습니다.")
else:
    hcols = st.columns(CW)
    for hc,txt in zip(hcols,HDR):
        hc.markdown(f"<div style='{FS};font-weight:700;color:#6b7280;"
                    f"padding:6px 0 4px;border-bottom:2px solid #e2e8f0'>{txt}</div>",
                    unsafe_allow_html=True)

    for idx, row in view_df.iterrows():
        rc = st.columns(CW)
        memo_txt  = str(row.get("memo","") or "").strip()
        memo_disp = (memo_txt[:20]+"…") if len(memo_txt)>20 else (memo_txt or "—")
        by_val    = int(row["birth_year"]) if pd.notna(row.get("birth_year")) and row.get("birth_year") else "—"
        app_val   = str(row.get("application","") or "—")
        app_color = {"Yes":"#16a34a","No":"#dc2626"}.get(app_val,"#9ca3af")

        rc[0].markdown(cell(idx+1,"#9ca3af"), unsafe_allow_html=True)
        rc[1].markdown(f"<div style='padding:5px 0'>{badge(row.get('category',''))}</div>", unsafe_allow_html=True)
        rc[2].markdown(cell(row.get('name',''),"#1a2e4a","font-weight:600"), unsafe_allow_html=True)
        rc[3].markdown(cell(row.get('cafe_id','') or '—',"#6b7280"), unsafe_allow_html=True)
        rc[4].markdown(cell(by_val), unsafe_allow_html=True)
        rc[5].markdown(f"<div style='padding:5px 0'>{gender_html(str(row.get('gender','')))}</div>", unsafe_allow_html=True)
        rc[6].markdown(cell(row.get('phone','') or '—'), unsafe_allow_html=True)
        rc[7].markdown(cell(row.get('join_date','') or '—',"#6b7280"), unsafe_allow_html=True)
        rc[8].markdown(cell(row.get('dormant_period','') or '—',"#ca8a04"), unsafe_allow_html=True)
        rc[9].markdown(cell(row.get('leave_date','') or '—',"#dc2626"), unsafe_allow_html=True)
        rc[10].markdown(f"<div style='padding:5px 0'><span style='{FS};font-weight:700;color:{app_color}'>{app_val}</span></div>", unsafe_allow_html=True)
        rc[11].markdown(f"<div style='padding:7px 0;{FS};color:#4b5563' title='{memo_txt}'>{memo_disp}</div>", unsafe_allow_html=True)

        b1,b2 = rc[12].columns(2)
        if b1.button("수정", key=f"edit_{row['id']}", use_container_width=True):
            st.session_state.open_dialog   = "pw_edit"
            st.session_state.edit_target   = {"type":"edit","id":int(row["id"]),"name":row["name"]}
            st.session_state.pw_verified_id = None
            st.rerun()
        if b2.button("삭제", key=f"del_{row['id']}", use_container_width=True):
            st.session_state.open_dialog   = "pw_delete"
            st.session_state.edit_target   = {"type":"delete","id":int(row["id"]),"name":row["name"]}
            st.session_state.pw_verified_id = None
            st.rerun()

        st.markdown("<div style='border-bottom:1px solid #f1f5f9'></div>", unsafe_allow_html=True)
