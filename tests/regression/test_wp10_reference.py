import json
from pathlib import Path


def test_wp10_reference_evidence_and_trace_hashes_are_frozen() -> None:
    root = Path(__file__).parents[2]
    report = json.loads(
        (root / "reports" / "sensitivity" / "wp10_coupling_validation.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["all_checks_passed"] is True
    assert report["default_topology"] == "NO_CONNECTION"
    assert report["negative_control"]["dressing_water_support"]["trace_sha256"] == (
        "f8359518903a8def6e02d03a8bc73123cc8a32dc5c32ed39dabc26745bfc3f20"
    )
    assert report["positive_causal_chain"]["no_connection"]["trace_sha256"] == (
        "3560cb28a4cc8e87d778146f2cf0964290d733da2a0b59bee283659644ae41fc"
    )
    assert report["positive_causal_chain"]["dressing_water_support"]["trace_sha256"] == (
        "19f440b2fd31959c619c31b851003ac496ff4d3b66c1643a6c6fbbb4951dfa10"
    )
    assert report["negative_control"]["dressing_water_support"][
        "minimum_effective_availability"
    ] == 1.0
    assert report["positive_causal_chain"]["dressing_water_support"][
        "mean_polish_mrr_m_s"
    ] < report["positive_causal_chain"]["no_connection"]["mean_polish_mrr_m_s"]
