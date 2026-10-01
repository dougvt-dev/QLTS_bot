from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from src.utils.config import CONNECTION_URL, MODEL_NAME 
from src.utils.prompt import sql_prompt
from src.utils.guard import make_guarded_query_tool
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware

def get_sql_agent():
    # Khởi tạo mô hình
    model = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0.4,
        max_tokens=None,
        timeout=60,
        max_retries=2,
    )

    middleware = SummarizationMiddleware(
        model=model,
        trigger=("tokens", 12000),
        keep=("messages", 20),
    )

    # Kết nối cơ sở dữ liệu
    db = SQLDatabase.from_uri(CONNECTION_URL, sample_rows_in_table_info=1)

    # Khởi tạo toolkit và lấy các tools
    toolkit = SQLDatabaseToolkit(db=db, llm=model)
    # Bọc tool chạy SQL bằng lớp kiểm tra (chỉ SELECT, bảng hợp lệ, có giới hạn dòng)
    # Bỏ sql_db_query_checker: đã có guard + prompt tự kiểm tra, tránh tốn thêm 1 lượt LLM
    tools = [
        make_guarded_query_tool(t, db.get_usable_table_names) if t.name == "sql_db_query" else t
        for t in toolkit.get_tools()
        if t.name != "sql_db_query_checker"
    ]

    # Tạo system prompt
    system_prompt = sql_prompt.format(
        dialect=db.dialect,
        top_k=10,
    )

    # Tạo agent (LangChain v1, chạy trên LangGraph)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
        middleware=[middleware],
    )

    return agent
