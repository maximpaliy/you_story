# Independent architecture review — GitHub Issue #5

- **Latest review date:** 2026-10-03
- **Material:** Two-role ADR-008 plus explicit repository tenant scoping and
  Issue #5 test design
- **Verdict:** Pass after documentation consistency corrections

## Revision reviewed

The human owner directed the MVP to use only:

- constrained `app_runtime` for the running application; and
- privileged `app_owner` solely for the controlled migration/deployment process.

The revision removes the previously proposed migrator and intermediate owner
roles, temporary privilege choreography, and predesigned tenant-data migration
mechanism. Privileged migration over existing tenant-private data is now a future
design gate triggered only by a concrete requirement.

## Findings and dispositions

1. **Existing review records described the superseded role model.** Resolved by
   replacing their conclusions with independent re-reviews of the two-role model.
2. **Migration terminology implied an existing exception mechanism.** Resolved by
   naming the MVP schema-migration boundary and future privileged tenant-data
   migration design gate explicitly.
3. **Module ownership and bootstrap compatibility.** Pass. Module-owned migration
   files remain enforced while the controlled process uses one database owner.
   The five-table authentication control plane and fixed security-definer function
   boundary remain coherent.
4. **Future compatibility.** Pass. Future grant-aware sharing, clients and service
   extraction do not require a separate migration role.
5. **Explicit repository scoping plus RLS.** Pass. The owner-only MVP requires
   every normal private table occurrence to be visibly anchored to the immutable
   actor tenant in repository SQL while FORCE RLS remains an independent
   backstop. This is data scoping, not duplicated object/action authorization.
6. **Future sharing semantics.** Pass. Actor/owner equality is explicitly an MVP
   rule. Sharing must retain visible scoping through reviewed grant/authorized-
   scope predicates mirrored in RLS and use-case authorization rather than
   weakening or removing repository scope.
7. **Catalog provisioning trigger was ambiguous.** Resolved. Provisioning runs
   after first login or a later login callback only while orthogonal provisioning
   state is pending—not during ordinary requests or session validation. Catalog
   plus owner grant commit atomically, and the internal ActorContext-derived ready
   transition is conditional, idempotent and cannot revive a disabled account.
   No retry endpoint, worker, middleware, CLI or scheduler is introduced.

## Conclusion

The simplified architecture is consistent with ADR-003, ADR-005, ADR-006,
ADR-007 and the foundation architecture. No concrete MVP requirement justifies a
third database identity or temporary grant/revoke mechanism. No blocking or
material architecture finding remains and no risk is accepted.

The human owner approved ADR-008 on 2026-10-03. SEC-05, SEC-07, Issue #9
implementation/security review, cumulative feature evidence, and Issue #16
platform proof of runtime/owner credential separation remain separate gates; no
risk is accepted by approval.
