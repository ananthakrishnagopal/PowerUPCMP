from scripts.validate_wp10_coupling import (
    chain_summary,
    simulate_chain,
    topology_config,
    upstream_projection,
)
from semifab_poc.simulation.coupling import UtilityCmpTopology


def test_healthy_ups_sag_remains_a_coupling_negative_control() -> None:
    null_rows = simulate_chain(
        "healthy_25pct_400ms_sag",
        topology_config(UtilityCmpTopology.NO_CONNECTION),
    )
    connected_rows = simulate_chain(
        "healthy_25pct_400ms_sag",
        topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT),
    )
    connected = chain_summary(connected_rows)

    assert upstream_projection(null_rows) == upstream_projection(connected_rows)
    assert connected["minimum_effective_availability"] == 1.0
    assert all(
        left["cmp_pad_surface_activity"] == right["cmp_pad_surface_activity"]
        and left["cmp_mrr_m_s"] == right["cmp_mrr_m_s"]
        for left, right in zip(null_rows, connected_rows, strict=True)
    )


def test_degraded_ups_interruption_reaches_later_mrr_through_dress_memory() -> None:
    null_rows = simulate_chain(
        "degraded_ups_3s_interruption_during_dress",
        topology_config(UtilityCmpTopology.NO_CONNECTION),
    )
    connected_rows = simulate_chain(
        "degraded_ups_3s_interruption_during_dress",
        topology_config(UtilityCmpTopology.DRESSING_WATER_SUPPORT),
    )
    null = chain_summary(null_rows)
    connected = chain_summary(connected_rows)

    assert upstream_projection(null_rows) == upstream_projection(connected_rows)
    assert connected["minimum_dressing_availability_during_dress"] == 0.0
    assert connected["pad_surface_activity_at_dress_end"] < null["pad_surface_activity_at_dress_end"]
    assert connected["mean_polish_mrr_m_s"] < null["mean_polish_mrr_m_s"]
    assert connected["final_cumulative_removal_m"] < null["final_cumulative_removal_m"]

