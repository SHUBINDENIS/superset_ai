import os
import sys
import asyncio
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import get_session_manager

load_dotenv()

st.set_page_config(
    page_title="Superset AI Assistant (Multi-User)",
    page_icon="chat",
    layout="wide",
    initial_sidebar_state="expanded",
)

def initialize_session_state():
    """Initialize Streamlit session state"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "agent_initialized" not in st.session_state:
        st.session_state.agent_initialized = False
    if "app_started" not in st.session_state:
        st.session_state.app_started = False

def display_message(role: str, content: str):
    """Display a chat message"""
    with st.chat_message(role):
        st.write(content)


async def initialize_session():
    """Initialize a new session for this user"""
    if not st.session_state.get("session_id"):
        session_manager = get_session_manager()
        session_id = await session_manager.create_session()
        st.session_state.session_id = session_id
        st.session_state.agent_initialized = False
    
    # Get agent for this session
    session_manager = get_session_manager()
    agent = await session_manager.get_agent(st.session_state.session_id)
    
    if not agent:
        return False, "Сессия не найдена"
    
    if not st.session_state.agent_initialized:
        with st.spinner("Инициализируем агента для вашей сессии..."):
            try:
                success = await agent.initialize()
                if success:
                    st.session_state.agent_initialized = True
                    return True, f"Сессия {st.session_state.session_id} готова!"
                else:
                    return False, "Не удалось инициализировать агент"
            except Exception as e:
                return False, f"Ошибка инициализации: {str(e)}"
    
    return True, "Агент уже инициализирован"


async def process_message(user_message: str):
    """Process a user message for this session"""
    if not st.session_state.session_id:
        return False, "Сессия не создана"
    
    session_manager = get_session_manager()
    agent = await session_manager.get_agent(st.session_state.session_id)
    
    if not agent:
        return False, "Агент для этой сессии не найден"
    
    # Add user message to history
    st.session_state.messages.append({
        "role": "user",
        "content": user_message
    })
    
    with st.spinner("Думаю..."):
        try:
            response = await agent.chat(st.session_state.messages)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["content"]
            })
            
            return True, response
            
        except Exception as e:
            return False, str(e)


def main():
    """Main application"""
    initialize_session_state()
    
    with st.sidebar:
        st.subheader("Superset AI Assistant (Мульти-пользователь)")
        
        if st.session_state.session_id:
            st.info(f"Сессия: {st.session_state.session_id}")
            if st.session_state.agent_initialized:
                st.success("✅ Агент готов")
            else:
                st.warning("⏳ Агент не инициализирован")
        else:
            st.warning("Сессия не создана")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Новая сессия", use_container_width=True):
                st.session_state.session_id = None
                st.session_state.agent_initialized = False
                st.session_state.messages = []
                st.rerun()
        
        with col2:
            if st.button("🗑️ Очистить чат", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        
        st.divider()
        st.caption("Статус системы:")
        st.caption(f"Пользователей: {len(get_session_manager().sessions) if hasattr(get_session_manager(), 'sessions') else 1}")
    
    st.title("Superset AI Assistant")
    st.write("Поддержка нескольких одновременных пользователей.")
    
    # Initialize session on first run
    if not st.session_state.session_id:
        success, message = asyncio.run(initialize_session())
        if success:
            st.success(message)
        else:
            st.error(message)
            if st.button("Попробовать снова"):
                st.rerun()
            st.stop()
    
    st.markdown("---")
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            display_message(message["role"], message["content"])
    
    user_input = st.chat_input("Введите сообщение...")
    
    if user_input:
        success, result = asyncio.run(process_message(user_input))
        
        if not success:
            st.error(f"Ошибка: {result}")
        
        st.rerun()


if __name__ == "__main__":
    main()