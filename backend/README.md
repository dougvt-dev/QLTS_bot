# Phát triển API Text-to-SQL cho Quản lý tài sản

Dựa trên code thử nghiệm từ `experiments/qlts-db.ipynb`, chúng ta sẽ xây dựng một API RESTful bằng FastAPI. API này sẽ nhận câu hỏi tự nhiên từ người dùng, sử dụng agent để truy vấn database SQL Server và trả về kết quả. 

## Cấu trúc thư mục đề xuất

Chúng ta sẽ tận dụng cấu trúc thư mục hiện có trong `src` và bổ sung các thành phần cần thiết:

```text
src/
├── main.py                # Điểm vào của ứng dụng FastAPI
├── app/
│   ├── api.py             # Định nghĩa các routes/endpoints (vd: POST /chat)
│   └── agent.py           # Logic LangChain/LangGraph agent từ notebook
├── models/
│   └── schemas.py         # Pydantic models cho Request/Response API
└── utils/
    └── config.py          # Quản lý cấu hình, biến môi trường (Database, API Keys)
```

## Các thay đổi chính (Proposed Changes)

### 1. Cập nhật `requirements.txt`
Bổ sung các thư viện cần thiết cho API và kết nối database:
- `fastapi`, `uvicorn` (cho API server)
- `pydantic` (cho data validation)
- `pyodbc`, `sqlalchemy` (cho kết nối SQL Server)
- `langchain-google-genai` (cho model Gemini)
- `python-dotenv` (cho biến môi trường)

### 2. Tạo file môi trường `.env`
Di chuyển các thông tin nhạy cảm từ code vào file `.env` (không đưa lên git) hoặc quản lý cấu hình:
- Cấu hình SQL Server (`DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASS`)
- Cấu hình Gemini (`GOOGLE_API_KEY`)

### 3. `src/utils/config.py`
Tạo module quản lý cấu hình và khởi tạo chuỗi kết nối Database (`connection_url`).

### 4. `src/app/agent.py`
Đưa logic khởi tạo model, kết nối DB và thiết lập tool/agent từ notebook vào một class hoặc các function quản lý vòng đời rõ ràng:
- Khởi tạo `SQLDatabase` và `ChatGoogleGenerativeAI`.
- Cấu hình `SQLDatabaseToolkit` và lấy các tools.
- Tái tạo `system_prompt` và hàm `create_agent()`.

### 5. `src/models/schemas.py`
Tạo request model:
```python
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
```

### 6. `src/app/api.py` & `src/main.py`
Tạo endpoint POST `/api/chat` nhận câu hỏi, gọi agent xử lý và trả về câu trả lời. Gắn router vào ứng dụng FastAPI trong `main.py`.

## User Review Required

> [!IMPORTANT]
> **Quyết định về Framework API**: Tôi đề xuất sử dụng **FastAPI** vì nó hiện đại, nhanh và hỗ trợ tốt cho Python. Bạn có đồng ý sử dụng FastAPI không?
> 
> **Quản lý mật khẩu**: Trong notebook, mật khẩu có chứa ký tự `@` được encode thành `%40` cho URL. Tôi sẽ sử dụng `urllib.parse.quote_plus` để tự động xử lý các ký tự đặc biệt này, giúp ứng dụng an toàn và linh hoạt hơn với mọi loại mật khẩu.

## Open Questions

> [!NOTE]
> 1. Bạn có muốn lưu trữ lịch sử chat của user không? Hay API chỉ xử lý từng câu hỏi riêng lẻ không có ngữ cảnh trước đó (stateless)?
> 2. Có thiết lập bảo mật API Key (Authentication) nào cho endpoint API này không, hay có thể truy cập công khai trong nội bộ mạng?

## Verification Plan

### Automated Tests
1. Cài đặt các thư viện mới (nếu bạn đồng ý, tôi sẽ chạy lệnh `pip install -r requirements.txt`).
2. Khởi chạy server FastAPI bằng lệnh `uvicorn src.main:app --reload`.
3. Gửi request POST thử nghiệm tới API `/api/chat` với câu hỏi mẫu (ví dụ: "Có bao nhiêu loại tài sản ?") và kiểm tra JSON response trả về.

### Manual Verification
- Bạn có thể dùng Postman, cURL hoặc Swagger UI tích hợp sẵn của FastAPI (truy cập `http://localhost:8000/docs`) để thử nghiệm gửi câu hỏi và xem kết quả.
