"""
테라클럽 회원 명부 - Streamlit Cloud + Google Sheets 버전
실행: streamlit run rostor_app.py
"""

import re
import io
import streamlit as st
import gspread
from gspread.utils import rowcol_to_a1
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, date, timedelta

st.set_page_config(
    page_title="테라클럽 회원 명부",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────
# 비밀번호: 우선 st.secrets에서 읽고, 없으면 기본값(개발용)
# 운영 시 반드시 .streamlit/secrets.toml 또는 Streamlit Cloud Secrets에 등록:
#   ADMIN_PASSWORD = "원하는비번"
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "1223")
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
COLUMNS = [
    "id", "category", "name", "cafe_id", "birth_year", "gender",
    "phone", "region", "join_date", "dormant_period", "leave_date",
    "email", "application", "memo", "updated_at",
    "deleted_at",   # 소프트 삭제: 삭제 시각. 비어있으면 정상 회원.
]
AUDIT_COLUMNS = ["timestamp", "action", "member_id", "member_name", "detail"]
TRASH_DAYS    = 90   # 휴지통 보관 기간 (일)
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
.stButton > button {
    border-radius:7px !important;
    font-family:'Noto Sans KR',sans-serif !important;
    font-weight:700 !important;
    font-size:12px !important;
}
/* 테이블 수정 버튼 = 노란색 */
div.edit-col button { background-color:#fbbf24 !important; color:#1a2e4a !important; border:none !important; font-size:12px !important; font-weight:700 !important; }
div.edit-col button:hover { background-color:#f59e0b !important; }
/* 폼 버튼 3개: 저장=파란색, 취소=회색, 삭제=빨간색 */
div.save-col button  { background-color:#2563eb !important; color:#fff !important; border:none !important; font-size:12px !important; font-weight:700 !important; }
div.save-col button:hover  { background-color:#1d4ed8 !important; }
div.cancel-col button { background-color:#6b7280 !important; color:#fff !important; border:none !important; font-size:12px !important; font-weight:700 !important; }
div.cancel-col button:hover { background-color:#4b5563 !important; }
div.delete-col button { background-color:#ef4444 !important; color:#fff !important; border:none !important; font-size:12px !important; font-weight:700 !important; }
div.delete-col button:hover { background-color:#dc2626 !important; }

/* 반응형 — 모바일(아이폰) 최적화 */
section[data-testid="stMain"] .stMainBlockContainer,
.block-container {
    max-width: 100% !important;
    width: 100% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
@media (max-width: 430px) {
    .app-header { padding: 14px 16px !important; border-radius: 10px !important; }
    .app-header h1 { font-size: 15px !important; }
    .app-header p  { font-size: 10px !important; }
    .stat-card { padding: 8px 10px !important; min-width: 70px !important; }
    .stat-num  { font-size: 18px !important; }
    .stat-label, .stat-sub { font-size: 10px !important; }
    section[data-testid="stMain"] .stMainBlockContainer,
    .block-container { padding-left: 0.3rem !important; padding-right: 0.3rem !important; }
}
/* 다이얼로그 */
div[data-testid="stDialog"] > div { max-width: 95vw !important; width: 95vw !important; }
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 ─────────────────────────────────────────────
for k, v in {
    "filter_cat":    "전체",
    "search_q":      "",
    "search_active": "",
    "open_dialog":   None,
    "edit_target":   None,
    "admin_authed":  False,
    "auth_time":     None,   # 관리자 인증 시각 (타임아웃용)
    "show_trash":    False,  # 휴지통 보기 토글
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 세션 타임아웃 체크 (1시간) ────────────────────────────
SESSION_TIMEOUT_MIN = 60
if st.session_state.admin_authed and st.session_state.auth_time:
    elapsed = (datetime.now() - st.session_state.auth_time).total_seconds() / 60
    if elapsed >= SESSION_TIMEOUT_MIN:
        st.session_state.admin_authed = False
        st.session_state.auth_time    = None
        st.toast("⏰ 관리자 세션이 만료되었습니다. 다시 인증해 주세요.", icon="🔒")

# ── Google Sheets ─────────────────────────────────────────
@st.cache_resource
def get_sheet():
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    wb     = client.open_by_key(st.secrets["SHEET_ID"])
    sheet  = wb.sheet1
    # 헤더가 없으면 전체 삽입
    if sheet.row_count == 0 or sheet.cell(1,1).value != "id":
        sheet.insert_row(COLUMNS, 1)
        return sheet
    # ── 컬럼 마이그레이션: 기존 시트에 없는 컬럼 자동 추가 ──
    existing_headers = sheet.row_values(1)
    missing = [c for c in COLUMNS if c not in existing_headers]
    if missing:
        for col_name in missing:
            next_col = len(existing_headers) + 1
            sheet.update_cell(1, next_col, col_name)
            existing_headers.append(col_name)
    return sheet

@st.cache_resource
def get_audit_sheet():
    """변경 이력 시트 (audit_log 탭). 없으면 자동 생성."""
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    wb     = client.open_by_key(st.secrets["SHEET_ID"])
    try:
        asheet = wb.worksheet("audit_log")
    except gspread.exceptions.WorksheetNotFound:
        asheet = wb.add_worksheet(title="audit_log", rows=2000, cols=len(AUDIT_COLUMNS))
        asheet.insert_row(AUDIT_COLUMNS, 1)
    return asheet

def log_audit(action: str, member_id, member_name: str, detail: str = ""):
    """변경 이력을 audit_log 시트에 기록. 실패해도 메인 기능에 영향 없도록 try/except."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        get_audit_sheet().append_row(
            [ts, action, str(member_id), member_name, detail],
            value_input_option="USER_ENTERED"
        )
    except Exception:
        pass  # 로그 실패는 조용히 무시

def load_df(include_deleted=False):
    # expected_headers 없이 로드 → 시트에 컬럼 없어도 오류 없음
    records = get_sheet().get_all_records()
    if not records:
        df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(records)
        # COLUMNS에 있지만 df에 없는 컬럼은 빈 문자열로 보정
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS]  # 컬럼 순서 통일
    df["id"]         = pd.to_numeric(df["id"],         errors="coerce").fillna(0).astype(int)
    df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce")
    df["deleted_at"] = df["deleted_at"].astype(str).str.strip()
    if not include_deleted:
        df = df[df["deleted_at"] == ""]
    return df

def save_row(df, row, is_new, action_detail=""):
    sheet = get_sheet()
    row["updated_at"] = datetime.today().strftime("%Y-%m-%d %H:%M")
    if "deleted_at" not in row:
        row["deleted_at"] = ""
    values = [str(row.get(c,"") or "") for c in COLUMNS]
    action = "등록" if is_new else "수정"
    if is_new:
        sheet.append_row(values, value_input_option="USER_ENTERED")
    else:
        all_ids = sheet.col_values(1)
        try:
            ri         = all_ids.index(str(row["id"])) + 1
            start_cell = rowcol_to_a1(ri, 1)
            end_cell   = rowcol_to_a1(ri, len(COLUMNS))
            sheet.update(f"{start_cell}:{end_cell}", [values], value_input_option="USER_ENTERED")
        except ValueError:
            sheet.append_row(values, value_input_option="USER_ENTERED")
    log_audit(action, row.get("id",""), row.get("name",""), action_detail or f"카테고리:{row.get('category','')}")

def soft_delete_row(mid, member_name):
    """소프트 삭제: deleted_at 컬럼에 현재 시각을 기록. 행은 보존됨."""
    sheet   = get_sheet()
    all_ids = sheet.col_values(1)
    if not all_ids or all_ids[0] != "id":
        raise RuntimeError("시트 헤더가 손상되었습니다.")
    try:
        idx = all_ids.index(str(mid))
        if idx == 0:
            raise RuntimeError("헤더 행은 삭제할 수 없습니다.")
        ri         = idx + 1
        del_col    = COLUMNS.index("deleted_at") + 1
        del_cell   = rowcol_to_a1(ri, del_col)
        sheet.update(del_cell, [[datetime.now().strftime("%Y-%m-%d %H:%M:%S")]],
                     value_input_option="USER_ENTERED")
        log_audit("삭제(소프트)", mid, member_name, f"휴지통 이동. {TRASH_DAYS}일 후 영구 삭제.")
    except ValueError:
        pass

def hard_delete_row(mid, member_name):
    """영구 삭제: 시트에서 행 자체를 제거."""
    sheet   = get_sheet()
    all_ids = sheet.col_values(1)
    if not all_ids or all_ids[0] != "id":
        raise RuntimeError("시트 헤더가 손상되었습니다.")
    try:
        idx = all_ids.index(str(mid))
        if idx == 0:
            raise RuntimeError("헤더 행은 삭제할 수 없습니다.")
        sheet.delete_rows(idx + 1)
        log_audit("삭제(영구)", mid, member_name, "영구 삭제 완료.")
    except ValueError:
        pass

def restore_row(mid, member_name):
    """소프트 삭제 취소: deleted_at을 비워서 복구."""
    sheet   = get_sheet()
    all_ids = sheet.col_values(1)
    try:
        idx = all_ids.index(str(mid))
        ri  = idx + 1
        del_col  = COLUMNS.index("deleted_at") + 1
        del_cell = rowcol_to_a1(ri, del_col)
        sheet.update(del_cell, [[""]], value_input_option="USER_ENTERED")
        log_audit("복구", mid, member_name, "휴지통에서 복구.")
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
# 검증 함수
# ─────────────────────────────────────────────────────────
PHONE_RE = re.compile(r"^\d{2,4}-?\d{3,4}-?\d{4}$")
EMAIL_RE = re.compile(r"^[\w\.\-+]+@[\w\.\-]+\.\w{2,}$")
DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DORMANT_RANGE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}~(\d{4}-\d{2}-\d{2})?$")  # YYYY-MM-DD~ 또는 YYYY-MM-DD~YYYY-MM-DD

def validate_phone(s):
    if not s: return True
    return bool(PHONE_RE.match(s.strip()))

def validate_email(s):
    if not s: return True
    return bool(EMAIL_RE.match(s.strip()))

def validate_date(s):
    if not s: return True
    if not DATE_RE.match(str(s).strip()): return False
    try:
        datetime.strptime(str(s).strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False

def normalize_date(s):
    """다양한 입력 형식을 YYYY-MM-DD로 자동 변환.
    - 8자리: 20260101 → 2026-01-01
    - 6자리: 260101  → 2026-01-01
    - 구분자 혼용: 2026/01/01, 2026.01.01 → 2026-01-01
    """
    if not s: return ""
    s = str(s).strip()
    if not s: return ""
    cleaned = re.sub(r"[/.]", "-", s)
    if DATE_RE.match(cleaned):
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return s
    digits = re.sub(r"\D", "", s)
    if len(digits) == 8:
        try: return datetime.strptime(digits, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError: return s
    elif len(digits) == 6:
        try: return datetime.strptime("20" + digits, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError: return s
    return s

def normalize_phone(s):
    """연락처 자동 포맷팅: 01012345678 → 010-1234-5678"""
    if not s: return ""
    digits = re.sub(r"\D", "", str(s).strip())
    if len(digits) == 11 and digits.startswith("010"):
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return s  # 변환 불가 시 원본

# ─────────────────────────────────────────────────────────
# 휴면 기간 관리 (누적)
# ─────────────────────────────────────────────────────────
def parse_dormant_periods(s):
    if not s or not str(s).strip(): return []
    periods = []
    for chunk in str(s).split(";"):
        chunk = chunk.strip()
        if not chunk: continue
        if "~" in chunk:
            start, _, end = chunk.partition("~")
            periods.append({"start": start.strip(), "end": end.strip()})
        else:
            periods.append({"start": chunk, "end": ""})
    return periods

def format_dormant_periods(periods):
    parts = []
    for p in periods:
        start = (p.get("start") or "").strip()
        end   = (p.get("end") or "").strip()
        if not start: continue
        parts.append(f"{start}~{end}")
    return "; ".join(parts)

def has_ongoing_dormant(s):
    return any(not p["end"] for p in parse_dormant_periods(s))

def check_dormant_overlap(periods):
    """휴면 기간 겹침 및 진행중 중복 검사. 문제 있으면 에러 문자열 반환, 없으면 None."""
    ongoing_count = 0
    date_ranges = []
    for i, p in enumerate(periods):
        s = p.get("start","")
        e = p.get("end","")
        if not e:
            ongoing_count += 1
            if ongoing_count > 1:
                return f"진행중 휴면 기간이 2개 이상입니다. 1개만 허용됩니다."
        else:
            try:
                sd = datetime.strptime(s, "%Y-%m-%d").date()
                ed = datetime.strptime(e, "%Y-%m-%d").date()
                for j, (psd, ped) in enumerate(date_ranges):
                    if sd <= ped and ed >= psd:
                        return f"#{i+1}번 기간이 #{j+1}번 기간과 겹칩니다."
                date_ranges.append((sd, ed))
            except ValueError:
                pass
    return None

def check_duplicate(df, name, phone, cafe_id, exclude_id=None):
    if df.empty: return None
    target = df[df["id"] != exclude_id] if exclude_id is not None else df
    name_n  = (name or "").strip()
    phone_n = (phone or "").strip()
    cafe_n  = (cafe_id or "").strip()
    if name_n and phone_n:
        dup = target[(target["name"].astype(str).str.strip() == name_n) &
                     (target["phone"].astype(str).str.strip() == phone_n)]
        if not dup.empty:
            return f"이름+연락처가 동일한 회원이 이미 있습니다 (No.{int(dup.iloc[0]['id'])} {dup.iloc[0]['name']})"
    if cafe_n:
        dup = target[target["cafe_id"].astype(str).str.strip() == cafe_n]
        if not dup.empty:
            return f"카페ID가 동일한 회원이 이미 있습니다 (No.{int(dup.iloc[0]['id'])} {dup.iloc[0]['name']})"
    return None

# ─────────────────────────────────────────────────────────
# 생일자 / 휴면 알림 헬퍼
# ─────────────────────────────────────────────────────────
def get_birthday_members(df):
    """이번 달 생일자 (birth_year 있는 회원 기준)"""
    today = date.today()
    result = []
    for _, row in df.iterrows():
        bday = str(row.get("birth_month_day","") or "").strip()
        # birth_year 컬럼에서 month는 없으므로 — join_date를 쓰거나 메모에서 MM-DD를 파싱
        # 현재 데이터 구조: birth_year만 있고 month/day 없음 → 입회일 기준 이번 달 신규
        pass
    return result

def get_this_month_birthdays(df):
    """이번 달 입회 기념일 회원 (입회월 기준)"""
    today = date.today()
    result = []
    for _, row in df.iterrows():
        jd = str(row.get("join_date","") or "").strip()
        if not jd: continue
        try:
            jdate = datetime.strptime(jd[:10], "%Y-%m-%d").date()
            if jdate.month == today.month:
                years = today.year - jdate.year
                result.append({"name": row["name"], "join_date": jd, "years": years, "category": row["category"]})
        except ValueError:
            pass
    return result

def get_long_dormant_members(df, months=3):
    """진행중 휴면이 N개월 이상인 회원 목록 반환"""
    today   = date.today()
    cutoff  = today - timedelta(days=months * 30)
    result  = []
    for _, row in df.iterrows():
        if row.get("category") != "휴면": continue
        for p in parse_dormant_periods(str(row.get("dormant_period","") or "")):
            if not p["end"] and p["start"]:
                try:
                    sd = datetime.strptime(p["start"], "%Y-%m-%d").date()
                    if sd <= cutoff:
                        result.append({"name": row["name"], "start": p["start"],
                                       "days": (today - sd).days})
                except ValueError:
                    pass
    return result

# ─────────────────────────────────────────────────────────
#  팝업 다이얼로그: 관리자 비밀번호
# ─────────────────────────────────────────────────────────
@st.dialog("🔐 관리자 인증")
def dialog_pw(target):
    action_label = "수정" if target["type"] == "edit" else "삭제"
    st.markdown(f"**[{target['name']}]** 회원 {action_label}을 위해 비밀번호를 입력하세요.")
    st.caption("💡 한 번 인증하면 브라우저를 닫기 전까지 다시 묻지 않습니다.")
    pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
    col_ok, col_cancel = st.columns(2)
    if col_ok.button("✅ 확인", type="primary", use_container_width=True):
        if pw == ADMIN_PASSWORD:
            # 인증 성공 → 세션 전체 인증 플래그 설정
            st.session_state.admin_authed = True
            st.session_state.auth_time    = datetime.now()   # 타임아웃 기산점
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
        st.rerun()

# ─────────────────────────────────────────────────────────
#  팝업 다이얼로그: 삭제 확인
# ─────────────────────────────────────────────────────────
@st.dialog("🗑️ 삭제 확인")
def dialog_delete(target):
    st.warning(
        f"**[{target['name']}]** 회원을 휴지통으로 이동합니다.\n\n"
        f"휴지통에서 **{TRASH_DAYS}일 후 자동 영구 삭제**됩니다. 그 전에는 복구 가능합니다."
    )
    cy, cn = st.columns(2)
    if cy.button("🗑️ 휴지통으로 이동", type="primary", use_container_width=True):
        with st.spinner("삭제 중…"):
            soft_delete_row(target["id"], target["name"])
        st.session_state.open_dialog   = None
        st.session_state.edit_target   = None
        st.cache_resource.clear()
        st.rerun()
    if cn.button("취소", use_container_width=True):
        st.session_state.open_dialog   = None
        st.session_state.edit_target   = None
        st.rerun()

# ─────────────────────────────────────────────────────────
#  팝업 다이얼로그: 삭제 1차 확인 (비번 전 경고)
# ─────────────────────────────────────────────────────────
@st.dialog("⚠️ 회원 삭제 확인")
def dialog_confirm_delete(target):
    st.markdown(f"""
    <div style="text-align:center; padding: 8px 0 16px;">
        <div style="font-size:48px; margin-bottom:12px;">🚨</div>
        <div style="font-size:17px; font-weight:700; color:#1a2e4a; margin-bottom:8px;">
            정말로 삭제하시겠습니까?
        </div>
        <div style="font-size:14px; color:#6b7280; line-height:1.6;">
            <b style="color:#dc2626;">[{target['name']}]</b> 회원의 모든 정보가<br>
            영구적으로 삭제되며 복구할 수 없습니다.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # 버튼 스타일 (Streamlit 내장 .st-key-{key} 클래스 사용)
    st.markdown("""
    <style>
    .st-key-confirm_del_yes button {
        background: #ef4444 !important; color: #fff !important; border: none !important;
        font-weight: 700 !important; height: 42px !important;
    }
    .st-key-confirm_del_yes button:hover { background: #dc2626 !important; color: #fff !important; }
    .st-key-confirm_del_yes button p { color: #fff !important; }
    .st-key-confirm_del_no button {
        background: #6b7280 !important; color: #fff !important; border: none !important;
        font-weight: 700 !important; height: 42px !important;
    }
    .st-key-confirm_del_no button:hover { background: #4b5563 !important; color: #fff !important; }
    .st-key-confirm_del_no button p { color: #fff !important; }
    </style>
    """, unsafe_allow_html=True)

    cy, cn = st.columns([1, 1], gap="small")
    with cy:
        if st.button("🗑️ 삭제 진행", use_container_width=True, key="confirm_del_yes"):
            st.session_state.edit_target = target
            # 이미 세션 인증된 경우 비번 건너뛰고 바로 최종 삭제 확인으로
            if st.session_state.admin_authed:
                st.session_state.open_dialog = "delete_confirm"
            else:
                st.session_state.open_dialog = "pw_delete"
            st.rerun()
    with cn:
        if st.button("✕ 취소", use_container_width=True, key="confirm_del_no"):
            st.session_state.open_dialog   = None
            st.session_state.edit_target   = None
            st.rerun()



@st.dialog("회원 정보", width="large")
def dialog_form(existing=None):
    title = "✏️ 회원 정보 수정" if existing else "➕ 새 회원 등록"
    st.markdown(f"#### {title}")

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

    # 행2: 카페ID / 생년 / 연락처 / 거주지
    c4,c5,c6,c6b = st.columns([1,1,1,1])
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
    with c6b:
        region = st.text_input("거주지",
            value=existing["region"] if existing else "", placeholder="서울 강남구")

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

    # 행4: 휴면기간 (누적 관리) — 폭 전체 사용 (행 단위 입력이라 넓게)
    # ─────────────────────────────────────────────────────────
    # 휴면 기간 세션 초기화: 이 다이얼로그가 처음 열릴 때만 기존 값 로드
    # (다른 위젯 조작으로 인한 rerun에서는 기존 편집 상태 유지)
    target_id = existing["id"] if existing else "new"
    dorm_session_key = f"dormant_edit_list_{target_id}"
    if dorm_session_key not in st.session_state:
        if existing and existing.get("dormant_period"):
            st.session_state[dorm_session_key] = parse_dormant_periods(existing["dormant_period"])
        else:
            st.session_state[dorm_session_key] = []

    # ── 콜백 함수: 다이얼로그 안에서는 st.rerun()을 호출하면 다이얼로그가 닫혀버림
    # 콜백은 다이얼로그를 닫지 않고 세션 상태만 변경한 뒤 자연스럽게 리렌더됨
    def _add_dormant_row(key=dorm_session_key):
        st.session_state[key].append({"start": "", "end": ""})

    def _delete_dormant_row(key, idx):
        if 0 <= idx < len(st.session_state[key]):
            st.session_state[key].pop(idx)

    def _normalize_date_input(widget_key):
        """텍스트 입력의 값을 정규화된 날짜로 자동 변환"""
        v = st.session_state.get(widget_key, "")
        if v:
            st.session_state[widget_key] = normalize_date(v)

    st.markdown("**휴면 기간** <span style='font-size:11px;color:#6b7280;'>(진행중이면 자동→휴면, 모두 종료 시 자동→정회원)</span>", unsafe_allow_html=True)

    # 휴면 기간 행 스타일
    st.markdown("""
    <style>
    div.dormant-row-wrap {
        background:#fef9c3; border-radius:8px; padding:8px 12px;
        margin-bottom:6px; border-left:3px solid #ca8a04;
    }
    .st-key-add_dormant_btn button {
        background:#fef3c7 !important; color:#854d0e !important;
        border:1px dashed #ca8a04 !important; font-weight:700 !important;
    }
    .st-key-add_dormant_btn button:hover { background:#fde68a !important; }
    </style>
    """, unsafe_allow_html=True)

    dorm_list = st.session_state[dorm_session_key]

    if not dorm_list:
        st.caption("📭 등록된 휴면 기간이 없습니다. 아래 '+ 기간 추가' 버튼으로 추가하세요.")
    else:
        for i, p in enumerate(dorm_list):
            st.markdown('<div class="dormant-row-wrap">', unsafe_allow_html=True)
            rc_lbl, rc_start, rc_end, rc_status, rc_del = st.columns([0.4, 1.5, 1.5, 1, 0.5])
            with rc_lbl:
                st.markdown(f"<div style='padding-top:8px;font-weight:700;color:#854d0e;{FS}'>#{i+1}</div>", unsafe_allow_html=True)
            with rc_start:
                start_key = f"dorm_start_{target_id}_{i}"
                # session에 위젯 값이 없으면 초기값 세팅
                if start_key not in st.session_state:
                    st.session_state[start_key] = p["start"]
                st.text_input(
                    "시작일", key=start_key,
                    placeholder="YYYY-MM-DD 또는 20260101", label_visibility="collapsed",
                    on_change=_normalize_date_input, args=(start_key,)
                )
                dorm_list[i]["start"] = st.session_state[start_key].strip()
            with rc_end:
                end_key = f"dorm_end_{target_id}_{i}"
                if end_key not in st.session_state:
                    st.session_state[end_key] = p["end"]
                st.text_input(
                    "종료일", key=end_key,
                    placeholder="YYYY-MM-DD (비우면 진행중)", label_visibility="collapsed",
                    on_change=_normalize_date_input, args=(end_key,)
                )
                dorm_list[i]["end"] = st.session_state[end_key].strip()
            with rc_status:
                is_ongoing = not dorm_list[i]["end"]
                status_html = ("<span style='color:#ca8a04;font-weight:700;'>🟡 진행중</span>"
                               if is_ongoing else
                               "<span style='color:#16a34a;font-weight:700;'>✅ 종료</span>")
                st.markdown(f"<div style='padding-top:8px;{FS}'>{status_html}</div>", unsafe_allow_html=True)
            with rc_del:
                # ⚠️ 콜백 사용 — 다이얼로그 안에서 st.rerun() 호출 금지 (다이얼로그 튕김 원인)
                st.button("🗑️", key=f"dorm_del_{target_id}_{i}",
                          use_container_width=True, help="이 기간 삭제",
                          on_click=_delete_dormant_row, args=(dorm_session_key, i))
            st.markdown('</div>', unsafe_allow_html=True)

    # + 기간 추가 버튼 — 콜백 방식 (rerun 금지)
    st.button("➕ 휴면 기간 추가", use_container_width=True, key="add_dormant_btn",
              on_click=_add_dormant_row)

    # ─── 탈퇴일 (휴면 아래) ───
    ld_str_existing = ""
    if existing and existing.get("leave_date"):
        ld_str_existing = str(existing["leave_date"]).strip()
    ld_key = f"leave_date_input_{target_id}"
    if ld_key not in st.session_state:
        st.session_state[ld_key] = ld_str_existing
    st.text_input(
        "탈퇴일 (입력 시 구분 자동→탈퇴)",
        key=ld_key,
        placeholder="YYYY-MM-DD 또는 20260101 (비우면 탈퇴 해제)",
        on_change=_normalize_date_input, args=(ld_key,)
    )
    leave_date_str = st.session_state[ld_key]


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

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 버튼 색상: Streamlit 내장 .st-key-{key} 클래스 사용 (가장 안정적) ──
    # st.button(key="xxx") → 자동으로 .st-key-xxx 클래스 부여됨
    st.markdown("""
    <style>
    /* 저장 (파랑) */
    .st-key-form_save button {
        background: #2563eb !important; color: #fff !important; border: none !important;
        font-weight: 700 !important;
    }
    .st-key-form_save button:hover { background: #1d4ed8 !important; color: #fff !important; }
    .st-key-form_save button p { color: #fff !important; }
    /* 취소 (회색) */
    .st-key-form_cancel button {
        background: #6b7280 !important; color: #fff !important; border: none !important;
        font-weight: 700 !important;
    }
    .st-key-form_cancel button:hover { background: #4b5563 !important; color: #fff !important; }
    .st-key-form_cancel button p { color: #fff !important; }
    /* 삭제 (빨강) */
    .st-key-form_delete button {
        background: #ef4444 !important; color: #fff !important; border: none !important;
        font-weight: 700 !important;
    }
    .st-key-form_delete button:hover { background: #dc2626 !important; color: #fff !important; }
    .st-key-form_delete button p { color: #fff !important; }
    </style>
    """, unsafe_allow_html=True)

    if existing:
        bs, bc, bd = st.columns([1,1,1])
    else:
        bs, bc = st.columns([1,1])
        bd = None

    with bs:
        save_clicked = st.button("💾 저장", use_container_width=True, key="form_save")
    with bc:
        cancel_clicked = st.button("✕ 취소", use_container_width=True, key="form_cancel")
    delete_clicked = False
    if bd:
        with bd:
            delete_clicked = st.button("🗑️ 삭제", use_container_width=True, key="form_delete")

    # ── 다이얼로그 종료 시 휴면 관련 위젯 세션 전부 정리하는 헬퍼 ──
    def _cleanup_dormant_session():
        # 리스트
        if dorm_session_key in st.session_state:
            del st.session_state[dorm_session_key]
        # 각 행의 위젯 키들 (dorm_start_*, dorm_end_*)
        for k in list(st.session_state.keys()):
            if k.startswith(f"dorm_start_{target_id}_") or k.startswith(f"dorm_end_{target_id}_"):
                del st.session_state[k]
        # 탈퇴일 위젯
        if f"leave_date_input_{target_id}" in st.session_state:
            del st.session_state[f"leave_date_input_{target_id}"]

    if cancel_clicked:
        _cleanup_dormant_session()
        st.session_state.open_dialog    = None
        st.session_state.edit_target    = None
        st.rerun()

    if delete_clicked and existing:
        _cleanup_dormant_session()
        st.session_state.open_dialog    = "confirm_delete"
        st.session_state.edit_target    = {"type":"delete","id":existing["id"],"name":existing["name"]}
        st.rerun()

    if save_clicked:
        # ── 검증 단계 (순차적으로 모든 에러를 수집) ──
        errors = []

        # 1. 필수 필드
        if not name.strip():
            errors.append("성명은 필수입니다.")

        # 2. 생년 범위
        by = None
        if birth_year.strip():
            try:
                by = int(birth_year.strip())
                if not (1900 <= by <= date.today().year):
                    errors.append(f"생년은 1900~{date.today().year} 사이여야 합니다.")
            except ValueError:
                errors.append("생년은 4자리 숫자여야 합니다.")

        # 3. 연락처 — 자동 포맷팅 후 형식 검증
        phone_normalized = normalize_phone(phone.strip())
        if phone_normalized and not validate_phone(phone_normalized):
            errors.append("연락처 형식이 올바르지 않습니다. (예: 010-1234-5678 또는 01012345678)")

        # 4. 이메일 형식
        if email.strip() and not validate_email(email.strip()):
            errors.append("이메일 형식이 올바르지 않습니다.")

        # 5. 탈퇴일 — 정규화 후 형식 검증
        ld_str = normalize_date(leave_date_str.strip())
        if ld_str and not validate_date(ld_str):
            errors.append("탈퇴일 형식이 올바르지 않습니다. (YYYY-MM-DD)")

        # 6. 휴면 기간 검증 + 정규화 + 겹침 검사
        clean_dorm_list = []
        for i, p in enumerate(dorm_list):
            s = normalize_date((p.get("start") or "").strip())
            e = normalize_date((p.get("end") or "").strip())
            if not s and not e: continue
            if not s:
                errors.append(f"휴면 기간 #{i+1}: 시작일이 비어있습니다."); continue
            if not validate_date(s):
                errors.append(f"휴면 기간 #{i+1}: 시작일 형식 오류 (예: 20260101)"); continue
            if e and not validate_date(e):
                errors.append(f"휴면 기간 #{i+1}: 종료일 형식 오류 (예: 20260101)"); continue
            if e and s > e:
                errors.append(f"휴면 기간 #{i+1}: 종료일이 시작일보다 빠를 수 없습니다."); continue
            clean_dorm_list.append({"start": s, "end": e})

        # 12번: 시작일 오름차순 자동 정렬
        clean_dorm_list.sort(key=lambda p: p["start"])

        # 11번: 겹침 검사
        if not errors and clean_dorm_list:
            overlap_err = check_dormant_overlap(clean_dorm_list)
            if overlap_err:
                errors.append(f"휴면 기간 겹침 오류: {overlap_err}")

        dorm_str = format_dormant_periods(clean_dorm_list)

        # 7. 중복 검사
        if not errors:
            exclude_id = existing["id"] if existing else None
            dup_msg = check_duplicate(df, name, phone_normalized, cafe_id, exclude_id=exclude_id)
            if dup_msg:
                errors.append(f"⚠️ {dup_msg}")

        if errors:
            for e in errors:
                st.error(f"❗ {e}")
        else:
            # ── 카테고리 자동 결정 ──
            had_dormant = bool(dorm_str)
            has_ongoing = had_dormant and any(not p["end"] for p in clean_dorm_list)
            if ld_str:
                final_cat = "탈퇴"
            elif has_ongoing:
                final_cat = "휴면"
            elif had_dormant and cat == "휴면":
                final_cat = "정회원"
            else:
                final_cat = cat

            action_detail = (f"{'신규등록' if not existing else '수정'} → "
                             f"카테고리:{final_cat}, 연락처:{phone_normalized}")
            row_data = {
                "id":             existing["id"] if existing else next_id(df),
                "category":       final_cat,
                "name":           name.strip(),
                "cafe_id":        cafe_id.strip(),
                "birth_year":     by or "",
                "gender":         gender,
                "phone":          phone_normalized,
                "join_date":      join_date.strftime("%Y-%m-%d") if join_date else "",
                "dormant_period": dorm_str,
                "leave_date":     ld_str,
                "email":          email.strip(),
                "application":    "" if application=="—" else application,
                "region":         region.strip(),
                "memo":           memo.strip(),
                "deleted_at":     "",
            }
            with st.spinner("구글 시트에 저장 중…"):
                save_row(df, row_data, is_new=(existing is None), action_detail=action_detail)

            st.success(f"✅ {'수정' if existing else '등록'} 완료! — {final_cat} {name.strip()}")
            _cleanup_dormant_session()
            st.session_state.open_dialog    = None
            st.session_state.edit_target    = None
            st.cache_resource.clear()
            st.rerun()

# ─────────────────────────────────────────────────────────
#  헤더
# ─────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <span style="font-size:36px">🎾</span>
  <div><h1>테라클럽 회원 명부 <span style="font-size:13px;font-weight:400;opacity:.65;">(v1.06)</span></h1>
  <p>TELA CLUB Member Roster · Google Sheets 연동</p></div>
</div>""", unsafe_allow_html=True)

# 관리자 인증 상태 (타임아웃 잔여 시간 표시)
if st.session_state.admin_authed and st.session_state.auth_time:
    elapsed_min = int((datetime.now() - st.session_state.auth_time).total_seconds() / 60)
    remain_min  = SESSION_TIMEOUT_MIN - elapsed_min
    auth_col1, auth_col2 = st.columns([6, 1])
    with auth_col1:
        st.markdown(
            f"<div style='background:#d1fae5;border-left:4px solid #10b981;"
            f"padding:6px 12px;border-radius:6px;font-size:12px;color:#065f46;font-weight:600;'>"
            f"🔓 관리자 인증됨 — 잔여 {remain_min}분 (총 {SESSION_TIMEOUT_MIN}분 세션)"
            f"</div>", unsafe_allow_html=True)
    with auth_col2:
        if st.button("🔒 로그아웃", use_container_width=True, key="admin_logout"):
            st.session_state.admin_authed = False
            st.session_state.auth_time    = None
            st.rerun()

# ─────────────────────────────────────────────────────────
#  데이터 로드
# ─────────────────────────────────────────────────────────
with st.spinner("📡 구글 시트에서 데이터 불러오는 중…"):
    try:
        df = load_df(include_deleted=False)
    except Exception as e:
        st.error(f"⚠️ Google Sheets 연결 오류: {e}")
        st.stop()

# ── 알림 배지 계산 (데이터 로드 직후) ────────────────────
anniversary_members = get_this_month_birthdays(df)
long_dormant_members = get_long_dormant_members(df, months=3)

# 알림 배지 표시
notif_parts = []
if anniversary_members:
    notif_parts.append(f"🎾 이번 달 입회기념 **{len(anniversary_members)}명**")
if long_dormant_members:
    notif_parts.append(f"⚠️ 장기 휴면(3개월↑) **{len(long_dormant_members)}명** — 탈퇴 검토 필요")
if notif_parts:
    st.markdown(
        "<div style='background:#fef3c7;border-left:4px solid #f59e0b;"
        "padding:8px 14px;border-radius:8px;font-size:13px;color:#92400e;margin-bottom:8px;'>"
        + " &nbsp;|&nbsp; ".join(notif_parts) +
        "</div>", unsafe_allow_html=True)

    # 상세 보기 (expander)
    if anniversary_members or long_dormant_members:
        with st.expander("📋 알림 상세 보기", expanded=False):
            if anniversary_members:
                st.markdown("**🎾 이번 달 입회 기념일**")
                for m in anniversary_members:
                    yr = f"{m['years']}주년" if m['years'] > 0 else "첫해"
                    st.markdown(f"- {m['name']} ({m['category']}) — 입회일 {m['join_date'][:10]} ({yr})")
            if long_dormant_members:
                st.markdown("**⚠️ 장기 휴면 탈퇴 검토 대상**")
                for m in long_dormant_members:
                    st.markdown(f"- {m['name']} — 휴면 시작 {m['start']} ({m['days']}일 경과)")

# ─────────────────────────────────────────────────────────
#  다이얼로그 라우터 — 렌더링 최상단에서 처리
#  ⚠️ 중요: 다이얼로그를 띄운 직후 open_dialog 상태를 비워서
#         다음 rerun(다른 위젯 조작 등)에서 다이얼로그가 재팝업되지 않도록 함
# ─────────────────────────────────────────────────────────
od = st.session_state.open_dialog
et = st.session_state.edit_target

# 다이얼로그 호출 전에 상태를 "소비"(consume) — 한 번만 표시되도록
if od is not None:
    st.session_state.open_dialog = None

if od == "add":
    dialog_form(existing=None)

elif od == "edit" and et and st.session_state.admin_authed:
    existing_row = None
    if not df.empty:
        rows = df[df["id"] == et["id"]]
        if not rows.empty:
            existing_row = rows.iloc[0].to_dict()
    dialog_form(existing=existing_row)

elif od == "confirm_delete" and et:
    dialog_confirm_delete(et)

elif od == "delete_confirm" and et and st.session_state.admin_authed:
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
# 총 회원수 = 탈퇴 제외
active_df = df[df["category"] != "탈퇴"] if not df.empty else df
tm = len(active_df[active_df["gender"]=="남"]) if not active_df.empty else 0
tf = len(active_df[active_df["gender"]=="여"]) if not active_df.empty else 0
sc[-1].markdown(f'<div class="stat-card total"><div class="stat-label white">총 회원수</div>'
                f'<div class="stat-num white">{tm+tf}</div><div class="stat-sub white">남 {tm} · 여 {tf}</div></div>',
                unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
#  툴바
# ─────────────────────────────────────────────────────────
c_s, c_sb, c_dl, c_add = st.columns([4, 0.8, 1.0, 1.2])
with c_s:
    search_q = st.text_input("검색", value=st.session_state.search_q,
        placeholder="이름 / 카페ID / 연락처 입력 후 검색 버튼 클릭",
        label_visibility="collapsed")
    st.session_state.search_q = search_q
with c_sb:
    if st.button("🔍 검색", use_container_width=True):
        st.session_state.search_active = search_q.strip()
        st.rerun()
with c_dl:
    # CSV 백업 다운로드 (BOM 추가로 엑셀 한글 깨짐 방지)
    csv_data = df.to_csv(index=False).encode("utf-8-sig") if not df.empty else "".encode("utf-8-sig")
    today_str = date.today().strftime("%Y%m%d")
    st.download_button(
        "📥 백업",
        data=csv_data,
        file_name=f"tela_club_backup_{today_str}.csv",
        mime="text/csv",
        use_container_width=True,
        help="현재 명부 전체를 CSV로 다운로드 (엑셀 호환)"
    )
with c_add:
    if st.button("＋ 회원 등록", type="primary", use_container_width=True):
        st.session_state.open_dialog  = "add"
        st.session_state.edit_target  = None
        st.rerun()

if not search_q.strip():
    st.session_state.search_active = ""

FILTER_OPTIONS = ["전체","운영진","정회원","휴면","탈퇴"]
if st.session_state.filter_cat not in FILTER_OPTIONS:
    st.session_state.filter_cat = "전체"
filter_cat = st.radio("필터", FILTER_OPTIONS,
    index=FILTER_OPTIONS.index(st.session_state.filter_cat),
    horizontal=True, label_visibility="collapsed",
    key="filter_radio")

# ── 카테고리 변경 감지: 필터가 바뀌면 정렬 위젯도 자동 초기화 ──
# 사용자 의도에 따라:
#  - 정회원: 입회일순 (오래된 회원이 위)
#  - 휴면: 최근 휴면일순 (최근 휴면 시작이 위)
#  - 탈퇴: 최근 탈퇴일순 (최근 탈퇴가 위)
#  - 전체/운영진: 구분순 (기존 기본값)
SORT_DEFAULT_BY_FILTER = {
    "전체":   "구분순",
    "운영진": "구분순",
    "정회원": "입회일순(빠른)",
    "휴면":   "휴면 시작일순(최근)",
    "탈퇴":   "탈퇴일순(최근)",
}
# 필터가 바뀌면 sort_select의 세션값을 해당 기본값으로 교체
if st.session_state.filter_cat != filter_cat:
    st.session_state["sort_select"] = SORT_DEFAULT_BY_FILTER[filter_cat]
    st.session_state.filter_cat = filter_cat

SORT_OPTIONS = [
    "No.순", "구분순", "이름순",
    "입회일순(빠른)", "입회일순(최근)",
    "휴면 시작일순(최근)",
    "탈퇴일순(최근)",
    "생년순", "성별순"
]
# 세션에 sort_select가 없거나 옵션에 없으면 현재 필터의 기본값으로
if "sort_select" not in st.session_state or st.session_state.get("sort_select") not in SORT_OPTIONS:
    st.session_state["sort_select"] = SORT_DEFAULT_BY_FILTER.get(filter_cat, "구분순")

sc2,_ = st.columns([1,5])
with sc2:
    sort_by = st.selectbox("정렬", SORT_OPTIONS,
        key="sort_select",
        label_visibility="collapsed")

# 휴지통 토글 (관리자 인증 시에만 표시)
if st.session_state.admin_authed:
    trash_col, _ = st.columns([2, 8])
    with trash_col:
        trash_label = "📦 휴지통 닫기" if st.session_state.show_trash else "🗑️ 휴지통 보기"
        if st.button(trash_label, use_container_width=True, key="toggle_trash"):
            st.session_state.show_trash = not st.session_state.show_trash
            st.rerun()

# ── 휴지통 뷰 ─────────────────────────────────────────────
if st.session_state.show_trash and st.session_state.admin_authed:
    st.markdown("---")
    st.markdown("### 🗑️ 휴지통")
    st.caption(f"삭제 후 {TRASH_DAYS}일이 지난 항목은 자동으로 영구 삭제됩니다.")
    try:
        df_all     = load_df(include_deleted=True)
        df_trash   = df_all[df_all["deleted_at"].astype(str).str.strip() != ""].copy()
        today_dt   = datetime.now()
        # 90일 초과 자동 영구 삭제
        for _, trow in df_trash.iterrows():
            try:
                del_dt = datetime.strptime(str(trow["deleted_at"])[:19], "%Y-%m-%d %H:%M:%S")
                if (today_dt - del_dt).days >= TRASH_DAYS:
                    hard_delete_row(trow["id"], trow["name"])
                    st.cache_resource.clear()
            except Exception:
                pass
        # 재로드 후 표시
        df_all   = load_df(include_deleted=True)
        df_trash = df_all[df_all["deleted_at"].astype(str).str.strip() != ""].copy()
    except Exception as e:
        df_trash = pd.DataFrame()
        st.warning(f"휴지통 로드 실패: {e}")

    if df_trash.empty:
        st.info("휴지통이 비어있습니다.")
    else:
        for _, trow in df_trash.iterrows():
            del_dt_str = str(trow.get("deleted_at",""))[:16]
            try:
                del_dt   = datetime.strptime(del_dt_str[:19], "%Y-%m-%d %H:%M:%S")
                days_ago = (today_dt - del_dt).days
                remain   = TRASH_DAYS - days_ago
            except Exception:
                remain = TRASH_DAYS
            tc1, tc2, tc3, tc4 = st.columns([3, 2, 2, 2])
            tc1.markdown(f"**{trow['name']}** ({trow['category']})")
            tc2.caption(f"삭제일: {del_dt_str}")
            tc3.caption(f"영구삭제까지 {remain}일")
            with tc4:
                rcol1, rcol2 = st.columns(2)
                if rcol1.button("↩️ 복구", key=f"restore_{trow['id']}", use_container_width=True):
                    restore_row(trow["id"], trow["name"])
                    st.cache_resource.clear()
                    st.rerun()
                if rcol2.button("💀 영구삭제", key=f"hardel_{trow['id']}", use_container_width=True):
                    hard_delete_row(trow["id"], trow["name"])
                    st.cache_resource.clear()
                    st.rerun()
    st.markdown("---")

# ─────────────────────────────────────────────────────────
#  필터링 & 정렬
# ─────────────────────────────────────────────────────────
def _latest_dormant_start(s):
    """휴면 기간 문자열에서 가장 최근의 시작일을 반환 (정렬용)"""
    periods = parse_dormant_periods(s) if s else []
    if not periods: return ""
    # 시작일 기준 최대값 반환
    return max((p["start"] for p in periods if p.get("start")), default="")

def apply_filters(data):
    if data.empty: return data
    if filter_cat == "운영진":
        data = data[data["category"].isin(OFFICER_CATS)]
    elif filter_cat == "탈퇴":
        data = data[data["category"] == "탈퇴"]
    elif filter_cat == "전체":
        data = data[data["category"] != "탈퇴"]   # 전체에서 탈퇴 제외
    else:
        data = data[data["category"] == filter_cat]
    q = st.session_state.search_active.lower()
    if q:
        mask = (data["name"].str.lower().str.contains(q,na=False) |
                data["cafe_id"].astype(str).str.lower().str.contains(q,na=False) |
                data["phone"].astype(str).str.contains(q,na=False))
        data = data[mask]

    if sort_by == "구분순":
        data = data.copy()
        data["_o"] = data["category"].map(CAT_ORDER).fillna(99)
        data = data.sort_values("_o").drop(columns="_o")
    elif sort_by == "이름순":
        data = data.sort_values("name")
    elif sort_by == "입회일순(빠른)":
        # 오래된 입회일이 위 (오름차순). 빈 값은 맨 뒤로.
        data = data.sort_values("join_date", ascending=True, na_position="last")
    elif sort_by == "입회일순(최근)":
        data = data.sort_values("join_date", ascending=False, na_position="last")
    elif sort_by == "휴면 시작일순(최근)":
        data = data.copy()
        data["_dorm_latest"] = data["dormant_period"].apply(_latest_dormant_start)
        data = data.sort_values("_dorm_latest", ascending=False, na_position="last").drop(columns="_dorm_latest")
    elif sort_by == "탈퇴일순(최근)":
        data = data.sort_values("leave_date", ascending=False, na_position="last")
    elif sort_by == "생년순":
        data = data.sort_values("birth_year")
    elif sort_by == "성별순":
        data = data.sort_values("gender")
    else:  # No.순
        data = data.sort_values("id")
    return data.reset_index(drop=True)

view_df = apply_filters(df.copy())
st.caption(f"검색 결과 **{len(view_df)}명** / 전체 {len(df)}명")

# ─────────────────────────────────────────────────────────
#  회원 목록 테이블
# ─────────────────────────────────────────────────────────
CW  = [0.28, 0.65, 0.82, 0.85, 0.46, 0.38, 0.95, 0.72, 0.75, 1.0, 0.72, 0.68, 1.1, 0.6]
HDR = ["No.","구분","성명","카페ID","생년","성별","연락처","거주지","입회일","휴면기간","탈퇴일","입회신청서","메모","관리"]

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
        rc[7].markdown(cell(row.get('region','') or '—',"#374151"), unsafe_allow_html=True)
        rc[8].markdown(cell(row.get('join_date','') or '—',"#6b7280"), unsafe_allow_html=True)
        # 휴면 기간 요약 표시
        # - 1건 종료: 시작~끝 그대로
        # - 진행중: 최신 진행중 기간의 시작일 표시 (사용자 요청)
        # - 여러 건 모두 종료: N건 종료
        dorm_raw = str(row.get('dormant_period','') or '').strip()
        if dorm_raw:
            dorm_list_disp = parse_dormant_periods(dorm_raw)
            dorm_cnt  = len(dorm_list_disp)
            ongoing_periods = [p for p in dorm_list_disp if not p["end"]]
            if ongoing_periods:
                # 진행중인 기간이 있으면 그 시작일 표시 (최신 = 마지막)
                latest_ongoing = ongoing_periods[-1]
                dorm_disp = f"{latest_ongoing['start']}~"
            elif dorm_cnt == 1:
                # 단일 종료된 기간
                dorm_disp = f"{dorm_list_disp[0]['start']}~{dorm_list_disp[0]['end']}"
            else:
                # 여러 건 모두 종료
                last = dorm_list_disp[-1]
                dorm_disp = f"{last['start']}~{last['end']} 외 {dorm_cnt-1}건"
        else:
            dorm_disp = "—"
        rc[9].markdown(f"<div style='padding:7px 0;{FS};color:#ca8a04' title='{dorm_raw}'>{dorm_disp}</div>", unsafe_allow_html=True)
        rc[10].markdown(cell(row.get('leave_date','') or '—',"#dc2626"), unsafe_allow_html=True)
        rc[11].markdown(f"<div style='padding:5px 0'><span style='{FS};font-weight:700;color:{app_color}'>{app_val}</span></div>", unsafe_allow_html=True)
        rc[12].markdown(f"<div style='padding:7px 0;{FS};color:#4b5563' title='{memo_txt}'>{memo_disp}</div>", unsafe_allow_html=True)

        with rc[13]:
            st.markdown("<div class='edit-col'>", unsafe_allow_html=True)
            if st.button("✏️ 수정", key=f"edit_{row['id']}", use_container_width=True):
                target = {"type":"edit","id":int(row["id"]),"name":row["name"]}
                st.session_state.edit_target = target
                # 이미 세션 인증된 경우 비번 건너뛰고 바로 수정 화면으로
                if st.session_state.admin_authed:
                    st.session_state.open_dialog = "edit"
                else:
                    st.session_state.open_dialog = "pw_edit"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='border-bottom:1px solid #f1f5f9'></div>", unsafe_allow_html=True)
