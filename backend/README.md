# Backend – Chatbot Text-to-SQL quản lý tài sản

API FastAPI cho phép hỏi đáp bằng ngôn ngữ tự nhiên về dữ liệu tài sản/nội thất (SQL Server) và trò chuyện, giải đáp kiến thức chung. Sử dụng LangChain/LangGraph agent với Google Gemini.

## Tính năng
- Tra cứu dữ liệu tài sản bằng tiếng Việt: agent tự xem schema, viết và chạy câu `SELECT`, rồi diễn giải kết quả.
- Trò chuyện và trả lời kiến thức chung (không dùng DB).
- Nhớ ngữ cảnh hội thoại theo `thread_id`.
- Nhiều lớp bảo vệ: lọc prompt injection, kiểm tra SQL trước khi chạy, DB chỉ cấp quyền đọc.

## Cấu trúc thư mục

```text
backend/
├── src/
│   ├── main.py            # Điểm vào FastAPI, gắn router /api
│   ├── app/
│   │   ├── api.py         # Endpoint POST /api/chat, điều phối luồng xử lý
│   │   └── agent.py       # Dựng model Gemini, tools SQL và agent
│   ├── models/
│   │   └── schemas.py     # Pydantic: ChatRequest, ChatResponse
│   └── utils/
│       ├── config.py      # Đọc biến môi trường, tạo chuỗi kết nối DB
│       ├── guard.py       # Lọc đầu vào + kiểm tra/chặn SQL nguy hiểm
│       └── prompt.py      # System prompt của agent
├── experiments/           # Notebook thử nghiệm (không đưa lên git)
├── requirements.txt       # Thư viện Python
├── .env.example           # Mẫu biến môi trường
└── README.md
```

## Luồng xử lý

```text
Client ── POST /api/chat ──► Pydantic (độ dài câu hỏi)
                              ──► check_user_input (lọc injection)
                              ──► agent (Gemini + tools, nhớ theo thread_id)
                                    ├─ kiến thức chung / chào hỏi → trả lời trực tiếp
                                    └─ cần dữ liệu → list_tables → schema → query
                                                         └─ validate_sql (guard) → SQL Server
                              ──► ChatResponse { answer, thread_id }
```

Các lớp phòng thủ theo thứ tự: schema Pydantic → bộ lọc injection → prompt bảo mật → `validate_sql` (chỉ một câu `SELECT`, không chú thích/`;`/`EXEC`, bảng hợp lệ, có `TOP` ≤ 100 hoặc truy vấn tổng hợp) → tài khoản DB chỉ có quyền `SELECT`.

## Yêu cầu
- Python 3.10+ (đã chạy với 3.12)
- **ODBC Driver 18 for SQL Server** (cài ở mức hệ điều hành, không qua pip)
- Truy cập được SQL Server và có Google API key (Gemini)

## Cài đặt và chạy

```bash
cd backend
pip install -r requirements.txt

cp .env.example .env      # rồi điền giá trị thật
uvicorn src.main:app --reload
```

Swagger UI: http://localhost:8000/docs

## Cấu hình (`.env`)

| Biến | Bắt buộc | Mô tả |
|---|---|---|
| `DB_SERVER` | có | Địa chỉ SQL Server |
| `DB_NAME` | có | Tên CSDL (vd: `QLTS`) |
| `DB_USER` | có | Tài khoản DB (khuyến nghị chỉ quyền `SELECT`) |
| `DB_PASS` | có | Mật khẩu DB |
| `GOOGLE_API_KEY` | có | API key Gemini |
| `MODEL_NAME` | không | Model Gemini, mặc định `gemini-2.5-flash-lite` |

> Không commit file `.env`. File này đã nằm trong `.gitignore`.

## API

### `POST /api/chat`

Request:
```json
{ "question": "Có bao nhiêu loại tài sản?", "thread_id": "tùy chọn" }
```
- `question`: 1–1000 ký tự.
- `thread_id`: không bắt buộc (tối đa 64 ký tự). Nếu bỏ trống, server tự sinh. Gửi lại cùng giá trị ở các lượt sau để giữ ngữ cảnh.

Response:
```json
{ "answer": "…", "thread_id": "…" }
```

| Mã | Ý nghĩa |
|---|---|
| 200 | Thành công (kể cả khi câu hỏi bị bộ lọc từ chối, `answer` là thông báo từ chối) |
| 422 | Dữ liệu đầu vào không hợp lệ |
| 503 | Chưa khởi tạo được agent (vd: không kết nối được DB) |
| 500 | Lỗi nội bộ khi xử lý |

Ví dụ:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Có bao nhiêu loại tài sản?"}'
```

## Lưu ý
- Lịch sử hội thoại lưu trong RAM (`InMemorySaver`): mất khi restart, không chia sẻ giữa nhiều worker.
- Chưa có xác thực và CORS; cần bổ sung trước khi mở cho người dùng bên ngoài.
- Agent được tạo ở request `/chat` đầu tiên, nên app vẫn khởi động được khi DB tạm thời không truy cập được.
