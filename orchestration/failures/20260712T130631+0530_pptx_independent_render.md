# Failure report

## Task

Independently render the generated PPTX through LibreOffice into `/tmp/` to visually validate Pandoc's 23-slide PowerPoint layout.

## Failed command

```text
libreoffice --headless --convert-to pdf --outdir /tmp/wp10_pptx_render reports/presentation/wp10_demo.pptx
```

## Error

```text
Warning: failed to launch javaldx - java may not function correctly

(process:17): dconf-CRITICAL **: 13:06:22.340: unable to create file '/run/user/1000/dconf/user': Read-only file system. dconf will not work properly.
```

Exit status: `1`.

## Files changed before failure

Presentation source and outputs had already been created before this optional independent render:

- `Makefile`
- `presentation/README.md`
- `presentation/wp10_demo.md`
- `scripts/generate_communication_figures.py`
- generated figures and their manifest under `reports/figures/`
- `reports/presentation/wp10_demo.pdf`
- `reports/presentation/wp10_demo.pptx`
- `orchestration/failures/20260712T130024+0530_presentation_preview.md`

The failed LibreOffice command changed no repository file. Its intended output directory under `/tmp/` is empty.

## Read-only diagnosis

- LibreOffice attempted to create its dconf state at `/run/user/1000/dconf/user`, which is read-only in this execution environment.
- The command exited before producing a converted PDF.
- The generated PPTX itself previously passed full ZIP integrity testing with no corrupt members.
- XML inspection found 23 non-empty slides. The six-slide difference from the 17-page Beamer PDF is attributable to Pandoc separating dense figures/tables from continuation bullets; all source sections and continuation content are present.
- The canonical Beamer PDF was independently built by XeLaTeX and has already passed structural, text, and representative-page visual checks.

## Likely causes

1. **Primary:** LibreOffice inherited an unwritable desktop configuration/runtime path inside the sandbox.
2. The `javaldx` warning may be incidental; the deck does not require Java features.
3. There is no current evidence of PPTX corruption or malformed slide XML.

## Recovery options

1. Retry the optional conversion with an isolated writable LibreOffice profile and XDG directories under `/tmp/`.
2. Skip this redundant render and accept the existing PPTX container, XML-content, and canonical-PDF validation evidence.
3. Open the PPTX manually in a desktop PowerPoint-compatible application outside this workflow.

## Recommended option

Option 1. It keeps the validation local and read-only with respect to the repository while addressing the diagnosed configuration-path failure directly. If that succeeds, inspect representative continuation slides and then commit the presentation deliverable.

## User decision required

Authorize the isolated-profile LibreOffice retry and continuation, or choose another recovery option.

## Resolution

The user authorized the isolated-profile retry. It removed the dconf error but LibreOffice still exited before conversion; the follow-up evidence is recorded in `20260712T130750+0530_pptx_isolated_render_retry.md`.
