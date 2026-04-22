import streamlit as st
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup
import os 

# ---------------------------
# 1. STATE & RESET (LOCKED)
# ---------------------------
if "total_saved" not in st.session_state:
    st.session_state.total_saved = 480
if "active_bid_text" not in st.session_state:
    st.session_state.active_bid_text = None
if "analysis_mode" not in st.session_state:
    st.session_state.analysis_mode = "Standard"

def hard_reset():
    for key in list(st.session_state.keys()):
        if key != "total_saved":
            del st.session_state[key]
    st.rerun()

# ---------------------------
# 2. THE ENGINE (RESTORED SCOPE LOGIC)
# ---------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def run_ai(text, prompt, is_compliance=False, is_header=False, is_search=False, is_scope=False):
    if not GROQ_API_KEY:
        return "⚠️ API Key missing in Railway Variables."
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    ctx = text[:60000] 
    today = "April 22, 2026"
    
    if is_compliance:
        system_rules = "RULES: 1. BE DIRECT. 2. Extract SLAs. 3. SIMPLE ENGLISH."
    elif is_header:
        system_rules = f"RULES: 1. 5 words or less. 2. Today is {today}. 3. If the document date is before 2026, YOU MUST SAY 'CLOSED'."
    elif is_search:
        system_rules = "You are a helpful assistant. Answer based on document."
    elif is_scope:
        # RESTORED: This is your original high-quality summary logic
        system_rules = "CORE INSTRUCTION: 1. ANALYZE the whole text. 2. List specific QUANTITIES and ACTION TASKS. 3. NO repetition. 4. Be descriptive and detailed."
    else:
        system_rules = "CORE INSTRUCTION: 1. List ONLY IT gear names. 2. START with bullets (*)."
    
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_rules}, {"role": "user", "content": f"Text: {ctx}\n\nTask: {prompt}"}], "temperature": 0.0}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=35)
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return "⚠️ AI Connection Error."

# ---------------------------
# 3. UNIVERSAL BID SCRAPER (LOCKED)
# ---------------------------
def scrape_agency_bids(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        found_bids = []
        noise = ["report", "photos", "sheet", "cards", "calculations", "addendum", "plans", "manual", "package", "response", "geotechnical", "reference only", "asbestos", "structural", "supplemental", "specifications", "technical", "dwgs", "dsa"]
        for element in soup.find_all(['b', 'strong', 'a', 'td', 'li']):
            text = " ".join(element.get_text().split()).strip()
            is_id = any(p in text for p in ["21-", "22-", "23-", "24-", "25-", "RFB-IS-", "RFP-"])
            if is_id:
                if element.name == 'td' or element.name == 'a':
                    parent_row = element.find_parent('tr')
                    if parent_row: text = " ".join(parent_row.get_text(separator=" ").split())
                if not any(n in text.lower() for n in noise):
                    clean_title = text.split("Powered by")[0].split("Contact Us")[0].strip()
                    if len(clean_title) > 12: found_bids.append(f"📄 {clean_title}")
        return list(dict.fromkeys(found_bids)) if found_bids else ["❓ No primary project titles found."]
    except: return ["⚠️ Connection error."]

# ---------------------------
# 4. MAIN APP LOGIC (RESTORED UI)
# ---------------------------
st.title("🏛️ Public Sector Contracts AI")
if st.button("🏠 Home / Reset App"):
    hard_reset()
st.divider()

if st.session_state.active_bid_text:
    doc = st.session_state.active_bid_text
    st.subheader("🔍 Search this Document")
    user_q = st.text_input("Ask a question:", key="active_q")
    if user_q:
        st.write(f"**Answer:** {run_ai(doc, user_q, is_search=True)}")
    st.divider()
    
    if st.session_state.analysis_mode == "Reporting":
        st.subheader("📊 SLA & Non-Compliance")
        st.info(run_ai(doc, "Identify SLAs and triggers.", is_compliance=True))
    else:
        if not st.session_state.get("agency_name"):
            with st.status("🏗️ Analyzing..."):
                st.session_state.status_flag = run_ai(doc, "OPEN or CLOSED?", is_header=True)
                st.session_state.agency_name = run_ai(doc, "Agency?", is_header=True)
                st.session_state.project_title = run_ai(doc, "Title?", is_header=True)
                st.session_state.due_date = run_ai(doc, "Deadline?", is_header=True)
            st.rerun()

        st.subheader("🏛️ Project Snapshot")
        
        # Keep the hard-logic year check to ensure status stays Red/CLOSED for 2022
        status_raw = st.session_state.status_flag.upper()
        date_raw = st.session_state.due_date
        is_past_year = any(yr in date_raw for yr in ["2021", "2022", "2023", "2024", "2025"])
        
        if "CLOSED" in status_raw or is_past_year:
            st.error(f"● STATUS: CLOSED | DUE: {date_raw}")
        else:
            st.success(f"● STATUS: OPEN | DUE: {date_raw}")
            
        st.write(f"**🏛️ AGENCY:** {st.session_state.agency_name}")
        st.write(f"**📄 BID NAME:** {st.session_state.project_title}")
        st.divider()
        
        b1, b2 = st.tabs(["📖 Scope of Work", "🛠️ Specifications"])
        with b1: 
            # RESTORED: Back to detailed summarization
            st.info(run_ai(doc, "Summarize the scope and quantities.", is_scope=True))
        with b2: 
            st.success(run_ai(doc, "List ONLY IT hardware, gear, and camera equipment."))
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
        url_input = st.text_input("Agency URL:", key="agency_url")
        if url_input:
            with st.spinner("Extracting Titles..."):
                for b in scrape_agency_bids(url_input): st.write(b)

with st.sidebar:
    st.header("Project Performance")
    st.metric("Total Est. Time Saved", f"{st.session_state.total_saved} mins")
    st.caption("UCR Master of Science - Jeffrey Gaspar")
