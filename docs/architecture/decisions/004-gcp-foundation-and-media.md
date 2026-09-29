# ADR-004: Managed GCP runtime and private object media

- Status: Accepted
- Date: 2026-09-26
- Owners: Architecture / human owner

## Context

The application needs low-operations deployment, relational durability, secure
optional media, environment isolation and diagnosable failures. GCP is preferred.

## Decision

Run an immutable application container on Cloud Run, PostgreSQL on Cloud SQL,
private media in Cloud Storage, secrets in Secret Manager and images in Artifact
Registry. Separate production/non-production projects. GitHub Actions uses
Workload Identity Federation. Media uses authorized intent/finalize flows and
short-lived operation-specific signed URLs.

## Alternatives considered

- GKE: control without a demonstrated need and significantly more operations.
- Store media in PostgreSQL: harms backup size and serving efficiency.
- Public bucket/object URLs: unacceptable authorization and privacy exposure.
- Self-managed VM/database: more patching, backup and availability burden.

## Consequences

Managed services reduce operations but introduce GCP coupling and recurring
cost. Domain/storage ports, standard PostgreSQL and OCI containers retain
reasonable portability. Production topology, region and HA need cost approval.

## Security / privacy impact

IAM, signed URL leakage, upload abuse, object retention, region and deletion are
security/privacy decisions requiring threat modeling and independent approval.

## Human approval

Approved by the human owner on 2026-09-27, relying on the documented GCP
architecture expertise and independent reviews. This approval accepts the
managed GCP service boundary, environment isolation, keyless GitHub Actions
federation, and private-media intent/finalize flow. It does not approve the
production region, topology/HA cost, media allowlists and limits, retention or
deletion policy, or accept any open security finding; those gates remain in
force before their stated implementation or deployment stages.
