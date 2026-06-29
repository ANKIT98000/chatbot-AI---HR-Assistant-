from pydantic import BaseModel
from typing import Dict, List, Optional

class Message(BaseModel):
    role: str
    content: str

class QuestionRequest(BaseModel):
    question: str
    history: Optional[List[Message]] = []
    job_description: Optional[str] = ""  # Ye naya field add kiya

class AssistantResponse(BaseModel):
    answer: str

class UploadResponse(BaseModel):
    ats_responses: Dict[str, str]
    failed_files: List[str]