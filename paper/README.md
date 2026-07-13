# Living journal manuscript

This directory contains the journal-neutral, two-column manuscript derived
from the detailed evidence ledger in [`docs/running_paper.md`](../docs/running_paper.md).
The LaTeX paper is the publication narrative; the Markdown ledger remains the
more detailed record of decisions, equations, artifacts, and pending work.

Build from the repository root with:

```text
conda run -n devkki make paper
```

The reviewed output is written to
[`reports/paper/semifab_cmp_poc_draft.pdf`](../reports/paper/semifab_cmp_poc_draft.pdf).
Intermediate LaTeX files remain under the ignored `paper/build/` directory.

The current manuscript reports guarded public-data WP09 virtual metrology,
bounded synthetic WP08/WP10 evidence, and the frozen WP12 simulation-only
early-warning experiment. It reports WP09's failed uncertainty and hybrid
gates alongside its point performance and the conditional synthetic WP13
attribution result, including the stronger rule-only comparator and
communication-driven abstention. Predictive control, safety filtering, and
paired controller results remain visibly pending. A target journal class and
final author affiliations will be selected only before submission.
