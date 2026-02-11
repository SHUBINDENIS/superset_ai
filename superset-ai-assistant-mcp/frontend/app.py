# import os
# import sys
# import asyncio
# import streamlit as st
# from dotenv import load_dotenv

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# from backend import get_session_manager

# load_dotenv()

# st.set_page_config(
#     page_title="Superset AI Assistant (Multi-User)",
#     page_icon="chat",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# def initialize_session_state():
#     """Initialize Streamlit session state"""
#     if "messages" not in st.session_state:
#         st.session_state.messages = []
#     if "session_id" not in st.session_state:
#         st.session_state.session_id = None
#     if "agent_initialized" not in st.session_state:
#         st.session_state.agent_initialized = False
#     if "app_started" not in st.session_state:
#         st.session_state.app_started = False

# def display_message(role: str, content: str):
#     """Display a chat message"""
#     with st.chat_message(role):
#         st.write(content)


# async def initialize_session():
#     """Initialize a new session for this user"""
#     if not st.session_state.get("session_id"):
#         session_manager = get_session_manager()
#         session_id = await session_manager.create_session()
#         st.session_state.session_id = session_id
#         st.session_state.agent_initialized = False
    
#     # Get agent for this session
#     session_manager = get_session_manager()
#     agent = await session_manager.get_agent(st.session_state.session_id)
    
#     if not agent:
#         return False, "Сессия не найдена"
    
#     if not st.session_state.agent_initialized:
#         with st.spinner("Инициализируем агента для вашей сессии..."):
#             try:
#                 success = await agent.initialize()
#                 if success:
#                     st.session_state.agent_initialized = True
#                     return True, f"Сессия {st.session_state.session_id} готова!"
#                 else:
#                     return False, "Не удалось инициализировать агент"
#             except Exception as e:
#                 return False, f"Ошибка инициализации: {str(e)}"
    
#     return True, "Агент уже инициализирован"


# async def process_message(user_message: str):
#     """Process a user message for this session"""
#     if not st.session_state.session_id:
#         return False, "Сессия не создана"
    
#     session_manager = get_session_manager()
#     agent = await session_manager.get_agent(st.session_state.session_id)
    
#     if not agent:
#         return False, "Агент для этой сессии не найден"
    
#     # Add user message to history
#     st.session_state.messages.append({
#         "role": "user",
#         "content": user_message
#     })
    
#     with st.spinner("Думаю..."):
#         try:
#             response = await agent.chat(st.session_state.messages)
            
#             st.session_state.messages.append({
#                 "role": "assistant",
#                 "content": response["content"]
#             })
            
#             return True, response
            
#         except Exception as e:
#             return False, str(e)


# def main():
#     """Main application"""
#     initialize_session_state()
    
#     with st.sidebar:
#         st.subheader("Superset AI Assistant (Мульти-пользователь)")
        
#         if st.session_state.session_id:
#             st.info(f"Сессия: {st.session_state.session_id}")
#             if st.session_state.agent_initialized:
#                 st.success("✅ Агент готов")
#             else:
#                 st.warning("⏳ Агент не инициализирован")
#         else:
#             st.warning("Сессия не создана")

#         st.markdown("### 📝 Примеры вопросов")
#         sample_questions = [
#             "Покажи все дашборды",
#             "Покажи список всех доступных баз данных",
#             "Выполни: SELECT * FROM sales LIMIT 10",
#             "Создай новый дашборд с названием «Отчёт по продажам»",
#             "Какие датасеты доступны?"
#         ]

#         for question in sample_questions:
#             if st.button(question, key=f"sample_{question}", use_container_width=True):
#                 st.session_state.sample_question = question

#         st.markdown("---")
        
#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("🔄 Новая сессия", use_container_width=True):
#                 st.session_state.session_id = None
#                 st.session_state.agent_initialized = False
#                 st.session_state.messages = []
#                 st.rerun()
        
#         with col2:
#             if st.button("🗑️ Очистить чат", use_container_width=True):
#                 st.session_state.messages = []
#                 st.rerun()
        
#         st.divider()
#         st.caption("Статус системы:")
#         st.caption(f"Пользователей: {len(get_session_manager().sessions) if hasattr(get_session_manager(), 'sessions') else 1}")
    
#     st.title("Superset AI Assistant")
#     st.write("Поддержка нескольких одновременных пользователей.")
    
#     # Initialize session on first run
#     if not st.session_state.session_id:
#         success, message = asyncio.run(initialize_session())
#         if success:
#             st.success(message)
#         else:
#             st.error(message)
#             if st.button("Попробовать снова"):
#                 st.rerun()
#             st.stop()
    
#     st.markdown("---")
#     chat_container = st.container()
    
#     with chat_container:
#         for message in st.session_state.messages:
#             display_message(message["role"], message["content"])
    
    

#     user_input = st.chat_input("Введите сообщение...")
    
#     if user_input:
#         success, result = asyncio.run(process_message(user_input))
        
#         if not success:
#             st.error(f"Ошибка: {result}")
        
#         st.rerun()


# if __name__ == "__main__":
#     main()






# import os
# import sys
# import asyncio
# import streamlit as st
# from dotenv import load_dotenv

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# from backend import get_session_manager

# load_dotenv()

# st.set_page_config(
#     page_title="Superset AI Assistant (Multi-User)",
#     page_icon="chat",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# def initialize_session_state():
#     """Initialize Streamlit session state"""
#     if "messages" not in st.session_state:
#         st.session_state.messages = []
#     if "session_id" not in st.session_state:
#         st.session_state.session_id = None
#     if "agent_initialized" not in st.session_state:
#         st.session_state.agent_initialized = False
#     if "app_started" not in st.session_state:
#         st.session_state.app_started = False

# def display_message(role: str, content: str):
#     """Display a chat message"""
#     with st.chat_message(role):
#         st.write(content)


# async def initialize_session():
#     """Initialize a new session for this user"""
#     if not st.session_state.get("session_id"):
#         session_manager = get_session_manager()
#         session_id = await session_manager.create_session()
#         st.session_state.session_id = session_id
#         st.session_state.agent_initialized = False
    
#     # Get agent for this session
#     session_manager = get_session_manager()
#     agent = await session_manager.get_agent(st.session_state.session_id)
    
#     if not agent:
#         return False, "Сессия не найдена"
    
#     if not st.session_state.agent_initialized:
#         with st.spinner("Инициализируем агента для вашей сессии..."):
#             try:
#                 success = await agent.initialize()
#                 if success:
#                     st.session_state.agent_initialized = True
#                     return True, f"Сессия {st.session_state.session_id} готова!"
#                 else:
#                     return False, "Не удалось инициализировать агент"
#             except Exception as e:
#                 return False, f"Ошибка инициализации: {str(e)}"
    
#     return True, "Агент уже инициализирован"


# async def process_message(user_message: str):
#     """Process a user message for this session"""
#     if not st.session_state.session_id:
#         return False, "Сессия не создана"
    
#     session_manager = get_session_manager()
#     agent = await session_manager.get_agent(st.session_state.session_id)
    
#     if not agent:
#         return False, "Агент для этой сессии не найден"
    
#     # Add user message to history
#     st.session_state.messages.append({
#         "role": "user",
#         "content": user_message
#     })
    
#     with st.spinner("Думаю..."):
#         try:
#             response = await agent.chat(st.session_state.messages)
            
#             st.session_state.messages.append({
#                 "role": "assistant",
#                 "content": response["content"]
#             })
            
#             return True, response
            
#         except Exception as e:
#             return False, str(e)


# def main():
#     """Main application"""
#     initialize_session_state()
    
#     with st.sidebar:
#         st.subheader("Superset AI Assistant (Мульти-пользователь)")
        
#         if st.session_state.session_id:
#             # st.info(f"Сессия: {st.session_state.session_id}")
#             if st.session_state.agent_initialized:
#                 st.success("✅ Агент готов")
#             else:
#                 st.warning("⏳ Агент не инициализирован")
#         else:
#             st.warning("Сессия не создана")

#         st.markdown("### 📝 Примеры вопросов")
#         sample_questions = [
#             "Покажи все дашборды со ссылками",
#             "Какие графики доступны?",
#             "Какие датасеты доступны?",
#             "Покажи список всех доступных баз данных",
#             "Выполни и выведи таблицей: SELECT * FROM users LIMIT 10",
#             "Создай новый дашборд с названием «Отчёт по продажам»",
#         ]

#         for question in sample_questions:
#             if st.button(question, key=f"sample_{question}", use_container_width=True):
#                 st.session_state.sample_question = question

#         st.markdown("---")
        
#         col1, col2 = st.columns(2)
#         with col1:
#             if st.button("🔄 Новая сессия", use_container_width=True):
#                 st.session_state.session_id = None
#                 st.session_state.agent_initialized = False
#                 st.session_state.messages = []
#                 st.rerun()
        
#         with col2:
#             if st.button("🗑️ Очистить чат", use_container_width=True):
#                 st.session_state.messages = []
#                 st.rerun()
        
#         st.divider()
#         st.caption("Статус системы:")
#         st.caption(f"Пользователей: {len(get_session_manager().sessions) if hasattr(get_session_manager(), 'sessions') else 1}")
    
#     st.title("Superset AI Assistant")
#     st.write("Поддержка нескольких одновременных пользователей.")
    
#     # Initialize session on first run
#     if not st.session_state.session_id:
#         success, message = asyncio.run(initialize_session())
#         if success:
#             st.success(message)
#         else:
#             st.error(message)
#             if st.button("Попробовать снова"):
#                 st.rerun()
#             st.stop()
    
#     st.markdown("---")
#     chat_container = st.container()
    
#     with chat_container:
#         for message in st.session_state.messages:
#             display_message(message["role"], message["content"])
    
#     if "sample_question" in st.session_state:
#         user_input = st.session_state.pop("sample_question")
#         success, result = asyncio.run(process_message(user_input))

#         if not success:
#             st.error(f"Ошибка: {result}")

#         st.rerun()


#     user_input = st.chat_input("Введите сообщение...")
    
#     if user_input:
#         success, result = asyncio.run(process_message(user_input))
        
#         if not success:
#             st.error(f"Ошибка: {result}")
        
#         st.rerun()


# if __name__ == "__main__":
#     main()






import os
import sys
import asyncio
import streamlit as st
from dotenv import load_dotenv

# --- Path & env --------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import get_session_manager

load_dotenv()

# --- Page config -------------------------------------------------------------
st.set_page_config(
    page_title="Superset AI Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session state -----------------------------------------------------------
def init_state():
    defaults = {
        "messages": [],
        "session_id": None,
        "agent_initialized": False,
        "pending_input": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# --- UI helpers --------------------------------------------------------------
def render_message(role: str, content: str):
    with st.chat_message(role):
        st.write(content)


def sidebar():
    with st.sidebar:
        st.subheader("🤖 Superset AI Assistant")

        if st.session_state.session_id:
            if st.session_state.agent_initialized:
                st.success("Агент готов")
            else:
                st.warning("Агент не инициализирован")
        else:
            st.warning("Сессия не создана")

        st.divider()
        st.markdown("### 📝 Примеры вопросов")

        samples = [
            "Покажи все дашборды со ссылками",
            "Какие графики доступны?",
            "Какие датасеты доступны?",
            "Покажи список всех доступных баз данных",
            "Выполни и выведи таблицей: SELECT * FROM users LIMIT 10",
            "Создай новый дашборд с названием «Отчёт по продажам»",
        ]

        for i, q in enumerate(samples):
            if st.button(q, key=f"sample_{i}", use_container_width=True):
                st.session_state.pending_input = q

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Новая сессия", use_container_width=True):
                reset_session()
        with col2:
            if st.button("🗑 Очистить чат", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        st.divider()
        manager = get_session_manager()
        count = len(manager.sessions) if hasattr(manager, "sessions") else 1
        st.caption(f"Активных пользователей: {count}")


# --- Backend interaction -----------------------------------------------------
async def ensure_session():
    manager = get_session_manager()

    if not st.session_state.session_id:
        st.session_state.session_id = await manager.create_session()
        st.session_state.agent_initialized = False

    agent = await manager.get_agent(st.session_state.session_id)
    if not agent:
        return False, "Сессия не найдена"

    if not st.session_state.agent_initialized:
        with st.spinner("Инициализация агента..."):
            ok = await agent.initialize()
            if not ok:
                return False, "Не удалось инициализировать агента"
            st.session_state.agent_initialized = True

    return True, None


async def handle_message(text: str):
    manager = get_session_manager()
    agent = await manager.get_agent(st.session_state.session_id)

    st.session_state.messages.append({"role": "user", "content": text})

    with st.spinner("Думаю..."):
        reply = await agent.chat(st.session_state.messages)

    st.session_state.messages.append({
        "role": "assistant",
        "content": reply["content"],
    })


# --- State utils -------------------------------------------------------------
def reset_session():
    st.session_state.session_id = None
    st.session_state.agent_initialized = False
    st.session_state.messages = []
    st.session_state.pending_input = None
    st.rerun()


# --- Main --------------------------------------------------------------------
def main():
    init_state()
    sidebar()

    st.title("Superset AI Assistant")
    st.caption("Чат-интерфейс для работы с Apache Superset")

    ok, error = asyncio.run(ensure_session())
    if not ok:
        st.error(error)
        st.stop()

    st.divider()

    for msg in st.session_state.messages:
        render_message(msg["role"], msg["content"])

    # обработка кнопок-примеров
    if st.session_state.pending_input:
        text = st.session_state.pending_input
        st.session_state.pending_input = None
        asyncio.run(handle_message(text))
        st.rerun()

    # обычный ввод
    user_text = st.chat_input("Введите запрос…")
    if user_text:
        asyncio.run(handle_message(user_text))
        st.rerun()


if __name__ == "__main__":
    main()