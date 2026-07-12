# Interim WP10 demonstration

`wp10_demo.md` is the canonical slide source. It is deliberately labelled as
an interim synthetic demonstration: predictive warning, attribution,
controller comparison, and independent safety filtering remain pending.

Build from the repository root:

```text
conda run -n devkki make presentation
```

Reviewed outputs are written to:

```text
reports/presentation/wp10_demo.pdf
reports/presentation/wp10_demo.pptx
```

All figures are regenerated from frozen WP08/WP10 CSV/JSON evidence by
`scripts/generate_communication_figures.py`. The figure manifest records input
and output SHA-256 values.
