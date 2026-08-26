# Phase 10 Performance Optimization Plan

## Rule

No optimization counts unless it either:

1. measurably improves a recorded benchmark; or
2. removes unnecessary work/complexity without changing application behavior.

Correctness, auditability, authorization, validation rules, immutable SitReps,
and recovery behavior take priority over speed.

## Phase 10A baseline

Run:

```powershell
python -m scripts.phase10_performance_baseline
```

The script is read-only. It benchmarks:

- operational dashboard bundle;
- population/evacuation reconciliation;
- barangay validation queue;
- evacuation-center validation queue;
- report-history retrieval.

For each operation it records:

- wall-clock time;
- measured SQL execution time;
- SQL query count;
- peak Python allocation during the operation;
- repeated SQL query shapes;
- diagnostic flags for high query count, possible N+1 patterns, and slow
  operations.

Machine-specific results are stored under `performance_results/` and are not
committed to Git.

## Phase 10B database/query optimization

Use the Phase 10A results to target only demonstrated bottlenecks. Candidate
work includes:

- replacing N+1 query loops with set-based/batched queries;
- reducing duplicate latest-report reads;
- consolidating dashboard/reconciliation database sessions where safe;
- adding indexes only where query plans demonstrate a need;
- preserving transaction and snapshot semantics.

## Phase 10C Streamlit optimization

After database hot paths are addressed:

- reduce repeated service calls caused by reruns;
- cache only safe, read-only data with explicit invalidation/TTL;
- avoid caching authorization-sensitive or mutable operational state
  indefinitely;
- reduce repeated dataframe/export transformations.

## Phase 10D verification

Re-run the exact same benchmark and compare the before/after JSON results.
All regression, migration, deployment, backup, and recovery checks must remain
green.
