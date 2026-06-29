import logging
import zipfile
import io
from typing import List
# Form import karna zaroori hai
from fastapi import FastAPI, UploadFile, File, Form
from models import QuestionRequest, AssistantResponse, UploadResponse
from ai_engine import ResumeAssistant

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Resume Backend Cloud")
ai = ResumeAssistant()

@app.post("/upload/", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    job_description: str = Form("")  # Upload ke sath JD accept karne ke liye
):
    ats_results = {}
    all_docs = []
    failed = []

    for file in files:
        try:
            file_bytes = await file.read()
            
            if file.filename.lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                    for z_name in z.namelist():
                        if z_name.lower().endswith(".pdf"):
                            pdf_bytes = z.read(z_name)
                            # process_pdf ko jd bhi pass kiya
                            ats_info, docs = ai.process_pdf(z_name, pdf_bytes, job_description)
                            if ats_info and docs:
                                ats_results[docs[0].metadata["name"]] = ats_info
                                all_docs.extend(docs)
                            else:
                                failed.append(z_name)
                                
            elif file.filename.lower().endswith(".pdf"):
                ats_info, docs = ai.process_pdf(file.filename, file_bytes, job_description)
                if ats_info and docs:
                    ats_results[docs[0].metadata["name"]] = ats_info 
                    all_docs.extend(docs)
                else:
                    failed.append(file.filename)
            else:
                failed.append(file.filename) 
                
        except Exception as e:
            logging.error(f"Upload Loop Error: {e}")
            failed.append(file.filename) 

    if all_docs:
        ai.update_db(all_docs)
        
    return UploadResponse(ats_responses=ats_results, failed_files=failed)

@app.post("/ask/", response_model=AssistantResponse)
async def ask_bot(request: QuestionRequest):
    ans = ai.ask(request.question, request.history, request.job_description)
    return AssistantResponse(answer=ans)

@app.post("/clear/")
async def clear_bot():
    ai.clear_db()
    return {"status": "Supabase Collection Cleared"}