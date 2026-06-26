from pydantic import BaseModel
from typing import Dict, List

class QuestionRequest(BaseModel):
    question: str

class AssistantResponse(BaseModel):
    answer: str

class UploadResponse(BaseModel):
    ats_responses: Dict[str, str]
    failed_files: List[str]