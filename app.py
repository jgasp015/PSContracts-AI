import streamlit as st
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup
import os 

# ---------------------------
# 1. STATE & RESET (UNTOUCHED)
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
# 2. THE ENGINE (UNTOUCHED)
# ---------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def run_ai(text, prompt, is_compliance=False, is_header=False, is_search=False, is_scope=False):
    if not GROQ_API_KEY:
        return "⚠️ API Key missing in Railway Variables."
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    ctx = text[:60000] 
    today = "April 22, 2026"
    if is_compliance:
        system_rules = "RULES: 1. BE DIRECT. 2. Extract 'Definition' and 'Objective' for SLAs. 3. SIMPLE ENGLISH."
    elif is_header:
        # Fixed logic for 2017 vs 2026 dates
        system_rules = f"RULES: 1. Answer in 5 words or less. 2. Compare the document date to {today}. 3. If the year is BEFORE 2026, you MUST say 'CLOSED'."
    elif is_search:
        system_rules = "You are a helpful assistant. Answer specifically based on the document provided."
    elif is_scope:
        system_rules = "CORE INSTRUCTION: 1. ANALYZE the whole text. 2. List specific QUANTITIES and ACTION TASKS. 3. NO repetition."
    else:
        system_rules = "CORE INSTRUCTION: 1. List ONLY IT gear names. 2. START IMMEDIATELY with vertical bullets (*)."
    payload = {"model": "llama-3.1-8b-instant", "messages": [{"role": "system", "content": system_rules}, {"role": "user", "content": f"Text: {ctx}\n\nTask: {prompt}"}], "temperature": 0.0}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=35)
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return "⚠️ Timeout or Connection Error."

# ---------------------------
# 3. SELECTIVE AGENCY SCRAPER (UPDATED)
# ---------------------------
def scrape_agency_bids(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        found_bids = []
        
        # Scans common tags for Project IDs (e.g., 24-XXXX, 25-XXXX)
        for element in soup.find_all(['b', 'strong', 'li', 'td', 'span', 'div']):
            text = element.get_text().strip()
            
            # Identify the specific Project Title row
            if any(text.startswith(year) for year in ["21-", "22-", "23-", "24-", "25-"]):
                # Look for the primary PDF link associated with this title
                link = element.find('a', href=True) or element.find_next('a', href=True)
                
                if link and ".pdf" in link['href'].lower():
                    href = link['href']
                    full_url = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                    # Format as a clean Project Title link
                    found_bids.append(f"📄 [{text}]({full_url})")
        
        # Remove duplicates while maintaining order
        return list(dict.fromkeys(found_bids)) if found_bids else ["❓ No specific Project Titles found on this page."]
    except:
        return ["⚠️ Connection error. Please check the URL."]

# ---------------------------
# 4. MAIN APP LOGIC (UI)
# ---------------------------
st.title("🏛️ Public Sector Contracts AI")
if st.button("🏠 Home / Reset App"):
    hard_reset()
st.divider()

if st.session_state.active_bid_text:
    doc = st.session_state.active_bid_text
    st.subheader("🔍 Search this Document")
    user_query = st.text_input("Ask a specific question about this contract:", key="q_bar")
    if user_query:
        st.write(f"**Answer:** {run_ai(doc, user_query, is_search=True)}")
    st.divider()
    
    if st.session_state.analysis_mode == "Reporting":
        # COMPLIANCE SECTION (UNTOUCHED)
        st.subheader("📊 SLA & Non-Compliance")
        st.info(run_ai(doc, "Identify SLAs, uptime %, and triggers.", is_compliance=True))
    else:
        # BID DOCUMENT SECTION (UNTOUCHED)
        if not st.session_state.get("agency_name"):
            with st.status("🏗️ Analyzing Document..."):
                st.session_state.status_flag = run_ai(doc, "Is the bid OPEN or CLOSED?", is_header=True)
                st.session_state.agency_name = run_ai(doc, "Agency name?", is_header=True)
                st.session_state.project_title = run_ai(doc, "Project Title?", is_header=True)
                st.session_state.due_date = run_ai(doc, "Deadline date?", is_header=True)
            st.rerun()
        st.subheader("🏛️ Project Snapshot")
        status = st.session_state.status_flag.upper() if st.session_state.status_flag else "UNKNOWN"
        if "CLOSED" in status:
            st.error(f"● STATUS: {status} (Deadline was {st.session_state.due_date})")
        else:
            st.success(f"● STATUS: {status} | DUE: {st.session_state.due_date}")
        st.write(f"**🏛️ AGENCY:** {st.session_state.agency_name}")
        st.write(f"**📄 BID NAME:** {st.session_state.project_title}")
        st.divider()
        b1, b2 = st.tabs(["📖 Scope of Work", "🛠️ Specifications"])
        with b1: st.info(run_ai(doc, "Summarize the scope.", is_scope=True))
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
        url = st.text_input("Agency URL (Extracts Project Titles):", key="url_bar")
        if url:
            with st.spinner("Extracting Main Project Titles..."):
                for b in scrape_agency_bids(url): st.write(b)

with st.sidebar:
    st.header("Project Performance")
    st.metric("Total Est. Time Saved", f"{st.session_state.total_saved} mins")
    st.caption("UCR Master of Science - Jeffrey Gaspar")
