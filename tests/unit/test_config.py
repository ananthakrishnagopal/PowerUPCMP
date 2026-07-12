import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from semifab_poc import __version__
from semifab_poc.cli import main
from semifab_poc.config import ConfigError, RuntimeConfig, load_runtime_config, runtime_config_sha256


def test_package_version_is_declared() -> None:
    assert __version__ == "0.1.0"


def test_runtime_config_has_safe_strict_defaults() -> None:
    config = RuntimeConfig()
    assert config.synthetic_only is True
    assert config.schema_version == "2.4.0"
    assert config.interface_version == "3.2.0"
    assert config.dt_s > 0
    assert config.duration_s > 0
    assert config.parameter_provenance_ids["electrical"] == config.electrical.provenance_id
    assert config.parameter_provenance_ids["cmp"] == config.cmp.provenance_id
    assert config.parameter_provenance_ids["coupling"] == config.coupling.provenance_id


def test_unknown_configuration_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuntimeConfig(unexpected_parameter=1)


def test_schema_and_interface_versions_must_form_a_supported_pair() -> None:
    with pytest.raises(ValidationError, match="unsupported schema/interface"):
        RuntimeConfig(schema_version="2.1.0", interface_version="3.0.0")


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RuntimeConfig(log_level="verbose")


def test_yaml_config_loads_strictly(tmp_path: Path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text("seed: 42\ndt_s: 0.02\n", encoding="utf-8")
    config = load_runtime_config(path)
    assert config.seed == 42
    assert config.dt_s == 0.02


def test_unknown_nested_configuration_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text("electrical:\n  unexpected_parameter: 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unexpected_parameter"):
        load_runtime_config(path)


def test_repository_default_config_is_complete_and_hash_stable() -> None:
    path = Path(__file__).parents[2] / "configs" / "default.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = load_runtime_config(path)

    assert set(raw) == set(RuntimeConfig.model_fields)
    for section in ("electrical", "drive", "pump", "upw", "cmp", "coupling"):
        assert set(raw[section]) == {field.name for field in fields(getattr(config, section))}
    assert len(raw["sensors"]) == len(config.sensors)
    for raw_sensor, sensor in zip(raw["sensors"], config.sensors, strict=True):
        assert set(raw_sensor) == {field.name for field in fields(sensor)}

    assert config == RuntimeConfig()
    first_hash = runtime_config_sha256(config)
    second_hash = runtime_config_sha256(load_runtime_config(path))
    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_frozen_r3_configuration_remains_reproducible() -> None:
    path = Path(__file__).parents[2] / "configs" / "checkpoints" / "r3_default.yaml"
    config = load_runtime_config(path)
    assert (config.schema_version, config.interface_version) == ("2.1.0", "2.0.0")
    assert runtime_config_sha256(config) == (
        "6a47eefbefee0fa3084b3f4f2e780d0aa430bf3cad1f3dbb64a988398bbbaf97"
    )


def test_frozen_r4_configuration_remains_reproducible() -> None:
    path = Path(__file__).parents[2] / "configs" / "checkpoints" / "r4_default.yaml"
    config = load_runtime_config(path)
    assert (config.schema_version, config.interface_version) == ("2.2.0", "3.0.0")
    assert runtime_config_sha256(config) == (
        "7a66469391268dae6e0458255ff88b263e6bf84965e87c93a7b04676caf4fd86"
    )


def test_frozen_wp08_configuration_hash_remains_reproducible() -> None:
    config = RuntimeConfig(schema_version="2.3.0", interface_version="3.1.0")
    assert runtime_config_sha256(config) == (
        "99d7876eb76d561de97ed577d77da30e929c70276070bb6f84df0fb9c9e91670"
    )


def test_parameter_provenance_respects_component_introduction_versions() -> None:
    root = Path(__file__).parents[2]
    r3 = load_runtime_config(root / "configs" / "checkpoints" / "r3_default.yaml")
    r4 = load_runtime_config(root / "configs" / "checkpoints" / "r4_default.yaml")
    wp08 = RuntimeConfig(schema_version="2.3.0", interface_version="3.1.0")
    wp10 = RuntimeConfig()
    base = {
        "electrical",
        "drive",
        "pump",
        "upw",
        "sensor:upw-supply-pressure",
        "sensor:upw-tool-flow",
        "sensor:upw-temperature",
    }

    assert set(r3.parameter_provenance_ids) == base
    assert set(r4.parameter_provenance_ids) == base
    assert set(wp08.parameter_provenance_ids) == base | {"cmp"}
    assert set(wp10.parameter_provenance_ids) == base | {"cmp", "coupling"}


def test_cli_help_and_validate_config(capsys, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    help_output = capsys.readouterr().out
    assert "validate-config" in help_output

    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[2] / "src")}
    process = subprocess.run(
        [sys.executable, "-m", "semifab_poc.cli", "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert process.returncode == 0
    assert "validate-config" in process.stdout

    path = tmp_path / "runtime.yaml"
    path.write_text("seed: 7\n", encoding="utf-8")
    assert main(["validate-config", str(path)]) == 0
    output = capsys.readouterr().out
    assert '"seed": 7' in output
