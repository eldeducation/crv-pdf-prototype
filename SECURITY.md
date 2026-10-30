# Security hardening — 2026-10-30

This remains an invitation-only prototype, not a production security approval.

## Changes that preserve the document-generation settings

- Session servers and video/PDF child processes receive an explicit allowlist of runtime environment variables. AI keys, the invitation password, unrelated cloud/Git credentials, Python startup paths and Node startup hooks are not inherited. This is defense in depth, not OS isolation.
- Starting a new session reserves one of the existing eight slots atomically, then starts the process outside the gateway lock. A slow startup no longer holds that lock against existing users. A failed startup releases its reservation. Capacity is unchanged.
- Browser-facing errors hide host paths and key-shaped values. Local source paths in public result metadata are reduced to filenames. Original evidence, prompts, generation records on disk, Markdown and PDF content are not rewritten. Administrators must still treat private diagnostics as sensitive.
- Gateway audit output contains only UTC time, HTTP method, a fixed route category and response status. It excludes keys, bodies, URLs, cookies, session IDs, IPs and video names. Successful health/status polling is omitted. Render controls retention of its platform logs.

Model selection, reasoning effort, instructions, extraction resolution/frame counts, transcription, external research, time/token/spending limits, HTML/CSS, the PDF renderer and API-key acceptance are unchanged.

## Validation

- Existing 159 regression tests passed; five infrastructure tests cover secret exclusion across an actual subprocess boundary, error sanitization, safe logging, concurrent session creation and failed-start capacity recovery.
- Nineteen local HTTP invitation/login/session checks passed using a disposable fixture password.
- Identical test-only responses were replayed through the before/after programs. Model request payloads, Markdown, PDF text, both rendered page images and an actual decoded video frame matched exactly. This is output parity for the fixtures, not a measurement or guarantee of AI accuracy.
- No paid AI API was called.

## Remaining work

Keys and video/PDF tools still share one OS identity/container. Per-user authentication/revocation, isolated key handling and workers, comprehensive download/disk quotas, dependency auditing, safe retention/deletion and Chromium sandbox compatibility remain open.

Automatic deletion and new processing limits were deliberately excluded from this change: active jobs and the user's download/recovery window require a separate retention design. The existing temporary storage can still disappear on a Render restart. Download completed results.

The app's spending estimate is not a provider-enforced limit. Use a dedicated key with a provider spending limit. No real user's key or password is included in this repository.
