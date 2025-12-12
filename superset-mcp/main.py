from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterator,
    Callable,
    TypeVar,
    Awaitable,
    Union,
)
import os
import httpx
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import wraps
import json
import logging
import asyncio
import sys
from fastapi import FastAPI, HTTPException
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Настройка логгера без ограничений на длину строки
logging.basicConfig(
    level=logging.DEBUG,  # Используйте DEBUG для максимальной детализации
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr  # Всегда пишем в stderr
)

# Создаем отдельный логгер для файла с безграничной длиной строк
logger = logging.getLogger('superset_mcp_file')
logger.setLevel(logging.DEBUG)

# Файловый обработчик с большим буфером
file_handler = logging.FileHandler('superset_mcp_full.log', mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Форматтер без ограничений
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)
logger.propagate = False  # Не передаем выше

# Используйте logger в ваших функциях:
# logger.error(f"Полная ошибка: {full_traceback}")

logger = logging.getLogger(__name__)

"""
Superset MCP Integration - Full version with all tools
"""

load_dotenv()

# Constants
SUPERSET_BASE_URL = os.getenv("SUPERSET_BASE_URL", "http://localhost:8088")
SUPERSET_USERNAME = os.getenv("SUPERSET_USERNAME")
SUPERSET_PASSWORD = os.getenv("SUPERSET_PASSWORD")
ACCESS_TOKEN_STORE_PATH = os.path.join(os.path.dirname(__file__), ".superset_token")

# Global state
_global_client: Optional[httpx.AsyncClient] = None
_global_access_token: Optional[str] = None
_global_base_url: str = SUPERSET_BASE_URL

app = FastAPI(title="Superset MCP Server")

logger.info(f"Superset URL: {SUPERSET_BASE_URL}")
logger.info(f"Username set: {'Yes' if SUPERSET_USERNAME else 'No'}")
logger.info(f"Password set: {'Yes' if SUPERSET_PASSWORD else 'No'}")

if not SUPERSET_USERNAME or not SUPERSET_PASSWORD:
    logger.error("SUPERSET_USERNAME or SUPERSET_PASSWORD environment variables not set!")
    logger.error("Please set them in your .env file or environment.")


@dataclass
class SupersetContext:
    client: httpx.AsyncClient = field(default_factory=lambda: get_global_client())
    base_url: str = field(default_factory=lambda: _global_base_url)
    access_token: Optional[str] = field(default_factory=lambda: _global_access_token)
    app: FastAPI = app


def get_global_client() -> httpx.AsyncClient:
    global _global_client
    if _global_client is None:
        _global_client = httpx.AsyncClient(
            base_url=_global_base_url,
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=100),
            transport=httpx.AsyncHTTPTransport(retries=3)
        )
        logger.info("Created new global HTTP client")
    return _global_client


def get_global_access_token() -> Optional[str]:
    global _global_access_token
    return _global_access_token


def set_global_access_token(token: str) -> None:
    global _global_access_token, _global_client
    _global_access_token = token
    if _global_client:
        _global_client.headers.update({"Authorization": f"Bearer {token}"})


def load_stored_token() -> Optional[str]:
    try:
        if os.path.exists(ACCESS_TOKEN_STORE_PATH):
            with open(ACCESS_TOKEN_STORE_PATH, "r") as f:
                token = f.read().strip()
                if token:
                    set_global_access_token(token)
                    logger.info("Loaded stored access token")
                    return token
    except Exception as e:
        logger.warning(f"Warning: Could not load access token: {e}")
    return None


def save_access_token(token: str) -> None:
    try:
        with open(ACCESS_TOKEN_STORE_PATH, "w") as f:
            f.write(token)
        logger.info("Access token saved to file")
    except Exception as e:
        logger.warning(f"Warning: Could not save access token: {e}")


T = TypeVar("T")
R = TypeVar("R")

# ===== Helper Functions =====

def requires_auth(
    func: Callable[..., Awaitable[Dict[str, Any]]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    
    @wraps(func)
    async def wrapper(ctx: Context, *args, **kwargs) -> Dict[str, Any]:
        token = get_global_access_token()
        if not token:
            return {"error": "Not authenticated. Please authenticate first."}
        
        return await func(ctx, *args, **kwargs)
    
    return wrapper


def handle_api_errors(
    func: Callable[..., Awaitable[Dict[str, Any]]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    """Декоратор для обработки ошибок API с полным логированием
    
    Этот декоратор:
    1. Перехватывает все исключения в функциях
    2. Логирует полный traceback в файл
    3. Возвращает структурированную информацию об ошибке
    4. Сохраняет детали ошибки в отдельный файл для анализа
    """
    
    @wraps(func)
    async def wrapper(ctx: Context, *args, **kwargs) -> Dict[str, Any]:
        try:
            return await func(ctx, *args, **kwargs)
        except Exception as e:
            import traceback
            import time
            from datetime import datetime
            
            function_name = func.__name__
            full_traceback = traceback.format_exc()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Создаем уникальный идентификатор ошибки
            error_id = f"{function_name}_{timestamp}_{hash(full_traceback) % 1000000}"
            
            # Сохраняем полный traceback в отдельный файл
            error_dir = "error_logs"
            os.makedirs(error_dir, exist_ok=True)
            error_file = os.path.join(error_dir, f"{error_id}.txt")
            
            # Формируем детальный отчет об ошибке
            error_report = f"""
{'='*80}
ERROR REPORT: {error_id}
{'='*80}
Timestamp: {datetime.now().isoformat()}
Function: {function_name}
Exception Type: {type(e).__name__}
Exception Message: {str(e)}

Function Args:
{args}

Function Kwargs:
{kwargs}

Full Traceback:
{full_traceback}

Context Information:
- Base URL: {_global_base_url}
- Has Auth Token: {bool(get_global_access_token())}
- Username: {SUPERSET_USERNAME}
{'='*80}
"""
            
            # Сохраняем отчет в файл
            try:
                with open(error_file, 'w', encoding='utf-8') as f:
                    f.write(error_report)
            except Exception as write_error:
                logger.error(f"Failed to save error report: {write_error}")
            
            # Логируем ключевую информацию
            logger.error(f"🚨 ERROR in {function_name}: {type(e).__name__}: {str(e)}")
            logger.error(f"📁 Full error report saved to: {error_file}")
            
            # Для консоли выводим первые 5 строк traceback
            traceback_lines = full_traceback.split('\n')
            short_traceback = '\n'.join(traceback_lines[:10])  # Первые 10 строк
            
            # Возвращаем структурированную ошибку с ссылкой на полный отчет
            return {
                "success": False,
                "error": f"Error in {function_name}: {type(e).__name__}",
                "error_id": error_id,
                "exception_message": str(e),
                "error_file": error_file,
                "short_traceback": short_traceback,
                "timestamp": datetime.now().isoformat(),
                "suggestions": [
                    f"Check error details in file: {error_file}",
                    "Verify Superset server is running",
                    "Check authentication token validity",
                    "Review function arguments and parameters"
                ],
                "debug_info": {
                    "function": function_name,
                    "base_url": _global_base_url,
                    "has_token": bool(get_global_access_token()),
                    "error_time": timestamp
                }
            }
    
    return wrapper


async def get_fresh_csrf_token() -> Optional[str]:
    client = get_global_client()
    
    try:
        response = await client.get("/api/v1/security/csrf_token/")
        if response.status_code == 200:
            data = response.json()
            csrf_token = data.get("result")
            logger.debug(f"Obtained fresh CSRF token")
            return csrf_token
        else:
            logger.warning(f"Failed to get CSRF token: {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Error getting CSRF token: {str(e)}")
        return None


async def make_api_request(
    method: str,
    endpoint: str,
    data: Dict[str, Any] = None,
    params: Dict[str, Any] = None,
    needs_csrf: bool = False,
) -> Dict[str, Any]:
    client = get_global_client()
    
    headers = {}
    token = get_global_access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    csrf_token = None
    if needs_csrf:
        csrf_token = await get_fresh_csrf_token()
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token
            headers["Content-Type"] = "application/json"
        else:
            return {"error": "Failed to obtain CSRF token for the request"}
    
    try:
        if method.lower() == "get":
            response = await client.get(endpoint, params=params, headers=headers)
        elif method.lower() == "post":
            response = await client.post(
                endpoint, json=data, params=params, headers=headers
            )
        elif method.lower() == "put":
            response = await client.put(endpoint, json=data, headers=headers)
        elif method.lower() == "delete":
            response = await client.delete(endpoint, headers=headers)
        else:
            return {"error": f"Unsupported HTTP method: {method}"}
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            error_text = response.text[:500] if response.text else "No error details"
            return {
                "error": f"API request failed ({response.status_code}): {error_text}"
            }
    
    except httpx.TimeoutException:
        return {"error": f"Request timeout to {endpoint}"}
    except httpx.RequestError as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Request error: {str(e)}"}


# ===== Authentication Tools =====

async def superset_auth_check_token_validity(ctx: Context) -> Dict[str, Any]:
    token = get_global_access_token()
    if not token:
        return {"valid": False, "error": "No access token available"}
    
    result = await make_api_request("get", "/api/v1/me/")
    
    if "error" in result:
        return {"valid": False, "error": result["error"]}
    
    return {"valid": True, "user_info": result}


async def superset_auth_refresh_token(ctx: Context) -> Dict[str, Any]:
    token = get_global_access_token()
    if not token:
        return {"error": "No access token to refresh. Please authenticate first."}
    
    result = await make_api_request("post", "/api/v1/security/refresh", needs_csrf=True)
    
    if "error" in result:
        return {"error": f"Failed to refresh token: {result['error']}"}
    
    access_token = result.get("access_token")
    if not access_token:
        return {"error": "No access token returned from refresh"}
    
    save_access_token(access_token)
    set_global_access_token(access_token)
    
    return {
        "message": "Successfully refreshed access token",
        "access_token": access_token,
    }


async def superset_auth_authenticate_user(
    ctx: Context,
    username: Optional[str] = None,
    password: Optional[str] = None,
    refresh: bool = True,
) -> Dict[str, Any]:
    """Аутентификация пользователя в Superset
    
    Args:
        ctx: Контекст MCP
        username: Имя пользователя (если None, используется из переменных окружения)
        password: Пароль (если None, используется из переменных окружения)
        refresh: Обновить токен
        
    Returns:
        Словарь с результатом аутентификации
    """
    # Явно обрабатываем None значения
    auth_username = username if username is not None else SUPERSET_USERNAME
    auth_password = password if password is not None else SUPERSET_PASSWORD
    
    if not auth_username or not auth_password:
        return {
            "error": "No credentials provided",
            "details": "Please set SUPERSET_USERNAME and SUPERSET_PASSWORD environment variables or provide username and password directly.",
            "provided_username": "None" if username is None else "Provided",
            "provided_password": "None" if password is None else "Provided",
            "env_username_set": bool(SUPERSET_USERNAME),
            "env_password_set": bool(SUPERSET_PASSWORD)
        }
    
    logger.info(f"Authenticating with username: {auth_username}")
    
    # Используем новый клиент без предварительного получения CSRF токена
    async with httpx.AsyncClient(base_url=_global_base_url, timeout=30.0) as temp_client:
        try:
            # Сначала попробуем получить CSRF токен, но если не получится - продолжим без него
            csrf_token = None
            try:
                csrf_response = await temp_client.get("/api/v1/security/csrf_token/")
                if csrf_response.status_code == 200:
                    csrf_data = csrf_response.json()
                    csrf_token = csrf_data.get("result")
                    logger.info("Obtained CSRF token for authentication")
                else:
                    logger.warning(f"CSRF token request failed: {csrf_response.status_code}")
            except Exception as e:
                logger.warning(f"Could not get CSRF token: {e}")
            
            # Подготавливаем заголовки
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if csrf_token:
                headers["X-CSRFToken"] = csrf_token
            
            # Выполняем логин
            login_data = {
                "username": auth_username,
                "password": auth_password,
                "provider": "db",
                "refresh": refresh,
            }
            
            response = await temp_client.post(
                "/api/v1/security/login",
                json=login_data,
                headers=headers
            )
            
            logger.info(f"Authentication response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get("access_token")
                
                if access_token:
                    save_access_token(access_token)
                    set_global_access_token(access_token)
                    
                    # Обновляем заголовки глобального клиента
                    global_client = get_global_client()
                    global_client.headers.update({"Authorization": f"Bearer {access_token}"})
                    
                    logger.info(f"Successfully authenticated user: {auth_username}")
                    
                    return {
                        "success": True,
                        "message": f"Successfully authenticated as {auth_username}",
                        "access_token": access_token[:50] + "..." if len(access_token) > 50 else access_token,
                        "username": auth_username,
                        "token_preview": f"{access_token[:20]}...{access_token[-20:]}" if len(access_token) > 40 else access_token
                    }
                else:
                    return {
                        "error": "No access token in response",
                        "response_data": data
                    }
            else:
                error_text = response.text[:500] if response.text else "No error details"
                logger.error(f"Authentication failed: {response.status_code} - {error_text}")
                return {
                    "error": f"Authentication failed with status {response.status_code}",
                    "details": error_text,
                    "status_code": response.status_code
                }
                
        except httpx.TimeoutException:
            return {
                "error": "Authentication timeout",
                "details": "Superset server is not responding within 30 seconds"
            }
        except httpx.RequestError as e:
            return {
                "error": "Network error",
                "details": f"Failed to connect to Superset: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected authentication error: {str(e)}")
            return {
                "error": "Authentication error",
                "details": f"Unexpected error: {str(e)}"
            }


# ===== Dashboard Tools =====

@requires_auth
@handle_api_errors
async def superset_dashboard_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/dashboard/")


@requires_auth
@handle_api_errors
async def superset_dashboard_get_by_id(
    ctx: Context, dashboard_id: int
) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/dashboard/{dashboard_id}")


@requires_auth
@handle_api_errors
async def superset_dashboard_create(
    ctx: Context, dashboard_title: str, json_metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Создание дашборда в Superset
    
    Args:
        ctx: Контекст MCP
        dashboard_title: Название дашборда
        json_metadata: Дополнительные метаданные в формате JSON
        
    Returns:
        Словарь с результатом операции
    """
    try:
        # Проверяем аутентификацию
        token = get_global_access_token()
        if not token:
            return {
                "error": "Not authenticated",
                "details": "No access token available. Please authenticate first using superset_auth_authenticate_user.",
                "solution": "Run authentication tool first"
            }
        
        logger.info(f"Creating dashboard: {dashboard_title}")
        
        # 1. Формируем payload
        payload = {"dashboard_title": dashboard_title}
        if json_metadata is not None:
            if isinstance(json_metadata, dict):
                payload["json_metadata"] = json.dumps(json_metadata)
            else:
                try:
                    parsed_metadata = json.loads(str(json_metadata))
                    payload["json_metadata"] = json.dumps(parsed_metadata)
                except:
                    payload["json_metadata"] = "{}"
        else:
            payload["json_metadata"] = "{}"
        
        logger.debug(f"Dashboard creation payload: {json.dumps(payload, indent=2)}")
        
        # 2. Получаем CSRF токен через сессию (важно!)
        csrf_token = None
        try:
            # Используем глобальный клиент с cookies
            client = get_global_client()
            
            # Получаем CSRF токен (это установит cookies в клиенте)
            csrf_response = await client.get(
                "/api/v1/security/csrf_token/",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if csrf_response.status_code == 200:
                csrf_data = csrf_response.json()
                csrf_token = csrf_data.get("result")
                logger.info(f"Got CSRF token: {csrf_token[:50]}..." if csrf_token else "No CSRF token")
                
                # Также получаем cookies из ответа
                cookies = csrf_response.cookies
                if cookies:
                    logger.debug(f"Got cookies from CSRF request: {dict(cookies)}")
            else:
                logger.warning(f"CSRF token request failed: {csrf_response.status_code}")
                logger.debug(f"CSRF response: {csrf_response.text[:500]}")
                
        except Exception as e:
            logger.error(f"Error getting CSRF token: {str(e)}")
            return {
                "error": "CSRF token error",
                "details": f"Failed to get CSRF token: {str(e)}",
                "solution": "Check if Superset CSRF endpoint is accessible"
            }
        
        if not csrf_token:
            logger.warning("No CSRF token received. Proceeding without it...")
        
        # 3. Подготавливаем заголовки
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token
        
        # 4. Отправляем запрос
        logger.info(f"Making POST request to create dashboard '{dashboard_title}'")
        
        try:
            client = get_global_client()
            response = await client.post(
                "/api/v1/dashboard/",
                json=payload,
                headers=headers,
                timeout=30.0
            )
        except httpx.TimeoutException:
            error_msg = "Request timeout (30s) while creating dashboard"
            logger.error(error_msg)
            return {
                "error": "Request timeout",
                "details": error_msg
            }
        except httpx.RequestError as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            return {
                "error": "Network error",
                "details": error_msg
            }
        
        # 5. Обрабатываем ответ
        response_text = response.text
        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                dashboard_id = result.get("id")
                
                if dashboard_id:
                    logger.info(f"✅ Dashboard created successfully! ID: {dashboard_id}")
                    return {
                        "success": True,
                        "message": f"Dashboard '{dashboard_title}' created successfully",
                        "dashboard_id": dashboard_id,
                        "dashboard_title": dashboard_title,
                        "result": result
                    }
                else:
                    logger.warning(f"Dashboard created but no ID in response: {result}")
                    return {
                        "warning": "Dashboard might be created but no ID returned",
                        "response": result,
                        "status_code": response.status_code
                    }
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return {
                    "error": "Invalid JSON response",
                    "details": f"Failed to parse response: {str(e)}",
                    "raw_response": response_text[:1000]
                }
        
        else:
            # Пытаемся понять причину ошибки
            error_data = None
            try:
                if response_text:
                    error_data = json.loads(response_text)
            except:
                pass
            
            error_message = f"Failed to create dashboard: HTTP {response.status_code}"
            error_details = error_data if error_data else response_text[:2000]
            
            logger.error(f"{error_message}: {error_details}")
            
            result = {
                "error": error_message,
                "status_code": response.status_code,
                "details": error_details,
                "dashboard_title": dashboard_title
            }
            
            # Добавляем рекомендации
            if response.status_code == 400:
                if "CSRF" in str(error_details).upper():
                    result["suggestions"] = [
                        "CSRF token validation failed",
                        "Try re-authenticating with superset_auth_authenticate_user",
                        "Check if Superset requires session-based authentication",
                        "Try using session cookies instead of Bearer token"
                    ]
                else:
                    result["suggestions"] = [
                        "Check if dashboard title is unique",
                        "Verify JSON metadata format",
                        "Check required fields"
                    ]
            elif response.status_code == 401:
                result["suggestions"] = [
                    "Authentication token expired or invalid",
                    "Run superset_auth_authenticate_user to refresh token",
                    "Check if user exists in Superset"
                ]
            elif response.status_code == 403:
                result["suggestions"] = [
                    "Insufficient permissions to create dashboards",
                    "Contact Superset administrator",
                    "Check user role permissions"
                ]
            
            return result
            
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"Unexpected error in superset_dashboard_create:\n{full_traceback}")
        
        return {
            "error": f"Unexpected error: {type(e).__name__}",
            "message": str(e),
            "traceback": full_traceback[-1000:],  # Последние 1000 символов
            "suggestions": [
                "Check Superset server status",
                "Verify authentication",
                "Check network connectivity"
            ]
        }


@requires_auth
@handle_api_errors
async def superset_dashboard_update(
    ctx: Context, dashboard_id: int, data: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request(
        "put", f"/api/v1/dashboard/{dashboard_id}", data=data, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_dashboard_delete(ctx: Context, dashboard_id: int) -> Dict[str, Any]:
    result = await make_api_request(
        "delete", f"/api/v1/dashboard/{dashboard_id}", needs_csrf=True
    )
    
    if "error" in result:
        return result
    
    return {"message": f"Dashboard {dashboard_id} deleted successfully"}


# ===== Chart Tools =====

@requires_auth
@handle_api_errors
async def superset_chart_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/chart/")


@requires_auth
@handle_api_errors
async def superset_chart_get_by_id(ctx: Context, chart_id: int) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/chart/{chart_id}")


@requires_auth
@handle_api_errors
async def superset_chart_create(
    ctx: Context,
    slice_name: str,
    datasource_id: int,
    datasource_type: str,
    viz_type: str,
    params: Dict[str, Any],
    dashboard_id: Optional[int] = None,
    description: Optional[str] = None,
    cache_timeout: Optional[int] = None
) -> Dict[str, Any]:
    """Создание графика (chart) в Superset
    
    Args:
        ctx: Контекст MCP
        slice_name: Название графика
        datasource_id: ID источника данных
        datasource_type: Тип источника данных (table, dataset, etc.)
        viz_type: Тип визуализации (line, bar, pie, etc.)
        params: Параметры графика в формате JSON
        dashboard_id: ID дашборда для привязки (опционально)
        description: Описание графика (опционально)
        cache_timeout: Таймаут кэша в секундах (опционально)
        
    Returns:
        Словарь с результатом операции
    """
    try:
        # Проверяем аутентификацию
        token = get_global_access_token()
        if not token:
            return {
                "error": "Not authenticated",
                "details": "No access token available. Please authenticate first using superset_auth_authenticate_user.",
                "solution": "Run authentication tool first"
            }
        
        logger.info(f"Creating chart: {slice_name}")
        logger.info(f"Datasource ID: {datasource_id}, Type: {datasource_type}")
        logger.info(f"Viz type: {viz_type}")
        
        # 1. Формируем payload
        payload = {
            "slice_name": slice_name,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
            "viz_type": viz_type,
            "params": json.dumps(params) if isinstance(params, dict) else str(params)
        }
        
        # Добавляем опциональные параметры
        if dashboard_id is not None:
            payload["dashboards"] = [dashboard_id]
        
        if description is not None:
            payload["description"] = description
        
        if cache_timeout is not None:
            payload["cache_timeout"] = cache_timeout
        
        logger.debug(f"Chart creation payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # 2. Получаем CSRF токен через сессию
        csrf_token = None
        try:
            # Используем глобальный клиент с cookies
            client = get_global_client()
            
            # Получаем CSRF токен
            csrf_response = await client.get(
                "/api/v1/security/csrf_token/",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if csrf_response.status_code == 200:
                csrf_data = csrf_response.json()
                csrf_token = csrf_data.get("result")
                logger.info(f"Got CSRF token for chart creation: {csrf_token[:50]}..." if csrf_token else "No CSRF token")
                
                # Также получаем cookies из ответа
                cookies = csrf_response.cookies
                if cookies:
                    logger.debug(f"Got cookies from CSRF request: {dict(cookies)}")
            else:
                logger.warning(f"CSRF token request failed: {csrf_response.status_code}")
                logger.debug(f"CSRF response: {csrf_response.text[:500]}")
                
        except Exception as e:
            logger.error(f"Error getting CSRF token: {str(e)}")
            return {
                "error": "CSRF token error",
                "details": f"Failed to get CSRF token: {str(e)}",
                "solution": "Check if Superset CSRF endpoint is accessible"
            }
        
        if not csrf_token:
            logger.warning("No CSRF token received. Proceeding without it...")
        
        # 3. Подготавливаем заголовки
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if csrf_token:
            headers["X-CSRFToken"] = csrf_token
        
        # 4. Отправляем запрос
        logger.info(f"Making POST request to create chart '{slice_name}'")
        
        try:
            client = get_global_client()
            response = await client.post(
                "/api/v1/chart/",
                json=payload,
                headers=headers,
                timeout=30.0
            )
        except httpx.TimeoutException:
            error_msg = "Request timeout (30s) while creating chart"
            logger.error(error_msg)
            return {
                "error": "Request timeout",
                "details": error_msg,
                "suggestion": "Check if Superset server is running and accessible"
            }
        except httpx.RequestError as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            return {
                "error": "Network error",
                "details": error_msg,
                "suggestion": "Check network connectivity and Superset URL"
            }
        
        # 5. Обрабатываем ответ
        response_text = response.text
        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        
        # Сохраняем полный ответ для анализа
        if len(response_text) > 5000:
            import time
            timestamp = int(time.time())
            response_file = f"chart_response_{timestamp}.json"
            with open(response_file, 'w', encoding='utf-8') as f:
                f.write(response_text)
            logger.warning(f"Full response saved to file: {response_file}")
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                chart_id = result.get("id")
                
                if chart_id:
                    logger.info(f"✅ Chart created successfully! ID: {chart_id}")
                    
                    # Дополнительная информация о созданном чарте
                    chart_info = {
                        "id": chart_id,
                        "slice_name": result.get("slice_name"),
                        "viz_type": result.get("viz_type"),
                        "datasource_id": result.get("datasource_id"),
                        "datasource_type": result.get("datasource_type"),
                        "url": result.get("url")
                    }
                    
                    return {
                        "success": True,
                        "message": f"Chart '{slice_name}' created successfully",
                        "chart_id": chart_id,
                        "chart_info": chart_info,
                        "full_result": result
                    }
                else:
                    logger.warning(f"Chart created but no ID in response: {result}")
                    return {
                        "warning": "Chart might be created but no ID returned",
                        "response": result,
                        "status_code": response.status_code
                    }
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.debug(f"Raw response (first 1000 chars): {response_text[:1000]}")
                
                return {
                    "error": "Invalid JSON response",
                    "details": f"Failed to parse response: {str(e)}",
                    "raw_response_preview": response_text[:1000],
                    "status_code": response.status_code
                }
        
        else:
            # Пытаемся понять причину ошибки
            error_data = None
            try:
                if response_text:
                    error_data = json.loads(response_text)
            except:
                pass
            
            error_message = f"Failed to create chart: HTTP {response.status_code}"
            error_details = error_data if error_data else response_text[:2000]
            
            logger.error(f"{error_message}")
            logger.error(f"Error details: {error_details}")
            
            # Формируем структурированный результат
            result = {
                "error": error_message,
                "status_code": response.status_code,
                "details": error_details,
                "chart_info": {
                    "slice_name": slice_name,
                    "viz_type": viz_type,
                    "datasource_id": datasource_id,
                    "datasource_type": datasource_type
                }
            }
            
            # Анализируем ошибку и добавляем рекомендации
            error_text = str(error_details).lower()
            
            if response.status_code == 400:
                if "csrf" in error_text:
                    result["suggestions"] = [
                        "CSRF token validation failed",
                        "Try re-authenticating with superset_auth_authenticate_user",
                        "Check if CSRF endpoint is accessible: /api/v1/security/csrf_token/"
                    ]
                elif "datasource" in error_text:
                    result["suggestions"] = [
                        "Check if datasource exists and is accessible",
                        f"Verify datasource ID {datasource_id} and type '{datasource_type}'",
                        "Check permissions for the datasource"
                    ]
                elif "validation" in error_text or "invalid" in error_text:
                    result["suggestions"] = [
                        "Check parameters format and values",
                        "Verify viz_type is supported by Superset",
                        "Check if required params are provided"
                    ]
                else:
                    result["suggestions"] = [
                        "Check if chart name is unique",
                        "Verify all required parameters are provided",
                        "Check parameter formats and types"
                    ]
                    
            elif response.status_code == 401:
                result["suggestions"] = [
                    "Authentication token expired or invalid",
                    "Run superset_auth_authenticate_user to refresh token",
                    "Check if user has permission to create charts"
                ]
                
            elif response.status_code == 403:
                result["suggestions"] = [
                    "Insufficient permissions to create charts",
                    "Contact Superset administrator",
                    "Check user role permissions"
                ]
                
            elif response.status_code == 404:
                result["suggestions"] = [
                    "API endpoint not found",
                    "Check Superset version compatibility",
                    "Verify Superset URL and API path"
                ]
                
            elif response.status_code == 422:
                result["suggestions"] = [
                    "Validation error - check all field values",
                    "Verify datasource exists and is accessible",
                    "Check if viz_type is valid"
                ]
                
            elif response.status_code == 500:
                result["suggestions"] = [
                    "Internal server error in Superset",
                    "Check Superset server logs",
                    "Try with simpler chart configuration",
                    "Verify database connection for datasource"
                ]
            
            # Добавляем популярные типы визуализаций для справки
            result["viz_type_reference"] = {
                "common_viz_types": [
                    "line", "bar", "pie", "area", "table", "pivot_table", 
                    "histogram", "box_plot", "scatter", "bubble", "heatmap",
                    "big_number", "big_number_total", "word_cloud", "treemap"
                ],
                "note": "Check Superset documentation for full list of visualization types"
            }
            
            return result
            
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        logger.error(f"Unexpected error in superset_chart_create:\n{full_traceback}")
        
        return {
            "error": f"Unexpected error: {type(e).__name__}",
            "message": str(e),
            "traceback_summary": full_traceback.split('\n')[-10:],  # Последние 10 строк
            "suggestions": [
                "Check Superset server status",
                "Verify authentication token is valid",
                "Check network connectivity",
                "Verify datasource exists and is accessible"
            ],
            "input_parameters": {
                "slice_name": slice_name,
                "datasource_id": datasource_id,
                "datasource_type": datasource_type,
                "viz_type": viz_type,
                "params_keys": list(params.keys()) if isinstance(params, dict) else "Not a dict"
            }
        }


# Дополнительная вспомогательная функция для получения списка типов визуализаций
async def superset_chart_get_viz_types(ctx: Context) -> Dict[str, Any]:
    """Получение списка доступных типов визуализаций в Superset"""
    try:
        token = get_global_access_token()
        if not token:
            return {"error": "Not authenticated"}
        
        client = get_global_client()
        response = await client.get(
            "/api/v1/chart/viz_types/",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "viz_types": result.get("result", []),
                "count": len(result.get("result", [])),
                "note": "Available visualization types for chart creation"
            }
        else:
            return {
                "error": f"Failed to get viz types: {response.status_code}",
                "details": response.text[:500]
            }
            
    except Exception as e:
        logger.error(f"Error getting viz types: {str(e)}")
        
        # Возвращаем статический список как fallback
        common_viz_types = [
            {"value": "line", "label": "Line Chart"},
            {"value": "bar", "label": "Bar Chart"},
            {"value": "pie", "label": "Pie Chart"},
            {"value": "area", "label": "Area Chart"},
            {"value": "table", "label": "Table"},
            {"value": "pivot_table", "label": "Pivot Table"},
            {"value": "histogram", "label": "Histogram"},
            {"value": "box_plot", "label": "Box Plot"},
            {"value": "scatter", "label": "Scatter Plot"},
            {"value": "big_number", "label": "Big Number"},
            {"value": "big_number_total", "label": "Big Number with Trendline"},
            {"value": "heatmap", "label": "Heatmap"},
            {"value": "treemap", "label": "Treemap"},
            {"value": "word_cloud", "label": "Word Cloud"}
        ]
        
        return {
            "warning": "Could not fetch dynamic viz types, using static list",
            "viz_types": common_viz_types,
            "count": len(common_viz_types)
        }


# Функция для получения информации о datasource
async def superset_chart_validate_datasource(
    ctx: Context,
    datasource_id: int,
    datasource_type: str
) -> Dict[str, Any]:
    """Валидация источника данных перед созданием графика"""
    try:
        token = get_global_access_token()
        if not token:
            return {"error": "Not authenticated"}
        
        # Пробуем получить информацию о datasource в зависимости от типа
        if datasource_type.lower() in ["table", "dataset"]:
            endpoint = f"/api/v1/dataset/{datasource_id}"
        else:
            # Для других типов пробуем общий подход
            endpoint = f"/api/v1/{datasource_type}/{datasource_id}"
        
        client = get_global_client()
        response = await client.get(
            endpoint,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            datasource_info = response.json()
            return {
                "valid": True,
                "datasource_exists": True,
                "datasource_info": {
                    "id": datasource_info.get("id"),
                    "name": datasource_info.get("table_name") or datasource_info.get("name"),
                    "type": datasource_type,
                    "database_id": datasource_info.get("database", {}).get("id"),
                    "schema": datasource_info.get("schema"),
                    "columns_count": len(datasource_info.get("columns", []))
                }
            }
        elif response.status_code == 404:
            return {
                "valid": False,
                "error": f"Datasource {datasource_id} of type '{datasource_type}' not found",
                "suggestions": [
                    f"Check if datasource with ID {datasource_id} exists",
                    f"Verify datasource type '{datasource_type}' is correct",
                    "Use superset_dataset_list to see available datasets"
                ]
            }
        else:
            return {
                "valid": False,
                "error": f"Failed to validate datasource: {response.status_code}",
                "details": response.text[:500]
            }
            
    except httpx.RequestError as e:
        return {
            "valid": False,
            "error": f"Network error validating datasource: {str(e)}"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error validating datasource: {str(e)}"
        }

@requires_auth
@handle_api_errors
async def superset_chart_update(
    ctx: Context, chart_id: int, data: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request("put", f"/api/v1/chart/{chart_id}", data=data, needs_csrf=True)


@requires_auth
@handle_api_errors
async def superset_chart_delete(ctx: Context, chart_id: int) -> Dict[str, Any]:
    result = await make_api_request("delete", f"/api/v1/chart/{chart_id}", needs_csrf=True)
    
    if "error" in result:
        return result
    
    return {"message": f"Chart {chart_id} deleted successfully"}


# ===== Database Tools =====

@requires_auth
@handle_api_errors
async def superset_database_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/database/")


@requires_auth
@handle_api_errors
async def superset_database_get_by_id(ctx: Context, database_id: int) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/database/{database_id}")


@requires_auth
@handle_api_errors
async def superset_database_create(
    ctx: Context,
    engine: str,
    configuration_method: str,
    database_name: str,
    sqlalchemy_uri: str,
) -> Dict[str, Any]:
    payload = {
        "engine": engine,
        "configuration_method": configuration_method,
        "database_name": database_name,
        "sqlalchemy_uri": sqlalchemy_uri,
        "allow_dml": True,
        "allow_cvas": True,
        "allow_ctas": True,
        "expose_in_sqllab": True,
    }
    
    return await make_api_request("post", "/api/v1/database/", data=payload, needs_csrf=True)


@requires_auth
@handle_api_errors
async def superset_database_get_tables(
    ctx: Context, database_id: int
) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/database/{database_id}/tables/")


@requires_auth
@handle_api_errors
async def superset_database_schemas(ctx: Context, database_id: int) -> Dict[str, Any]:
    return await make_api_request(
        "get", f"/api/v1/database/{database_id}/schemas/"
    )


@requires_auth
@handle_api_errors
async def superset_database_test_connection(
    ctx: Context, database_data: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request(
        "post", "/api/v1/database/test_connection", data=database_data, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_database_update(
    ctx: Context, database_id: int, data: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request(
        "put", f"/api/v1/database/{database_id}", data=data, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_database_delete(ctx: Context, database_id: int) -> Dict[str, Any]:
    result = await make_api_request("delete", f"/api/v1/database/{database_id}", needs_csrf=True)
    
    if "error" in result:
        return result
    
    return {"message": f"Database {database_id} deleted successfully"}


@requires_auth
@handle_api_errors
async def superset_database_get_catalogs(
    ctx: Context, database_id: int
) -> Dict[str, Any]:
    return await make_api_request(
        "get", f"/api/v1/database/{database_id}/catalogs/"
    )


@requires_auth
@handle_api_errors
async def superset_database_get_connection(
    ctx: Context, database_id: int
) -> Dict[str, Any]:
    return await make_api_request(
        "get", f"/api/v1/database/{database_id}/connection"
    )


@requires_auth
@handle_api_errors
async def superset_database_get_function_names(
    ctx: Context, database_id: int
) -> Dict[str, Any]:
    return await make_api_request(
        "get", f"/api/v1/database/{database_id}/function_names/"
    )


@requires_auth
@handle_api_errors
async def superset_database_get_related_objects(
    ctx: Context, database_id: int
) -> Dict[str, Any]:
    return await make_api_request(
        "get", f"/api/v1/database/{database_id}/related_objects/"
    )


@requires_auth
@handle_api_errors
async def superset_database_validate_sql(
    ctx: Context, database_id: int, sql: str
) -> Dict[str, Any]:
    payload = {"sql": sql}
    return await make_api_request(
        "post", f"/api/v1/database/{database_id}/validate_sql/", data=payload, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_database_validate_parameters(
    ctx: Context, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request(
        "post", "/api/v1/database/validate_parameters/", data=parameters, needs_csrf=True
    )


# ===== Dataset Tools =====

@requires_auth
@handle_api_errors
async def superset_dataset_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/dataset/")


@requires_auth
@handle_api_errors
async def superset_dataset_get_by_id(ctx: Context, dataset_id: int) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/dataset/{dataset_id}")


@requires_auth
@handle_api_errors
async def superset_dataset_create(
    ctx: Context,
    table_name: str,
    database_id: int,
    schema: str = None,
    owners: List[int] = None,
) -> Dict[str, Any]:
    payload = {
        "table_name": table_name,
        "database": database_id,
    }
    
    if schema:
        payload["schema"] = schema
    
    if owners:
        payload["owners"] = owners
    
    return await make_api_request("post", "/api/v1/dataset/", data=payload, needs_csrf=True)


# ===== SQL Lab Tools =====

@requires_auth
@handle_api_errors
async def superset_sqllab_execute_query(
    ctx: Context, database_id: int, sql: str
) -> Dict[str, Any]:
    payload = {
        "database_id": database_id,
        "sql": sql,
        "schema": "",
        "tab": "MCP Query",
        "runAsync": False,
        "select_as_cta": False,
    }
    
    return await make_api_request("post", "/api/v1/sqllab/execute/", data=payload, needs_csrf=True)


@requires_auth
@handle_api_errors
async def superset_sqllab_get_saved_queries(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/saved_query/")


@requires_auth
@handle_api_errors
async def superset_sqllab_format_sql(ctx: Context, sql: str) -> Dict[str, Any]:
    payload = {"sql": sql}
    return await make_api_request(
        "post", "/api/v1/sqllab/format_sql", data=payload, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_sqllab_get_results(ctx: Context, key: str) -> Dict[str, Any]:
    return await make_api_request(
        "get", f"/api/v1/sqllab/results/", params={"key": key}
    )


@requires_auth
@handle_api_errors
async def superset_sqllab_estimate_query_cost(
    ctx: Context, database_id: int, sql: str, schema: str = None
) -> Dict[str, Any]:
    payload = {
        "database_id": database_id,
        "sql": sql,
    }
    
    if schema:
        payload["schema"] = schema
    
    return await make_api_request("post", "/api/v1/sqllab/estimate", data=payload, needs_csrf=True)


@requires_auth
@handle_api_errors
async def superset_sqllab_export_query_results(
    ctx: Context, client_id: str
) -> Dict[str, Any]:
    client = get_global_client()
    
    try:
        response = await client.get(f"/api/v1/sqllab/export/{client_id}")
        
        if response.status_code != 200:
            return {
                "error": f"Failed to export query results: {response.status_code} - {response.text}"
            }
        
        return {"message": "Query results exported successfully", "data": response.text}
        
    except Exception as e:
        return {"error": f"Error exporting query results: {str(e)}"}


@requires_auth
@handle_api_errors
async def superset_sqllab_get_bootstrap_data(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/sqllab/")


# ===== Saved Query Tools =====

@requires_auth
@handle_api_errors
async def superset_saved_query_get_by_id(ctx: Context, query_id: int) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/saved_query/{query_id}")


@requires_auth
@handle_api_errors
async def superset_saved_query_create(
    ctx: Context, query_data: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request("post", "/api/v1/saved_query/", data=query_data, needs_csrf=True)


# ===== Query Tools =====

@requires_auth
@handle_api_errors
async def superset_query_stop(ctx: Context, client_id: str) -> Dict[str, Any]:
    payload = {"client_id": client_id}
    return await make_api_request("post", "/api/v1/query/stop", data=payload, needs_csrf=True)


@requires_auth
@handle_api_errors
async def superset_query_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/query/")


@requires_auth
@handle_api_errors
async def superset_query_get_by_id(ctx: Context, query_id: int) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/query/{query_id}")


# ===== Activity and User Tools =====

@requires_auth
@handle_api_errors
async def superset_activity_get_recent(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/log/recent_activity/")


@requires_auth
@handle_api_errors
async def superset_user_get_current(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/me/")


@requires_auth
@handle_api_errors
async def superset_user_get_roles(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/me/roles/")


# ===== Tag Tools =====

@requires_auth
@handle_api_errors
async def superset_tag_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/tag/")


@requires_auth
@handle_api_errors
async def superset_tag_create(ctx: Context, name: str) -> Dict[str, Any]:
    payload = {"name": name}
    return await make_api_request("post", "/api/v1/tag/", data=payload, needs_csrf=True)


@requires_auth
@handle_api_errors
async def superset_tag_get_by_id(ctx: Context, tag_id: int) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/tag/{tag_id}")


@requires_auth
@handle_api_errors
async def superset_tag_objects(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/tag/get_objects/")


@requires_auth
@handle_api_errors
async def superset_tag_delete(ctx: Context, tag_id: int) -> Dict[str, Any]:
    result = await make_api_request("delete", f"/api/v1/tag/{tag_id}", needs_csrf=True)
    
    if "error" in result:
        return result
    
    return {"message": f"Tag {tag_id} deleted successfully"}


@requires_auth
@handle_api_errors
async def superset_tag_object_add(
    ctx: Context, object_type: str, object_id: int, tag_name: str
) -> Dict[str, Any]:
    payload = {
        "object_type": object_type,
        "object_id": object_id,
        "tag_name": tag_name,
    }
    
    return await make_api_request(
        "post", "/api/v1/tag/tagged_objects", data=payload, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_tag_object_remove(
    ctx: Context, object_type: str, object_id: int, tag_name: str
) -> Dict[str, Any]:
    result = await make_api_request(
        "delete",
        f"/api/v1/tag/{object_type}/{object_id}",
        params={"tag_name": tag_name},
        needs_csrf=True
    )
    
    if "error" in result:
        return result
    
    return {
        "message": f"Tag '{tag_name}' removed from {object_type} {object_id} successfully"
    }


# ===== Explore Tools =====

@requires_auth
@handle_api_errors
async def superset_explore_form_data_create(
    ctx: Context, form_data: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request(
        "post", "/api/v1/explore/form_data", data=form_data, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_explore_form_data_get(ctx: Context, key: str) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/explore/form_data/{key}")


@requires_auth
@handle_api_errors
async def superset_explore_permalink_create(
    ctx: Context, state: Dict[str, Any]
) -> Dict[str, Any]:
    return await make_api_request(
        "post", "/api/v1/explore/permalink", data=state, needs_csrf=True
    )


@requires_auth
@handle_api_errors
async def superset_explore_permalink_get(ctx: Context, key: str) -> Dict[str, Any]:
    return await make_api_request("get", f"/api/v1/explore/permalink/{key}")


# ===== Menu Tools =====

@requires_auth
@handle_api_errors
async def superset_menu_get(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/menu/")


# ===== Configuration Tools =====

@handle_api_errors
async def superset_config_get_base_url(ctx: Context) -> Dict[str, Any]:
    return {
        "base_url": _global_base_url,
        "message": f"Connected to Superset instance at: {_global_base_url}",
    }


# ===== Advanced Data Type Tools =====

@requires_auth
@handle_api_errors
async def superset_advanced_data_type_convert(
    ctx: Context, type_name: str, value: Any
) -> Dict[str, Any]:
    params = {
        "type_name": type_name,
        "value": value,
    }
    
    return await make_api_request(
        "get", "/api/v1/advanced_data_type/convert", params=params
    )


@requires_auth
@handle_api_errors
async def superset_advanced_data_type_list(ctx: Context) -> Dict[str, Any]:
    return await make_api_request("get", "/api/v1/advanced_data_type/types")


# ===== Minimal MCP Server =====

class MinimalMCPServer:
    """Минимальный MCP сервер для запуска через stdio"""
    
    def __init__(self):
        # Создаем словарь инструментов
        self.tools = {
            # Authentication Tools
            "superset_auth_authenticate_user": superset_auth_authenticate_user,
            "superset_auth_check_token_validity": superset_auth_check_token_validity,
            "superset_auth_refresh_token": superset_auth_refresh_token,
            
            # Dashboard Tools
            "superset_dashboard_list": superset_dashboard_list,
            "superset_dashboard_get_by_id": superset_dashboard_get_by_id,
            "superset_dashboard_create": superset_dashboard_create,
            "superset_dashboard_update": superset_dashboard_update,
            "superset_dashboard_delete": superset_dashboard_delete,
            
            # Chart Tools
            "superset_chart_list": superset_chart_list,
            "superset_chart_get_by_id": superset_chart_get_by_id,
            "superset_chart_create": superset_chart_create,
            "superset_chart_update": superset_chart_update,
            "superset_chart_delete": superset_chart_delete,
            
            # Database Tools
            "superset_database_list": superset_database_list,
            "superset_database_get_by_id": superset_database_get_by_id,
            "superset_database_create": superset_database_create,
            "superset_database_get_tables": superset_database_get_tables,
            "superset_database_schemas": superset_database_schemas,
            "superset_database_test_connection": superset_database_test_connection,
            "superset_database_update": superset_database_update,
            "superset_database_delete": superset_database_delete,
            "superset_database_get_catalogs": superset_database_get_catalogs,
            "superset_database_get_connection": superset_database_get_connection,
            "superset_database_get_function_names": superset_database_get_function_names,
            "superset_database_get_related_objects": superset_database_get_related_objects,
            "superset_database_validate_sql": superset_database_validate_sql,
            "superset_database_validate_parameters": superset_database_validate_parameters,
            
            # Dataset Tools
            "superset_dataset_list": superset_dataset_list,
            "superset_dataset_get_by_id": superset_dataset_get_by_id,
            "superset_dataset_create": superset_dataset_create,
            
            # SQL Lab Tools
            "superset_sqllab_execute_query": superset_sqllab_execute_query,
            "superset_sqllab_get_saved_queries": superset_sqllab_get_saved_queries,
            "superset_sqllab_format_sql": superset_sqllab_format_sql,
            "superset_sqllab_get_results": superset_sqllab_get_results,
            "superset_sqllab_estimate_query_cost": superset_sqllab_estimate_query_cost,
            "superset_sqllab_export_query_results": superset_sqllab_export_query_results,
            "superset_sqllab_get_bootstrap_data": superset_sqllab_get_bootstrap_data,
            
            # Saved Query Tools
            "superset_saved_query_get_by_id": superset_saved_query_get_by_id,
            "superset_saved_query_create": superset_saved_query_create,
            
            # Query Tools
            "superset_query_stop": superset_query_stop,
            "superset_query_list": superset_query_list,
            "superset_query_get_by_id": superset_query_get_by_id,
            
            # Activity and User Tools
            "superset_activity_get_recent": superset_activity_get_recent,
            "superset_user_get_current": superset_user_get_current,
            "superset_user_get_roles": superset_user_get_roles,
            
            # Tag Tools
            "superset_tag_list": superset_tag_list,
            "superset_tag_create": superset_tag_create,
            "superset_tag_get_by_id": superset_tag_get_by_id,
            "superset_tag_objects": superset_tag_objects,
            "superset_tag_delete": superset_tag_delete,
            "superset_tag_object_add": superset_tag_object_add,
            "superset_tag_object_remove": superset_tag_object_remove,
            
            # Explore Tools
            "superset_explore_form_data_create": superset_explore_form_data_create,
            "superset_explore_form_data_get": superset_explore_form_data_get,
            "superset_explore_permalink_create": superset_explore_permalink_create,
            "superset_explore_permalink_get": superset_explore_permalink_get,
            
            # Menu Tools
            "superset_menu_get": superset_menu_get,
            
            # Configuration Tools
            "superset_config_get_base_url": superset_config_get_base_url,
            
            # Advanced Data Type Tools
            "superset_advanced_data_type_convert": superset_advanced_data_type_convert,
            "superset_advanced_data_type_list": superset_advanced_data_type_list,
        }
        
        # Автоматически генерируем схемы для инструментов
        self.tool_schemas = self._generate_tool_schemas()

            # Ручные схемы для критически важных инструментов (переопределят автоматические)
        self.manual_schemas = {
            # Authentication Tools
            "superset_auth_authenticate_user": {
                "name": "superset_auth_authenticate_user",
                "description": "Аутентификация пользователя в Superset",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": ["string", "null"],
                            "description": "Имя пользователя (если не указано или null, используется из переменных окружения)"
                        },
                        "password": {
                            "type": ["string", "null"],
                            "description": "Пароль (если не указан или null, используется из переменных окружения)"
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Обновить токен",
                            "default": True
                        }
                    },
                    "required": []
                }
            },
            "superset_auth_login": {
                "name": "superset_auth_login",
                "description": "Упрощенная аутентификация с использованием переменных окружения",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_auth_check_token_validity": {
                "name": "superset_auth_check_token_validity",
                "description": "Проверка валидности токена аутентификации",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_auth_refresh_token": {
                "name": "superset_auth_refresh_token",
                "description": "Обновление токена аутентификации",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Dashboard Tools
            "superset_dashboard_list": {
                "name": "superset_dashboard_list",
                "description": "Получение списка всех дашбордов",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_dashboard_get_by_id": {
                "name": "superset_dashboard_get_by_id",
                "description": "Получение информации о дашборде по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dashboard_id": {
                            "type": "integer",
                            "description": "ID дашборда"
                        }
                    },
                    "required": ["dashboard_id"]
                }
            },
            "superset_dashboard_create": {
                "name": "superset_dashboard_create",
                "description": "Создание дашборда в Superset",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dashboard_title": {
                            "type": "string",
                            "description": "Название дашборда (обязательно)"
                        },
                        "json_metadata": {
                            "type": "object",
                            "description": "Дополнительные метаданные в формате JSON",
                            "default": {}
                        }
                    },
                    "required": ["dashboard_title"]
                }
            },
            "superset_dashboard_update": {
                "name": "superset_dashboard_update",
                "description": "Обновление дашборда",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dashboard_id": {
                            "type": "integer",
                            "description": "ID дашборда"
                        },
                        "data": {
                            "type": "object",
                            "description": "Данные для обновления"
                        }
                    },
                    "required": ["dashboard_id", "data"]
                }
            },
            "superset_dashboard_delete": {
                "name": "superset_dashboard_delete",
                "description": "Удаление дашборда",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dashboard_id": {
                            "type": "integer",
                            "description": "ID дашборда"
                        }
                    },
                    "required": ["dashboard_id"]
                }
            },

            # Chart Tools
            "superset_chart_list": {
                "name": "superset_chart_list",
                "description": "Получение списка всех графиков",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_chart_get_by_id": {
                "name": "superset_chart_get_by_id",
                "description": "Получение информации о графике по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chart_id": {
                            "type": "integer",
                            "description": "ID графика"
                        }
                    },
                    "required": ["chart_id"]
                }
            },
            "superset_chart_create": {
                "name": "superset_chart_create",
                "description": "Создание графика (chart) в Superset",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "slice_name": {
                            "type": "string",
                            "description": "Название графика"
                        },
                        "datasource_id": {
                            "type": "integer",
                            "description": "ID источника данных"
                        },
                        "datasource_type": {
                            "type": "string",
                            "description": "Тип источника данных",
                            "default": "table"
                        },
                        "viz_type": {
                            "type": "string",
                            "description": "Тип визуализации",
                            "default": "table"
                        },
                        "params": {
                            "type": "object",
                            "description": "Параметры графика",
                            "default": {}
                        },
                        "dashboard_id": {
                            "type": "integer",
                            "description": "ID дашборда для привязки"
                        },
                        "description": {
                            "type": "string",
                            "description": "Описание графика"
                        },
                        "cache_timeout": {
                            "type": "integer",
                            "description": "Таймаут кэша в секундах"
                        },
                        "force_csrf": {
                            "type": "boolean",
                            "description": "Принудительно использовать CSRF",
                            "default": False
                        }
                    },
                    "required": ["slice_name", "datasource_id"]
                }
            },
            "superset_chart_update": {
                "name": "superset_chart_update",
                "description": "Обновление графика",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chart_id": {
                            "type": "integer",
                            "description": "ID графика"
                        },
                        "data": {
                            "type": "object",
                            "description": "Данные для обновления"
                        }
                    },
                    "required": ["chart_id", "data"]
                }
            },
            "superset_chart_delete": {
                "name": "superset_chart_delete",
                "description": "Удаление графика",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chart_id": {
                            "type": "integer",
                            "description": "ID графика"
                        }
                    },
                    "required": ["chart_id"]
                }
            },
            "superset_chart_get_viz_types": {
                "name": "superset_chart_get_viz_types",
                "description": "Получение списка доступных типов визуализаций",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_chart_validate_datasource": {
                "name": "superset_chart_validate_datasource",
                "description": "Валидация источника данных перед созданием графика",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "datasource_id": {
                            "type": "integer",
                            "description": "ID источника данных"
                        },
                        "datasource_type": {
                            "type": "string",
                            "description": "Тип источника данных",
                            "default": "table"
                        }
                    },
                    "required": ["datasource_id", "datasource_type"]
                }
            },

            # Database Tools
            "superset_database_list": {
                "name": "superset_database_list",
                "description": "Получение списка всех баз данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_database_get_by_id": {
                "name": "superset_database_get_by_id",
                "description": "Получение информации о базе данных по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_create": {
                "name": "superset_database_create",
                "description":  "Создание базы данных в Superset",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "Тип базы данных (например, postgresql, mysql, etc.)"
                        },
                        "configuration_method": {
                            "type": "string",
                            "description": "Метод конфигурации"
                        },
                        "database_name": {
                            "type": "string",
                            "description": "Имя базы данных"
                        },
                        "sqlalchemy_uri": {
                            "type": "string",
                            "description": "URI подключения SQLAlchemy"
                        }
                    },
                    "required": ["engine", "configuration_method", "database_name", "sqlalchemy_uri"]
                }
            },
            "superset_database_get_tables": {
                "name": "superset_database_get_tables",
                "description": "Получение списка таблиц в базе данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_schemas": {
                "name": "superset_database_schemas",
                "description": "Получение списка схем в базе данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_test_connection": {
                "name": "superset_database_test_connection",
                "description": "Тестирование подключения к базе данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_data": {
                            "type": "object",
                            "description": "Данные для подключения к базе данных"
                        }
                    },
                    "required": ["database_data"]
                }
            },
            "superset_database_update": {
                "name": "superset_database_update",
                "description": "Обновление базы данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        },
                        "data": {
                            "type": "object",
                            "description": "Данные для обновления"
                        }
                    },
                    "required": ["database_id", "data"]
                }
            },
            "superset_database_delete": {
                "name": "superset_database_delete",
                "description": "Удаление базы данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_get_catalogs": {
                "name": "superset_database_get_catalogs",
                "description": "Получение списка каталогов в базе данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_get_connection": {
                "name": "superset_database_get_connection",
                "description": "Получение информации о подключении к базе данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_get_function_names": {
                "name": "superset_database_get_function_names",
                "description": "Получение списка имен функций в базе данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_get_related_objects": {
                "name": "superset_database_get_related_objects",
                "description": "Получение связанных объектов базы данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        }
                    },
                    "required": ["database_id"]
                }
            },
            "superset_database_validate_sql": {
                "name": "superset_database_validate_sql",
                "description": "Валидация SQL запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL запрос для валидации"
                        }
                    },
                    "required": ["database_id", "sql"]
                }
            },
            "superset_database_validate_parameters": {
                "name": "superset_database_validate_parameters",
                "description": "Валидация параметров базы данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "parameters": {
                            "type": "object",
                            "description": "Параметры для валидации"
                        }
                    },
                    "required": ["parameters"]
                }
            },

            # Dataset Tools
            "superset_dataset_list": {
                "name": "superset_dataset_list",
                "description": "Получение списка всех наборов данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_dataset_get_by_id": {
                "name": "superset_dataset_get_by_id",
                "description": "Получение информации о наборе данных по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "integer",
                            "description": "ID набора данных"
                        }
                    },
                    "required": ["dataset_id"]
                }
            },
            "superset_dataset_create": {
                "name": "superset_dataset_create",
                "description": "Создание набора данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Имя таблицы"
                        },
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        },
                        "schema": {
                            "type": "string",
                            "description": "Схема (опционально)"
                        },
                        "owners": {
                            "type": "array",
                            "description": "Список ID владельцев",
                            "items": {"type": "integer"}
                        }
                    },
                    "required": ["table_name", "database_id"]
                }
            },

            # SQL Lab Tools
            "superset_sqllab_execute_query": {
                "name": "superset_sqllab_execute_query",
                "description": "Выполнение SQL запроса в SQL Lab",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL запрос"
                        }
                    },
                    "required": ["database_id", "sql"]
                }
            },
            "superset_sqllab_get_saved_queries": {
                "name": "superset_sqllab_get_saved_queries",
                "description": "Получение списка сохраненных SQL запросов",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_sqllab_format_sql": {
                "name": "superset_sqllab_format_sql",
                "description": "Форматирование SQL запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL запрос для форматирования"
                        }
                    },
                    "required": ["sql"]
                }
            },
            "superset_sqllab_get_results": {
                "name": "superset_sqllab_get_results",
                "description": "Получение результатов SQL запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Ключ результатов"
                        }
                    },
                    "required": ["key"]
                }
            },
            "superset_sqllab_estimate_query_cost": {
                "name": "superset_sqllab_estimate_query_cost",
                "description": "Оценка стоимости SQL запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "database_id": {
                            "type": "integer",
                            "description": "ID базы данных"
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL запрос"
                        },
                        "schema": {
                            "type": "string",
                            "description": "Схема (опционально)"
                        }
                    },
                    "required": ["database_id", "sql"]
                }
            },
            "superset_sqllab_export_query_results": {
                "name": "superset_sqllab_export_query_results",
                "description": "Экспорт результатов SQL запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "ID клиента"
                        }
                    },
                    "required": ["client_id"]
                }
            },
            "superset_sqllab_get_bootstrap_data": {
                "name": "superset_sqllab_get_bootstrap_data",
                "description": "Получение bootstrap данных SQL Lab",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Saved Query Tools
            "superset_saved_query_get_by_id": {
                "name": "superset_saved_query_get_by_id",
                "description": "Получение информации о сохраненном запросе по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query_id": {
                            "type": "integer",
                            "description": "ID сохраненного запроса"
                        }
                    },
                    "required": ["query_id"]
                }
            },
            "superset_saved_query_create": {
                "name": "superset_saved_query_create",
                "description": "Создание сохраненного SQL запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query_data": {
                            "type": "object",
                            "description": "Данные запроса"
                        }
                    },
                    "required": ["query_data"]
                }
            },

            # Query Tools
            "superset_query_stop": {
                "name": "superset_query_stop",
                "description": "Остановка выполнения запроса",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "client_id": {
                            "type": "string",
                            "description": "ID клиента"
                        }
                    },
                    "required": ["client_id"]
                }
            },
            "superset_query_list": {
                "name": "superset_query_list",
                "description": "Получение списка запросов",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_query_get_by_id": {
                "name": "superset_query_get_by_id",
                "description": "Получение информации о запросе по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query_id": {
                            "type": "integer",
                            "description": "ID запроса"
                        }
                    },
                    "required": ["query_id"]
                }
            },

            # Activity and User Tools
            "superset_activity_get_recent": {
                "name": "superset_activity_get_recent",
                "description": "Получение последней активности",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_user_get_current": {
                "name": "superset_user_get_current",
                "description": "Получение информации о текущем пользователе",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_user_get_roles": {
                "name": "superset_user_get_roles",
                "description": "Получение ролей текущего пользователя",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Tag Tools
            "superset_tag_list": {
                "name": "superset_tag_list",
                "description": "Получение списка всех тегов",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_tag_create": {
                "name": "superset_tag_create",
                "description": "Создание тега",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Имя тега"
                        }
                    },
                    "required": ["name"]
                }
            },
            "superset_tag_get_by_id": {
                "name": "superset_tag_get_by_id",
                "description": "Получение информации о теге по ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tag_id": {
                            "type": "integer",
                            "description": "ID тега"
                        }
                    },
                    "required": ["tag_id"]
                }
            },
            "superset_tag_objects": {
                "name": "superset_tag_objects",
                "description": "Получение объектов тега",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_tag_delete": {
                "name": "superset_tag_delete",
                "description": "Удаление тега",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tag_id": {
                            "type": "integer",
                            "description": "ID тега"
                        }
                    },
                    "required": ["tag_id"]
                }
            },
            "superset_tag_object_add": {
                "name": "superset_tag_object_add",
                "description": "Добавление тега к объекту",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {
                            "type": "string",
                            "description": "Тип объекта"
                        },
                        "object_id": {
                            "type": "integer",
                            "description": "ID объекта"
                        },
                        "tag_name": {
                            "type": "string",
                            "description": "Имя тега"
                        }
                    },
                    "required": ["object_type", "object_id", "tag_name"]
                }
            },
            "superset_tag_object_remove": {
                "name": "superset_tag_object_remove",
                "description": "Удаление тега с объекта",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {
                            "type": "string",
                            "description": "Тип объекта"
                        },
                        "object_id": {
                            "type": "integer",
                            "description": "ID объекта"
                        },
                        "tag_name": {
                            "type": "string",
                            "description": "Имя тега"
                        }
                    },
                    "required": ["object_type", "object_id", "tag_name"]
                }
            },

            # Explore Tools
            "superset_explore_form_data_create": {
                "name": "superset_explore_form_data_create",
                "description": "Создание form данных для Explore",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "form_data": {
                            "type": "object",
                            "description": "Данные формы"
                        }
                    },
                    "required": ["form_data"]
                }
            },
            "superset_explore_form_data_get": {
                "name": "superset_explore_form_data_get",
                "description": "Получение form данных Explore",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Ключ данных"
                        }
                    },
                    "required": ["key"]
                }
            },
            "superset_explore_permalink_create": {
                "name": "superset_explore_permalink_create",
                "description": "Создание постоянной ссылки для Explore",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "object",
                            "description": "Состояние Explore"
                        }
                    },
                    "required": ["state"]
                }
            },
            "superset_explore_permalink_get": {
                "name": "superset_explore_permalink_get",
                "description": "Получение постоянной ссылки Explore",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Ключ ссылки"
                        }
                    },
                    "required": ["key"]
                }
            },

            # Menu Tools
            "superset_menu_get": {
                "name": "superset_menu_get",
                "description": "Получение меню Superset",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Configuration Tools
            "superset_config_get_base_url": {
                "name": "superset_config_get_base_url",
                "description": "Получение базового URL Superset",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Advanced Data Type Tools
            "superset_advanced_data_type_convert": {
                "name": "superset_advanced_data_type_convert",
                "description": "Конвертация расширенных типов данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type_name": {
                            "type": "string",
                            "description": "Имя типа данных"
                        },
                        "value": {
                            "type": ["string", "number", "boolean", "object", "array"],
                            "description": "Значение для конвертации"
                        }
                    },
                    "required": ["type_name", "value"]
                }
            },
            "superset_advanced_data_type_list": {
                "name": "superset_advanced_data_type_list",
                "description": "Получение списка расширенных типов данных",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Diagnostic Tools
            "superset_check_config": {
                "name": "superset_check_config",
                "description": "Проверка конфигурации Superset MCP сервера",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "superset_diagnose_chart_creation": {
                "name": "superset_diagnose_chart_creation",
                "description": "Диагностика проблем с созданием графиков",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "datasource_id": {
                            "type": "integer",
                            "description": "ID источника данных для диагностики"
                        }
                    },
                    "required": ["datasource_id"]
                }
            },
            "superset_csrf_check_and_fix": {
                "name": "superset_csrf_check_and_fix",
                "description": "Проверка и исправление CSRF проблем",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Session Tools
            "superset_auth_login_with_session": {
                "name": "superset_auth_login_with_session",
                "description": "Аутентификация через сессию (для CSRF)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": ["string", "null"],
                            "description": "Имя пользователя (если None, используется из переменных окружения)"
                        },
                        "password": {
                            "type": ["string", "null"],
                            "description": "Пароль (если None, используется из переменных окружения)"
                        }
                    },
                    "required": []
                }
            },
            "superset_dashboard_create_with_session": {
                "name": "superset_dashboard_create_with_session",
                "description": "Создание дашборда с использованием сессии",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dashboard_title": {
                            "type": "string",
                            "description": "Название дашборда"
                        },
                        "json_metadata": {
                            "type": "object",
                            "description": "Дополнительные метаданные",
                            "default": {}
                        }
                    },
                    "required": ["dashboard_title"]
                }
            }
        }
    
        
            # Объединяем схемы (ручные имеют приоритет)
        for tool_name, schema in self.manual_schemas.items():
            if tool_name in self.tool_schemas:
                self.tool_schemas[tool_name] = schema
        
        logger.info(f"Initialized MCP server with {len(self.tools)} tools and {len(self.manual_schemas)} schemas")
        
    def _generate_tool_schemas(self) -> Dict[str, Dict]:
        """Автоматически генерирует схемы для всех инструментов"""
        schemas = {}
        
        for tool_name, tool_func in self.tools.items():
            try:
                # Получаем сигнатуру функции
                sig = inspect.signature(tool_func)

                # Пропускаем первый параметр (ctx)
                params = list(sig.parameters.items())
                if params and params[0][0] == 'ctx':
                    params = params[1:]
                
                properties = {}
                required = []
                
                for param_name, param in params:
                    # Определяем тип параметра
                    param_type = "string"
                    param_desc = ""
                    
                    # Пытаемся определить тип из аннотации
                    if param.annotation != inspect.Parameter.empty:
                        ann_str = str(param.annotation)
                        if "str" in ann_str:
                            param_type = "string"
                        elif "int" in ann_str or "Integer" in ann_str:
                            param_type = "integer"
                        elif "float" in ann_str:
                            param_type = "number"
                        elif "bool" in ann_str:
                            param_type = "boolean"
                        elif "List" in ann_str or "list" in ann_str:
                            param_type = "array"
                        elif "Dict" in ann_str or "dict" in ann_str:
                            param_type = "object"
                    
                    # Определяем, обязателен ли параметр
                    if param.default == inspect.Parameter.empty:
                        required.append(param_name)
                    
                    # Создаем описание свойства
                    properties[param_name] = {
                        "type": param_type,
                        "description": param_desc
                    }
                
                # Создаем схему инструмента
                schemas[tool_name] = {
                    "name": tool_name,
                    "description": f"Execute {tool_name}",
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
                
            except Exception as e:
                logger.warning(f"Failed to generate schema for {tool_name}: {e}")
                # Создаем минимальную схему в случае ошибки
                schemas[tool_name] = {
                    "name": tool_name,
                    "description":  f"Execute {tool_name}",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
        
        return schemas
    
    def _validate_arguments(self, tool_name: str, arguments: Dict) -> List[str]:
        """Валидирует аргументы для указанного инструмента

        Returns:
            List[str]: Список ошибок валидации (пустой если все ок)
        """
        errors = []

        if tool_name not in self.tool_schemas:
            return errors  # Нет схемы - не можем валидировать

        schema = self.tool_schemas[tool_name]
        input_schema = schema.get("inputSchema", {})
        required_params = input_schema.get("required", [])
        properties = input_schema.get("properties", {})

        # Проверяем обязательные параметры
        for param_name in required_params:
            if param_name not in arguments:
                errors.append(f"Missing required parameter: {param_name}")

        # Проверяем типы параметров (более гибкая проверка)
        for param_name, param_value in arguments.items():
            if param_name in properties:
                param_schema = properties[param_name]
                expected_type = param_schema.get("type", "string")

                # Если значение None, оно допустимо для всех необязательных параметров
                if param_value is None:
                    continue  # None допустимо для опциональных параметров

                # Обрабатываем случай, когда expected_type может быть массивом (например, ["string", "null"])
                if isinstance(expected_type, list):
                    # Проверяем, соответствует ли тип одному из ожидаемых
                    type_matched = False
                    for t in expected_type:
                        if t == "null" and param_value is None:
                            type_matched = True
                            break
                        elif t == "string" and isinstance(param_value, str):
                            type_matched = True
                            break
                        elif t == "integer" and isinstance(param_value, int):
                            type_matched = True
                            break
                        elif t == "number" and isinstance(param_value, (int, float)):
                            type_matched = True
                            break
                        elif t == "boolean" and isinstance(param_value, bool):
                            type_matched = True
                            break
                        elif t == "array" and isinstance(param_value, list):
                            type_matched = True
                            break
                        elif t == "object" and isinstance(param_value, dict):
                            type_matched = True
                            break

                    if not type_matched:
                        errors.append(f"Parameter '{param_name}' should be one of {expected_type}, got {type(param_value).__name__}")
                else:
                    # Одиночный тип
                    if expected_type == "string" and not isinstance(param_value, str):
                        errors.append(f"Parameter '{param_name}' should be string, got {type(param_value).__name__}")
                    elif expected_type == "integer" and not isinstance(param_value, int):
                        errors.append(f"Parameter '{param_name}' should be integer, got {type(param_value).__name__}")
                    elif expected_type == "boolean" and not isinstance(param_value, bool):
                        errors.append(f"Parameter '{param_name}' should be boolean, got {type(param_value).__name__}")
                    elif expected_type == "number" and not isinstance(param_value, (int, float)):
                        errors.append(f"Parameter '{param_name}' should be number, got {type(param_value).__name__}")
                    elif expected_type == "array" and not isinstance(param_value, list):
                        errors.append(f"Parameter '{param_name}' should be array, got {type(param_value).__name__}")
                    elif expected_type == "object" and not isinstance(param_value, dict):
                        errors.append(f"Parameter '{param_name}' should be object, got {type(param_value).__name__}")

        return errors
        
    async def initialize_server(self):
        """Инициализация сервера"""
        load_stored_token()
        logger.info("MCP server initialized with all tools")
        
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка JSON-RPC запроса"""
        # Логируем входящий запрос (кроме шумных методов)
        method = request.get("method")
        request_id = request.get("id")
        
        if method not in ["ping", "heartbeat"]:
            logger.debug(f"📨 Received request: {method}, ID: {request_id}")
        
        if method == "initialize":
            await self.initialize_server()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "roots": {"listChanged": False},
                        "resources": {"listChanged": False},
                        "prompts": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "superset-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            # Формируем список инструментов со схемами
            tools_list = []
            
            for tool_name, schema in self.tool_schemas.items():
                if tool_name in self.tools:  # Проверяем, что инструмент существует
                    tools_list.append(schema)
            
            logger.info(f"📋 Sending list of {len(tools_list)} tools")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools_list}
            }
        
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            logger.info(f"🔧 Calling tool: {tool_name}")
            logger.debug(f"Arguments received: {arguments}")
            
            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32600,
                        "message": "Invalid request: missing 'name' in params"
                    }
                }
            
            if tool_name not in self.tools:
                logger.error(f"❌ Tool not found: {tool_name}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}",
                        "data": {
                            "available_tools": list(self.tools.keys())[:20],  # Первые 20 для примера
                            "total_tools": len(self.tools)
                        }
                    }
                }
            
            # Валидируем аргументы
            validation_errors = self._validate_arguments(tool_name, arguments)
            if validation_errors:
                logger.error(f"❌ Validation errors for {tool_name}: {validation_errors}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Invalid parameters for {tool_name}",
                        "data": {
                            "errors": validation_errors,
                            "expected_schema": self.tool_schemas.get(tool_name, {}).get("inputSchema", {})
                        }
                    }
                }
            
            try:
                # Создаем контекст для инструмента
                ctx = SupersetContext()
                
                # Для отладки: логируем вызов с аргументами
                logger.debug(f"Calling {tool_name} with arguments: {arguments}")
                
                # Вызываем инструмент
                result = await self.tools[tool_name](ctx, **arguments)
                
                # Логируем результат
                if isinstance(result, dict) and result.get("success") is False:
                    logger.warning(f"⚠️ Tool {tool_name} returned error: {result.get('error', 'Unknown error')}")
                else:
                    logger.info(f"✅ Tool {tool_name} executed successfully")
                
                # Форматируем результат для MCP
                if isinstance(result, dict):
                    result_text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
                else:
                    result_text = json.dumps({"result": str(result)}, ensure_ascii=False, indent=2)
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": result_text
                        }]
                    }
                }
            
            except TypeError as e:
                # Ошибка неправильных аргументов
                error_msg = str(e)
                logger.error(f"❌ TypeError in {tool_name}: {error_msg}")
                
                # Пытаемся извлечь информацию об ожидаемых аргументах
                expected_args = []
                try:
                    sig = inspect.signature(self.tools[tool_name])
                    expected_args = list(sig.parameters.keys())
                    if expected_args and expected_args[0] == 'ctx':
                        expected_args = expected_args[1:]
                except:
                    pass
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Type error in {tool_name}: {error_msg}",
                        "data": {
                            "tool_name": tool_name,
                            "expected_arguments": expected_args,
                            "provided_arguments": list(arguments.keys()),
                            "detailed_error": error_msg
                        }
                    }
                }
            
            except Exception as e:
                # Любая другая ошибка
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(f"❌ Exception in tool {tool_name}: {str(e)}")
                logger.error(f"Traceback:\n{error_traceback}")
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error in {tool_name}: {str(e)}",
                        "data": {
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                            "tool_name": tool_name
                        }
                    }
                }
        
        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": "pong"
            }
        
        elif method == "shutdown":
            logger.info("Shutdown requested")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {}
            }
        
        else:
            logger.warning(f"Unknown method: {method}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    async def run_stdio(self):
        """Запуск сервера через stdio"""
        logger.info("🚀 Starting Superset MCP server in stdio mode...")
        logger.info(f"📊 Available tools: {len(self.tools)}")
        logger.info(f"🔗 Superset URL: {_global_base_url}")
        logger.info(f"👤 Username: {SUPERSET_USERNAME}")
        
        loop = asyncio.get_event_loop()
        
        # Настраиваем stdin для чтения
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        
        # Настраиваем stdout для записи
        w_transport, w_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
        
        try:
            while True:
                # Читаем строку из stdin
                line_bytes = await reader.readline()
                if not line_bytes:
                    logger.info("EOF received, shutting down")
                    break
                
                line = line_bytes.decode('utf-8').strip()
                if not line:
                    continue
                
                logger.debug(f"📥 Received: {line[:200]}..." if len(line) > 200 else line)
                
                try:
                    # Парсим JSON запрос
                    request = json.loads(line)
                    
                    # Обрабатываем запрос
                    response = await self.handle_request(request)
                    
                    # Отправляем ответ
                    response_json = json.dumps(response, ensure_ascii=False)
                    writer.write((response_json + '\n').encode('utf-8'))
                    await writer.drain()
                    
                    logger.debug(f"📤 Sent response for request ID: {response.get('id')}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: {str(e)}"
                        }
                    }
                    writer.write((json.dumps(error_response) + '\n').encode('utf-8'))
                    await writer.drain()
                
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }
                    writer.write((json.dumps(error_response) + '\n').encode('utf-8'))
                    await writer.drain()
                
        except KeyboardInterrupt:
            logger.info("Server stopped by user (KeyboardInterrupt)")
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            # Закрываем writer
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
            logger.info("MCP server stopped")


async def main_async():
    """Асинхронная основная функция"""
    server = MinimalMCPServer()
    await server.run_stdio()


def main():
    """Точка входа для запуска MCP сервера"""
    # Показываем информацию о конфигурации
    print("\n" + "="*60)
    print("Superset MCP Server")
    print("="*60)
    print(f"Superset URL: {SUPERSET_BASE_URL}")
    print(f"Username: {SUPERSET_USERNAME}")
    print(f"Log file: {os.path.abspath('superset_mcp_full.log')}")
    print("="*60 + "\n")
    
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        print("\n👋 Server stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()