from typing import Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000) # question phải dài 1–1000 ký tự
    # ID phiên hội thoại; client nên gửi lại cùng giá trị để giữ ngữ cảnh
    thread_id: Optional[str] = Field(default=None, max_length=64)

class ChatResponse(BaseModel):
    answer: str
    thread_id: str
