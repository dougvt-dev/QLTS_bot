"""Lớp bảo vệ: lọc đầu vào người dùng và kiểm tra câu SQL trước khi thực thi."""
import logging
import re
import unicodedata
from typing import Callable, Iterable, Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 1000
MAX_ROWS = 100

REFUSAL_MESSAGE = (
    "Xin lỗi, mình không thể xử lý yêu cầu này. "
    "Bạn có thể hỏi mình về dữ liệu tài sản hoặc các kiến thức chung, hãy thử đặt lại câu hỏi nhé."
)

# ---------------------------------------------------------------------------
# 1. Lọc đầu vào (chống prompt injection phổ biến)
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    # Tiếng Anh
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions?|prompts?|rules?)",
    r"disregard (all |any |the )?(previous|prior|above|earlier)",
    r"forget (all |everything |your )?(previous|prior|above|instructions?|rules?)",
    r"(reveal|show|print|repeat|leak|display|tell me) (me )?(your |the )?(system|initial|hidden|original) (prompt|instructions?|message)",
    r"what (is|are) your (system )?(prompt|instructions?|rules?)",
    r"you are now\b",
    r"\bjailbreak\b",
    r"\bdeveloper mode\b",
    r"\bdan mode\b",
    r"override (the |your )?(rules?|instructions?|safety)",
    # Tiếng Việt (đã bỏ dấu, xem _normalize)
    r"bo qua (tat ca |moi |cac )?(huong dan|chi dan|quy tac|lenh|cau lenh) (truoc|o tren|ban dau)",
    r"quen (het |tat ca |cac )?(huong dan|chi dan|quy tac|lenh) (truoc|o tren|ban dau)",
    r"(tiet lo|hien thi|in ra|cho (toi|minh) xem|lap lai) (system )?prompt",
    r"(tiet lo|hien thi|in ra|cho (toi|minh) xem|lap lai) (huong dan|chi dan) (he thong|goc|ban dau)",
    r"tu bay gio (ban|may) (la|hay)",
    r"che do (nha phat trien|developer|khong gioi han)",
    # Thẻ/định dạng giả mạo vai trò hệ thống
    r"</?\s*(system|assistant|instructions?|user_question)\s*>",
    r"\[/?(inst|system)\]",
    r"<\|[a-z_]+\|>",
    r"^\s*(system|assistant)\s*:",
    # Lệnh SQL phá hoại viết thẳng trong câu hỏi
    r"\b(drop|truncate|alter)\s+(table|database|schema)\b",
    r"\b(delete\s+from|insert\s+into)\b",
    r"\bxp_cmdshell\b",
    r";\s*(drop|delete|update|insert|exec|shutdown)\b",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _INJECTION_PATTERNS]

# Ký tự tàng hình thường dùng để lách bộ lọc
_INVISIBLE_CHARS = re.compile("[​-‏‪-‮⁠-⁤﻿]")


def _normalize(text: str) -> str:
    """Chuẩn hóa: bỏ ký tự tàng hình, bỏ dấu tiếng Việt, hạ chữ thường, gọn khoảng trắng."""
    text = _INVISIBLE_CHARS.sub("", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[ \t]+", " ", text)
    return text.lower().strip()


def check_user_input(question: str) -> Optional[str]:
    """Trả về lý do bị chặn, hoặc None nếu câu hỏi hợp lệ."""
    if not question or not question.strip():
        return "empty"
    if len(question) > MAX_QUESTION_LENGTH:
        return "too_long"

    # Kiểm tra cả bản gốc lẫn bản đã chuẩn hóa để bắt được cả tiếng Việt có/không dấu
    for candidate in (question, _normalize(question)):
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(candidate):
                return f"injection:{pattern.pattern[:40]}"
    return None


# ---------------------------------------------------------------------------
# 2. Kiểm tra câu SQL
# ---------------------------------------------------------------------------
class UnsafeSQLError(ValueError):
    """Câu SQL vi phạm chính sách; message được trả lại cho model để sửa."""


_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(xp_\w+|sp_\w+|openrowset|opendatasource|openquery|exec|execute|waitfor|"
    r"shutdown|bulk|backup|restore|grant|revoke|deny|dbcc|reconfigure)\b",
    re.IGNORECASE,
)

_FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
    exp.Merge, exp.TruncateTable, exp.Command, exp.Into, exp.Use,
)

_STRING_LITERAL = re.compile(r"N?'(?:[^']|'')*'", re.IGNORECASE)


def _strip_literals(sql: str) -> str:
    return _STRING_LITERAL.sub("''", sql)


def validate_sql(sql: str, allowed_tables: Iterable[str]) -> str:
    """Kiểm tra câu SQL; trả về câu SQL đã làm sạch hoặc raise UnsafeSQLError."""
    if not sql or not sql.strip():
        raise UnsafeSQLError("Câu truy vấn rỗng.")

    # Bỏ hàng rào markdown nếu model lỡ thêm vào
    cleaned = re.sub(r"^\s*```(?:sql)?\s*|\s*```\s*$", "", sql.strip(), flags=re.IGNORECASE)
    cleaned = cleaned.rstrip().rstrip(";").strip()

    no_literals = _strip_literals(cleaned)

    if "--" in no_literals or "/*" in no_literals or "*/" in no_literals:
        raise UnsafeSQLError("Không được dùng chú thích (-- hoặc /* */) trong câu truy vấn.")
    if ";" in no_literals:
        raise UnsafeSQLError("Chỉ được phép một câu lệnh duy nhất, không dùng dấu chấm phẩy.")
    match = _FORBIDDEN_KEYWORDS.search(no_literals)
    if match:
        raise UnsafeSQLError(f"Từ khóa/hàm không được phép: {match.group(0)}.")

    try:
        statements = sqlglot.parse(cleaned, read="tsql")
    except SqlglotError as e:
        raise UnsafeSQLError(f"Không phân tích được câu SQL: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise UnsafeSQLError("Chỉ được phép một câu lệnh duy nhất.")
    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        raise UnsafeSQLError("Chỉ được phép câu lệnh SELECT.")

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise UnsafeSQLError(f"Câu lệnh không được phép: {type(node).__name__}.")

    # Bảng được phép (không phân biệt hoa thường); bỏ qua tên CTE
    allowed = {t.lower() for t in allowed_tables}
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in cte_names:
            continue
        if table.args.get("catalog") or (table.db and table.db.lower() != "dbo"):
            raise UnsafeSQLError(f"Không được truy cập schema/CSDL khác: {table.sql(dialect='tsql')}.")
        if name not in allowed:
            raise UnsafeSQLError(f"Bảng '{table.name}' không tồn tại hoặc không được phép truy vấn.")

    # Chặn kéo toàn bộ bảng: phải có TOP, hoặc là truy vấn tổng hợp
    _enforce_row_limit(tree)
    return cleaned


def _enforce_row_limit(tree: exp.Expression) -> None:
    limit = tree.find(exp.Limit) or tree.find(exp.Fetch)
    if limit is not None:
        value = limit.args.get("expression") or limit.args.get("count")
        if isinstance(value, exp.Literal) and value.is_int and int(value.this) > MAX_ROWS:
            raise UnsafeSQLError(f"TOP tối đa {MAX_ROWS} dòng.")
        return
    if tree.find(exp.AggFunc) is not None or tree.find(exp.Group) is not None:
        return
    raise UnsafeSQLError(f"Câu truy vấn phải có TOP (tối đa {MAX_ROWS}) hoặc là truy vấn tổng hợp (COUNT/SUM/...).")


def make_guarded_query_tool(query_tool, get_allowed_tables: Callable[[], Iterable[str]]):
    """Bọc tool sql_db_query: kiểm tra SQL trước, chỉ khi hợp lệ mới thực thi."""
    from langchain_core.tools import StructuredTool

    def guarded_query(query: str) -> str:
        try:
            safe_sql = validate_sql(query, get_allowed_tables())
        except UnsafeSQLError as e:
            logger.warning("SQL bị chặn: %s | %r", e, query)
            return f"Error: Câu truy vấn bị từ chối. {e} Hãy viết lại câu SELECT hợp lệ."
        return query_tool.invoke({"query": safe_sql})

    return StructuredTool.from_function(
        func=guarded_query,
        name=query_tool.name,
        description=query_tool.description,
        args_schema=query_tool.args_schema,
    )
