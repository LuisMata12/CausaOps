# ADR 0001: Begin with a modular monolith

Status: Accepted

## Context

The MVP needs a complete, auditable incident loop, not independent scaling of many services. A distributed backend would add networking, consistency, deployment, and debugging work before those costs buy anything.

## Decision

Use one FastAPI application and one PostgreSQL database. Keep domain boundaries explicit in Python modules and isolate external LLM/action integrations behind interfaces. Use Next.js as a separate presentation application. Add a worker or Redis only when a measured background-job requirement appears.

## Consequences

Local setup and testing remain small. Database transactions can preserve incident invariants. Future extraction is possible at the module seams, but is not promised or optimized prematurely.

