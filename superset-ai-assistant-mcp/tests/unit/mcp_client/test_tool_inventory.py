import unittest
from pathlib import Path

import yaml

from backend.mcp_client.tool_registry import (
    REQUIRED_CUSTOM_EXTENSION_TOOLS,
    REQUIRED_DIRECT_BUILTIN_TOOLS,
)


class TestMCPToolInventory(unittest.TestCase):
    def test_target_product_tools_are_fully_inventory_covered(self):
        repo_root = Path(__file__).resolve().parents[4]
        assistant_root = repo_root / "superset-ai-assistant-mcp"
        inventory_path = assistant_root / "tests" / "fixtures" / "mcp_tool_inventory.yaml"

        with inventory_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)

        entries = payload.get("tools", [])
        self.assertIsInstance(entries, list)

        actual_by_name = {}
        for entry in entries:
            self.assertIsInstance(entry, dict)
            name = str(entry.get("name", "")).strip()
            self.assertTrue(name)
            self.assertNotIn(name, actual_by_name)
            actual_by_name[name] = entry

        expected_layers = {
            tool_name: "builtin" for tool_name in REQUIRED_DIRECT_BUILTIN_TOOLS
        }
        expected_layers.update(
            {
                tool_name: "custom_extension"
                for tool_name in REQUIRED_CUSTOM_EXTENSION_TOOLS
            }
        )

        self.assertEqual(set(actual_by_name), set(expected_layers))

        for tool_name, expected_layer in expected_layers.items():
            with self.subTest(tool_name=tool_name):
                entry = actual_by_name[tool_name]
                self.assertEqual(entry.get("layer"), expected_layer)

                use_cases = entry.get("use_cases")
                self.assertIsInstance(use_cases, list)
                self.assertTrue(use_cases)

                coverage_refs = entry.get("covered_by")
                self.assertIsInstance(coverage_refs, list)
                self.assertTrue(coverage_refs)

                for ref in coverage_refs:
                    file_part = str(ref).split("::", 1)[0]
                    self.assertTrue(file_part)
                    self.assertTrue((repo_root / file_part).is_file(), ref)
