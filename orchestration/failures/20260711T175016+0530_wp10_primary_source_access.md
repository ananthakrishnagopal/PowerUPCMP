# Failure report

## Task

Review primary literature before freezing the WP10 utility-to-CMP connection
topologies and parameter-provenance plan.

## Failed command

Internet open requests for four primary CMP sources returned by the prior
search: a PMC article on slurry/rinse-water availability, an Elsevier article
on DI-water pad conditioning, a Wear article on conditioner deterioration, and
an Electrochemical Society article on CMP pad experiments.

## Error

```text
PMC: reCAPTCHA/checking-your-browser page
Elsevier: HTTP 403
Elsevier: HTTP 429
DOI/publisher page: robots.txt fetch denied
```

## Files changed before failure

WP08 documentation/governance closeout completed before this separate WP10
research action, including:

- `docs/running_paper.md`
- `docs/mathematical_model.md`
- `docs/modeling_notes.md`
- `docs/architecture.md`
- `docs/README.md`
- `README.md`
- `orchestration/project_charter.md`
- `orchestration/architecture.md`
- `orchestration/implementation_plan.md`
- `orchestration/dependency_graph.md`
- `orchestration/project_status.md`
- `orchestration/task_manifest.yaml`
- `orchestration/reports/phase_3_cmp_model_redesign.md`

No WP10 source, configuration, schema, interface, or topology decision file
was created before the access failure.

## Read-only diagnosis

The failure is access-control behavior at the source hosts, not an invalid DOI
or contradictory scientific result. The preceding search successfully
returned bibliographic metadata and abstract/experimental snippets for:

- `10.1016/j.mee.2005.07.080`, which reports DI water used with a diamond
  conditioner to regenerate glazed CMP pad areas;
- `10.1016/j.wear.2017.07.019`, which experimentally studies conditioning
  performance deterioration and pad roughness maintenance;
- `10.1149/2162-8777/abdc40`, which reports DI-water pad break-in and explicit
  polishing/conditioning conditions; and
- the PMC-indexed slurry-injection study, whose search result states that UPW
  pad rinsing occurs between polishes and residual rinse water can mix with
  slurry.

These sources support the existence of DI/UPW conditioning or rinse pathways.
They do not calibrate the proposed facility-header pressure/flow thresholds or
prove the plumbing of the PHM tool. Those mappings would remain synthetic.

## Likely causes

Publisher rate limiting, bot protection, and robots restrictions prevent the
browser tool from opening pages that are otherwise identifiable by DOI.

## Recovery options

1. Continue using the successfully returned publisher/search metadata and DOI
   records, cite only the narrow supported structural facts, and classify all
   facility-to-tool threshold values as synthetic assumptions.
2. Search for author-hosted or institutional copies of the same identified
   articles without retrying the blocked hosts.
3. Omit literature support for the dressing-water topology and classify the
   entire topology as synthetic; this is more conservative but discards useful
   structural evidence already available.

## Recommended option

Option 1, with option 2 used later only if a specific equation or quotation is
needed. The WP10 decision needs structural plausibility, not verbatim article
content, and must not reinterpret the sources as real-tool plumbing or
parameter calibration.

## User decision required

Authorize resuming WP10 scientific freeze using the available DOI metadata and
abstract-level evidence, with every unmeasured facility-to-CMP mapping kept
explicitly synthetic and sensitivity-tested.
