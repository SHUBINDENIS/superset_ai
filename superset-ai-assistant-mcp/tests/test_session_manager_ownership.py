import os
import unittest
from unittest.mock import patch

from backend.ai_agent import AgentSessionManager


class TestSessionManagerOwnership(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env_patch = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "OPENAI_MODEL": "gpt-5.4-mini",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    async def test_owner_bound_session_rejects_other_user(self):
        manager = AgentSessionManager()
        session_id = await manager.create_session(owner="alice")

        agent = await manager.get_agent(session_id, owner="alice")
        self.assertIsNotNone(agent)
        self.assertEqual(await manager.get_session_owner(session_id), "alice")

        with self.assertRaises(PermissionError):
            await manager.get_agent(session_id, owner="bob")

        with self.assertRaises(PermissionError):
            await manager.get_or_create_agent(session_id, owner="bob")

    async def test_unowned_session_can_be_claimed_once(self):
        manager = AgentSessionManager()
        session_id = await manager.create_session()

        self.assertIsNone(await manager.get_session_owner(session_id))

        agent = await manager.get_agent(session_id, owner="owner1")
        self.assertIsNotNone(agent)
        self.assertEqual(await manager.get_session_owner(session_id), "owner1")

        with self.assertRaises(PermissionError):
            await manager.get_or_create_agent(session_id, owner="owner2")


if __name__ == "__main__":
    unittest.main()
