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
# 2. THE ENGINE (LOCKED)
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
        system_rules = f"RULES: 1. 5 words or less. 2. If BEFORE {today}, say 'CLOSED'."
    elif is_search:
        system_rules = "You are a helpful assistant. Answer based on document."
    elif is_scope:
        system_rules = "CORE INSTRUCTION: 1. ANALYZE text. 2. List QUANTITIES and TASKS."
    else:
        system_rules = "CORE INSTRUCTION: 1. List ONLY IT gear names. 2. START with bullets (*)."
    
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_rules}, {"role": "user", "content": f"Text: {ctx}\n\nTask: {prompt}"}], "temperature": 0.0}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=35)
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return "⚠️ AI Connection Error."

# ---------------------------
# 3. STRICT UNIVERSAL BID SCRAPER (FIXED)
# ---------------------------
def scrape_agency_bids(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        found_bids = []
        
        # Noise list to remove sub-files and non-titles
        noise = [
            "report", "photos", "sheet", "cards", "calculations", "addendum", 
            "plans", "manual", "package", "response", "geotechnical", 
            "reference only", "asbestos", "structural", "supplemental"
        ]

        for element in soup.find_all(['b', 'strong', 'a', 'td', 'li']):
            text = " ".join(element.get_text().split()).strip()
            
            # Check for Project IDs (24-, RFB-, etc.)
            is_id = any(p in text for p in ["21-", "22-", "23-", "24-", "25-", "RFB-IS-", "RFP-"])
            
            if is_id:
                # Capture LA County row text
                if element.name == 'td' or element.name == 'a':
                    parent_row = element.find_parent('tr')
                    if parent_row:
                        text = " ".join(parent_row.get_text(separator=" ").split())
                
                # REJECT lines containing any noise words (Specifically for DGS cleanup)
                if not any(n in text.lower() for n in noise):
                    # Clean up and shorten strings
                    clean_title = text.split("Powered by")[0].split("Contact Us")[0].strip()
                    if len(clean_title) > 12:
                        found_bids.append(f"📄 {clean_title}")
        
        return list(dict.fromkeys(found_bids)) if found_bids else ["❓ No primary project titles found."]
    except:
        return ["⚠️ Connection error."]

# ---------------------------
# 4. MAIN APP LOGIC (LOCKED UI)
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
        status = st.session_state.status_flag.upper() if st.session_state.status_flag else "UNKNOWN"
        if "CLOSED" in status:
            st.error(f"● STATUS: {status} | Deadline: {st.session_state.due_date}")
        else:
            st.success(f"● STATUS: {status} | DUE: {st.session_state.due_date}")
        st.write(f"**🏛️ AGENCY:** {st.session_state.agency_name}"); st.write(f"**📄 BID NAME:** {st.session_state.project_title}")
        st.divider()
        b1, b2 = st.tabs(["📖 Scope of Work", "🛠️ Specifications"])
        with b1: st.info(run_ai(doc, "Summarize scope.", is_scope=True))
        with b2: st.success(run_ai(doc, "List ONLY IT hardware."))
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
            with st.spinner("Extracting Main Project Names..."):
                for b in scrape_agency_bids(url_input): st.write(b)

with st.sidebar:
    st.header("Project Performance")
    st.metric("Total Est. Time Saved", f"{st.session_state.total_saved} mins")
    st.caption("UCR Master of Science - Jeffrey Gaspar")
