import streamlit as st
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup
import os 
from datetime import datetime

# Safety import for pytz
try:
    import pytz
except ImportError:
    os.system('pip install pytz')
    import pytz

# ---------------------------
# 0. PAGE & PORT CONFIG (FIXED FOR RAILWAY)
# ---------------------------
# This forces Streamlit to use the port Railway is looking for
os.environ['STREAMLIT_SERVER_PORT'] = '8080'
os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'

st.set_page_config(page_title="Public Sector Contracts AI", page_icon="🏛️")

# ---------------------------
# 1. STATE & RESET (LOCKED)
# ---------------------------
if "total_saved" not in st.session_state:
    st.session_state.total_saved = 480
if "active_bid_text" not in st.session_state:
    st.session_state.active_bid_text = None
if "reset_ver" not in st.session_state:
    st.session_state.reset_ver = 0

def hard_reset_callback():
    st.session_state.reset_ver += 1
    keys_to_keep = ["total_saved", "reset_ver"]
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]

# ---------------------------
# 2. THE ENGINE (LOCKED)
# ---------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def run_ai(text, prompt, is_compliance=False, is_header=False, is_search=False, is_scope=False):
    if not GROQ_API_KEY:
        return "⚠️ API Key missing."
    tz = pytz.timezone('US/Pacific'); now = datetime.now(tz)
    current_time_str = now.strftime("%B %d, %Y %I:%M %p")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    ctx = text[:60000] 
    
    simple_translation_rules = "STRICT TRANSLATION RULES: 1. Act as a Plain English Translator. 2. NO legal jargon."

    if is_compliance:
        system_rules = "RULES: 1. BE DIRECT. 2. Extract SLAs. 3. SIMPLE ENGLISH."
    elif is_header:
        system_rules = f"RULES: 1. Extract ONLY proper names. 2. Today is {current_time_str}. 3. If deadline passed, say 'CLOSED'."
    elif is_search:
        system_rules = f"{simple_translation_rules}\nTASK: Answer the user's question about the document in plain English."
    elif is_scope:
        system_rules = f"{simple_translation_rules}\nTASK: Explain the whole job in simple terms."
    else:
        system_rules = "CORE INSTRUCTION: 1. List physical hardware only."
    
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_rules}, {"role": "user", "content": f"Text: {ctx}\n\nTask: {prompt}"}], "temperature": 0.0}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=35)
        return r.json()["choices"][0]["message"]["content"].strip()
    except: return "⚠️ AI Error."

# ---------------------------
# 3. UNIVERSAL BID SCRAPER (LOCKED)
# ---------------------------
def scrape_agency_bids(url):
    guidance = ["⚠️ **Dynamic Portal Detected.**", "📄 **Instruction:** Download the PDF and upload to 'Bid Document'."]
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}; url_lower = url.lower()
        dynamic_portals = ["planetbids", "rampla.org", "caleprocure", "oc.gov", "bidnetdirect", "hacla.org", "gep.com"]
        if any(p in url_lower for p in dynamic_portals): return guidance
        r = requests.get(url, headers=headers, timeout=15); soup = BeautifulSoup(r.text, 'html.parser')
        found_bids = []
        for el in soup.find_all(['b', 'strong', 'a', 'li']):
            text = " ".join(el.get_text().split()).strip()
            if any(text.startswith(yr) for yr in ["21-", "22-", "23-", "24-", "25-"]):
                if not any(n in text.lower() for n in ["plans", "specifications", "addendum"]):
                    if len(text) > 12: found_bids.append(f"📄 {text}")
        return list(dict.fromkeys(found_bids)) if found_bids else guidance
    except: return guidance

# ---------------------------
# 4. MAIN APP LOGIC (LOCKED)
# ---------------------------
st.title("🏛️ Public Sector Contracts AI")
st.button("🏠 Home / Reset App", on_click=hard_reset_callback)
st.divider()

if st.session_state.get("active_bid_text"):
    doc = st.session_state.active_bid_text
    st.subheader("🔍 Search Document")
    user_q = st.text_input("Enter your query:", key="active_q")
    if user_q: st.write(f"**Answer (Simplified):** {run_ai(doc, user_q, is_search=True)}")
    st.divider()
    
    if st.session_state.get("analysis_mode") == "Reporting":
        st.subheader("📊 SLA & Non-Compliance"); st.info(run_ai(doc, "Identify SLAs.", is_compliance=True))
    else:
        if not st.session_state.get("agency_name"):
            with st.status("🏗️ Analyzing..."):
                st.session_state.status_flag = run_ai(doc, "Status: OPEN or CLOSED?", is_header=True)
                st.session_state.agency_name = run_ai(doc, "Agency name?", is_header=True)
                st.session_state.project_title = run_ai(doc, "Project Title?", is_header=True)
                st.session_state.due_date = run_ai(doc, "Deadline date?", is_header=True)
            st.rerun()

        st.subheader("🏛️ Project Snapshot")
        is_past = any(yr in st.session_state.due_date for yr in ["2021", "2022", "2023", "2024", "2025"])
        if is_past or "CLOSED" in st.session_state.status_flag.upper():
            st.error(f"● STATUS: CLOSED | DUE: {st.session_state.due_date}")
        else:
            st.success(f"● STATUS: OPEN | DUE: {st.session_state.due_date}")
        st.write(f"**🏛️ AGENCY:** {st.session_state.agency_name}"); st.write(f"**📄 BID NAME:** {st.session_state.project_title}")
        st.divider(); st.subheader("📖 Bid Overview (Simple Terms)")
        st.info(run_ai(doc, "Explain this job in simple terms.", is_scope=True))
else:
    tab1, tab2, tab3 = st.tabs(["📄 Bid Document", "📊 Compliance", "🔗 Agency URL"])
    with tab1:
        up = st.file_uploader("Upload Bid PDF", type="pdf", key="u1")
        if up: st.session_state.active_bid_text = "\n".join([p.extract_text() for p in PdfReader(up).pages]); st.session_state.analysis_mode = "Standard"; st.rerun()
    with tab2:
        up_c = st.file_uploader("Upload Contract PDF", type="pdf", key="u2")
        if up_c: st.session_state.active_bid_text = "\n".join([p.extract_text() for p in PdfReader(up_c).pages]); st.session_state.analysis_mode = "Reporting"; st.rerun()
    with tab3:
        url_input = st.text_input("Agency URL:", key=f"url_input_v{st.session_state.reset_ver}")
        if url_input:
            with st.spinner("Analyzing..."):
                for b in scrape_agency_bids(url_input): st.write(b)

with st.sidebar:
    st.header("Project Performance"); st.metric("Total Est. Time Saved", f"{st.session_state.total_saved} mins")
