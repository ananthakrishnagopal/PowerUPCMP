from pathlib import Path

from semifab_poc.models.virtual_metrology import (
    feature_set_columns,
    load_virtual_metrology_config,
    prepare_feature_only_roles,
)


CONFIG_PATH = Path("configs/models/virtual_metrology.yaml")


def test_real_wp09_feature_only_roles_are_deterministic_and_target_free() -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    bundle, manifest = prepare_feature_only_roles(config)
    assert manifest["holdout_targets_accessed"] is False
    assert manifest["target_in_feature_files"] is False
    assert manifest["official_precedence_audit"]["original_overlap_counts"] == {
        "training_test": 113,
        "training_validation": 115,
        "test_validation": 34,
    }
    assert manifest["official_precedence_audit"]["retained_row_counts"] == {
        "training": 1981,
        "test": 311,
        "validation": 275,
    }
    assert manifest["official_precedence_audit"]["retained_group_counts"] == {
        "training": 1699,
        "test": 302,
        "validation": 267,
    }
    assert not any(manifest["pairwise_group_overlap_counts"].values())
    assert len(manifest["roles"]["TRAIN_CORE"]["group_values"]) == 1189
    assert len(manifest["roles"]["MODEL_SELECTION"]["group_values"]) == 255
    assert len(manifest["roles"]["INTERVAL_CALIBRATION"]["group_values"]) == 255
    assert sum(
        manifest["roles"][role]["row_count"]
        for role in ("TRAIN_CORE", "MODEL_SELECTION", "INTERVAL_CALIBRATION")
    ) == 1981
    assert len(bundle.predictor_columns) == 405
    assert config.dataset.target not in bundle.source_test.columns
    assert config.dataset.target not in bundle.source_validation.columns

    assert len(feature_set_columns(bundle.predictor_columns, "FULL", config)) == 405
    assert len(feature_set_columns(bundle.predictor_columns, "ACTIVE_ONLY", config)) == 85
    assert len(feature_set_columns(bundle.predictor_columns, "NO_UNRESOLVED", config)) == 325
    assert (
        len(
            feature_set_columns(
                bundle.predictor_columns, "WITHOUT_CONSUMABLE_USAGE", config
            )
        )
        == 285
    )


def test_real_wp09_feature_only_manifest_replays_exactly() -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    _, first = prepare_feature_only_roles(config)
    _, second = prepare_feature_only_roles(config)
    assert first["deterministic_payload_sha256"] == second["deterministic_payload_sha256"]
    assert first == second
