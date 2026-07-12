# Failure report

## Task

Verify and fetch the PHM 2016 CMP dataset under T-DATA-FETCH.

## Failed command

Read-only web open of the historical download URL referenced by the PHM 2016 challenge materials:

```text
https://www.dropbox.com/s/1ihr7wkmrj7nfyw/2016%20PHM%20DATA%20CHALLENGE%20CMP%20DATA%20SET.zip?dl=0
```

## Error

The web tool refused the URL as unsafe/non-retryable:

```text
URL ... is not safe to open (non-retryable error)
```

An independent check of the download link on the PHM Society’s official 2016 challenge page returned HTTP 404 for:

```text
https://www.phmsociety.org/sites/phmsociety.org/files/2016%20PHM%20DATA%20CHALLENGE%20CMP%20DATA%20SET.zip
```

## Files changed before failure

None in this turn. Repository inspection, orchestration reads, and web source verification were read-only. No fetch tool, registry entry, or dataset file was created or modified.

## Read-only diagnosis

- The official PHM Society challenge page documents the CMP task and expected filename patterns `CMP-training-ddd.csv`, `CMP-training-removalrate.csv`, and `CMP-test-ddd.csv`.
- The official page’s current ZIP link is unavailable (404).
- A PHM challenge call-for-participation PDF hosted outside the official site references a historical Dropbox ZIP URL.
- The source/licence terms for that Dropbox archive are not stated in the repository or the official challenge page.
- The PHM Society NASA repository mirror currently points the CMP entry to a 2019 data-challenge page, not a direct 2016 CMP archive.
- The repository policy forbids silently using a mirror, requires licence verification, and requires an exact filename/size/checksum manifest before transfer.
- No network download occurred and no credentials were used.

## Likely causes

The original competition archive was retired or moved, while historical references still point to a Dropbox host. The available pages do not establish a current licence or a safe authoritative download endpoint.

## Recovery options

1. User provides an approved current URL and licence statement, or explicitly confirms the historical Dropbox URL and its permitted licence for this project.
2. User supplies the archive locally; the fetch tool can then validate filename, size, SHA-256, ZIP members, and schema without network access.
3. Implement the registry-gated fetch tool and tests without downloading; keep PHM acquisition blocked.
4. Use an unregistered mirror or paper/repository attachment; this is not permitted without a provenance and licence decision.

## Recommended option

Option 1 or 2. A source/licence decision is required before any transfer. Option 3 can proceed after user direction, but it cannot produce public-data validation.

## User decision required

Provide an approved download URL with licence information, or provide the archive locally. If you want the historical Dropbox URL used despite the absent licence, explicitly state the permitted use and accept that provenance remains non-authoritative.
