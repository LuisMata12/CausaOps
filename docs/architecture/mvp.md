# MVP architecture

## Boundary

The MVP is one product with three applications: the web UI, the API, and (from Phase 2) a controlled Demo Service. PostgreSQL is the system of record. The browser never talks directly to the database or an LLM.

## Data flow by the end of the MVP

1. The Demo Service sends versioned telemetry and deployment events to the API.
2. The API validates and stores raw facts before running configurable deterministic rules.
3. A detector opens or updates an incident and creates evidence references.
4. Deterministic analysis calculates rates, percentiles, deployment distance, and frequent errors.
5. Groq receives only the selected facts and returns a strictly validated diagnosis.
6. The API rejects diagnoses containing evidence references that were not supplied.
7. A human approves one allow-listed action; an executor performs the simulated rollback.
8. The detector observes the recovery window and closes the incident only when facts support it.

## Module direction

Future API modules will follow `routes -> services -> repositories/models`. Provider adapters and action executors implement narrow interfaces and do not own incident state. This prevents model output from bypassing validation or approval.

## Safety invariants

- Persist facts independently from AI inferences.
- Never accept arbitrary commands or URLs as remediation actions.
- Validate input at the API boundary and LLM output against a strict schema.
- Require an authenticated human approval before any state-changing action once authentication is introduced.
- Keep the platform useful when the configured LLM is unavailable.
