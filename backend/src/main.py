from fastapi import FastAPI
from src.app.api import router as api_router
import logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Quản lý tài sản Text-to-SQL API",
    description="API cho phép truy vấn cơ sở dữ liệu bằng ngôn ngữ tự nhiên sử dụng LangChain và Gemini.",
    version="1.0.0"
)

# Thêm route cho API
app.include_router(api_router, prefix="/api", tags=["chat"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Text-to-SQL API. Visit /docs for more information."}
