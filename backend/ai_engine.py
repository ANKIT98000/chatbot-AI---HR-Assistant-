import io
import logging
import re
from typing import List, Tuple, Optional
from pypdf import PdfReader

from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace, HuggingFaceEndpointEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import DATABASE_URL

logger = logging.getLogger(__name__)

class ResumeAssistant:
    def __init__(self):
        self.embeddings = HuggingFaceEndpointEmbeddings(model="sentence-transformers/all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
        
        # SUPABASE (POSTGRES) CLOUD CONNECTION
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name="hr_resumes",
            connection=DATABASE_URL,
            use_jsonb=True,
        )
        self._init_models()

    def _init_models(self):
        llm = HuggingFaceEndpoint(repo_id="meta-llama/Meta-Llama-3-8B-Instruct", temperature=0.01)
        self.model = ChatHuggingFace(llm=llm)
        parser = StrOutputParser()

        self.ats_chain = PromptTemplate(
            template=(
                "Extract candidate details from the resume below. You MUST format your response exactly like this:\n"
                "Name: [Exact Name]\n"
                "ATS Score: [Score/100]\n"
                "Skills: [List]\n"
                "Experience: [Years]\n\n"
                "Resume:\n{resume}"
            ),
            input_variables=['resume']
        ) | self.model | parser

        self.qa_chain = PromptTemplate(
            template=(
                "You are an HR AI. Answer questions using ONLY the Context below.\n"
                "Context contains chunks of resumes. EACH chunk has a [CANDIDATE NAME and ATS SCORE] at the top.\n"
                "If asked to sort, compare, or list ATS scores, ALWAYS output a neat Markdown Table using the exact Names and Scores provided in the headers.\n\n"
                "CONTEXT:\n{context}\n\n"
                "QUESTION: {question}\nANSWER:"
            ),
            input_variables=['context', 'question']
        ) | self.model | parser

    def process_pdf(self, filename: str, file_bytes: bytes) -> Tuple[Optional[str], List[Document]]:
        try:
            pdf_stream = io.BytesIO(file_bytes)
            pdf_reader = PdfReader(pdf_stream)
            resume_text = "".join([page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text()])
            
            if len(resume_text.strip()) < 50:
                return None, []

            raw_ats_info = self.ats_chain.invoke({'resume': resume_text})
            
            # The Bulletproof Fix (Regex)
            name_match = re.search(r'Name:\s*([^\n]+)', raw_ats_info, re.IGNORECASE)
            score_match = re.search(r'ATS Score:\s*([^\n]+)', raw_ats_info, re.IGNORECASE)
            
            candidate_name = name_match.group(1).strip() if name_match else filename.replace('.pdf', '')
            ats_score = score_match.group(1).strip() if score_match else "N/A"

            header = f"\n=== [CANDIDATE NAME: {candidate_name.upper()} | ATS SCORE: {ats_score}] ===\n"
            
            chunks = self.text_splitter.split_text(resume_text)
            docs = [Document(page_content=header + chunk, metadata={"name": candidate_name}) for chunk in chunks]
                
            return raw_ats_info, docs
            
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            return None, []

    def update_db(self, docs: List[Document]):
        if not docs: return
        self.vector_store.add_documents(docs)

    def ask(self, question: str) -> str:
        try:
            docs = self.vector_store.similarity_search(question, k=15)
            if not docs: return "Boss, database khali hai, pehle resume upload kijiye."
            context = "\n\n".join([d.page_content for d in docs])
            return self.qa_chain.invoke({'context': context, 'question': question})
        except Exception as e:
            logger.error(f"Ask Error: {e}")
            return f"Error fetching answer: {str(e)}"

    def clear_db(self):
        try:
            # Supabase se collection udane ka sahi function
            self.vector_store.drop_tables()
        except Exception as e:
            logger.error(f"Clear DB Error: {e}")