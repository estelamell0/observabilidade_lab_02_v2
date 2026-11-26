#!/usr/bin/env python3
"""Headless, zero-browser validation suite for Lab 02 (Turma 1747)."""

import ast
import json
import re
import unittest
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent.parent


class TestLab02Structure(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        expected = [
            "docker-compose.yml",
            "README.md",
            "config/otel-collector-config.yaml",
            "config/prometheus.yml",
            "config/alert.rules.yaml",
            "config/tempo.yaml",
            "config/loki.yaml",
            "grafana/provisioning/datasources/datasources.yaml",
            "grafana/provisioning/dashboards/dashboards.yaml",
            "grafana/dashboards/sistema_observavel_lab02.json",
            "app_observavel/Dockerfile",
            "app_observavel/server.py",
        ]
        for rel in expected:
            with self.subTest(file=rel):
                self.assertTrue((LAB_DIR / rel).is_file(), f"Missing {rel}")

    def test_docker_compose_services_and_ports(self) -> None:
        compose = (LAB_DIR / "docker-compose.yml").read_text(encoding="utf-8")
        for service in ("tempo:", "loki:", "otel-collector:", "prometheus:", "grafana:", "app-observavel:"):
            self.assertIn(service, compose)
        for port in ("4317:4317", "4318:4318", "8889:8889", "9090:9090", "3000:3000", "3100:3100", "8080:8080"):
            self.assertIn(port, compose)
        self.assertIn("--enable-feature=exemplar-storage", compose)

    def test_collector_pipelines_and_scrubbing(self) -> None:
        cfg = (LAB_DIR / "config/otel-collector-config.yaml").read_text(encoding="utf-8")
        for key in ("enable_open_metrics: true", "delta_to_cumulative:", "otlphttp/loki:", "key: ci.token", "key: cpf", "key: pan", "key: user.email"):
            self.assertIn(key, cfg)
        for pipeline in ("traces:", "metrics:", "logs:"):
            self.assertIn(pipeline, cfg)

    def test_loki_and_grafana_bidirectional_correlation(self) -> None:
        loki_cfg = (LAB_DIR / "config/loki.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_structured_metadata: true", loki_cfg)

        ds = (LAB_DIR / "grafana/provisioning/datasources/datasources.yaml").read_text(encoding="utf-8")
        self.assertIn("exemplarTraceIdDestinations", ds)
        self.assertIn("tracesToLogsV2", ds)
        self.assertIn("derivedFields", ds)

        dash = json.loads((LAB_DIR / "grafana/dashboards/sistema_observavel_lab02.json").read_text(encoding="utf-8"))
        self.assertEqual(dash["uid"], "lab02-sistema")
        self.assertEqual(len(dash["panels"]), 5)

    def test_server_python_syntax_and_three_phases(self) -> None:
        src = (LAB_DIR / "app_observavel/server.py").read_text(encoding="utf-8")
        ast.parse(src)
        for route in (
            "/api/fase1/ok",
            "/api/fase1/slow",
            "/api/fase1/fail",
            "/api/fase1/bypass",
            "/api/fase2/log-estruturado",
            "/api/fase2/checkout-pii",
            "/api/fase3/incidente-cadeia",
        ):
            self.assertIn(route, src)
        self.assertIn("safe_log", src)
        self.assertIn("AggregationTemporality.DELTA", src)

    def test_readme_editorial_constraints(self) -> None:
        readme = (LAB_DIR / "README.md").read_text(encoding="utf-8")
        forbidden = [
            r"CY-SE-014",
            r"Ada Tech",
            r"\bAda\b",
            r"\bleigo\b",
            r"sem conhecimento",
            r"nível fácil",
            r"Aula 0?[5-9]",
            r"próxima aula",
            r"projeto final",
            r"\b(?:10|15|20|30|45|50|60|75) min\b",
            r"\b3h\b",
        ]
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, readme, flags=re.IGNORECASE))


if __name__ == "__main__":
    unittest.main(verbosity=2)
