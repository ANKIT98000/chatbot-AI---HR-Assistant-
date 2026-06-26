import streamlit as st
import requests

API_URL = "http://127.0.0.1:8080"
st.set_page_config(page_title="AI HR Screener", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("👨‍💼 Enterprise Resume Screener")

with st.sidebar:
    st.header("📂 Bulk Upload Resumes")
    st.caption("Upload PDFs or ZIP files containing multiple PDFs!")
    
    # Allows multiple files selection at once
    uploaded_files = st.file_uploader("Select Files", type=["pdf", "zip"], accept_multiple_files=True)
    
    if st.button("Process Files", type="primary") and uploaded_files:
        with st.spinner("Processing files into Remote Database..."):
            
            # Prepare files payload
            files_payload = [
                ("files", (f.name, f.getbuffer(), "application/zip" if f.name.endswith('.zip') else "application/pdf")) 
                for f in uploaded_files
            ]
            
            try:
                # Increased timeout to 120 seconds for large zip files
                res = requests.post(f"{API_URL}/upload/", files=files_payload, timeout=120)
                
                if res.status_code == 200:
                    data = res.json()
                    st.success(f"Processed {len(data['ats_responses'])} resumes!")
                    if data['failed_files']:
                        st.error(f"Failed to read: {', '.join(data['failed_files'])}")
                    
                    summary = "### 📊 Processed Candidates:\n"
                    for name, ats in data['ats_responses'].items():
                        summary += f"**{name}**\n```text\n{ats}\n```\n"
                    st.session_state.messages.append({"role": "assistant", "content": summary})
                else:
                    st.error(f"Backend Error! Status Code: {res.status_code}")
            except Exception as e:
                st.error(f"Network Error: Could not connect to backend. {str(e)}")

    if st.button("🧹 Clear Database"):
        try:
            requests.post(f"{API_URL}/clear/")
            st.session_state.messages = []
            st.success("Remote Database Cleared!")
            st.rerun()
        except:
            st.error("Make sure Backend is running.")

# Chat Interface
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_q = st.chat_input("Ask anything (e.g., 'Compare ATS scores in a table')")

if user_q:
    st.session_state.messages.append({"role": "user", "content": user_q})
    with st.chat_message("user"): 
        st.markdown(user_q)
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing Database..."):
            try:
                # 60 sec timeout for heavy sorting questions
                response = requests.post(f"{API_URL}/ask/", json={"question": user_q}, timeout=60)
                if response.status_code == 200:
                    ans = response.json().get("answer", "No answer found.")
                else:
                    ans = "❌ Backend returned an error."
            except Exception as e:
                ans = f"❌ Network Error: Backend might be down or processing took too long."
            
            st.markdown(ans)
            st.session_state.messages.append({"role": "assistant", "content": ans})