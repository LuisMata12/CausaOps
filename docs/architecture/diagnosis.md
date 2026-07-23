# Evidence-bound Groq diagnosis

## Boundary

Groq is the only real inference provider. CausaOps uses `openai/gpt-oss-20b` for development and
integration checks and `openai/gpt-oss-120b` for primary diagnoses. Unit tests use an in-process
test double and never make network calls or consume quota.

The model has no database, shell, Docker, browser, or remediation tools. It receives one curated
JSON snapshot and returns one JSON object.

## Input snapshot

The backend selects the incident identity, service, deterministic detection context, correlated
deployment, allow-listed actions, and at most the configured number of incident evidence records.
Every evidence record is assigned its persisted `IncidentEvidence.id`. Log and evidence content is
explicitly treated as untrusted data rather than instructions.

The Groq API key is read from the local or deployed environment and is never included in the
snapshot, API response, diagnosis record, or frontend.

## Output contract

Groq receives the Pydantic-derived JSON Schema in strict mode. The response contains a conclusion,
Spanish summary, optional probable cause, alternatives, allow-listed recommendation, missing
information, confidence, and evidence IDs. The backend—not the model—adds the mandatory
human-review flag to every accepted result.

The backend validates the schema again and verifies that every cited ID was included in the input
snapshot. A valid JSON response with an unknown evidence ID is rejected.

## Persistence and failure behavior

Every attempt begins as `pending` and ends as `completed`, `rejected`, or `provider_error`.
Completed records retain the validated response, cited evidence IDs, model, profile, latency, token
usage, and prompt snapshot. Rejections and provider failures retain a safe error description for
auditability.

Inference failure never changes incident state and never interrupts deterministic detection.
Recommendations are inert data. Phase 5 will introduce a separate human-approval boundary before
any simulated remediation.
