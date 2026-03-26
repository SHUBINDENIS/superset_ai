import unittest

from frontend.state import (
    APP_STATE_DEFAULTS,
    build_authenticated_state,
    build_feedback_state,
    build_logout_state,
    build_session_reset_state,
    ensure_state_defaults,
)


class TestFrontendState(unittest.TestCase):
    def test_ensure_state_defaults_copies_mutable_values(self):
        first = {}
        second = {}

        ensure_state_defaults(first)
        ensure_state_defaults(second)

        first["messages"].append({"role": "user", "content": "hello"})
        first["us13_databases"].append({"id": 1})

        self.assertEqual(second["messages"], [])
        self.assertEqual(second["us13_databases"], [])

    def test_build_authenticated_state_resets_chat_session_fields(self):
        state = build_authenticated_state(
            username="alice",
            role="analyst",
            auth_token="token-alice",
            session_id="session-alice",
            messages=[{"role": "assistant", "content": "saved"}],
            chat_sessions=[{"session_id": "session-alice", "title": "Чат"}],
        )

        self.assertTrue(state["auth_is_authenticated"])
        self.assertEqual(state["auth_username"], "alice")
        self.assertEqual(state["session_id"], "session-alice")
        self.assertEqual(state["messages"], [{"role": "assistant", "content": "saved"}])
        self.assertEqual(state["chat_sessions"], [{"session_id": "session-alice", "title": "Чат"}])
        self.assertEqual(state["chat_rename_session_id"], "")
        self.assertEqual(state["chat_rename_value"], "")
        self.assertFalse(state["chat_is_processing"])
        self.assertEqual(state["chat_processing_text"], "")
        self.assertIsNone(state["pending_input"])
        self.assertFalse(state["agent_initialized"])

    def test_build_session_reset_state_uses_default_values_with_new_session(self):
        state = build_session_reset_state("rotated-1")

        self.assertEqual(state["session_id"], "rotated-1")
        self.assertEqual(state["messages"], [])
        self.assertEqual(state["chat_sessions"], [])
        self.assertEqual(state["chat_rename_session_id"], "")
        self.assertFalse(state["chat_is_processing"])
        self.assertEqual(state["chat_processing_text"], "")
        self.assertEqual(state["us13_sql"], APP_STATE_DEFAULTS["us13_sql"])
        self.assertEqual(state["us15_chart_title"], "AI Widget")
        self.assertIsNone(state["us14_recommendation"])

    def test_build_logout_state_clears_auth_fields(self):
        state = build_logout_state()

        self.assertFalse(state["auth_is_authenticated"])
        self.assertEqual(state["auth_username"], "")
        self.assertEqual(state["auth_role"], "")
        self.assertEqual(state["auth_token"], "")
        self.assertIsNone(state["session_id"])
        self.assertEqual(state["messages"], [])

    def test_build_feedback_state_sets_status_and_extra_values(self):
        state = build_feedback_state(
            status_key="us15_status_message",
            error_key="us15_error_message",
            status_message="done",
            extra_values={"us15_result": {"chart_id": 5}},
        )

        self.assertEqual(state["us15_status_message"], "done")
        self.assertEqual(state["us15_error_message"], "")
        self.assertEqual(state["us15_result"], {"chart_id": 5})

    def test_build_feedback_state_copies_mutable_extra_values(self):
        payload = {"items": ["a"]}

        state = build_feedback_state(
            status_key="status",
            error_key="error",
            extra_values={"payload": payload},
        )
        payload["items"].append("b")

        self.assertEqual(state["payload"], {"items": ["a"]})


if __name__ == "__main__":
    unittest.main()
