"""
Backend module for Superset AI Chat Assistant - Multi-user session support
"""
import asyncio
import uuid
import re
import time
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient
import logging
import sys
import os
from .us2_glossary_service import get_glossary_service
from .us3_mapping_rules import get_us3_mapping_rules_service
from .us4_query_assistant import get_us4_query_assistant_service
from .us5_query_builder import get_us5_query_builder_service
from .us10_12_guardrails import get_us10_12_guardrails_service
from .us13_15_viz_service import get_us13_15_viz_service

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
_global_mcp_client_loop_id: Optional[int] = None
_global_mcp_client_lock: Optional[asyncio.Lock] = None
_global_mcp_client_lock_loop_id: Optional[int] = None


def _current_loop_id() -> int:
    return id(asyncio.get_running_loop())


def _get_global_mcp_client_lock() -> asyncio.Lock:
    global _global_mcp_client_lock, _global_mcp_client_lock_loop_id
    loop_id = _current_loop_id()
    if (
        _global_mcp_client_lock is None
        or _global_mcp_client_lock_loop_id != loop_id
    ):
        _global_mcp_client_lock = asyncio.Lock()
        _global_mcp_client_lock_loop_id = loop_id
    return _global_mcp_client_lock


class SupersetAIAgent:
    """AI Agent for interacting with Superset via MCP - Session-specific"""
    
    def __init__(self, session_id: str):
        """Initialize the AI agent for a specific session"""
        self.session_id = session_id
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        os.environ.setdefault("LANGCHAIN_GRAPH_RECURSION_LIMIT", "50")
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=0,
            api_key=api_key
        )

        self.agent_max_steps = max(
            5,
            int(os.getenv("AI_AGENT_MAX_STEPS", "10")),
        )
        self.agent_recursion_limit = max(
            self.agent_max_steps * 2,
            int(os.getenv("AI_AGENT_RECURSION_LIMIT", "30")),
        )
        self.agent_max_recursion_limit = max(
            self.agent_recursion_limit,
            int(os.getenv("AI_AGENT_MAX_RECURSION_LIMIT", "160")),
        )
        self.max_history_messages = max(
            1,
            int(os.getenv("AI_AGENT_HISTORY_MESSAGES", "3")),
        )
        self.max_history_chars = max(
            300,
            int(os.getenv("AI_AGENT_HISTORY_CHARS", "700")),
        )
        self.max_history_item_chars = max(
            120,
            int(os.getenv("AI_AGENT_HISTORY_ITEM_CHARS", "220")),
        )
        self.max_context_chars = max(
            250,
            int(os.getenv("AI_AGENT_CONTEXT_CHARS", "900")),
        )
        self.max_user_message_chars = max(
            150,
            int(os.getenv("AI_AGENT_USER_MESSAGE_CHARS", "900")),
        )
        self.rate_limit_cooldown_seconds = max(
            5,
            int(os.getenv("AI_AGENT_RATE_LIMIT_COOLDOWN_SECONDS", "20")),
        )
        self._rate_limited_until_monotonic: Optional[float] = None
        
        # Agent components (will be initialized later)
        self._initialized = False
        self.mcp_client = None
        self.agent = None
        
        # Session-specific locks
        self._init_lock = None
        self._run_lock = None
        self._locks_loop_id: Optional[int] = None
        self._bound_loop_id: Optional[int] = None
        
        backend_logger.debug(f"Created agent for session {session_id}")

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> str:
        if not isinstance(text, str):
            return ""
        if max_chars <= 0:
            return ""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "...[truncated]"

    def _clip_context(self, context_name: str, value: str) -> str:
        clipped = self._truncate_text(value, self.max_context_chars)
        if len(clipped) < len(value):
            backend_logger.debug(
                f"Session {self.session_id}: context '{context_name}' clipped "
                f"from {len(value)} to {len(clipped)} chars"
            )
        return clipped

    def _build_conversation_context(self, messages: List[Dict[str, str]]) -> str:
        if not messages:
            return ""

        selected = messages[-self.max_history_messages :]
        lines: List[str] = []
        total_chars = 0
        for msg in selected:
            role = str(msg.get("role", "user"))
            raw_content = str(msg.get("content", ""))
            compact_content = self._truncate_text(
                raw_content,
                self.max_history_item_chars,
            )
            if not compact_content:
                continue
            line = f"{role}: {compact_content}"
            line_len = len(line) + 1
            if total_chars + line_len > self.max_history_chars:
                break
            lines.append(line)
            total_chars += line_len

        if not lines:
            return ""
        return "История диалога (кратко):\n" + "\n".join(lines) + "\n\n"

    def _extract_table_hints_from_text(self, text: str) -> List[str]:
        if not isinstance(text, str) or not text.strip():
            return []
        patterns = [
            r"(?:таблиц[аы]|датасет[а]?|dataset|table)\s*[`\"']?([A-Za-z_][A-Za-z0-9_\.]*)[`\"']?",
            r"(?:из|from)\s+[`\"']?([A-Za-z_][A-Za-z0-9_\.]*)[`\"']?",
        ]
        found: List[str] = []
        for pattern in patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                token = str(match).strip()
                if token and token not in found:
                    found.append(token)
        return found

    def _build_datasource_guardrail(self, table_hints: List[str]) -> str:
        if not table_hints:
            return ""
        joined = ", ".join(table_hints)
        return (
            "СТРОГОЕ ОГРАНИЧЕНИЕ ПО DATASOURCE:\n"
            f"- Пользователь явно указал таблицу/датасет: {joined}\n"
            "- Разрешено использовать только dataset, связанный с указанной таблицей.\n"
            "- Запрещено подменять datasource на другую таблицу.\n"
            "- Если dataset для указанной таблицы не найден, верни явную ошибку и попроси уточнение, "
            "но не создавай chart на другой таблице.\n"
        )

    @staticmethod
    def _parse_scope_from_text(text: str) -> Dict[str, str]:
        raw = str(text or "")
        patterns = [
            r"используй\s*scope\s*:\s*база\s*:\s*([^;\n]+?)\s*;\s*таблица\s*:\s*([^\n]+)",
            r"scope\s*:\s*database\s*:\s*([^;\n]+?)\s*;\s*table\s*:\s*([^\n]+)",
        ]
        db_value = ""
        table_value = ""
        for pattern in patterns:
            match = re.search(pattern, raw, flags=re.IGNORECASE)
            if not match:
                continue
            db_value = str(match.group(1)).strip(" .`\"'")
            table_value = str(match.group(2)).strip(" .`\"'")
            break

        if not db_value and not table_value:
            return {}

        schema_name = ""
        table_name = table_value
        if "." in table_value:
            schema_name, table_name = table_value.split(".", 1)
            schema_name = schema_name.strip(" .`\"'")
            table_name = table_name.strip(" .`\"'")

        return {
            "database": db_value,
            "table": table_value,
            "schema": schema_name,
            "table_name": table_name,
        }

    def _resolve_dataset_for_scope(self, scope: Dict[str, str]) -> Dict[str, Any]:
        if not isinstance(scope, dict):
            return {}
        table_name = str(scope.get("table_name", "")).strip().casefold()
        if not table_name:
            return {}
        db_scope = str(scope.get("database", "")).strip().casefold()
        schema_scope = str(scope.get("schema", "")).strip().casefold()
        table_scope_full = str(scope.get("table", "")).strip().casefold()

        try:
            svc = get_us13_15_viz_service()
            datasets = svc.list_datasets(limit=1000)
        except Exception as exc:
            backend_logger.warning(
                f"Session {self.session_id}: failed to list datasets for scope resolution: {exc}"
            )
            return {}

        candidates: List[Dict[str, Any]] = []
        for item in datasets:
            if not isinstance(item, dict):
                continue
            dataset_id = int(item.get("id", 0) or 0)
            if dataset_id <= 0:
                continue
            item_db = str(item.get("database_name", "")).strip()
            item_schema = str(item.get("schema", "")).strip()
            item_table = str(item.get("table_name", "")).strip()
            if not item_table:
                continue

            item_db_low = item_db.casefold()
            item_schema_low = item_schema.casefold()
            item_table_low = item_table.casefold()
            item_full_low = (
                f"{item_schema_low}.{item_table_low}" if item_schema_low else item_table_low
            )
            if item_table_low != table_name and item_full_low != table_scope_full:
                continue
            if db_scope and item_db_low != db_scope:
                continue
            if schema_scope and item_schema_low != schema_scope:
                continue

            score = 0
            if db_scope and item_db_low == db_scope:
                score += 2
            if schema_scope and item_schema_low == schema_scope:
                score += 2
            if item_full_low == table_scope_full:
                score += 1
            candidates.append(
                {
                    "score": score,
                    "dataset_id": dataset_id,
                    "database_name": item_db,
                    "schema": item_schema,
                    "table_name": item_table,
                    "table_full": f"{item_schema}.{item_table}" if item_schema else item_table,
                }
            )

        if not candidates:
            return {}
        candidates.sort(key=lambda x: (int(x.get("score", 0)), int(x.get("dataset_id", 0))), reverse=True)
        best = dict(candidates[0])

        try:
            svc = get_us13_15_viz_service()
            metadata = svc.get_dataset_metadata(int(best["dataset_id"]))
            columns = metadata.get("columns", [])
            metrics = metadata.get("metrics", [])
            if isinstance(columns, list):
                best["columns"] = [
                    str(c.get("column_name", "")).strip()
                    for c in columns
                    if isinstance(c, dict) and str(c.get("column_name", "")).strip()
                ][:15]
            if isinstance(metrics, list):
                best["metrics"] = [str(x).strip() for x in metrics if str(x).strip()][:10]
        except Exception as exc:
            backend_logger.warning(
                f"Session {self.session_id}: failed to fetch metadata for scoped dataset: {exc}"
            )
        return best

    def _build_scope_context(
        self,
        user_message: str,
        resolved_dataset: Optional[Dict[str, Any]] = None,
    ) -> str:
        scope = self._parse_scope_from_text(user_message)
        if not scope:
            return ""

        lines = [
            "US Scope (из запроса пользователя):",
            f"- database={scope.get('database', '-')}; table={scope.get('table', '-')}",
        ]
        resolved = resolved_dataset or self._resolve_dataset_for_scope(scope)
        if resolved:
            lines.append(
                "- Scope-resolved dataset: "
                f"id={resolved.get('dataset_id')}, database={resolved.get('database_name', '-')}, "
                f"table={resolved.get('table_full', '-')}"
            )
            columns = resolved.get("columns", [])
            if isinstance(columns, list) and columns:
                lines.append("- dataset columns: " + ", ".join(columns[:12]))
            metrics = resolved.get("metrics", [])
            if isinstance(metrics, list) and metrics:
                lines.append("- dataset metrics: " + ", ".join(metrics[:8]))
            lines.append(
                "- Обязательно используй этот dataset_id для запросов/графиков."
            )
            lines.append(
                "- Не используй superset_database_get_tables как обязательный шаг."
            )
        else:
            lines.append(
                "- Dataset по scope не найден через list_datasets. "
                "Сначала попробуй superset_dataset_list и фильтрацию по schema/table, "
                "не останавливайся на ошибке /database/*/tables."
            )
        lines.append(
            "- Ошибка /api/v1/database/*/tables 400 не является финальной: "
            "продолжай через dataset-level операции."
        )
        return "\n".join(lines)

    @staticmethod
    def _looks_like_scope_tables_failure(text: str) -> bool:
        low = str(text or "").casefold()
        patterns = [
            "не смог получить доступ к таблицам",
            "ошибка доступа к таблицам",
            "/api/v1/database/",
            "/tables/",
            "database_get_tables",
        ]
        if "таблиц" in low and "ошиб" in low:
            return True
        return all(
            token in low for token in ["/database/", "/tables/"]
        ) or any(token in low for token in patterns)

    @staticmethod
    def _get_superset_public_url() -> str:
        for key in ("SUPERSET_PUBLIC_URL", "US15_SHARE_BASE_URL", "SUPERSET_BASE_URL"):
            value = str(os.getenv(key, "") or "").strip()
            if value:
                if not value.startswith("http://") and not value.startswith("https://"):
                    value = f"http://{value}"
                return value.rstrip("/")
        return "http://103.54.18.91:8088"

    @staticmethod
    def _extract_retry_after_seconds(error_text: str, default: int = 12) -> int:
        try:
            match = re.search(
                r"try again in\\s*([0-9]+(?:\\.[0-9]+)?)s",
                str(error_text),
                flags=re.IGNORECASE,
            )
            if match:
                return max(1, int(float(match.group(1))) + 1)
        except Exception:
            pass
        return max(1, int(default))

    def _set_rate_limit_cooldown(self, wait_seconds: int) -> None:
        seconds = max(self.rate_limit_cooldown_seconds, int(wait_seconds))
        self._rate_limited_until_monotonic = time.monotonic() + seconds

    def _get_rate_limit_remaining(self) -> int:
        until = self._rate_limited_until_monotonic
        if until is None:
            return 0
        remaining = int(until - time.monotonic())
        if remaining <= 0:
            self._rate_limited_until_monotonic = None
            return 0
        return remaining

    @staticmethod
    def _format_allowed_tables_hint() -> str:
        raw = str(os.getenv("US11_ALLOWED_TABLES", "") or "").strip()
        if not raw:
            return ""
        values = [x.strip() for x in raw.split(",") if x.strip()]
        if not values:
            return ""
        preview = ", ".join(values[:5])
        if len(values) > 5:
            preview += ", ..."
        return preview

    @staticmethod
    def _extract_column_name_from_error(error_text: str) -> str:
        text = str(error_text or "")
        patterns = [
            r'Referenced column\s+"([^"]+)"',
            r'column\s+"([^"]+)"\s+does not exist',
            r"column\s+'([^']+)'\s+does not exist",
            r"Unknown column '([^']+)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return str(match.group(1)).strip()
        return ""

    def _build_guardrail_block_reply(
        self,
        *,
        reason_code: str,
        reason_text: str,
        user_message: str,
    ) -> str:
        code = str(reason_code or "").strip().lower()
        reason = str(reason_text or "").strip() or "Запрос заблокирован политикой."
        if code == "offtopic_blocked":
            return (
                f"Запрос отклонён: {reason}\n\n"
                "Чтобы я выполнил задачу, уточните, пожалуйста:\n"
                "1. Какая метрика нужна (count/sum/avg и поле).\n"
                "2. По какой таблице или датасету строить расчёт.\n"
                "3. Какой период и группировка нужны (день/месяц/регион и т.д.)."
            )
        if code == "table_policy_blocked":
            allowed = self._format_allowed_tables_hint()
            allowed_line = (
                f"\nРазрешённые таблицы для роли: {allowed}."
                if allowed
                else ""
            )
            return (
                f"Запрос отклонён политикой доступа: {reason}{allowed_line}\n\n"
                "Уточните, какую разрешённую таблицу использовать, и я сразу продолжу."
            )
        if code == "pii_blocked":
            return (
                f"Запрос отклонён по защите PII: {reason}\n\n"
                "Могу продолжить в обезличенном виде. Уточните:\n"
                "1. Достаточно ли агрегатов без персональных полей.\n"
                "2. Нужны ли срезы по сегментам/регионам вместо персоналий."
            )
        if code == "sql_blocked":
            return (
                f"Запрос отклонён: {reason}\n\n"
                "Переформулируйте запрос в read-only формате (SELECT/WITH/EXPLAIN), "
                "и я выполню его."
            )
        if code in {"quota_per_minute", "quota_per_hour", "complexity_limit"}:
            return (
                f"{reason}\n\n"
                "Чтобы пройти ограничения, уточните более узкий период и добавьте фильтр "
                "или LIMIT."
            )
        return (
            f"Запрос отклонён: {reason}\n\n"
            "Уточните, какую таблицу/метрику/период использовать, и я повторю попытку."
        )

    def _build_error_clarification_reply(
        self,
        *,
        user_message: str,
        error_text: str,
    ) -> str:
        text = str(error_text or "")
        low = text.casefold()
        table_hints = self._extract_table_hints_from_text(user_message)
        table_hint = table_hints[0] if table_hints else "таблицу/датасет"

        if "authentication timeout" in low or "not authorized" in low or "401" in low:
            return (
                "Не удалось обратиться к Superset из-за авторизации.\n\n"
                "Проверьте, что Superset доступен и учётные данные корректны, затем повторите запрос. "
                "Если нужно, уточните какой URL Superset использовать."
            )
        if "timeout" in low:
            return (
                "Запрос не успел выполниться по таймауту.\n\n"
                "Уточните более узкий период или добавьте фильтры, например: "
                "'за последние 30 дней, top-10'."
            )
        if "recursion limit" in low:
            return (
                "Запрос получился слишком неоднозначным и зациклился на шагах планирования.\n\n"
                "Уточните: таблицу, метрику и нужный результат одним предложением."
            )
        if "rate limit" in low or "429" in low:
            wait_seconds = self._extract_retry_after_seconds(
                text,
                default=self.rate_limit_cooldown_seconds,
            )
            self._set_rate_limit_cooldown(wait_seconds)
            return (
                f"Достигнут лимит запросов OpenAI (429). Подождите примерно {wait_seconds} сек и повторите запрос."
            )
        if ("column" in low and "not found" in low) or "does not exist" in low:
            bad_column = self._extract_column_name_from_error(text)
            column_hint = f" (проблемная колонка: {bad_column})" if bad_column else ""
            return (
                f"Не удалось выполнить SQL: в таблице нет нужного поля{column_hint}.\n\n"
                f"Уточните точные названия колонок для {table_hint} или попросите меня сначала показать структуру таблицы."
            )
        if ("table" in low and "not found" in low) or (
            "relation" in low and "does not exist" in low
        ):
            return (
                "Не удалось найти таблицу/датасет.\n\n"
                "Уточните точное имя таблицы (и схему, если есть), например `public.birth_names`."
            )
        if "bad request" in low and "/tables/" in low:
            return (
                "Superset вернул 400 при запросе списка таблиц.\n\n"
                "Уточните схему для выбранной БД или проверьте, что у пользователя есть доступ к списку таблиц."
            )
        if "dataset" in low and ("not found" in low or "не найден" in low):
            return (
                "Не удалось подобрать dataset под запрос.\n\n"
                f"Уточните, на какой таблице строить запрос ({table_hint}) и нужен ли конкретный database/schema."
            )

        return (
            "Не удалось выполнить запрос в текущем виде.\n\n"
            "Чтобы я продолжил, уточните:\n"
            "1. Таблицу/датасет.\n"
            "2. Метрику и агрегацию (count/sum/avg).\n"
            "3. Период и разрез (по дням/месяцам/регионам).\n"
            f"\nТехническая причина: {text}"
        )
    
    def _get_locks(self):
        """Create locks lazily for current event loop"""
        loop_id = _current_loop_id()
        if (
            self._init_lock is None
            or self._run_lock is None
            or self._locks_loop_id != loop_id
        ):
            self._init_lock = asyncio.Lock()
            self._run_lock = asyncio.Lock()
            self._locks_loop_id = loop_id
        return self._init_lock, self._run_lock
    
    async def _get_or_create_mcp_client(self):
        """Get or create global MCP client (shared across sessions)"""
        global _global_mcp_client, _global_mcp_client_loop_id
        
        mcp_client_lock = _get_global_mcp_client_lock()
        async with mcp_client_lock:
            current_loop_id = _current_loop_id()
            if (
                _global_mcp_client is None
                or _global_mcp_client_loop_id != current_loop_id
            ):
                if _global_mcp_client is not None:
                    try:
                        await _global_mcp_client.close()
                    except Exception as exc:
                        logger.warning(
                            f"Failed closing stale global MCP client: {exc}"
                        )

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
                _global_mcp_client_loop_id = current_loop_id
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
                    max_steps=self.agent_max_steps
                )
                self.agent.max_steps = self.agent_max_steps
                self.agent.recursion_limit = self.agent_recursion_limit
                backend_logger.debug(
                    f"Session {self.session_id}: MCPAgent configured "
                    f"max_steps={self.agent.max_steps}, "
                    f"recursion_limit={self.agent.recursion_limit}"
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
                self._bound_loop_id = _current_loop_id()
                backend_logger.debug(f"Session {self.session_id}: Agent initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Session {self.session_id}: Error initializing MCP agent: {e}")
                self._initialized = False
                # Don't close shared client here
                raise
    
    async def _ensure_initialized(self):
        """Ensure agent is initialized for this session"""
        current_loop_id = _current_loop_id()
        if (
            self._initialized
            and self.agent
            and self._bound_loop_id == current_loop_id
        ):
            return True
        if self._initialized and self._bound_loop_id != current_loop_id:
            backend_logger.debug(
                f"Session {self.session_id}: event loop changed, forcing reinitialize"
            )
            self._initialized = False
            self.agent = None
            self.mcp_client = None
            self._bound_loop_id = None
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
                    current_limit = int(getattr(self.agent, "recursion_limit", 0) or 0)
                    boosted_limit = max(current_limit * 2, current_limit + 40, 120)
                    boosted_limit = min(boosted_limit, self.agent_max_recursion_limit)
                    if attempt <= max_retries and boosted_limit > current_limit:
                        setattr(self.agent, "recursion_limit", boosted_limit)
                        setattr(
                            self.agent,
                            "max_steps",
                            max(
                                int(getattr(self.agent, "max_steps", self.agent_max_steps)),
                                boosted_limit // 2,
                            ),
                        )
                        logger.warning(
                            f"Session {self.session_id}: Recursion limit error, "
                            f"retry with recursion_limit={boosted_limit}, "
                            f"max_steps={getattr(self.agent, 'max_steps', '-')}"
                        )
                        await asyncio.sleep(0.2)
                        continue
                    logger.error(
                        f"Session {self.session_id}: Recursion limit error "
                        f"at {current_limit}: {e}"
                    )
                    raise

                is_rate_limit = "rate limit" in text or "429" in text
                if is_rate_limit:
                    wait_seconds = self._extract_retry_after_seconds(
                        str(e),
                        default=self.rate_limit_cooldown_seconds,
                    )
                    if attempt <= max_retries:
                        logger.warning(
                            f"Session {self.session_id}: OpenAI rate limit, "
                            f"sleep {wait_seconds}s before retry (attempt {attempt}/{max_retries})"
                        )
                        await asyncio.sleep(min(wait_seconds, 30))
                        continue
                    self._set_rate_limit_cooldown(wait_seconds)
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

        last_user_message = messages[-1]["content"] if messages else ""
        try:
            # Build conversation context from history
            cooldown_left = self._get_rate_limit_remaining()
            if cooldown_left > 0:
                return {
                    "content": (
                        "Лимит OpenAI временно исчерпан. "
                        f"Подождите примерно {cooldown_left} сек и повторите запрос."
                    ),
                    "role": "assistant",
                    "finish_reason": "rate_limit_cooldown",
                    "model": self.model_name,
                    "session_id": self.session_id
                }

            conversation_context = ""
            if len(messages) > 1:
                history_messages = messages[:-1]
                conversation_context = self._build_conversation_context(history_messages)
            
            last_user_message = self._truncate_text(
                str(last_user_message),
                self.max_user_message_chars,
            )
            us10_12_context = ""
            glossary_context = ""
            us3_context = ""
            us4_context = ""
            us5_context = ""
            scope_context = ""
            datasource_guardrail = ""
            us3_matches_count = 0
            table_hints: List[str] = self._extract_table_hints_from_text(last_user_message)
            scope_payload: Dict[str, str] = {}
            scope_dataset: Dict[str, Any] = {}

            try:
                guardrails_role = os.getenv("US11_DEFAULT_ROLE", "").strip().lower() or None
                guardrails_service = get_us10_12_guardrails_service()
                guardrails_decision = guardrails_service.evaluate_user_input(
                    last_user_message,
                    session_id=self.session_id,
                    role=guardrails_role,
                )
                if not guardrails_decision.get("allowed", False):
                    reason_code = str(guardrails_decision.get("code", "")).strip()
                    reason_text = str(guardrails_decision.get("reason", "")).strip()
                    return {
                        "content": self._build_guardrail_block_reply(
                            reason_code=reason_code,
                            reason_text=reason_text,
                            user_message=last_user_message,
                        ),
                        "role": "assistant",
                        "finish_reason": "blocked",
                        "model": self.model_name,
                        "session_id": self.session_id
                    }

                warnings = guardrails_decision.get("warnings", [])
                us10_12_context = (
                    "US10-US12 policies enforced: read-only SQL, table/PII access control, quotas."
                )
                if warnings:
                    warning_lines = "\n".join(f"- {w}" for w in warnings[:3])
                    us10_12_context = (
                        f"{us10_12_context}\n"
                        f"- Дополнительные предупреждения по текущему запросу:\n"
                        f"{warning_lines}"
                    )
                us10_12_context = self._clip_context("US10_US12", us10_12_context)
            except Exception as exc:
                backend_logger.warning(
                    f"Session {self.session_id}: US10-US12 guardrails check failed: {exc}"
                )
                us10_12_context = ""

            try:
                glossary_context = get_glossary_service().build_agent_context(
                    max_terms=6,
                    max_mappings=10,
                )
                glossary_context = self._clip_context("US2", glossary_context)
            except Exception:
                glossary_context = ""
            try:
                us3_service = get_us3_mapping_rules_service()
                matched_rules = us3_service.evaluate_query(
                    last_user_message,
                    session_id=self.session_id,
                )
                us3_matches_count = len(matched_rules)
                us3_context = us3_service.build_inference_context(
                    matched_rules,
                    max_lines=4,
                )
                us3_context = self._clip_context("US3", us3_context)
            except Exception as exc:
                backend_logger.warning(
                    f"Session {self.session_id}: US3 mapping evaluation failed: {exc}"
                )
                us3_context = ""
            try:
                us4_context = get_us4_query_assistant_service().build_agent_context_for_query(
                    last_user_message,
                    max_examples=1,
                    max_entities=4,
                )
                us4_context = self._clip_context("US4", us4_context)
            except Exception as exc:
                backend_logger.warning(
                    f"Session {self.session_id}: US4 context build failed: {exc}"
                )
                us4_context = ""
            try:
                us5_context = get_us5_query_builder_service().build_agent_context(
                    session_id=self.session_id,
                    max_lines=4,
                )
                us5_context = self._clip_context("US5", us5_context)
            except Exception as exc:
                backend_logger.warning(
                    f"Session {self.session_id}: US5 context build failed: {exc}"
                )
                us5_context = ""
            try:
                us5_latest = get_us5_query_builder_service().get_latest_criteria(
                    session_id=self.session_id
                )
                latest_table = str(us5_latest.get("table_name", "")).strip()
                if latest_table and latest_table not in table_hints:
                    table_hints.append(latest_table)
            except Exception:
                pass
            try:
                scope_payload = self._parse_scope_from_text(last_user_message)
                if scope_payload:
                    scope_dataset = self._resolve_dataset_for_scope(scope_payload)
                    scope_context = self._build_scope_context(
                        last_user_message,
                        resolved_dataset=scope_dataset,
                    )
                    scope_context = self._clip_context("US_SCOPE", scope_context)
                    scope_table_full = str(scope_dataset.get("table_full", "")).strip()
                    if scope_table_full and scope_table_full not in table_hints:
                        table_hints.append(scope_table_full)
            except Exception as exc:
                backend_logger.warning(
                    f"Session {self.session_id}: scope resolution failed: {exc}"
                )
                scope_context = ""
            datasource_guardrail = self._clip_context(
                "DATASOURCE_GUARDRAIL",
                self._build_datasource_guardrail(table_hints),
            )
            superset_public_url = self._get_superset_public_url()
            
            # Enhanced prompt
            enhanced_query = (
                f"Ты ассистент Apache Superset (сессия: {self.session_id}).\n"
                f"{conversation_context}"
                f"{glossary_context}\n\n"
                f"{us3_context}\n\n"
                f"{us4_context}\n\n"
                f"{us5_context}\n\n"
                f"{scope_context}\n\n"
                f"{us10_12_context}\n\n"
                f"{datasource_guardrail}\n\n"
                "Запрос пользователя:\n"
                f"{last_user_message}\n\n"
                "Правила выполнения:\n"
                "- Работай только с инструментами Superset MCP.\n"
                "- Если нужно, сначала аутентифицируйся через superset_auth_authenticate_user.\n"
                "- Для dashboard list/create используй профильные инструменты.\n"
                "- Для chart create используй корректные datasource_id/datasource_type/viz_type/params.\n"
                f"- Для всех ссылок на Superset используй базовый URL: {superset_public_url}.\n"
                "- Если в запросе есть scope (база/таблица), сначала резолвь dataset через "
                "superset_dataset_list и используй dataset-level операции.\n"
                "- Не считай ошибку /api/v1/database/*/tables (400) финальной, если dataset уже известен.\n"
                "- Если пользователь указал таблицу/датасет, не подменяй datasource.\n"
                "- Если данных недостаточно или возникает ошибка инструмента, задай до 3 уточняющих вопросов "
                "про таблицу/метрику/период вместо общего отказа.\n"
            )
            
            backend_logger.debug(f"Session {self.session_id}: Processing query with {len(messages)} messages")
            backend_logger.debug(f"Session {self.session_id}: US3 matched rules: {us3_matches_count}")
            
            # Run the agent
            result = await self._safe_agent_run(enhanced_query, max_retries=2)
            if (
                scope_payload
                and scope_dataset
                and self._looks_like_scope_tables_failure(str(result))
            ):
                retry_prompt = (
                    f"{enhanced_query}\n\n"
                    "Дополнительная инструкция для повтора:\n"
                    f"- Уже резолвлен dataset_id={scope_dataset.get('dataset_id')} "
                    f"(database={scope_dataset.get('database_name', '-')}, "
                    f"table={scope_dataset.get('table_full', '-')}).\n"
                    "- Не запрашивай список таблиц через database/tables endpoint.\n"
                    "- Выполни задачу пользователя через dataset-level инструменты."
                )
                result = await self._safe_agent_run(retry_prompt, max_retries=1)
            
            return {
                "content": result,
                "role": "assistant",
                "finish_reason": "stop",
                "model": self.model_name,
                "session_id": self.session_id
            }
            
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error in chat processing: {e}")
            error_text = str(e)
            if "rate limit" in error_text.lower() or "429" in error_text:
                wait_seconds = self._extract_retry_after_seconds(
                    error_text,
                    default=self.rate_limit_cooldown_seconds,
                )
                self._set_rate_limit_cooldown(wait_seconds)
                return {
                    "content": (
                        "Достигнут лимит запросов OpenAI (429). "
                        f"Подождите примерно {wait_seconds} сек и повторите запрос."
                    ),
                    "role": "assistant",
                    "finish_reason": "error",
                    "model": self.model_name,
                    "session_id": self.session_id
                }
            return {
                "content": self._build_error_clarification_reply(
                    user_message=last_user_message,
                    error_text=error_text,
                ),
                "role": "assistant",
                "finish_reason": "error",
                "model": self.model_name,
                "session_id": self.session_id
            }
    
    async def close(self):
        """Close session-specific resources"""
        backend_logger.debug(f"Closing agent for session {self.session_id}")
        # Don't close shared MCP client
        self._initialized = False
        self._bound_loop_id = None
        self.agent = None
        self.mcp_client = None  # Just drop reference, don't close


# Agent session manager
class AgentSessionManager:
    """Manager for agent sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SupersetAIAgent] = {}
        self.sessions_lock: Optional[asyncio.Lock] = None
        self.sessions_lock_loop_id: Optional[int] = None

    def _get_sessions_lock(self) -> asyncio.Lock:
        loop_id = _current_loop_id()
        if (
            self.sessions_lock is None
            or self.sessions_lock_loop_id != loop_id
        ):
            self.sessions_lock = asyncio.Lock()
            self.sessions_lock_loop_id = loop_id
        return self.sessions_lock
    
    async def create_session(self) -> str:
        """Create a new agent session"""
        session_id = str(uuid.uuid4())[:8]
        
        async with self._get_sessions_lock():
            agent = SupersetAIAgent(session_id)
            self.sessions[session_id] = agent
        
        backend_logger.debug(f"Created new session: {session_id}")
        return session_id
    
    async def get_agent(self, session_id: str) -> Optional[SupersetAIAgent]:
        """Get agent for session"""
        async with self._get_sessions_lock():
            return self.sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        """Close a session"""
        async with self._get_sessions_lock():
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
    global _global_mcp_client, _global_mcp_client_loop_id, _session_manager
    
    # Close all sessions
    if _session_manager:
        await _session_manager.close_all_sessions()
        _session_manager = None
    
    # Close global MCP client
    if _global_mcp_client:
        await _global_mcp_client.close()
        _global_mcp_client = None
        _global_mcp_client_loop_id = None
        backend_logger.debug("Global MCP client closed")
