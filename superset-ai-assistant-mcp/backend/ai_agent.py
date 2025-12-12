"""
Backend module for Superset AI Chat Assistant - Multi-user session support
"""
import os
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
import logging
import sys
import os

# Создаем и настраиваем логгер для вашего бэкенда
backend_logger = logging.getLogger('superset_backend')
backend_logger.setLevel(logging.DEBUG)  # Уровень детализации

# Создаем обработчик для записи в файл
log_file_path = os.path.join(os.path.dirname(__file__), '..', 'backend_logs.log')
file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.DEBUG)

# Задаем формат сообщений
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Добавляем обработчик к логгеру
backend_logger.addHandler(file_handler)

# Также можно выводить логи в консоль для отладки
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
backend_logger.addHandler(console_handler)

# Теперь используйте этот логгер вместо print
backend_logger.info("Модуль ai_agent инициализирован")




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global MCP client (shared across sessions)
_global_mcp_client: Optional[MCPClient] = None
_global_mcp_client_lock = asyncio.Lock()


class SupersetAIAgent:
    """AI Agent for interacting with Superset via MCP - Session-specific"""
    
    def __init__(self, session_id: str):
        """Initialize the AI agent for a specific session"""
        self.session_id = session_id
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        os.environ.setdefault("LANGCHAIN_GRAPH_RECURSION_LIMIT", "50")
        
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=api_key
        )
        
        # Agent components (will be initialized later)
        self._initialized = False
        self.mcp_client = None
        self.agent = None
        
        # Session-specific locks
        self._init_lock = None
        self._run_lock = None
        
        backend_logger.debug(f"Created agent for session {session_id}")
    
    def _get_locks(self):
        """Create locks lazily for current event loop"""
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        if self._run_lock is None:
            self._run_lock = asyncio.Lock()
        return self._init_lock, self._run_lock
    
    async def _get_or_create_mcp_client(self):
        """Get or create global MCP client (shared across sessions)"""
        global _global_mcp_client
        
        async with _global_mcp_client_lock:
            if _global_mcp_client is None:
                mcp_server_path = os.getenv("SUPERSET_MCP_PATH")
                if not mcp_server_path:
                    raise ValueError("SUPERSET_MCP_PATH environment variable not set")
                
                mcp_python = os.getenv("SUPERSET_MCP_PYTHON", "python")
                
                mcp_config = {
                    "mcpServers": {
                        "superset": {
                            "command": mcp_python,
                            "args": [mcp_server_path]
                        }
                    }
                }
                
                backend_logger.debug("Creating global MCP client...")
                _global_mcp_client = MCPClient.from_dict(mcp_config)
                backend_logger.debug("Global MCP client created")
            
            return _global_mcp_client
    
    async def initialize(self):
        """Initialize the agent for this session"""
        init_lock, _ = self._get_locks()
        
        async with init_lock:
            if self._initialized:
                return True
            
            try:
                backend_logger.debug(f"Initializing agent for session {self.session_id}")
                
                # Get shared MCP client
                self.mcp_client = await self._get_or_create_mcp_client()
                
                # Create agent with the client
                self.agent = MCPAgent(
                    llm=self.llm, 
                    client=self.mcp_client, 
                    max_steps=10
                )

                # Wait for tools to be populated
                max_tool_wait = 20.0
                waited = 0.0
                interval = 0.3
                while waited < max_tool_wait:
                    tools = getattr(self.agent, "tools", None)
                    if tools and len(tools) > 0:
                        backend_logger.debug(f"Session {self.session_id}: Found {len(tools)} tools")
                        break
                    await asyncio.sleep(interval)
                    waited += interval
                else:
                    logger.warning(f"Session {self.session_id}: agent.tools not populated after wait")

                self._initialized = True
                backend_logger.debug(f"Session {self.session_id}: Agent initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Session {self.session_id}: Error initializing MCP agent: {e}")
                self._initialized = False
                # Don't close shared client here
                raise
    
    async def _ensure_initialized(self):
        """Ensure agent is initialized for this session"""
        if self._initialized and self.agent:
            return True
        return await self.initialize()
    
    async def _safe_agent_run(self, prompt: str, max_retries: int = 3):
        """Safe agent run with session-specific lock"""
        _, run_lock = self._get_locks()
        
        attempt = 0
        while True:
            attempt += 1
            try:
                async with run_lock:
                    result = await self.agent.run(prompt)
                return result
            except Exception as e:
                text = str(e).lower()
                if "recursion limit" in text:
                    logger.error(f"Session {self.session_id}: Recursion limit error: {e}")
                    raise
                
                transient = any(x in text for x in [
                    "invalid request parameters",
                    "before initialization was complete",
                    "401",
                    "no access token available",
                    "received request before initialization"
                ])
                if attempt <= max_retries and transient:
                    backoff = 0.5 * attempt
                    logger.warning(f"Session {self.session_id}: Transient error (attempt {attempt}): {e!r}. Backing off {backoff}s")
                    await asyncio.sleep(backoff)
                    # Try to re-initialize
                    try:
                        self._initialized = False
                        await self.initialize()
                    except Exception:
                        pass
                    continue
                raise
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a chat message for this session
        """
        # Ensure agent is initialized
        try:
            await self._ensure_initialized()
        except Exception as e:
            return {
                "content": f"Ошибка инициализации агента: {str(e)}",
                "role": "assistant",
                "finish_reason": "error"
            }
        
        try:
            # Build conversation context from history
            conversation_context = ""
            if len(messages) > 1:
                history_messages = messages[-6:-1] if len(messages) > 6 else messages[:-1]
                conversation_context = "История диалога:\n" + "\n".join([
                    f"{msg['role']}: {msg['content']}" for msg in history_messages
                ]) + "\n\n"
            
            last_user_message = messages[-1]["content"] if messages else ""
            
            # Enhanced prompt
            enhanced_query = (
                f"Ты ассистент для Apache Superset (сессия: {self.session_id}). Используй контекст из истории диалога.\n"
                f"{conversation_context}"
                "Текущий запрос пользователя:\n"
                f"{last_user_message}\n\n"
                "ОЧЕНЬ ВАЖНЫЕ ИНСТРУКЦИИ:\n"
                "1. Перед выполнением операций с дашбордами убедись, что агент аутентифицирован в Superset.\n"
                "2. Используй инструмент superset_auth_authenticate_user для аутентификации.\n"
                "3. Для создания дашборда используй superset_dashboard_create.\n"
                "4. Для списка дашбордов используй superset_dashboard_list.\n"
                "5. Для создания чарта используй superset_chart_create с параметрами: slice_name, datasource_id, datasource_type, viz_type, params.\n\n"
            )
            
            backend_logger.debug(f"Session {self.session_id}: Processing query with {len(messages)} messages")
            
            # Run the agent
            result = await self._safe_agent_run(enhanced_query, max_retries=2)
            
            return {
                "content": result,
                "role": "assistant",
                "finish_reason": "stop",
                "model": "gpt-4o",
                "session_id": self.session_id
            }
            
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error in chat processing: {e}")
            return {
                "content": f"Ошибка при обработке запроса: {str(e)}",
                "role": "assistant",
                "finish_reason": "error",
                "model": "gpt-4o",
                "session_id": self.session_id
            }
    
    async def close(self):
        """Close session-specific resources"""
        backend_logger.debug(f"Closing agent for session {self.session_id}")
        # Don't close shared MCP client
        self._initialized = False
        self.agent = None
        self.mcp_client = None  # Just drop reference, don't close


# Agent session manager
class AgentSessionManager:
    """Manager for agent sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SupersetAIAgent] = {}
        self.sessions_lock = asyncio.Lock()
    
    async def create_session(self) -> str:
        """Create a new agent session"""
        session_id = str(uuid.uuid4())[:8]
        
        async with self.sessions_lock:
            agent = SupersetAIAgent(session_id)
            self.sessions[session_id] = agent
        
        backend_logger.debug(f"Created new session: {session_id}")
        return session_id
    
    async def get_agent(self, session_id: str) -> Optional[SupersetAIAgent]:
        """Get agent for session"""
        async with self.sessions_lock:
            return self.sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Close a session"""
        async with self.sessions_lock:
            if session_id in self.sessions:
                agent = self.sessions[session_id]
                await agent.close()
                del self.sessions[session_id]
                backend_logger.debug(f"Closed session: {session_id}")
    
    async def close_all_sessions(self):
        """Close all sessions"""
        async with self.sessions_lock:
            for session_id in list(self.sessions.keys()):
                await self.close_session(session_id)


# Global session manager
_session_manager: Optional[AgentSessionManager] = None


def get_session_manager() -> AgentSessionManager:
    """Get or create the session manager singleton"""
    global _session_manager
    if _session_manager is None:
        _session_manager = AgentSessionManager()
    return _session_manager


async def shutdown_global_resources():
    """Shutdown all global resources (call on application exit)"""
    global _global_mcp_client, _session_manager
    
    # Close all sessions
    if _session_manager:
        await _session_manager.close_all_sessions()
        _session_manager = None
    
    # Close global MCP client
    if _global_mcp_client:
        await _global_mcp_client.close()
        _global_mcp_client = None
        backend_logger.debug("Global MCP client closed")