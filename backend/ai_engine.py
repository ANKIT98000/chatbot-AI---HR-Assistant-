import io
import os
import logging
import re
from typing import List, Tuple, Optional
from pypdf import PdfReader

from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEndpointEmbeddings  
from langchain_google_genai import ChatGoogleGenerativeAI        
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from backend.config import DATABASE_URL

logger = logging.getLogger(__name__)

class ResumeAssistant:
    def __init__(self):
        self.embeddings = HuggingFaceEndpointEmbeddings(model="sentence-transformers/all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
        
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name="hr_resumes",
            connection=DATABASE_URL,
            use_jsonb=True,
        )
        self._init_models()

    def _init_models(self):
        self.model = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.01,
            google_api_key=os.getenv("GOOGLE_API_KEY") 
        )
        parser = StrOutputParser()

        self.ats_chain = PromptTemplate(
            template=("""
                You are an expert HR AI Assistant. Your job is to screen the candidate's Resume. 
                The HR professional will only read this for 5-7 seconds. NEVER generate paragraphs. Output strictly in the template below.
                
                CRITICAL SCORING RULE (BE BRUTALLY HONEST): 
                - Be extremely STRICT and CRITICAL when calculating the ATS MATCH SCORE and JD MATCH.
                - Do NOT give high scores easily. You are serving the HR, not pleasing the candidate.
                - Average resumes should score between 60-70.
                - Only exceptional resumes with perfect formatting, highly relevant experience, measurable achievements, and exact skill matches should score above 75.
                - Deduct points heavily for missing contact info, vague project descriptions, lack of quantifiable achievements, or irrelevant experience.
                - If a JOB DESCRIPTION is provided, evaluate strictly. If core skills from the JD are missing, the score MUST drop significantly (below 50).
                
                CRITICAL: DO NOT output any extra text, notes, or explanations below the template.

JOB DESCRIPTION:
{job_description}

Template:(ALL LINE MUST BE COME IN NEW LINE)
👤 NAME: [Candidate Name] (AFTER NAME NEXT LINE MUST BE COME IN NEW LINE)
                      
📞 PHONE: [Phone Number or 'N/A'](AFTER PHONE NEXT LINE MUST BE COME IN NEW LINE)
                      
📧 EMAIL: [Email Address or 'N/A'](AFTER EMAIL NEXT LINE MUST BE COME IN NEW LINE)
                      
📊 ATS MATCH SCORE: [Calculated Score]/100 - [1 brutally honest reason for the score/deduction](AFTER ATS NEXT LINE MUST BE COME IN NEW LINE)

📋 JD MATCH: [If JD provided: Score/100, Strong/Partial/Poor, Matching/Missing Skills. If no JD: 'No JD Provided'](AFTER JD MATCH NEXT LINE MUST BE COME IN NEW LINE)
                      
💼 EXPERIENCE: [Total Years with company name if no exp then add Fresher] | [if Fresher then dont add Current Title] (AFTER EXPERIENCE NEXT LINE MUST BE COME IN NEW LINE)
                      
🎯 TOP 3 SKILLS MATCH: [Skill 1], [Skill 2], [Skill 3], if more then add more if needed  (AFTER SKILLS NEXT LINE MUST BE COME IN NEW LINE)
                      
✅ Projects: [projects with time or key technologies] (AFTER Projects NEXT LINE MUST BE COME IN NEW LINE)
                      
⚠️ RED FLAG: [1 short strict sentence on missing skill, bad formatting, or write 'None'] 

---
Candidate Resume:
{resume}
"""
            ),
            input_variables=['job_description', 'resume']
        ) | self.model | parser

        self.qa_chain = PromptTemplate(
            template=(
                "You are an expert HR AI Assistant. Answer the user's question based ONLY on the Context, Conversation History, and Job Description (if provided) below.\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. DIRECT ANSWER ONLY: Give the final answer immediately. Do NOT output your internal reasoning.\n"
                "2. EXPLICIT JD MATCHING (CRITICAL): If a Job Description is provided, you MUST explicitly state whether the candidate is a 'Strong Match', 'Partial Match', or 'Poor Match'. You MUST generate a 'JD Match Score' (out of 100) based strictly on how their skills align with the JD requirements. Clearly list the 'Matching Skills' and 'Missing Skills'.\n"
                "3. PRONOUN RESOLUTION (CRITICAL): If the user query uses 'he', 'she', 'his', 'her', or 'him', you MUST scan the CONVERSATION HISTORY from top to bottom and find the candidate whose name appears at the ABSOLUTE BOTTOM / LAST in the history text. Answer ONLY for that bottom-most candidate.\n"
                "4. ATS SCORE: Always retrieve the general ATS MATCH SCORE from the header tags in the context chunks.\n"
                "5. LIVE RESPONSE: Extract requested details dynamically from the raw resume text inside the context chunks.\n"
                "6. NO EXTRA TEXT: Provide exactly what the user asked for and nothing else.\n\n"
                "JOB DESCRIPTION:\n{job_description}\n\n"
                "CONVERSATION HISTORY:\n{history}\n\n"
                "CONTEXT (Resume Text Chunks):\n{context}\n\n"
                "QUESTION: {question}\nANSWER:"
            ),
            input_variables=['job_description', 'history', 'context', 'question']
        ) | self.model | parser

    def process_pdf(self, filename: str, file_bytes: bytes, job_description: str = "") -> Tuple[Optional[str], List[Document]]:
        try:
            pdf_stream = io.BytesIO(file_bytes)
            pdf_reader = PdfReader(pdf_stream)
            resume_text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text()])
            
            if len(resume_text.strip()) < 50:
                return None, []

            jd_text = job_description if job_description.strip() else "None provided."
            raw_ats_info = self.ats_chain.invoke({'job_description': jd_text, 'resume': resume_text}).strip()
            
            name_match = re.search(r'👤 NAME:\s*([^\n]+)', raw_ats_info, re.IGNORECASE)
            score_match = re.search(r'ATS MATCH SCORE:\s*([^\n]+)', raw_ats_info, re.IGNORECASE)
            jd_match = re.search(r'📋 JD MATCH:\s*([^\n]+)', raw_ats_info, re.IGNORECASE)
            
            candidate_name = name_match.group(1).strip() if name_match else filename.replace('.pdf', '')
            ats_score = score_match.group(1).strip() if score_match else "N/A"
            jd_score = jd_match.group(1).strip() if jd_match else "N/A"

            header = f"\n=== [CANDIDATE NAME: {candidate_name.upper()} | ATS SCORE: {ats_score} | JD MATCH: {jd_score}] ===\n"
            
            chunks = self.text_splitter.split_text(resume_text)
            docs = [Document(page_content=header + chunk, metadata={"name": candidate_name}) for chunk in chunks]
                
            return raw_ats_info, docs
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            return None, []

    def update_db(self, docs: List[Document]):
        if not docs: return
        self.vector_store.add_documents(docs)

    def ask(self, question: str, history: list = None, job_description: str = "") -> str:
        try:
            docs = self.vector_store.similarity_search(question, k=25)
            if not docs: return "Boss, database khali hai, pehle resume upload kijiye."
            context = "\n\n".join([d.page_content for d in docs])
            
            hist_str = ""
            if history:
                for h in history[-4:]:
                    try:
                        role = h.role if hasattr(h, 'role') else h.get('role', 'unknown')
                        content = h.content if hasattr(h, 'content') else h.get('content', '')
                        hist_str += f"{role.capitalize()}: {content}\n"
                    except AttributeError:
                        pass
            if not hist_str.strip():
                hist_str = "No previous history."
            
            jd_text = job_description if job_description.strip() else "No Job Description provided."
                
            return self.qa_chain.invoke({
                'job_description': jd_text, 
                'history': hist_str, 
                'context': context, 
                'question': question
            }).strip()
        except Exception as e:
            logger.error(f"Ask Error: {e}")
            return f"Error fetching answer: {str(e)}"

    def clear_db(self):
        try:
            self.vector_store.drop_tables()
            
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name="hr_resumes",
                connection=DATABASE_URL,
                use_jsonb=True,
            )
            logger.info("Database cleared and re-initialized successfully!")
        except Exception as e:
            logger.error(f"Clear DB Error: {e}")