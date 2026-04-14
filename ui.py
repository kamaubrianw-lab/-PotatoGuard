"""
ui.py — Final Production Frontend
===================================

"""

from __future__ import annotations

import os
import requests
import streamlit as st
from PIL import Image
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. Config & Theme Mapping
# ---------------------------------------------------------------------------
API_BASE = os.getenv("API_BASE_URL", "https://potatoguard-1.onrender.com/")

CLASS_DISPLAY = {
    "Potato___Early_blight": "🍂 Early Blight",
    "Potato___Late_blight" : "🌧️ Late Blight",
    "Potato___healthy"     : "✅ Healthy",
}
CLASS_COLOUR = {
    "Potato___Early_blight": "#8B6914",
    "Potato___Late_blight" : "#7A1F1F",
    "Potato___healthy"     : "#4F7942",
}
SEVERITY_TAG = {
    "Potato___Early_blight": ("Moderate Risk", "#8B6914", "#FFF3CD"),
    "Potato___Late_blight" : ("High Risk ⚠️",  "#7A1F1F", "#FDECEA"),
    "Potato___healthy"     : ("No Disease",    "#4F7942", "#EAF4E8"),
}

# ---------------------------------------------------------------------------
# 2. Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PotatoGuard AI",
    page_icon="🥔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# 3. Organic Agricultural CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #FDF6E3;
    color: #2C2C1E;
}
.stApp { background-color: #FDF6E3; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #4F7942 0%, #3A5C30 100%);
}
[data-testid="stSidebar"] * { color: #F3E5AB !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.15) !important;
    border: 1px solid rgba(243,229,171,0.4) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(243,229,171,0.2) !important;
    color: #F3E5AB !important;
    border: 1px solid rgba(243,229,171,0.35) !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(243,229,171,0.35) !important;
}

/* Hero Text */
.pg-hero {
    font-family: 'Lora', serif;
    font-size: 3.2rem;
    color: #4F7942;
    font-weight: 600;
    margin-bottom: 0.1rem;
    line-height: 1.15;
}
.pg-sub {
    font-size: 0.95rem;
    color: #8B6914;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-bottom: 2rem;
}

/* Cards */
.organic-card {
    background: #FFFDF5;
    border: 1px solid #E8D9A0;
    border-radius: 20px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 15px rgba(79,121,66,0.1);
}
.metric-card {
    background: #FFFDF5;
    border: 1px solid #E8D9A0;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    height: 100%;
    box-shadow: 0 2px 8px rgba(139,105,20,0.08);
}

/* Advice box */
.advice-box {
    background: #F7F3E3;
    border-left: 5px solid #4F7942;
    padding: 1.5rem;
    border-radius: 0 15px 15px 0;
    line-height: 1.75;
    font-size: 0.9rem;
    max-height: 350px;
    overflow-y: auto;
    white-space: pre-wrap;
}
.gemini-label {
    font-size: 0.75rem;
    color: #4F7942;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
    display: block;
}
.conf-text {
    font-size: 1.2rem;
    font-weight: 700;
    margin-bottom: 10px;
}
.disease-badge {
    display: inline-block;
    padding: 0.3rem 0.9rem;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.82rem;
}

/* Buttons */
.stButton > button {
    background: #4F7942 !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(79,121,66,0.25) !important;
    transition: background 0.15s, transform 0.1s !important;
}
.stButton > button:hover {
    background: #3A5C30 !important;
    transform: translateY(-1px) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #EDE8D0;
    border-radius: 14px;
    padding: 5px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    color: #8B6914;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: #4F7942 !important;
    color: white !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #4F7942, #7AB36A);
    border-radius: 6px;
}

/* File uploader */
[data-testid="stFileUploader"] {
    border: 2px dashed #C8B97A !important;
    border-radius: 16px !important;
    background: #FFFDF5 !important;
}

hr { border-color: #E8D9A0; }
.stAlert { border-radius: 12px !important; }
.stDataFrame { border-radius: 12px !important; overflow: hidden !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 4. Global Session State
# ---------------------------------------------------------------------------
for key, val in {
    "token"            : None,
    "email"            : None,
    "role"             : None,
    "prediction"       : None,
    "page"             : "home",
    "delete_confirm_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------------------------
# 5. API Helpers — unified call with 401 interceptor
# ---------------------------------------------------------------------------
def _clear_session() -> None:
    """Wipe all auth state and return user to home."""
    for k in ("token", "email", "role", "prediction", "delete_confirm_id"):
        st.session_state[k] = None
    st.session_state.page = "home"


def api_call(method: str, endpoint: str, **kwargs):
    """
    Unified HTTP helper.

    auth=True   — attach Bearer token, intercept 401 as session expiry.
    public=True — skip 401 intercept (used for login/register so that
                  wrong-credential 401s show as errors, not session expiry).
    """
    use_auth  = kwargs.pop("auth",   False)
    is_public = kwargs.pop("public", False)

    # Guard: if auth required but no token, intercept before the request
    if use_auth and not st.session_state.get("token"):
        _clear_session()
        st.warning("⚠️ Your session has expired. Please log in again.")
        st.stop()

    headers = {}
    if use_auth:
        headers["Authorization"] = f"Bearer {st.session_state.token}"

    # Merge any caller-supplied headers
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))

    try:
        resp = requests.request(
            method,
            f"{API_BASE}{endpoint}",
            headers=headers,
            timeout=60,
            **kwargs,
        )

        # 401 on a PROTECTED endpoint — session expired or token invalid.
        # Do NOT intercept 401 for public endpoints (login returns 401
        # on wrong credentials — that is NOT a session expiry).
        if resp.status_code == 401 and not is_public:
            _clear_session()
            st.warning(
                "⚠️ Your session has expired or is invalid. "
                "Please log in again using the sidebar."
            )
            st.stop()

        # Other errors — show message, return None
        if resp.status_code not in (200, 201, 204):
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            st.error(f"🚫 Backend Error ({resp.status_code}): {detail}")
            return None

        return resp

    except requests.exceptions.ConnectionError:
        st.error("📡 Cannot reach the API. Is `uvicorn app.main:app` running?")
        return None
    except Exception as exc:
        st.error(f"📡 Unexpected error: {exc}")
        return None

# ---------------------------------------------------------------------------
# 6. Sidebar
# ---------------------------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<p style="font-family:Lora,serif;font-size:2rem;'
            'color:#F3E5AB;font-weight:600;margin-bottom:4px">'
            '🥔 PotatoGuard</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p style="font-size:0.72rem;color:#C8D8A0;letter-spacing:0.1em;'
            'text-transform:uppercase;margin-top:0">AI Disease Detection</p>',
            unsafe_allow_html=True,
        )
        st.divider()

        if st.session_state.token:
            _sidebar_logged_in()
        else:
            _sidebar_auth()


def _sidebar_logged_in():
    icon = "🛡️" if st.session_state.role == "admin" else "🌿"
    st.markdown(
        f'<div style="background:rgba(243,229,171,0.15);border:1px solid '
        f'rgba(243,229,171,0.3);border-radius:12px;padding:12px 14px;'
        f'margin-bottom:14px">'
        f'<div style="font-size:1.3rem">{icon}</div>'
        f'<div style="font-weight:600;font-size:0.82rem;word-break:break-all;'
        f'margin-top:5px;color:#F3E5AB">{st.session_state.email}</div>'
        f'<div style="font-size:0.7rem;text-transform:uppercase;'
        f'letter-spacing:0.06em;color:#C8D8A0;margin-top:2px">'
        f'{st.session_state.role}</div></div>',
        unsafe_allow_html=True,
    )

    # Navigation
    if st.button("🏠 Home", width="stretch"):
        st.session_state.page = "home"
        st.session_state.prediction = None
        st.rerun()

    if st.session_state.role == "user":
        if st.button("🔬 New Scan", width="stretch"):
            st.session_state.page = "scan"
            st.rerun()
        if st.button("📋 My History", width="stretch"):
            st.session_state.page = "history"
            st.rerun()
    else:
        if st.button("📊 System Analytics", width="stretch"):
            st.session_state.page = "analytics"
            st.rerun()
        if st.button("👥 Manage Users", width="stretch"):
            st.session_state.page = "users"
            st.rerun()

    st.divider()
    if st.button("🚪 Logout", width="stretch"):
        _clear_session()
        st.rerun()


def _sidebar_auth():
    """
    Login uses public=True so wrong-password 401 shows as
    "Incorrect email or password" instead of "session expired".
    Tabs renamed: "Sign In" / "Register" to avoid confusion with
    the Sign In button inside the tab.
    """
    t1, t2 = st.tabs(["Sign In", "Register"])

    with t1:
        st.markdown(
            '<p style="font-size:0.78rem;color:#C8D8A0;margin-bottom:4px">' 
            'Enter your email and password below.</p>',
            unsafe_allow_html=True,
        )
        email    = st.text_input("Email address",
                                 placeholder="you@example.com",
                                 key="login_email")
        password = st.text_input("Password", type="password",
                                 key="login_password")
        if st.button("🔑 Login", width="stretch", key="signin_btn"):
            if not email or not password:
                st.warning("Please enter your email and password.")
            else:
                # public=True prevents wrong-password 401 from
                # triggering the session-expired interceptor
                r = api_call(
                    "POST", "/auth/login",
                    data={"username": email.strip().lower(),
                          "password": password},
                    public=True,
                )
                if r:
                    d = r.json()
                    st.session_state.update({
                        "token": d["access_token"],
                        "email": d["email"],
                        "role" : d["role"],
                        "page" : "home",
                    })
                    st.rerun()

    with t2:
        st.markdown(
            '<p style="font-size:0.78rem;color:#C8D8A0;margin-bottom:4px">' 
            'Create a new account to start scanning.</p>',
            unsafe_allow_html=True,
        )
        reg_email = st.text_input("Email address",
                                  placeholder="you@example.com",
                                  key="reg_email")
        reg_pass  = st.text_input("Password (min 6 chars)",
                                  type="password", key="reg_pass")
        if st.button("Create Account", width="stretch", key="register_btn"):
            if not reg_email or not reg_pass:
                st.warning("Please fill in all fields.")
            else:
                r = api_call(
                    "POST", "/auth/register",
                    json={"email": reg_email.strip().lower(),
                          "password": reg_pass},
                    public=True,
                )
                if r:
                    st.success("✅ Account created! Switch to Sign In tab to log in.")

# ---------------------------------------------------------------------------
# 7. Home
# ---------------------------------------------------------------------------
def render_home():
    st.markdown('<h1 class="pg-hero">Potato Leaf<br>Disease Detection</h1>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="pg-sub">'
        'EfficientNetB0 · INT8 Quantized · Expert Agricultural Advisory'
        '</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    features = [
        ("🔬", "AI Diagnosis",
         "Instant classification using our optimized EfficientNetB0 model."),
        ("💊", "Expert Advisory",
         "Tailored treatment plans with specific fungicide recommendations."),
    ]
    for col, (icon, title, desc) in zip([c1, c2], features):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div style="font-size:3.5rem;margin-bottom:10px">{icon}</div>'
                f'<h2 style="font-family:Lora,serif;color:#4F7942">{title}</h2>'
                f'<p style="color:#8B6914;font-size:1rem;line-height:1.5">'
                f'{desc}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.token:
        st.markdown("---")
        st.markdown("### What would you like to do?")
        if st.session_state.role == "user":
            col_a, col_b, _ = st.columns([1, 1, 2])
            with col_a:
                if st.button("🔬 Start New Scan", width="stretch"):
                    st.session_state.page = "scan"
                    st.rerun()
            with col_b:
                if st.button("📋 View My History", width="stretch"):
                    st.session_state.page = "history"
                    st.rerun()
        else:
            col_a, col_b, _ = st.columns([1, 1, 2])
            with col_a:
                if st.button("📊 View Analytics", width="stretch"):
                    st.session_state.page = "analytics"
                    st.rerun()
            with col_b:
                if st.button("👥 Manage Users", width="stretch"):
                    st.session_state.page = "users"
                    st.rerun()
    else:
        st.info("👈 Please login or register in the sidebar to begin.")

# ---------------------------------------------------------------------------
# 8. Scan
# ---------------------------------------------------------------------------
def render_scan():
    st.markdown(
        '<h2 style="font-family:Lora,serif;color:#4F7942">Leaf Scanner</h2>',
        unsafe_allow_html=True,
    )
    col_left, col_right = st.columns([1, 1.2], gap="large")

    with col_left:
        st.markdown('<div class="organic-card">', unsafe_allow_html=True)
        up = st.file_uploader(
            "Upload Image",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )
        if up:
            st.image(up, caption="Source Image",  width="stretch")

            if st.button("🚀 Run Diagnosis", width="stretch"):
                # st.status for live inference progress
                with st.status("🌿 Analysing leaf...", expanded=True) as status:
                    st.write("📤 Uploading image to server...")
                    up.seek(0)
                    files = {"file": (up.name, up.read(), up.type)}

                    st.write("🔬 Running TFLite model inference...")
                    r = api_call("POST", "/predict", files=files, auth=True)

                    if r:
                        st.write("💊 Retrieving expert advisory...")
                        st.session_state.prediction = r.json()
                        status.update(
                            label="✅ Diagnosis complete!",
                            state="complete",
                            expanded=False,
                        )
                        st.rerun()
                    else:
                        status.update(
                            label="❌ Diagnosis failed",
                            state="error",
                            expanded=False,
                        )

        st.markdown('</div>', unsafe_allow_html=True)
        # FIX: closing div is inside col_left block (correct indentation)

    with col_right:
        if st.session_state.prediction:
            p      = st.session_state.prediction
            cls    = p["disease_type"]
            conf   = p["confidence_score"]
            advice = p.get("llm_advice", "")
            color  = CLASS_COLOUR.get(cls, "#4F7942")
            severity, sev_col, sev_bg = SEVERITY_TAG.get(
                cls, ("Unknown", "#8B6914", "#FFF3CD")
            )

            st.markdown(
                f'<div class="organic-card">'
                f'<p style="color:#8B6914;font-weight:600;text-transform:uppercase;'
                f'font-size:0.78rem;margin-bottom:5px">AI Diagnosis Result</p>'
                f'<h1 style="color:{color};margin-top:0;font-family:Lora,serif;">'
                f'{CLASS_DISPLAY.get(cls, cls)}</h1>'
                f'<div class="conf-text" style="color:{color}">'
                f'Confidence: {conf:.1%}</div>'
                f'<span class="disease-badge" style="background:{sev_bg};'
                f'color:{sev_col};border:1px solid {sev_col}40">'
                f'{severity}</span></div>',
                unsafe_allow_html=True,
            )

            st.progress(conf)

            st.markdown(
                f'<div style="margin-top:20px">'
                f'<span class="gemini-label">✨ Expert Advisory</span>'
                f'<div class="advice-box">'
                f'{advice or "No advisory available."}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="organic-card" style="text-align:center;padding:3rem 1rem">'
                '<div style="font-size:4rem;margin-bottom:1rem">🌿</div>'
                '<div style="color:#8B6914;font-size:0.92rem;line-height:1.6">'
                'Upload a leaf image and click<br><b>Run Diagnosis</b>'
                ' to see results here.</div></div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# 9. History
# ---------------------------------------------------------------------------
def render_history():
    st.markdown(
        '<h2 style="font-family:Lora,serif;color:#4F7942">My Prediction History</h2>',
        unsafe_allow_html=True,
    )
    r = api_call("GET", "/history", auth=True)
    if not r:
        return

    scans = r.json()
    if not scans:
        st.info("No scans yet — go to New Scan to get started.")
        if st.button("🔬 Go to New Scan", width="content"):
            st.session_state.page = "scan"
            st.rerun()
        return

    # Backend already returns newest first — do NOT reverse
    st.caption(f"{len(scans)} scan(s) on record")
    for s in scans:
        disease = s["disease_type"]
        display = CLASS_DISPLAY.get(disease, disease)
        conf    = s["confidence_score"]
        _, sev_col, sev_bg = SEVERITY_TAG.get(disease, ("", "#8B6914", "#FFF3CD"))
        try:
            ts = datetime.fromisoformat(
                s["timestamp"].replace("Z", "+00:00")
            ).strftime("%d %b %Y  %H:%M UTC")
        except ValueError:
            ts = s["timestamp"]

        with st.expander(f"📅 {ts} — {display}  ·  {conf:.1%}"):
            st.markdown(
                f'<span class="disease-badge" style="background:{sev_bg};'
                f'color:{sev_col};border:1px solid {sev_col}40">'
                f'{display}</span>',
                unsafe_allow_html=True,
            )
            st.write(f"**Certainty:** {conf:.1%}")
            st.progress(conf)
            st.markdown(
                f'<div class="advice-box">'
                f'{s.get("llm_advice") or "_No advice recorded._"}'
                f'</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# 10. Admin Analytics
# ---------------------------------------------------------------------------
def render_analytics():
    import pandas as pd

    st.markdown(
        '<h2 style="font-family:Lora,serif;color:#4F7942">'
        'Global System Analytics</h2>',
        unsafe_allow_html=True,
    )
    r = api_call("GET", "/admin/stats", auth=True)
    if not r:
        return

    d     = r.json()
    dist  = d["disease_distribution"]
    total = sum(dist.values())

    c1, c2, c3 = st.columns(3)
    healthy_pct = (
        f'{dist.get("Potato___healthy", 0) / total * 100:.0f}%'
        if total else "0%"
    )
    for col, (val, label, icon) in zip([c1, c2, c3], [
        (d["total_scans"], "Global Scans",    "🔬"),
        (d["total_users"], "Total Users",     "👤"),
        (healthy_pct,      "Healthy Scans",   "✅"),
    ]):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div style="font-size:2rem;margin-bottom:6px">{icon}</div>'
                f'<div style="font-family:Lora,serif;font-size:2.4rem;'
                f'color:#4F7942;font-weight:600">{val}</div>'
                f'<div style="font-size:0.78rem;color:#8B6914;'
                f'text-transform:uppercase;letter-spacing:0.06em">'
                f'{label}</div></div>',
                unsafe_allow_html=True,
            )

    if dist:
        st.markdown("---")
        st.markdown("### 🦠 Disease Distribution")
        st.bar_chart(
            pd.Series({
                CLASS_DISPLAY.get(k, k): v for k, v in dist.items()
            })
        )

# ---------------------------------------------------------------------------
# 11. Admin User Management — with confirmation dialog
# ---------------------------------------------------------------------------
def render_users():
    st.markdown(
        '<h2 style="font-family:Lora,serif;color:#4F7942">User Management</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#8B6914;font-size:0.85rem;margin-top:-8px">'
        'Delete a user to permanently remove them and all their scan records.'
        '</p>',
        unsafe_allow_html=True,
    )

    r = api_call("GET", "/admin/users", auth=True)
    if not r:
        return

    users = r.json()
    if not users:
        st.info("No users registered yet.")
        return

    st.caption(f"Total: {len(users)} user(s)")

    # Confirmation dialog
    if st.session_state.delete_confirm_id is not None:
        target = next(
            (u for u in users
             if u["id"] == st.session_state.delete_confirm_id), None
        )
        if target:
            st.warning(
                f"⚠️ Permanently delete **{target['email']}** and all "
                f"their scan records? This cannot be undone."
            )
            col_yes, col_no, _ = st.columns([1, 1, 4])
            with col_yes:
                if st.button("✅ Yes, Delete", width="stretch"):
                    dr = api_call(
                        "DELETE",
                        f"/admin/users/{st.session_state.delete_confirm_id}",
                        auth=True,
                    )
                    if dr is not None:
                        st.success(f"User {target['email']} deleted.")
                        st.session_state.delete_confirm_id = None
                        st.rerun()
            with col_no:
                if st.button("❌ Cancel", width="stretch"):
                    st.session_state.delete_confirm_id = None
                    st.rerun()
            st.divider()

    # User rows
    for u in users:
        is_admin = u["role"] == "admin"
        try:
            joined = datetime.fromisoformat(
                u["created_at"].replace("Z", "+00:00")
            ).strftime("%d %b %Y")
        except ValueError:
            joined = u["created_at"]

        c1, c2, c3, c4 = st.columns([3, 1, 1.5, 1.2])

        with c1:
            st.markdown(
                f'<div style="padding:8px 0">'
                f'<div style="font-weight:500;color:#2C3E1E;font-size:0.9rem">'
                f'📧 {u["email"]}</div>'
                f'<div style="font-size:0.73rem;color:#8B6914">'
                f'ID: {u["id"]}</div></div>',
                unsafe_allow_html=True,
            )
        with c2:
            badge_col = "#4F7942" if is_admin else "#8B6914"
            badge_bg  = "#EAF4E8" if is_admin else "#FFF3CD"
            st.markdown(
                f'<div style="padding:8px 0">'
                f'<span class="disease-badge" style="background:{badge_bg};'
                f'color:{badge_col};border:1px solid {badge_col}40;'
                f'font-size:0.73rem">'
                f'{"🛡️ Admin" if is_admin else "🌿 User"}'
                f'</span></div>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<div style="padding:8px 0;color:#8B6914;font-size:0.82rem">'
                f'📅 {joined}</div>',
                unsafe_allow_html=True,
            )
        with c4:
            if not is_admin:
                if st.button("🗑️ Remove", key=f"u_{u['id']}",
                             width="stretch"):
                    st.session_state.delete_confirm_id = u["id"]
                    st.rerun()
            else:
                st.markdown(
                    '<div style="padding:8px 0;color:#C8C8C8;'
                    'font-size:0.8rem">Protected</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

# ---------------------------------------------------------------------------
# 12. Router
# ---------------------------------------------------------------------------
def main():
    render_sidebar()
    page = st.session_state.get("page", "home")

    if page == "home":
        render_home()
    elif page == "scan":
        if st.session_state.role == "user":
            render_scan()
        else:
            st.session_state.page = "home"
            render_home()
    elif page == "history":
        if st.session_state.role == "user":
            render_history()
        else:
            st.session_state.page = "home"
            render_home()
    elif page == "analytics":
        if st.session_state.role == "admin":
            render_analytics()
        else:
            st.session_state.page = "home"
            render_home()
    elif page == "users":
        if st.session_state.role == "admin":
            render_users()
        else:
            st.session_state.page = "home"
            render_home()
    else:
        st.session_state.page = "home"
        render_home()


if __name__ == "__main__":
    main()