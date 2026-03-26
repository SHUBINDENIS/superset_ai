from copy import deepcopy
from typing import Any, Iterable, Mapping


WINDOW_CHAT = "chat"
WINDOW_US1 = "us1"
WINDOW_US2 = "us2"
WINDOW_US3 = "us3"
WINDOW_US4 = "us4"
WINDOW_US5 = "us5"
WINDOW_US13 = "us13"
WINDOW_US14 = "us14"
WINDOW_US15 = "us15"

WINDOW_LABELS = {
    WINDOW_CHAT: "💬 Чат",
    WINDOW_US1: "🧱 Сканер схем",
    WINDOW_US2: "📚 Глоссарий",
    WINDOW_US3: "🧭 Маппинг правил",
    WINDOW_US4: "💡 Подсказки",
    WINDOW_US5: "🧩 Конструктор",
    WINDOW_US13: "🔎 Предпросмотр",
    WINDOW_US14: "🎯 Рекомендации",
    WINDOW_US15: "🔗 Шеринг",
}

AUTH_COOKIE_NAME = "ai_assistant_auth_token"

APP_STATE_DEFAULTS = {
    "auth_is_authenticated": False,
    "auth_username": "",
    "auth_role": "",
    "auth_token": "",
    "auth_cookie_sync_token": "",
    "auth_cookie_clear_requested": False,
    "messages": [],
    "chat_sessions": [],
    "chat_rename_session_id": "",
    "chat_rename_value": "",
    "chat_is_processing": False,
    "chat_processing_text": "",
    "chat_trace_id": "",
    "chat_request_id": "",
    "session_id": None,
    "agent_initialized": False,
    "active_window": WINDOW_CHAT,
    "pending_input": None,
    "us1_scan_result": None,
    "us1_scan_error": None,
    "us1_scan_status": "idle",
    "us1_scan_started_at": None,
    "us1_scan_finished_at": None,
    "us2_status_message": "",
    "us2_error_message": "",
    "us2_selected_term_id": None,
    "us3_status_message": "",
    "us3_error_message": "",
    "us3_selected_rule_id": None,
    "us4_draft_query": "",
    "us4_entity_to_apply": None,
    "us4_submit_draft_requested": False,
    "us4_submit_payload": "",
    "us4_clear_draft_requested": False,
    "us4_scope_databases": [],
    "us4_scope_datasets": [],
    "us4_scope_database": "",
    "us4_scope_table": "",
    "us4_scope_status_message": "",
    "us4_scope_error_message": "",
    "us4_generated_prompts": [],
    "us4_generated_status_message": "",
    "us4_generated_error_message": "",
    "us4_prompt_limit": 6,
    "us5_objective": "",
    "us5_table_name": "",
    "us5_metric": "",
    "us5_dimensions_raw": "",
    "us5_period": "",
    "us5_time_grain": "month",
    "us5_filters_raw": "",
    "us5_sort_by": "",
    "us5_sort_direction": "desc",
    "us5_top_n": 0,
    "us5_compare_to": "",
    "us5_chart_type": "auto",
    "us5_built_query": "",
    "us5_status_message": "",
    "us5_error_message": "",
    "us5_last_validation": None,
    "us5_pending_field_update": None,
    "us5_dataset_options": [],
    "us5_dataset_options_status_message": "",
    "us5_dataset_options_error_message": "",
    "us5_dataset_metadata_cache": {},
    "us5_table_choice": "",
    "us5_metric_choice": "",
    "us5_metric_custom": "",
    "us5_dimensions_multiselect": [],
    "us5_period_choice": "",
    "us5_period_custom": "",
    "us5_sort_by_choice": "",
    "us5_sort_by_custom": "",
    "us5_compare_to_choice": "",
    "us5_compare_to_custom": "",
    "us5_filter_field_choice": "",
    "us5_filter_value_choice": "",
    "us13_databases": [],
    "us13_datasets": [],
    "us13_database_id": 0,
    "us13_dataset_id": 0,
    "us13_schema": "",
    "us13_sql_template": "table_preview",
    "us13_sql": "SELECT * FROM birth_names",
    "us13_preview_limit": 20,
    "us13_column_type_filter": "all",
    "us13_column_focus": "",
    "us13_preview_result": None,
    "us13_status_message": "",
    "us13_error_message": "",
    "us14_metric_column": "",
    "us14_dimension_column": "",
    "us14_time_column": "",
    "us14_recommendation": None,
    "us14_status_message": "",
    "us14_error_message": "",
    "us15_datasets": [],
    "us15_dataset_id": 0,
    "us15_dashboard_title": "AI Dashboard",
    "us15_chart_title": "AI Widget",
    "us15_viz_type": "table",
    "us15_metric_column": "",
    "us15_dimension_column": "",
    "us15_time_column": "",
    "us15_row_limit": 1000,
    "us15_description": "",
    "us15_dataset_columns_cache": {},
    "us15_result": None,
    "us15_status_message": "",
    "us15_error_message": "",
}

SESSION_RESET_KEYS = (
    "session_id",
    "agent_initialized",
    "active_window",
    "messages",
    "chat_sessions",
    "chat_rename_session_id",
    "chat_rename_value",
    "chat_is_processing",
    "chat_processing_text",
    "chat_trace_id",
    "chat_request_id",
    "pending_input",
    "us4_draft_query",
    "us4_entity_to_apply",
    "us4_submit_draft_requested",
    "us4_submit_payload",
    "us4_clear_draft_requested",
    "us4_scope_databases",
    "us4_scope_datasets",
    "us4_scope_database",
    "us4_scope_table",
    "us4_scope_status_message",
    "us4_scope_error_message",
    "us4_generated_prompts",
    "us4_generated_status_message",
    "us4_generated_error_message",
    "us4_prompt_limit",
    "us5_objective",
    "us5_table_name",
    "us5_metric",
    "us5_dimensions_raw",
    "us5_period",
    "us5_time_grain",
    "us5_filters_raw",
    "us5_sort_by",
    "us5_sort_direction",
    "us5_top_n",
    "us5_compare_to",
    "us5_chart_type",
    "us5_built_query",
    "us5_status_message",
    "us5_error_message",
    "us5_last_validation",
    "us5_pending_field_update",
    "us5_dataset_options",
    "us5_dataset_options_status_message",
    "us5_dataset_options_error_message",
    "us5_dataset_metadata_cache",
    "us5_table_choice",
    "us5_metric_choice",
    "us5_metric_custom",
    "us5_dimensions_multiselect",
    "us5_period_choice",
    "us5_period_custom",
    "us5_sort_by_choice",
    "us5_sort_by_custom",
    "us5_compare_to_choice",
    "us5_compare_to_custom",
    "us5_filter_field_choice",
    "us5_filter_value_choice",
    "us13_databases",
    "us13_datasets",
    "us13_database_id",
    "us13_dataset_id",
    "us13_schema",
    "us13_sql_template",
    "us13_sql",
    "us13_preview_limit",
    "us13_column_type_filter",
    "us13_column_focus",
    "us13_preview_result",
    "us13_status_message",
    "us13_error_message",
    "us14_metric_column",
    "us14_dimension_column",
    "us14_time_column",
    "us14_recommendation",
    "us14_status_message",
    "us14_error_message",
    "us15_datasets",
    "us15_dataset_id",
    "us15_dashboard_title",
    "us15_chart_title",
    "us15_viz_type",
    "us15_metric_column",
    "us15_dimension_column",
    "us15_time_column",
    "us15_row_limit",
    "us15_description",
    "us15_dataset_columns_cache",
    "us15_result",
    "us15_status_message",
    "us15_error_message",
)

SESSION_WIDGET_KEYS_TO_CLEAR = (
    "us13_preview_limit_choice",
    "us14_apply_type_choice",
    "us15_row_limit_choice",
)


def clone_state_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in values.items()}


def apply_state_patch(session_state, values: Mapping[str, Any], *, clear_keys: Iterable[str] = ()) -> None:
    for key, value in clone_state_values(values).items():
        session_state[key] = value
    for key in clear_keys:
        session_state.pop(key, None)


def ensure_state_defaults(session_state) -> None:
    for key, value in APP_STATE_DEFAULTS.items():
        if key not in session_state:
            session_state[key] = deepcopy(value)


def build_authenticated_state(
    *,
    username: str,
    role: str,
    auth_token: str,
    session_id: str,
    messages: list[dict[str, Any]],
    chat_sessions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "auth_is_authenticated": True,
        "auth_username": username,
        "auth_role": role,
        "auth_token": auth_token,
        "session_id": session_id,
        "agent_initialized": False,
        "messages": messages,
        "chat_sessions": list(chat_sessions or []),
        "chat_rename_session_id": "",
        "chat_rename_value": "",
        "chat_is_processing": False,
        "chat_processing_text": "",
        "chat_trace_id": "",
        "chat_request_id": "",
        "pending_input": None,
        "active_window": WINDOW_CHAT,
    }


def build_session_reset_state(new_session_id: str | None) -> dict[str, Any]:
    values = {key: APP_STATE_DEFAULTS[key] for key in SESSION_RESET_KEYS}
    values["session_id"] = new_session_id
    return clone_state_values(values)


def build_feedback_state(
    *,
    status_key: str,
    error_key: str,
    status_message: str = "",
    error_message: str = "",
    extra_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        status_key: status_message,
        error_key: error_message,
    }
    if extra_values:
        values.update(extra_values)
    return clone_state_values(values)


def build_logout_state() -> dict[str, Any]:
    values = build_session_reset_state(new_session_id=None)
    values.update(
        {
            "auth_is_authenticated": False,
            "auth_username": "",
            "auth_role": "",
            "auth_token": "",
        }
    )
    return values
