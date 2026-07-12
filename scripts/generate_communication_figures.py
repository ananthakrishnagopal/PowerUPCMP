#!/usr/bin/env python3
"""Generate reviewed WP08/WP10 figures for the interim deck and manuscript."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "semifab-poc-matplotlib"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "reports" / "figures"
POSITIVE_TRACE = ROOT / "reports" / "sensitivity" / "wp10_positive_chain_trace.csv"
NEGATIVE_TRACE = ROOT / "reports" / "sensitivity" / "wp10_negative_control_trace.csv"
WP10_REPORT = ROOT / "reports" / "sensitivity" / "wp10_coupling_validation.json"
WP08_TRACE = ROOT / "reports" / "cmp" / "wp08_reference_trace.csv"

NAVY = "#17324D"
BLUE = "#2474B5"
CYAN = "#20A4B5"
ORANGE = "#E67E22"
RED = "#C0392B"
GREEN = "#2E8B57"
GRAY = "#68737D"
LIGHT = "#EEF3F6"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_figure(fig: plt.Figure, filename: str) -> Path:
    destination = OUTPUT_DIR / filename
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    fig.savefig(temporary, format="png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    temporary.replace(destination)
    return destination


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.edgecolor": GRAY,
            "axes.labelcolor": NAVY,
            "axes.titleweight": "bold",
            "xtick.color": GRAY,
            "ytick.color": GRAY,
            "grid.color": "#D7E0E6",
            "grid.linewidth": 0.7,
            "legend.frameon": False,
            "figure.titleweight": "bold",
        }
    )


def shade_process(ax: plt.Axes, event: tuple[float, float] | None = None) -> None:
    if event is not None:
        ax.axvspan(event[0], event[1], color=RED, alpha=0.08, lw=0)
    ax.axvline(6.0, color=GRAY, ls="--", lw=0.8)
    ax.axvline(7.0, color=GRAY, ls="--", lw=0.8)
    ax.grid(True, axis="y")
    ax.set_xlim(0.0, 9.0)


def positive_chain_figure(positive: pd.DataFrame) -> Path:
    connected = positive[positive["topology"] == "DRESSING_WATER_SUPPORT"].copy()
    time = connected["source_time_s"]
    fig, axes = plt.subplots(4, 1, figsize=(10.5, 9.0), sharex=True)
    fig.suptitle(
        "Synthetic degraded-UPS interruption propagates to the CMP dressing boundary",
        color=NAVY,
        y=0.995,
    )

    axes[0].plot(time, connected["grid_voltage_pu"], color=GRAY, lw=1.8, label="Grid voltage")
    axes[0].plot(time, connected["ups_output_voltage_pu"], color=BLUE, lw=2.0, label="UPS output")
    axes[0].set_ylabel("Voltage (pu)")
    axes[0].legend(loc="lower right", ncol=2)

    axes[1].plot(time, connected["motor_speed_rad_s"] / 188.5, color=ORANGE, lw=2.0, label="Motor speed / nominal")
    axes[1].plot(time, connected["pump_flow_m3_s"] / 2.0e-4, color=CYAN, lw=2.0, label="Pump flow / reference")
    axes[1].set_ylabel("Normalized state")
    axes[1].legend(loc="lower right", ncol=2)

    axes[2].plot(time, connected["upw_supply_pressure_pa"] / 300_000.0, color=BLUE, lw=2.0, label="Supply pressure / nominal")
    axes[2].plot(time, connected["upw_tool_flow_m3_s"] / 1.0e-4, color=GREEN, lw=2.0, label="Tool flow / nominal")
    axes[2].set_ylabel("UPW service ratio")
    axes[2].legend(loc="lower right", ncol=2)

    axes[3].plot(time, connected["effective_availability"], color=RED, lw=2.1, label="Effective utility availability")
    axes[3].plot(time, connected["cmp_pad_surface_activity"], color=NAVY, lw=2.0, label="Stored pad-surface activity")
    axes[3].set_ylabel("Dimensionless")
    axes[3].set_xlabel("Simulation time (s)")
    axes[3].legend(loc="lower right", ncol=2)

    for ax in axes:
        shade_process(ax, event=(1.0, 4.0))
    axes[0].text(2.5, 1.03, "Grid interruption", color=RED, ha="center", va="bottom")
    axes[3].text(3.0, 0.04, "DRESS", color=GRAY, ha="center")
    axes[3].text(6.5, 0.04, "PREPARE", color=GRAY, ha="center")
    axes[3].text(8.0, 0.04, "POLISH", color=GRAY, ha="center")
    fig.text(
        0.01,
        0.005,
        "All signals are synthetic simulator states. Shading denotes the declared interruption.",
        color=GRAY,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.025, 1, 0.975))
    return save_figure(fig, "wp10_positive_chain.png")


def negative_control_figure(negative: pd.DataFrame) -> Path:
    connected = negative[negative["topology"] == "DRESSING_WATER_SUPPORT"].copy()
    time = connected["source_time_s"]
    baseline = connected.loc[connected["source_time_s"] < 1.0, "upw_supply_pressure_pa"].tail(10).mean()
    pressure_delta_kpa = (connected["upw_supply_pressure_pa"] - baseline) / 1000.0
    fig, axes = plt.subplots(2, 1, figsize=(10.0, 5.4), sharex=True)
    fig.suptitle("Healthy UPS ride-through remains a coupling negative control", color=NAVY)

    axes[0].plot(time, connected["ups_output_voltage_pu"], color=BLUE, lw=2.0, label="UPS output")
    axes[0].plot(time, pressure_delta_kpa, color=ORANGE, lw=1.8, label="UPW pressure deviation (kPa)")
    axes[0].set_ylabel("pu / kPa")
    axes[0].legend(loc="lower right", ncol=2)

    axes[1].plot(time, connected["upw_tool_flow_m3_s"] / 1.0e-4, color=GREEN, lw=2.0, label="Tool flow / nominal")
    axes[1].plot(time, connected["effective_availability"], color=RED, lw=2.0, label="Effective availability")
    axes[1].set_ylabel("Dimensionless")
    axes[1].set_xlabel("Simulation time (s)")
    axes[1].legend(loc="lower right", ncol=2)
    for ax in axes:
        shade_process(ax, event=(1.0, 1.4))
    axes[1].set_ylim(0.96, 1.01)
    fig.text(
        0.01,
        0.005,
        "25% grid-voltage sag for 400 ms; tool flow and coupling availability remain exactly nominal.",
        color=GRAY,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    return save_figure(fig, "wp10_negative_control.png")


def delayed_result_figure(positive: pd.DataFrame, report: dict[str, object]) -> Path:
    null = positive[positive["topology"] == "NO_CONNECTION"].copy()
    connected = positive[positive["topology"] == "DRESSING_WATER_SUPPORT"].copy()
    positive_summary = report["positive_causal_chain"]
    assert isinstance(positive_summary, dict)
    null_summary = positive_summary["no_connection"]
    connected_summary = positive_summary["dressing_water_support"]
    assert isinstance(null_summary, dict) and isinstance(connected_summary, dict)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4))
    fig.suptitle("The DRESS disturbance changes later MRR through stored pad state", color=NAVY)

    pad_values = [
        float(null_summary["pad_surface_activity_at_dress_end"]),
        float(connected_summary["pad_surface_activity_at_dress_end"]),
    ]
    axes[0].bar(["No connection", "Dressing-water\nsupport"], pad_values, color=[GRAY, RED], width=0.62)
    axes[0].set_ylabel("Pad-surface activity at DRESS end")
    axes[0].set_ylim(0.48, 0.57)
    axes[0].grid(True, axis="y")
    for index, value in enumerate(pad_values):
        axes[0].text(index, value + 0.002, f"{value:.4f}", ha="center", color=NAVY)
    axes[0].text(0.5, 0.487, "5.36% lower", ha="center", color=RED, fontweight="bold")

    for frame, label, color in (
        (null, "No connection", GRAY),
        (connected, "Dressing-water support", RED),
    ):
        axes[1].plot(
            frame["source_time_s"],
            frame["cmp_mrr_m_s"] * 6.0e10,
            lw=2.1,
            color=color,
            label=label,
        )
    axes[1].axvline(7.0, color=NAVY, ls="--", lw=0.9)
    axes[1].set_xlim(6.7, 9.0)
    axes[1].set_xlabel("Simulation time (s)")
    axes[1].set_ylabel("Simulated instantaneous MRR (nm/min)")
    axes[1].grid(True, axis="y")
    axes[1].legend(loc="lower right")
    axes[1].text(7.05, 63, "POLISH", color=NAVY)
    fig.text(
        0.01,
        0.005,
        "Mean POLISH MRR is 3.19% lower in the connected synthetic case; no safe envelope or control claim is implied.",
        color=GRAY,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return save_figure(fig, "wp10_delayed_mrr_result.png")


def sensitivity_figure(report: dict[str, object]) -> Path:
    global_sensitivity = report["global_sensitivity"]
    assert isinstance(global_sensitivity, dict)
    indices = global_sensitivity["indices"]
    assert isinstance(indices, list)
    labels = {
        "link_strength": "Link strength",
        "reference_supply_pressure_pa": "Reference pressure",
        "pressure_zero_fraction": "Pressure zero fraction",
        "pressure_full_fraction": "Pressure full fraction",
        "reference_tool_flow_m3_s": "Reference flow",
        "flow_zero_fraction": "Flow zero fraction",
        "flow_full_fraction": "Flow full fraction",
    }
    ordered = sorted(indices, key=lambda item: float(item["total_order_estimate"]))
    names = [labels[str(item["parameter"])] for item in ordered]
    first = [float(item["first_order_estimate_raw"]) for item in ordered]
    total = [float(item["total_order_estimate"]) for item in ordered]
    y = np.arange(len(names))

    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    ax.barh(y - 0.18, first, height=0.34, color=CYAN, label="First-order estimate")
    ax.barh(y + 0.18, total, height=0.34, color=BLUE, label="Total-order estimate")
    ax.set_yticks(y, names)
    ax.set_xlabel("Variance-based sensitivity estimate")
    ax.set_title("WP10 response is contingent on synthetic coupling assumptions", color=NAVY)
    ax.grid(True, axis="x")
    ax.legend(loc="lower right")
    fig.tight_layout()
    return save_figure(fig, "wp10_global_sensitivity.png")


def wp08_reference_figure(wp08: pd.DataFrame) -> Path:
    time = wp08["timestamp_s"]
    fig, axes = plt.subplots(3, 1, figsize=(10.0, 6.8), sharex=True)
    fig.suptitle("WP08 standalone CMP reference trace", color=NAVY)

    axes[0].plot(time, wp08["contact_pressure_pa"] / 1000.0, color=BLUE, lw=2.0, label="Contact pressure")
    axes[0].set_ylabel("Pressure (kPa)")
    axes[0].legend(loc="lower right")

    axes[1].plot(time, wp08["relative_velocity_m_s"], color=ORANGE, lw=2.0, label="Relative velocity")
    axes[1].plot(time, wp08["slurry_availability"], color=GREEN, lw=2.0, label="Slurry availability")
    axes[1].set_ylabel("m/s or fraction")
    axes[1].legend(loc="lower right", ncol=2)

    axes[2].plot(time, wp08["instantaneous_mrr_m_s"] * 6.0e10, color=RED, lw=2.1, label="Instantaneous MRR")
    axes[2].set_ylabel("MRR (nm/min)")
    axes[2].set_xlabel("Simulation time (s)")
    axes[2].legend(loc="upper right")
    for ax in axes:
        ax.axvline(1.0, color=GRAY, ls="--", lw=0.8)
        ax.axvline(6.0, color=GRAY, ls="--", lw=0.8)
        ax.grid(True, axis="y")
    axes[2].text(0.5, 4, "PREPARE", color=GRAY, ha="center")
    axes[2].text(3.5, 4, "POLISH", color=GRAY, ha="center")
    axes[2].text(6.5, 4, "HOLD", color=GRAY, ha="center")
    fig.text(
        0.01,
        0.005,
        "Synthetic reference: 100 nm/min nominal MRR; removal is mode-gated and zero in HOLD.",
        color=GRAY,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    return save_figure(fig, "wp08_reference_trace.png")


def architecture_figure() -> Path:
    fig, ax = plt.subplots(figsize=(12.0, 4.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.set_title("Simulation and supervisory-control architecture", color=NAVY, pad=12)

    x_positions = [0.25, 2.05, 3.85, 5.65, 7.45, 9.25]
    labels = [
        "Electrical\ndisturbance",
        "UPS / VFD\nand motor",
        "Pump\nresponse",
        "UPW pressure,\nflow, thermal",
        "Declared\nCMP topology",
        "CMP state\nand MRR",
    ]
    colors = [GRAY, BLUE, CYAN, GREEN, ORANGE, RED]
    boxes = []
    for x, label, color in zip(x_positions, labels, colors, strict=True):
        box = FancyBboxPatch(
            (x, 2.25),
            1.45,
            0.9,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            facecolor=color,
            edgecolor="white",
            linewidth=1.0,
        )
        ax.add_patch(box)
        ax.text(x + 0.725, 2.70, label, ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        boxes.append(box)
    for left, right in zip(x_positions, x_positions[1:]):
        ax.add_patch(
            FancyArrowPatch(
                (left + 1.45, 2.70),
                (right, 2.70),
                arrowstyle="-|>",
                mutation_scale=12,
                color=NAVY,
                linewidth=1.4,
            )
        )

    pending = [
        (6.0, "Observed sensors\n+ streaming features"),
        (8.15, "Early warning +\nroot-cause attribution"),
        (10.3, "Controller +\nindependent safety"),
    ]
    for x, label in pending:
        box = FancyBboxPatch(
            (x, 0.55),
            1.65,
            0.75,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            facecolor=LIGHT,
            edgecolor=GRAY,
            linestyle="--",
            linewidth=1.2,
        )
        ax.add_patch(box)
        ax.text(x + 0.825, 0.925, label, ha="center", va="center", color=NAVY, fontsize=8.5)
    ax.add_patch(FancyArrowPatch((9.98, 2.25), (6.8, 1.3), arrowstyle="-|>", mutation_scale=12, color=GRAY, linestyle="--"))
    ax.add_patch(FancyArrowPatch((7.65, 0.925), (8.15, 0.925), arrowstyle="-|>", mutation_scale=12, color=GRAY, linestyle="--"))
    ax.add_patch(FancyArrowPatch((9.8, 0.925), (10.3, 0.925), arrowstyle="-|>", mutation_scale=12, color=GRAY, linestyle="--"))
    ax.text(0.25, 0.17, "Solid path validated synthetically through WP10", color=NAVY, fontweight="bold")
    ax.text(6.0, 0.17, "Dashed supervisory path remains pending", color=GRAY, fontweight="bold")
    fig.tight_layout()
    return save_figure(fig, "system_architecture_wp10.png")


def main() -> int:
    apply_style()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    positive = pd.read_csv(POSITIVE_TRACE)
    negative = pd.read_csv(NEGATIVE_TRACE)
    wp08 = pd.read_csv(WP08_TRACE)
    report = json.loads(WP10_REPORT.read_text(encoding="utf-8"))

    outputs = [
        architecture_figure(),
        wp08_reference_figure(wp08),
        negative_control_figure(negative),
        positive_chain_figure(positive),
        delayed_result_figure(positive, report),
        sensitivity_figure(report),
    ]
    manifest = {
        "manifest_id": "INTERIM_COMMUNICATION_FIGURES_WP10_V1",
        "evidence_plane": "SYNTHETIC_SIMULATOR",
        "public_data_model_results_included": False,
        "controller_results_included": False,
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (POSITIVE_TRACE, NEGATIVE_TRACE, WP10_REPORT, WP08_TRACE)
        },
        "outputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in outputs
        },
        "claims_boundary": (
            "Interim WP08/WP10 synthetic evidence only; no public-data model, "
            "real-fab, defect, yield, predictive-control, or equipment claim."
        ),
    }
    manifest_path = OUTPUT_DIR / "communication_figure_manifest.json"
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    print(json.dumps({"manifest": str(manifest_path.relative_to(ROOT)), **manifest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
