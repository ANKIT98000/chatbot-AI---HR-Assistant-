import streamlit as st
import requests

API_URL = "http://127.0.0.1:8080"
st.set_page_config(page_title="AI HR Screener", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "file_uploader_key" not in st.session_state:
    st.session_state.file_uploader_key = 0

st.title("👨‍💼 Enterprise Resume Screener")

with st.sidebar:
    # JD Field ko UPAR shift kar diya taaki upload se pehle set ho sake
    st.header("📝 Job Description (Optional)")
    st.caption("Add JD before processing to see JD Match Score")
    jd_input = st.text_area("Paste JD here...", height=150)
    
    st.divider()

    st.header("📂 Bulk Upload Resumes")
    st.caption("Upload PDFs or ZIP files containing multiple PDFs!")
    
    uploaded_files = st.file_uploader(
        "Select Files", 
        type=["pdf", "zip"], 
        accept_multiple_files=True, 
        key=f"uploader_{st.session_state.file_uploader_key}"
    )
    
    if st.button("Process Files", type="primary") and uploaded_files:
        with st.spinner("Processing files into Remote Database..."):
            files_payload = [
                ("files", (f.name, f.getbuffer(), "application/zip" if f.name.endswith('.zip') else "application/pdf")) 
                for f in uploaded_files
            ]
            
            try:
                # data param mein job_description bhej diya
                res = requests.post(f"{API_URL}/upload/", files=files_payload, data={"job_description": jd_input}, timeout=120)
                
                if res.status_code == 200:
                    data = res.json()
                    st.success(f"Processed {len(data['ats_responses'])} resumes!")
                    if data['failed_files']:
                        st.error(f"Failed to read: {', '.join(data['failed_files'])}")
                    
                    summary = "### 📊 Processed Candidates:\n"
                    for name, ats in data['ats_responses'].items():
                        summary += f"**{name}**\n\n{ats}\n\n---\n"
                    
                    st.session_state.messages.append({"role": "assistant", "content": summary})
                    
                    st.session_state.file_uploader_key += 1
                    st.rerun()
                else:
                    st.error(f"Backend Error! Status Code: {res.status_code}")
            except Exception as e:
                st.error(f"Network Error: Could not connect to backend. {str(e)}")

    st.divider()

    if st.button("🧹 Clear Database"):
        try:
            requests.post(f"{API_URL}/clear/")
            st.session_state.messages = []
            st.success("Remote Database Cleared!")
            st.rerun()
        except:
            st.error("Make sure Backend is running.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_q = st.chat_input("Ask anything (e.g., 'Who is the best match for this JD?')")

if user_q:
    history_payload = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    
    with st.chat_message("user"): 
        st.markdown(user_q)
    st.session_state.messages.append({"role": "user", "content": user_q})
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing Database..."):
            try:
                response = requests.post(
                    f"{API_URL}/ask/", 
                    json={
                        "question": user_q, 
                        "history": history_payload,
                        "job_description": jd_input 
                    }, 
                    timeout=60
                )
                if response.status_code == 200:
                    ans = response.json().get("answer", "No answer found.")
                else:
                    ans = "❌ Backend returned an error."
            except Exception as e:
                ans = f"❌ Network Error: Backend might be down or processing took too long."
            
            st.markdown(ans)
            st.session_state.messages.append({"role": "assistant", "content": ans})