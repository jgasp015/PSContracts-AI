import streamlit as st
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup
import os 
from datetime import datetime
import pytz # Standard for timezone handling

# ---------------------------
# 0. PAGE CONFIGURATION (LOCKED)
# ---------------------------
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
# 2. THE ENGINE (REAL-TIME CLOCK UPDATED)
# ---------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def run_ai(text, prompt, is_compliance=False, is_header=False, is_search=False, is_scope=False):
    if not GROQ_API_KEY:
        return "⚠️ API Key missing."
    
    # NEW: Get Real-Time California Time
    tz = pytz.timezone('US/Pacific')
    now = datetime.now(tz)
    current_time_str = now.strftime("%B %d, %Y %I:%M %p")
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    ctx = text[:60000] 
    
    if is_compliance:
        system_rules = "RULES: 1. BE DIRECT. 2. Extract SLAs. 3. SIMPLE ENGLISH."
    elif is_header:
        # UPDATED: AI now knows the exact minute it is currently
        system_rules = f"RULES: 1. Extract ONLY proper names. 2. Today is {current_time_str}. 3. If the document deadline has passed this exact time, say 'CLOSED'. 4. Provide a 1-sentence max response."
    elif is_search:
        system_rules = "You are a helpful assistant. Answer based on document."
    elif is_scope:
        system_rules = "CORE INSTRUCTION: 1. ANALYZE whole text. 2. List QUANTITIES and TASKS. 3. NO repetition."
    else:
        system_rules = "CORE INSTRUCTION: 1. List physical hardware only. 2. Use bullets (*)."
    
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_rules}, {"role": "user", "content": f"Text: {ctx}\n\nTask: {prompt}"}], "temperature": 0.0}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=35)
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return "⚠️ AI Error."

# ---------------------------
# 3. UNIVERSAL BID SCRAPER (LOCKED)
# ---------------------------
def scrape_agency_bids(url):
    guidance = ["⚠️ **Dynamic Portal Detected.**", "📄 **Instruction:** Download the PDF from the portal and upload it to the **'Bid Document'** tab."]
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url_lower = url.lower()
        dynamic_portals = ["planetbids", "rampla.org", "caleprocure", "oc.gov", "bidnetdirect", "hacla.org", "gep.com"]
        if any(p in url_lower for p in dynamic_portals): return guidance
        r = requests.get(url, headers=headers, timeout=15); soup = BeautifulSoup(r.text, 'html.parser')
        found_bids = []
        for el in soup.find_all(['b', 'strong', 'a', 'li']):
            text = " ".join(el.get_text().split()).strip()
            if any(text.startswith(yr) for yr in ["21-", "22-", "23-", "24-", "25-"]):
                if len(text) > 15: found_bids.append(f"📄 {text}")
        return list(dict.fromkeys(found_bids)) if found_bids else guidance
    except: return guidance

# ---------------------------
# 4. MAIN APP LOGIC (REAL-TIME STATUS UPDATED)
# ---------------------------
st.title("🏛️ Public Sector Contracts AI")
st.button("🏠 Home / Reset App", on_click=hard_reset_callback)
st.divider()

if st.session_state.get("active_bid_text"):
    doc = st.session_state.active_bid_text
    st.subheader("🔍 Search Document")
    user_q = st.text_input("Enter your query:", key="active_q")
    if user_q: st.write(f"**Answer:** {run_ai(doc, user_q, is_search=True)}")
    st.divider()
    
    if st.session_state.get("analysis_mode") == "Reporting":
        st.subheader("📊 SLA & Non-Compliance")
        st.info(run_ai(doc, "Identify SLAs and triggers.", is_compliance=True))
    else:
        if not st.session_state.get("agency_name"):
            with st.status("🏗️ Analyzing..."):
                st.session_state.status_flag = run_ai(doc, "Status: OPEN or CLOSED?", is_header=True)
                st.session_state.agency_name = run_ai(doc, "What is the Government Agency name?", is_header=True)
                st.session_state.project_title = run_ai(doc, "What is the specific Project Title/Bid Name?", is_header=True)
                st.session_state.due_date = run_ai(doc, "When is the deadline date and time?", is_header=True)
            st.rerun()

        st.subheader("🏛️ Project Snapshot")
        
        # Real-time Comparison Logic
        tz = pytz.timezone('US/Pacific')
        current_dt = datetime.now(tz)
        status_raw = st.session_state.status_flag.upper()
        
        # If the AI says it's CLOSED, or if the year is clearly in the past
        is_past_year = any(yr in st.session_state.due_date for yr in ["2021", "2022", "2023", "2024", "2025"])
        
        if is_past_year or "CLOSED" in status_raw:
            st.error(f"● STATUS: CLOSED | DUE: {st.session_state.due_date}")
        else:
            st.success(f"● STATUS: OPEN | DUE: {st.session_state.due_date}")
        
        st.write(f"**🏛️ AGENCY:** {st.session_state.agency_name}")
        st.write(f"**📄 BID NAME:** {st.session_state.project_title}")
        st.divider()
        st.subheader("📖 Bid Overview")
        st.info(run_ai(doc, "Summarize the scope and quantities.", is_scope=True))

else:
    tab1, tab2, tab3 = st.tabs(["📄 Bid Document", "📊 Compliance", "🔗 Agency URL"])
    with tab1:
        up = st.file_uploader("Upload Bid PDF", type="pdf", key="u1")
        if up: 
            st.session_state.active_bid_text = "\n".join([p.extract_text() for p in PdfReader(up).pages])
            st.session_state.analysis_mode = "Standard"; st.rerun()
    with tab2:
        up_c = st.file_uploader("Upload Contract PDF", type="pdf", key="u2")
        if up_c: 
            st.session_state.active_bid_text = "\n".join([p.extract_text() for p in PdfReader(up_c).pages])
            st.session_state.analysis_mode = "Reporting"; st.rerun()
    with tab3:
        url_input = st.text_input("Agency URL:", key=f"url_input_v{st.session_state.reset_ver}")
        if url_input:
            with st.spinner("Analyzing..."):
                for b in scrape_agency_bids(url_input): st.write(b)

with st.sidebar:
    st.header("Project Performance"); st.metric("Total Est. Time Saved", f"{st.session_state.total_saved} mins"); st.caption("UCR Master of Science - Jeffrey Gaspar")
