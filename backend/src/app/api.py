import logging
import uuid
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from src.models.schemas import ChatRequest, ChatResponse
from src.app.agent import get_sql_agent
from src.utils.guard import check_user_input, REFUSAL_MESSAGE

logger = logging.getLogger(__name__)

router = APIRouter()


@lru_cache(maxsize=1)
def get_agent():
    """Tạo agent ở lần gọi đầu tiên rồi tái sử dụng (DB tắt không làm sập app lúc khởi động)."""
    return get_sql_agent()


def _to_text(content) -> str:
    """Gemini có thể trả content dạng list các block thay vì str."""
    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())
    blocked_reason = check_user_input(request.question)
    if blocked_reason:
        logger.warning("Câu hỏi bị chặn (%s): %r", blocked_reason, request.question[:200])
        return ChatResponse(answer=REFUSAL_MESSAGE, thread_id=thread_id)

    try:
        agent = get_agent()
    except Exception:
        logger.exception("Không khởi tạo được agent")
        raise HTTPException(status_code=503, detail="Dịch vụ chưa sẵn sàng, vui lòng thử lại sau.")

    try:
        # ainvoke không chặn event loop (tool đồng bộ chạy trong thread pool)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": request.question}]},
            config={"configurable": {"thread_id": thread_id},
                    "recursion_limit": 20},
        )

        final_response = ""
        for message in reversed(result["messages"]):
            if message.type == "ai" and message.content:
                final_response = _to_text(message.content)
                break

        return ChatResponse(answer=final_response, thread_id=thread_id)

    except Exception:
        logger.exception("Lỗi khi xử lý /chat")
        raise HTTPException(status_code=500, detail="Lỗi nội bộ khi xử lý câu hỏi.")
