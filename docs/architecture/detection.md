# Deterministic incident detection

## Window and thresholds

The detector evaluates each registered service over a configurable rolling window. A request-based rule requires a minimum sample count before it can trigger. The initial rules are:

- error rate greater than 10% with at least five requests;
- request duration p95 greater than 2,000 ms with at least five requests;
- three or more failed health-check events.

The nearest-rank method calculates p95. All calculations happen in the backend and the resulting inputs, thresholds, and active rules are persisted in `Incident.detection_context`.

## Grouping

At most one open service-degradation incident is updated per service. Multiple active rules become signals on that incident instead of creating parallel alerts. Event evidence is unique by incident, type, and source reference. The latest deterministic analysis is updated in place.

## Deployment correlation and severity

The most recent deployment is correlated only when it precedes detection by no more than the configured correlation window. Correlation raises severity to `high`; an error rate of at least 50% or p95 of at least 5,000 ms is `critical`. Correlation is a deterministic fact and is not yet a root-cause claim.

## Recovery

An open incident is resolved only when no rule is active and the current window contains enough new request or health-check samples to demonstrate recovery. Silence is not treated as recovery.

## Execution

Compose runs `python -m app.detect --loop` every 30 seconds. `POST /api/v1/detection/run` provides an immediate, reproducible development trigger. Both paths use the same transaction-scoped detection service.
