import os
import sys
import asyncio
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import get_agent

load_dotenv()

st.set_page_config(
    page_title="Superset AI Assistant (Prototype)",
    page_icon="chat",
    layout="wide",
    initial_sidebar_state="expanded",
)


def initialize_session_state():
    """Initialize Streamlit session state"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_initialized" not in st.session_state:
        st.session_state.agent_initialized = False


def display_message(role: str, content: str):
    """Display a chat message"""
    with st.chat_message(role):
        st.write(content)


async def initialize_agent():
    """Initialize the AI agent"""
    if not st.session_state.agent_initialized:
        with st.spinner("Подключаемся к серверу Superset MCP..."):
            try:
                agent = get_agent()
                await agent.initialize()
                st.session_state.agent_initialized = True
                return True, "Успешно подключились к Superset!"
            except Exception as e:
                return False, f"Ошибка подключения к Superset: {str(e)}"
    return True, "Уже подключены"


async def process_message(user_message: str):
    """Process a user message and get AI response"""
    agent = get_agent()

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
        st.subheader("Superset AI Assistant (прототип)")
        if st.session_state.agent_initialized:
            st.success("Подключено к Superset")
        else:
            st.warning("Не подключено")
        if st.button("Очистить чат", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.title("Superset AI Assistant")
    st.write("Минимальный прототип чата для общения с Superset через MCP.")

    if not st.session_state.agent_initialized:
        success, message = asyncio.run(initialize_agent())
        if success:
            st.success(message)
        else:
            st.error(message)
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
