import asyncio
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
import json
import uuid
from pathlib import Path

from backend.mcp_client.built_in_client import BuiltInMCPClient, McpUseToolTransport
from backend.mcp_client.tool_registry import build_agent_mcp_use_config
from backend.us13_15_viz_service import US13To15VizService


REPO_ROOT = Path(__file__).resolve().parents[4]
SUPERSET_REPO = REPO_ROOT / "superset"
DOCKER_IMAGE = "apachesuperset.docker.scarf.sh/apache/superset:latest-dev"
REQUIRED_BUNDLE_DIRS = (
    "superset",
    "superset-core",
    "docker",
    "requirements",
)
REQUIRED_BUNDLE_FILES = (
    "pyproject.toml",
    "setup.py",
    "MANIFEST.in",
    "README.md",
)
REQUIRED_CONTAINER_ENV = (
    "DATABASE_DIALECT",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_DB",
    "EXAMPLES_USER",
    "EXAMPLES_PASSWORD",
    "EXAMPLES_HOST",
    "EXAMPLES_PORT",
    "EXAMPLES_DB",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_CELERY_DB",
    "REDIS_RESULTS_DB",
    "SUPERSET_APP_ROOT",
    "SUPERSET_SECRET_KEY",
)


class TestBuiltInMCPLive(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _chmod_tree(root: Path, mode: int) -> None:
        root.chmod(mode)
        for current_root, dirnames, filenames in os.walk(root):
            Path(current_root).chmod(mode)
            for dirname in dirnames:
                Path(current_root, dirname).chmod(mode)
            for filename in filenames:
                Path(current_root, filename).chmod(mode)

    @classmethod
    def setUpClass(cls):
        if shutil.which("docker") is None:
            raise unittest.SkipTest("docker is required for live MCP integration tests")
        inspect = subprocess.run(
            ["docker", "inspect", "superset_app"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
        if inspect.returncode != 0:
            raise unittest.SkipTest("superset_app container is required for live MCP integration tests")
        inspect_payload = json.loads(inspect.stdout)[0]
        container_env_map = {}
        for item in inspect_payload["Config"].get("Env", []):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            container_env_map[key] = value

        cls.bundle_dir = Path(tempfile.mkdtemp(prefix="built_in_mcp_bundle_"))
        for dirname in REQUIRED_BUNDLE_DIRS:
            shutil.copytree(SUPERSET_REPO / dirname, cls.bundle_dir / dirname)
        for filename in REQUIRED_BUNDLE_FILES:
            shutil.copy2(SUPERSET_REPO / filename, cls.bundle_dir / filename)
        frontend_bundle_dir = cls.bundle_dir / "superset-frontend"
        frontend_bundle_dir.mkdir()
        shutil.copy2(
            SUPERSET_REPO / "superset-frontend" / "package.json",
            frontend_bundle_dir / "package.json",
        )
        dev_config_path = cls.bundle_dir / "docker" / "pythonpath_dev" / "superset_config.py"
        with dev_config_path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n# Added by MCP migration integration test harness.\n"
                'MCP_DEV_USERNAME = "admin"\n'
            )
        cls._chmod_tree(cls.bundle_dir, 0o755)

        cls.env_file = cls.bundle_dir / "superset_app.env"
        env_lines = [
            f"{key}={container_env_map[key]}"
            for key in REQUIRED_CONTAINER_ENV
            if key in container_env_map
        ]
        cls.env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        cls.env_file.chmod(0o644)
        cls.launcher_path = cls.bundle_dir / "run_builtin_mcp_stdio.sh"
        launcher = textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail
            exec docker run --rm -i -u 0:0 \\
              --network container:superset_app \\
              --env-file {cls.env_file} \\
              -v {cls.bundle_dir}:/workspace:ro \\
              {DOCKER_IMAGE} \\
              /bin/bash -lc '
                set -euo pipefail
                TMP_WS=/tmp/workspace
                rm -rf "$TMP_WS"
                cp -R /workspace "$TMP_WS"
                chmod -R u+w "$TMP_WS"
                cd "$TMP_WS"
                /app/.venv/bin/python -m pip install -e "./superset-core" "fastmcp<3" "marshmallow-union>=0.1,<1" >/tmp/mcp_fastmcp_install.log 2>&1
                /app/.venv/bin/python -m pip install -e . >/tmp/mcp_superset_install.log 2>&1
                export PYTHONPATH="$TMP_WS/docker/pythonpath_dev"
                export SUPERSET_CONFIG_PATH="$TMP_WS/docker/pythonpath_dev/superset_config.py"
                /app/.venv/bin/superset db upgrade >/tmp/mcp_db_upgrade.log 2>&1
                export FASTMCP_TRANSPORT=stdio
                exec /app/.venv/bin/python -m superset.mcp_service
              '
            """
        )
        cls.launcher_path.write_text(launcher, encoding="utf-8")
        cls.launcher_path.chmod(cls.launcher_path.stat().st_mode | stat.S_IXUSR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.bundle_dir, ignore_errors=True)

    async def asyncSetUp(self):
        self._env = {
            "MCP_USE_ANONYMIZED_TELEMETRY": "false",
            "SUPERSET_BUILT_IN_MCP_COMMAND": str(self.launcher_path),
            "SUPERSET_BUILT_IN_MCP_ARGS": "",
        }
        self._old_env = {key: os.environ.get(key) for key in self._env}
        os.environ.update(self._env)

        self.transport = McpUseToolTransport(
            mcp_config=build_agent_mcp_use_config(runtime="built_in_stdio")
        )
        self.client = BuiltInMCPClient(self.transport)

    async def asyncTearDown(self):
        await self.client.close()
        for key, previous in self._old_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    async def test_live_stdio_startup_and_core_readonly_tools(self):
        tools = set(await self.transport.list_tools())
        self.assertTrue(
            {
                "list_datasets",
                "get_dataset_info",
                "list_charts",
                "get_chart_info",
                "list_dashboards",
                "get_dashboard_info",
                "execute_sql",
                "mcp_ext.list_databases",
                "mcp_ext.create_empty_dashboard",
                "mcp_ext.legacy_chart_create",
                "generate_chart",
                "update_chart",
                "generate_dashboard",
                "add_chart_to_existing_dashboard",
                "generate_explore_link",
            }.issubset(tools)
        )

        datasets = await self.client.list_datasets({"page": 1, "page_size": 5})
        dataset_items = list(datasets.get("datasets", []) or [])
        self.assertGreater(len(dataset_items), 0)
        first_dataset = dataset_items[0]
        dataset_id = int(first_dataset["id"])

        dataset_info = await self.client.get_dataset_info(dataset_id)
        self.assertEqual(int(dataset_info["id"]), dataset_id)
        database_id = int(
            dataset_info.get("database_id")
            or first_dataset.get("database_id")
            or 0
        )
        self.assertGreater(database_id, 0)

        charts = await self.client.list_charts({"page": 1, "page_size": 5})
        chart_items = list(charts.get("charts", []) or [])
        self.assertGreater(len(chart_items), 0)
        first_chart = chart_items[0]
        chart_info = await self.client.get_chart_info(int(first_chart["id"]))
        self.assertEqual(int(chart_info["id"]), int(first_chart["id"]))

        dashboards = await self.client.list_dashboards({"page": 1, "page_size": 5})
        dashboard_items = list(dashboards.get("dashboards", []) or [])
        self.assertGreater(len(dashboard_items), 0)
        first_dashboard = dashboard_items[0]
        dashboard_info = await self.client.get_dashboard_info(int(first_dashboard["id"]))
        self.assertEqual(int(dashboard_info["id"]), int(first_dashboard["id"]))

        sql_result = await self.client.execute_sql(
            {
                "database_id": database_id,
                "sql": "SELECT 1 AS one",
                "limit": 1,
            }
        )
        self.assertTrue(sql_result["success"])
        self.assertEqual(sql_result["rows"][0]["one"], 1)

    async def test_live_mutation_tools_and_product_service_flows(self):
        datasets = await self.client.list_datasets({"page": 1, "page_size": 5})
        dataset_items = list(datasets.get("datasets", []) or [])
        self.assertGreater(len(dataset_items), 0)
        dataset_id = int(dataset_items[0]["id"])

        dataset_info = await self.client.get_dataset_info(dataset_id)
        columns = list(dataset_info.get("columns", []) or [])
        self.assertGreater(len(columns), 0)
        column_names = [
            str(column.get("column_name", "")).strip()
            for column in columns
            if isinstance(column, dict) and str(column.get("column_name", "")).strip()
        ]
        self.assertGreater(len(column_names), 0)

        table_config = {
            "chart_type": "table",
            "columns": [{"name": column_names[0]}],
        }
        if len(column_names) > 1:
            table_config["columns"].append({"name": column_names[1]})

        explore = await self.client.generate_explore_link(
            {"dataset_id": dataset_id, "config": table_config}
        )
        self.assertIn("/explore/?", str(explore.get("url", "")))

        unique = uuid.uuid4().hex[:8]
        empty_dashboard = await self.client.create_empty_dashboard(
            {"dashboard_title": f"MCP Empty {unique}"}
        )
        self.assertIsNone(empty_dashboard.get("error"))
        empty_dashboard_id = int(empty_dashboard["dashboard"]["id"])

        chart_result = await self.client.generate_chart(
            {
                "dataset_id": dataset_id,
                "config": table_config,
                "save_chart": True,
                "generate_preview": False,
            }
        )
        self.assertTrue(chart_result["success"])
        chart_id = int(chart_result["chart"]["id"])

        updated_chart = await self.client.update_chart(
            {
                "identifier": chart_id,
                "config": table_config,
                "generate_preview": False,
            }
        )
        self.assertTrue(updated_chart["success"])
        self.assertEqual(int(updated_chart["chart"]["id"]), chart_id)

        attach_result = await self.client.add_chart_to_existing_dashboard(
            {"dashboard_id": empty_dashboard_id, "chart_id": chart_id}
        )
        self.assertIsNone(attach_result.get("error"))
        self.assertEqual(int(attach_result["dashboard"]["id"]), empty_dashboard_id)

        generated_dashboard = await self.client.generate_dashboard(
            {
                "chart_ids": [chart_id],
                "dashboard_title": f"MCP Generated {unique}",
                "published": False,
            }
        )
        self.assertIsNone(generated_dashboard.get("error"))
        self.assertIn("/superset/dashboard/", str(generated_dashboard["dashboard_url"]))

        service = US13To15VizService(
            base_url="http://localhost:8088",
            username="",
            password="",
            timeout_seconds=5.0,
            default_preview_limit=20,
            share_base_url="http://localhost:9001",
        )
        try:
            databases = await asyncio.to_thread(service.list_databases)
            self.assertGreater(len(databases), 0)

            preview = await asyncio.to_thread(
                service.preview_sql,
                database_id=int(dataset_info["database_id"]),
                sql="SELECT 1 AS one",
            )
            self.assertEqual(preview["rows"][0]["one"], 1)

            service_explore_url = await asyncio.to_thread(
                service.generate_explore_link,
                dataset_id=dataset_id,
                viz_type="table",
            )
            self.assertIn("/explore/?", service_explore_url)

            widget = await asyncio.to_thread(
                service.create_dashboard_widget_with_share,
                dataset_id=dataset_id,
                dashboard_title=f"Service Dashboard {unique}",
                slice_name=f"Service Chart {unique}",
                viz_type="table",
            )
            self.assertGreater(int(widget["dashboard_id"]), 0)
            self.assertGreater(int(widget["chart_id"]), 0)
            self.assertIn("/superset/dashboard/", widget["dashboard_link"])
            self.assertIn("/explore/?", widget["chart_link"])

            updated = await asyncio.to_thread(
                service.update_chart,
                chart_id=int(widget["chart_id"]),
                dataset_id=dataset_id,
                viz_type="table",
            )
            self.assertEqual(int(updated["chart_id"]), int(widget["chart_id"]))
        finally:
            await asyncio.to_thread(service.close)
