"""Unit tests for the manifest loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from contracts.manifest import PolicyMode
from runtime.manifest_loader import load_manifest


SAMPLE_MANIFEST = """\
app:
  name: test-app
  version: "0.1.0"

runtime:
  base_url: "http://127.0.0.1:8080"
  policy_mode: local_only

policy:
  tools:
    allow:
      - sql_query
      - read_file
  data:
    sqlite:
      allow:
        - health.db
    filesystem:
      allow_read:
        - "data/*.csv"
      allow_write:
        - "output/*"
  network:
    outbound: deny
    allow_domains:
      - "127.0.0.1"

audit:
  path: audit.jsonl
"""


class TestManifestLoader:
    def test_load_valid_manifest(self, tmp_path: Path) -> None:
        f = tmp_path / "domekit.yaml"
        f.write_text(SAMPLE_MANIFEST)
        m = load_manifest(str(f))
        assert m.app.name == "test-app"
        assert m.runtime.policy_mode == PolicyMode.LOCAL_ONLY
        assert "sql_query" in m.policy.tools.allow
        assert "health.db" in m.policy.data.sqlite.allow

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_manifest("/nonexistent/domekit.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("just a string")
        with pytest.raises(ValueError, match="YAML mapping"):
            load_manifest(str(f))
