"""
HAL — Heuristically Programmed Algorithmic Layer
Christos Iatropoulos | Ashlar Insurance
Railway Edition — HAL is the brain, everything else is a tool.
"""

import streamlit as st
import json
import re
import base64
import time as _time
from datetime import datetime

# ── HAL Brain — universal file analysis + ChatGPT second opinion ─────────────
from hal_brain import process_uploads, second_opinion

# ── Rate tables ──────────────────────────────────────────────────────────────
try:
    from rate_tables import (
        MORGAN_PRICE_2025, APRIL_2025, IMG_EUROPE_2025,
        RATE_PLANS, CARRIER_BROCHURES,
        lookup_premium, get_brochure_info, _mp_band, _apr_band
    )
    RATES_LOADED = True
except ImportError:
    RATES_LOADED = False

# ── Extraction + Analysis ────────────────────────────────────────────────────
try:
    from extraction import compute_score, extract_insurance_data
    from analysis import generate_recommendation_analysis
    EXTRACT_OK = True
except ImportError:
    EXTRACT_OK = False

# ── Google Sheets ────────────────────────────────────────────────────────────
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False

# ── PPTX ─────────────────────────────────────────────────────────────────────
try:
    from pptx_builder import build_comparison_pptx
    PPTX_OK = True
except ImportError:
    PPTX_OK = False


# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="HAL · Ashlar Insurance",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════════════════════
# STYLING
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* Ashlar brand */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.hal-logo { text-align: center; padding: 16px 0 8px; }
.hal-title { font-size: 36px; font-weight: 800; letter-spacing: 6px;
    background: linear-gradient(135deg, #C9A96E 0%, #E8D5B0 50%, #C9A96E 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hal-sub { font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
    color: #7A6A5A; margin-top: -4px; }

/* Section headers */
.section-header { font-size: 11px; font-weight: 600; letter-spacing: 2px;
    text-transform: uppercase; color: #7A6A5A;
    border-bottom: 1px solid #E8E0D5; padding-bottom: 8px; margin-bottom: 16px; }

/* HAL response */
.hal-response { background: white; border-left: 3px solid #C9A96E;
    padding: 16px 20px; border-radius: 0 10px 10px 0; margin-top: 8px; }

/* Second opinion */
.gpt-opinion { background: #F0F7FF; border-left: 3px solid #3B82F6;
    padding: 14px 18px; border-radius: 0 10px 10px 0; margin-top: 8px;
    font-size: 14px; }
.gpt-label { font-size: 11px; font-weight: 700; color: #3B82F6;
    letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; }

/* File tray */
.file-badge { display: inline-block; background: #F4F0EB; border: 1px solid #E8E0D5;
    border-radius: 8px; padding: 4px 10px; margin: 2px 4px; font-size: 12px; }

/* PIN */
.pin-container { max-width: 320px; margin: 60px auto; text-align: center; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
RETRY_WAIT_BASE = 10


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
_defaults = {
    "mode": "business",
    "private_unlocked": False,
    "active_module": "hal_chat",     # HAL is always the default — THE BRAIN
    "chat_history": [],
    "hal_uploads": [],               # current uploaded files metadata
    "hal_digest": "",                # extracted text for ChatGPT
    "hal_file_blocks": [],           # Claude content blocks from uploads
    "second_opinions": {},           # {msg_index: gpt_text}
    "session_id": datetime.now().strftime("%Y%m%d-%H%M"),
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def get_api_key():
    return (
        st.secrets.get("Claude_API_Key") or
        st.secrets.get("ANTHROPIC_API_KEY") or
        st.secrets.get("claude_api_key") or ""
    )

def get_openai_key():
    return (
        st.secrets.get("OPENAI_API_KEY") or
        st.secrets.get("openai_api_key") or ""
    )

def check_pin(pin_input):
    stored = st.secrets.get("HAL_PIN", "")
    if not stored:
        return False
    return pin_input == stored


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS — THE KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_BUSINESS = """You are HAL — the AI operating system for Christos Iatropoulos, founder of Ashlar Insurance (formerly CHI Insurance Brokers), Athens, Greece.

You are THE BRAIN of the entire operation. Every document, every quote, every question comes through you first. You analyse everything uploaded to you — PDFs, images, spreadsheets, Word docs — and provide expert insurance intelligence.

KEY KNOWLEDGE:
- Carriers: Groupama, Generali, Ethniki, Morgan Price, NOW Health, Bupa Global, April International, IMG Global
- Greek domestic plans: no free-network outpatient, no dental treatment, no psychiatric outpatient, no MRI/PET/CT outside hospitalisation. Greek deductibles: per-hospitalisation OR annual (important difference).
- International plans: full outpatient, diagnostics, physio, dental, psychiatric depending on plan.
- Bupa Global claim expertise: formal complaint procedure, FSPO (Dublin), 7-day escalation protocol.
- Brand: Ashlar Insurance (ashlar-assurance.com). Pet brand: petshealth.gr.
- Pantelis Kourbelas is a CLIENT of Ashlar Insurance, NOT the operator.

WHEN DOCUMENTS ARE UPLOADED:
- Read them thoroughly before answering
- For insurance quotes/proposals: extract insurer, plan name, premium, deductible, coverage limits, exclusions
- For claims: identify claim number, amounts, dates, medical codes
- For any document: summarise key points and flag anything unusual
- When multiple quotes are uploaded: automatically compare them side by side
- Always mention what you found AND what's missing

ACTIVE CLIENT CASES:
- KONSTANTINA ALEXOPOULOU (Tzina) | Bupa Global BI-6000-0113-6189 | 🔴 ESCALATED
  Claim CL260306821932 — EUR 12,999.97 — Facial nerve palsy surgery. FSPO complaint filed. Member since 1996, premium GBP 66,219/yr.
- KATIA TOTIKIDOU + ALEXIA (17) | Comparing plans | 🟡 PENDING
  Katia 54, Alexia 17. Greece-based. Needs hospitalisation + diagnostics abroad. Cancer history.
- CHRISTOS IATROPOULOS | Morgan Price M000106069/1 | 🟡 PENDING
  Own claim — colonoscopy + gastroscopy. Pending upload to portal.
- MR. SYNODINOS | Lloyd's binder | 🔵 IN PROGRESS
  Holiday rental Syros. Outstanding: signatures on pages 5, 8-9.

LIVE 2025 RATE TABLES (EUR, annual, Area 1 = Europe excl USA):

MORGAN PRICE (area1):
- Standard (HOSPITAL ONLY): 30y=1,061 | 40y=1,380 | 45y=1,698 | 50y=2,041 | 55y=2,810 | 60y=3,548 | 65y=4,719
- Standard Plus (hospital + outpatient 80%): 30y=1,322 | 40y=1,719 | 45y=2,136 | 50y=2,495 | 55y=3,436 | 60y=4,338 | 65y=5,810
- Comprehensive (full): 30y=2,247 | 40y=2,921 | 45y=3,690 | 50y=4,104 | 55y=5,656 | 60y=7,849 | 65y=10,647

APRIL (area1):
- International: 30y=1,940 | 40y=2,501 | 45y=2,869 | 50y=3,700 | 55y=4,913 | 60y=6,670 | 65y=10,011
- Executive: 30y=4,459 | 40y=5,743 | 45y=6,596 | 50y=8,640 | 55y=10,678 | 60y=13,675 | 65y=20,142

IMG (area1, EUR 150 deductible):
- Silver: 30y=1,813 | 40y=2,339 | 45y=2,872 | 50y=3,764 | 55y=4,993 | 60y=6,366 | 65y=8,427
- Gold: 30y=2,320 | 40y=3,004 | 45y=3,694 | 50y=4,854 | 55y=6,450 | 60y=8,233 | 65y=10,914
- Platinum: 30y=2,912 | 40y=3,797 | 45y=4,686 | 50y=6,178 | 55y=8,238 | 60y=10,535 | 65y=13,987

Respond in the language of the message. Be direct — produce outputs, not advice about producing them."""

SYSTEM_PRIVATE = """You are HAL — the private AI assistant for Christos Iatropoulos. In this private mode you have access to lodge and personal context.

LODGE: You assist as secretary for Στ∴ ΑΚΡΟΠΟΛΙΣ υπ' αρ. 84 (Grand Lodge of Greece, ΜΣΤΕ) and ΚΛΕΙΣ ΑΛΗΘΕΙΑΣ αρ. 1 (A.A.S.R.). Always use Masonic ∴ notation. Style: contemporary Greek Tektonic — NOT archaic. Closing: Μ.τ.Τ.Α.Α. / Κατ' εντολήν του Σεβ∴ / Ο Γραμμ∴ / Χρήστος Ιατρόπουλος. Lodge email: st.akropolis.84@gmail.com.

PERSONAL: Financial adviser, nurse, gym coach. Help with savings plans, retirement modelling, workout programmes, health monitoring.

You can also analyse uploaded documents in private mode — lodge circulars, financial statements, health reports.

Never mix lodge content with business sessions. Respond in Greek unless asked otherwise."""


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — HAL is the brain, tools are subsidiary
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="hal-logo">
        <div class="hal-title">HAL</div>
        <div class="hal-sub">Ashlar Intelligence Layer</div>
    </div>
    """, unsafe_allow_html=True)

    # Mode switch
    st.markdown("**Mode**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏛 Business", use_container_width=True,
                     type="primary" if st.session_state.mode == "business" else "secondary"):
            st.session_state.mode = "business"
            st.session_state.active_module = "hal_chat"
            st.rerun()
    with col2:
        if st.button("🔒 Private", use_container_width=True,
                     type="primary" if st.session_state.mode == "private" else "secondary"):
            st.session_state.mode = "private"
            st.session_state.active_module = "hal_chat"
            st.rerun()

    st.divider()

    # ── THE BRAIN — always first ─────────────────────────────────────────
    st.markdown('<div class="section-header">🧠 THE BRAIN</div>', unsafe_allow_html=True)
    if st.button("💬  HAL Assistant", key="nav_hal", use_container_width=True,
                 type="primary" if st.session_state.active_module == "hal_chat" else "secondary"):
        st.session_state.active_module = "hal_chat"
        st.rerun()

    st.divider()

    # ── TOOLS — subsidiary ───────────────────────────────────────────────
    if st.session_state.mode == "business":
        st.markdown('<div class="section-header">🔧 TOOLS</div>', unsafe_allow_html=True)

        tools_business = [
            ("📊", "quotes",       "Quote Engine"),
            ("🔄", "renewals",     "Renewals"),
            ("📄", "documents",    "Document Filler"),
            ("✉️", "comms",        "Communications"),
            ("📈", "commissions",  "Commissions"),
            ("🔍", "market",       "Market Intel"),
            ("🤝", "clients",      "Clients"),
            ("🏗️", "apps",         "App Builder"),
            ("🐾", "pets",         "PetsHealth"),
        ]
        for icon, key, label in tools_business:
            active = st.session_state.active_module == key
            if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.active_module = key
                st.rerun()
    else:
        if st.session_state.private_unlocked:
            st.markdown('<div class="section-header">🔧 PRIVATE TOOLS</div>', unsafe_allow_html=True)
            tools_private = [
                ("🏛️", "lodge",     "Lodge Secretary"),
                ("💰", "finance",   "Financial Planner"),
                ("💪", "health",    "Health & Gym"),
            ]
            for icon, key, label in tools_private:
                active = st.session_state.active_module == key
                if st.button(f"{icon}  {label}", key=f"nav_p_{key}", use_container_width=True,
                             type="primary" if active else "secondary"):
                    st.session_state.active_module = key
                    st.rerun()

            st.divider()
            if st.button("🔓 Lock Private Mode", use_container_width=True):
                st.session_state.private_unlocked = False
                st.session_state.mode = "business"
                st.session_state.active_module = "hal_chat"
                st.rerun()

    st.divider()
    api_key = get_api_key()
    if api_key:
        st.success("🔑 API key loaded", icon="✅")
    else:
        st.warning("Add Claude_API_Key to secrets")

    openai_key = get_openai_key()
    if openai_key:
        st.caption("🤖 ChatGPT second opinion: ready")
    else:
        st.caption("🤖 Add OPENAI_API_KEY for second opinions")

    st.markdown('<div style="font-size:11px;color:#4A3728;margin-top:8px;text-align:center">'
                'HAL v2.0 · Railway · June 2026</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PIN SCREEN
# ══════════════════════════════════════════════════════════════════════════════
def render_pin_screen():
    st.markdown('<div class="pin-container">', unsafe_allow_html=True)
    st.markdown("## 🔒 Private Mode")
    st.caption("Enter your PIN to access private modules")
    pin = st.text_input("PIN", type="password", key="pin_input")
    if st.button("Unlock", type="primary"):
        if check_pin(pin):
            st.session_state.private_unlocked = True
            st.rerun()
        else:
            st.error("Wrong PIN")
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HAL CHAT — THE BRAIN
# ══════════════════════════════════════════════════════════════════════════════
def render_hal_chat():
    import anthropic

    is_private = st.session_state.mode == "private"
    mode_label = "Private · Lodge & Personal" if is_private else "Business · Ashlar Insurance"

    st.markdown(f"## 🧠 HAL — {mode_label}")
    st.caption("Upload anything. Ask anything. HAL is the brain.")

    system = SYSTEM_PRIVATE if is_private else SYSTEM_BUSINESS
    api_key = get_api_key()
    openai_key = get_openai_key()

    # ── FILE UPLOAD — the killer feature ─────────────────────────────────
    with st.expander("📎 Upload files for HAL to analyse", expanded=not bool(st.session_state.chat_history)):
        uploaded = st.file_uploader(
            "Drop PDFs, images, Word docs, Excel, CSV — anything",
            type=["pdf", "png", "jpg", "jpeg", "webp", "gif", "docx",
                  "xlsx", "xls", "csv", "tsv", "txt", "md", "json"],
            accept_multiple_files=True,
            key="hal_file_upload",
        )

        if uploaded:
            with st.spinner("Reading files..."):
                blocks, digest, summaries = process_uploads(uploaded)
                st.session_state.hal_file_blocks = blocks
                st.session_state.hal_digest = digest
                st.session_state.hal_uploads = summaries

            # Show file badges
            badges = " ".join(
                f'<span class="file-badge">{icon} {name}</span>'
                for name, icon in summaries
            )
            st.markdown(badges, unsafe_allow_html=True)
            st.success(f"✅ {len(summaries)} file(s) loaded — HAL can see them now. Ask your question below.")
        elif st.session_state.hal_uploads:
            # Show previously loaded files
            badges = " ".join(
                f'<span class="file-badge">{icon} {name}</span>'
                for name, icon in st.session_state.hal_uploads
            )
            st.markdown(badges, unsafe_allow_html=True)
            st.caption("Files still loaded from this session")

    # ── CHAT DISPLAY ─────────────────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.info("HAL is ready. Upload documents or ask anything — insurance quotes, "
                    "client cases, claims, comparisons, lodge matters, or personal queries.")
        else:
            for i, msg in enumerate(st.session_state.chat_history):
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        content = msg["content"]
                        if isinstance(content, list):
                            # Show text parts only (images shown as badge)
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    st.write(block["text"])
                                elif isinstance(block, dict) and block.get("type") == "image":
                                    st.caption("📎 [image attached]")
                                elif isinstance(block, str):
                                    st.write(block)
                        else:
                            st.write(content)
                else:
                    with st.chat_message("assistant"):
                        st.write(msg["content"])

                    # ── SECOND OPINION BUTTON ────────────────────────
                    if openai_key and msg["role"] == "assistant":
                        col_a, col_b = st.columns([6, 1])
                        with col_b:
                            if st.button("🤖 2nd", key=f"gpt_{i}", help="Get ChatGPT second opinion"):
                                with st.spinner("Asking ChatGPT..."):
                                    opinion = second_opinion(
                                        openai_key=openai_key,
                                        hal_system=system,
                                        chat_history=st.session_state.chat_history[:i+1],
                                        digest=st.session_state.hal_digest,
                                    )
                                    st.session_state.second_opinions[i] = opinion
                                    st.rerun()

                        # Show existing second opinion
                        if i in st.session_state.second_opinions:
                            st.markdown(f"""<div class="gpt-opinion">
                                <div class="gpt-label">🤖 ChatGPT Second Opinion (advisory only)</div>
                                {st.session_state.second_opinions[i]}
                            </div>""", unsafe_allow_html=True)

    # ── QUICK ACTIONS ────────────────────────────────────────────────────
    if not st.session_state.chat_history:
        st.markdown("**Quick actions:**")
        if is_private:
            quick = [
                "Draft a circular to the lodge brothers in Greek Tektonic style",
                "Generate agenda for next lodge session",
                "Create a savings plan for retirement in 15 years",
                "Design a 4-week gym programme for strength",
            ]
        else:
            quick = [
                "I uploaded 3 quotes — compare them for a female 44 in Belgium",
                "Compare Morgan Price vs April for a 50-year-old client",
                "Draft a renewal notice email in Greek",
                "Write a Bupa appeal letter for a denied claim",
                "Draft a cold outreach email to a corporate HR manager",
            ]
        cols = st.columns(2)
        for i, q in enumerate(quick):
            with cols[i % 2]:
                if st.button(q, key=f"quick_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": q})
                    st.rerun()

    # ── CHAT INPUT ───────────────────────────────────────────────────────
    user_input = st.chat_input("Message HAL — upload files above, then ask here...")
    if user_input:
        # Build message with file blocks if present
        file_blocks = st.session_state.hal_file_blocks
        if file_blocks:
            # Combine text input + file blocks into a multi-block message
            content_blocks = list(file_blocks) + [{"type": "text", "text": user_input}]
            st.session_state.chat_history.append({"role": "user", "content": content_blocks})
            # Clear file blocks after first use (they're in the conversation now)
            st.session_state.hal_file_blocks = []
        else:
            st.session_state.chat_history.append({"role": "user", "content": user_input})

        if not api_key:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "⚠️ No API key found. Add Claude_API_Key to your Streamlit/Railway secrets."
            })
        else:
            with st.spinner("HAL is thinking..."):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    # Build messages for Claude
                    messages = []
                    for m in st.session_state.chat_history:
                        messages.append({"role": m["role"], "content": m["content"]})

                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=4000,
                        system=system,
                        messages=messages
                    )
                    reply = response.content[0].text
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                except Exception as e:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"⚠️ Error: {str(e)}"
                    })
        st.rerun()

    # ── CONTROLS ─────────────────────────────────────────────────────────
    if st.session_state.chat_history:
        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("🗑 Clear", key="clear_chat"):
                st.session_state.chat_history = []
                st.session_state.hal_file_blocks = []
                st.session_state.hal_digest = ""
                st.session_state.hal_uploads = []
                st.session_state.second_opinions = {}
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# QUOTE ENGINE — subsidiary tool
# ══════════════════════════════════════════════════════════════════════════════
def render_quotes():
    st.markdown("## 📊 Quote Engine")
    st.caption("Live 2025 rates · Morgan Price · April · IMG · PDF extraction · PPTX generation")
    st.info("💡 **Tip:** You can also upload quote PDFs directly into HAL Chat — "
            "HAL will analyse and compare them automatically.", icon="🧠")

    tab_live, tab_pdf = st.tabs([
        "⚡ Instant Quote (Rate Tables)",
        "📄 PDF → AI Extraction → PPTX",
    ])

    # ══ TAB 1: INSTANT LIVE QUOTE ════════════════════════════════════════
    with tab_live:
        if not RATES_LOADED:
            st.warning("rate_tables.py not found. Add it alongside app.py.")
            return

        st.markdown("### Client Details")
        qc1, qc2, qc3 = st.columns(3)
        with qc1:
            q_name = st.text_input("Client name", placeholder="e.g. Maria K.")
            q_age = st.number_input("Age", min_value=0, max_value=80, value=45)
        with qc2:
            q_area = st.radio("Coverage area", ["Area 1 — Europe (excl USA)", "Area 2 — Worldwide incl USA"])
            area_key = "area1" if "Area 1" in q_area else "area2"
        with qc3:
            q_notes = st.text_area("Client priorities / notes", height=100,
                placeholder="e.g. Needs outpatient, travels frequently, cancer history...")

        st.markdown("### Members")
        if "quote_members" not in st.session_state:
            st.session_state.quote_members = [{"name": q_name or "Member 1", "age": q_age}]
        with st.expander("➕ Add family member"):
            m_name = st.text_input("Name", key="m_name")
            m_age = st.number_input("Age", min_value=0, max_value=80, value=35, key="m_age")
            if st.button("Add member", key="add_member"):
                st.session_state.quote_members.append({"name": m_name, "age": m_age})
                st.rerun()
        for i, m in enumerate(st.session_state.quote_members):
            mc1, mc2 = st.columns([4, 1])
            mc1.markdown(f"👤 **{m['name']}** — Age {m['age']}")
            if mc2.button("✕", key=f"del_m_{i}") and len(st.session_state.quote_members) > 1:
                st.session_state.quote_members.pop(i)
                st.rerun()

        st.markdown("### Plans to compare")
        all_plans = list(RATE_PLANS)
        selected_plans = st.multiselect("Select plans",
            options=[p[2] for p in all_plans],
            default=["Morgan Price Standard", "Morgan Price Comprehensive",
                     "April International", "April Executive", "IMG Silver", "IMG Gold"])

        if st.button("⚡ Generate Comparison", type="primary", use_container_width=True):
            if not st.session_state.quote_members:
                st.warning("Add at least one member.")
            else:
                results = []
                plan_map = {p[2]: p for p in all_plans}
                for plan_name in selected_plans:
                    if plan_name not in plan_map:
                        continue
                    carrier, plan_key, display, coverage, ded_note = plan_map[plan_name]
                    total = 0
                    member_rates = []
                    valid = True
                    for m in st.session_state.quote_members:
                        prem = lookup_premium(carrier, plan_key, m["age"], area_key)
                        if prem is None:
                            valid = False
                            break
                        total += prem
                        member_rates.append((m["name"], m["age"], prem))
                    if valid:
                        results.append({
                            "plan": display, "carrier": carrier, "total": total,
                            "members": member_rates, "coverage": coverage, "deductible": ded_note
                        })
                results.sort(key=lambda x: x["total"])
                st.session_state["quote_results"] = results
                st.session_state["quote_client"] = q_name
                st.rerun()

        # Display results
        if st.session_state.get("quote_results"):
            results = st.session_state["quote_results"]
            client = st.session_state.get("quote_client", "Client")
            st.markdown("---")
            st.markdown(f"### 📋 Quote Comparison — {client or 'Client'}")
            cheapest = results[0]["total"] if results else 0
            for i, r in enumerate(results):
                diff = r["total"] - cheapest
                badge = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
                diff_str = f"+€{diff:,.0f}/yr" if diff > 0 else "✅ Lowest"
                color = "#EDFBF0" if i == 0 else "white"
                st.markdown(f"""<div style="background:{color};border:1px solid #E8E0D5;
                    border-radius:12px;padding:16px 20px;margin-bottom:10px">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div><span style="font-size:18px">{badge}</span>
                        <strong style="font-size:16px;margin-left:8px">{r["plan"]}</strong>
                        <span style="font-size:12px;color:#6B7280;margin-left:10px">{r["deductible"]}</span></div>
                        <div style="text-align:right">
                        <div style="font-size:22px;font-weight:800;color:#1C1410">€{r["total"]:,.0f}/yr</div>
                        <div style="font-size:12px;color:#6B7280">{diff_str}</div></div>
                    </div>
                    <div style="margin-top:10px;font-size:12px;color:#6B7280">
                    {" · ".join(str(m[0]) + ": €" + f"{m[2]:,.0f}" for m in r["members"])}
                    </div></div>""", unsafe_allow_html=True)

    # ══ TAB 2: PDF EXTRACTION ════════════════════════════════════════════
    with tab_pdf:
        if not EXTRACT_OK:
            st.warning("extraction.py or analysis.py not found.")
            return

        api_key = get_api_key()
        st.markdown("### 📄 Upload Insurance Quotes (PDF)")
        st.info("Upload 2–4 PDF proposals. Claude extracts everything automatically.", icon="ℹ️")
        uploaded_files = st.file_uploader("Select PDF files", type="pdf",
                                          accept_multiple_files=True, key="qe_pdfs")
        if not uploaded_files:
            st.markdown("**1️⃣** Upload PDFs → **2️⃣** Claude analyses → **3️⃣** Download PPTX")
            return

        if "qe_proposals" not in st.session_state:
            st.session_state.qe_proposals = {}

        if st.button("🤖 Analyse with Claude", type="primary", disabled=not api_key, key="qe_analyse"):
            progress = st.progress(0, text="Initialising...")
            st.session_state.qe_proposals = {}
            total = len(uploaded_files)
            for idx, uf in enumerate(uploaded_files):
                progress.progress(idx / total, text=f"Analysing {idx+1}/{total}: {uf.name}...")
                try:
                    pdf_bytes = uf.read()
                    data = extract_insurance_data(pdf_bytes, api_key, filename=uf.name)
                    st.success(f"✅ {uf.name} → {data.get('insurer','')} {data.get('plan_name','')}")
                    st.session_state.qe_proposals[uf.name] = data
                except Exception as e:
                    st.error(f"❌ Error in {uf.name}: {e}")
                if idx < total - 1:
                    _time.sleep(10)
            progress.progress(1.0, text="✅ Complete!")

        if st.session_state.get("qe_proposals"):
            proposals_list = list(st.session_state.qe_proposals.values())
            st.markdown("---")
            st.markdown("### 📊 Extracted Data")
            for prop in proposals_list:
                sc = compute_score(prop)
                emoji = "🟢" if sc >= 7 else ("🟡" if sc >= 5 else "🔴")
                st.metric(
                    label=f"{prop.get('insurer','?')} — {prop.get('plan_name','?')[:18]}",
                    value=f"{sc} / 10",
                    delta=f"{emoji} Coverage Score"
                )


# ══════════════════════════════════════════════════════════════════════════════
# COMMUNICATIONS — subsidiary tool
# ══════════════════════════════════════════════════════════════════════════════
def render_comms():
    import anthropic

    st.markdown("## ✉️ Communications")
    st.caption("Client emails, provider letters, cold outreach")
    st.info("💡 **Tip:** You can also ask HAL directly to draft any email or letter.", icon="🧠")

    api_key = get_api_key()
    if not api_key:
        st.warning("Add Claude_API_Key to secrets.")
        return

    comm_type = st.selectbox("Type", [
        "Client renewal notice (Greek)",
        "Client renewal notice (English)",
        "Bupa appeal / complaint letter",
        "Cold outreach to HR manager",
        "Provider letter (English)",
        "Custom — describe below",
    ])
    details = st.text_area("Details / context", height=120,
        placeholder="Client name, policy details, what you need...")

    if st.button("✍️ Generate", type="primary", use_container_width=True):
        with st.spinner("Drafting..."):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                prompt = f"Generate a {comm_type}.\n\nContext:\n{details}\n\nWrite it fully ready to send. No placeholders."
                response = client.messages.create(
                    model=MODEL, max_tokens=2000,
                    system=SYSTEM_BUSINESS,
                    messages=[{"role": "user", "content": prompt}]
                )
                st.markdown("### ✉️ Draft")
                st.markdown(response.content[0].text)
            except Exception as e:
                st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PLACEHOLDER MODULES — subsidiary tools
# ══════════════════════════════════════════════════════════════════════════════
def render_placeholder(title, icon):
    st.markdown(f"## {icon} {title}")
    st.info(f"This module is available. For now, you can use **HAL Chat** to handle "
            f"{title.lower()} tasks — just ask HAL directly.", icon="🧠")
    if st.button("💬 Go to HAL", type="primary"):
        st.session_state.active_module = "hal_chat"
        st.rerun()


def render_renewals():
    render_placeholder("Renewals", "🔄")

def render_documents():
    render_placeholder("Document Filler", "📄")

def render_commissions():
    render_placeholder("Commissions", "📈")

def render_market():
    render_placeholder("Market Intel", "🔍")

def render_clients():
    render_placeholder("Clients", "🤝")

def render_apps():
    render_placeholder("App Builder", "🏗️")

def render_pets():
    render_placeholder("PetsHealth", "🐾")

def render_lodge():
    render_placeholder("Lodge Secretary", "🏛️")

def render_finance():
    render_placeholder("Financial Planner", "💰")

def render_health():
    render_placeholder("Health & Gym", "💪")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER — HAL is always the default
# ══════════════════════════════════════════════════════════════════════════════
module = st.session_state.active_module
mode = st.session_state.mode

if mode == "private" and not st.session_state.private_unlocked:
    render_pin_screen()

elif mode == "business":
    if module == "hal_chat":       render_hal_chat()
    elif module == "quotes":       render_quotes()
    elif module == "renewals":     render_renewals()
    elif module == "documents":    render_documents()
    elif module == "comms":        render_comms()
    elif module == "commissions":  render_commissions()
    elif module == "market":       render_market()
    elif module == "clients":      render_clients()
    elif module == "apps":         render_apps()
    elif module == "pets":         render_pets()
    else:                          render_hal_chat()  # Default = HAL

elif mode == "private" and st.session_state.private_unlocked:
    if module == "hal_chat":       render_hal_chat()
    elif module == "lodge":        render_lodge()
    elif module == "finance":      render_finance()
    elif module == "health":       render_health()
    else:                          render_hal_chat()  # Default = HAL
