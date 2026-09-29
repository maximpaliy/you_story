# Music Practice Tracker — Project Definition

## 1. Project Goal

Build an application for tracking musical practice and progress.

The initial use case is personal: I want to track my practice sessions while learning music through applications and other learning resources.

Although the initial user base is a single user, the system must be designed from the beginning to support multiple users with isolated personal data and preferences.

The application should be useful as a real product, while also serving as a learning project for developing and operating a properly architected multi-client cloud application.

---

## 2. Users and Accounts

### Initial state

* Initially, there will be a single user.
* The application must nevertheless support multiple users architecturally.

### Authentication

* Users should be able to authenticate using their Google account.
* The application should use Google's supported authentication mechanisms rather than implementing its own password authentication.
* The application must maintain its own internal user identity independently of a user's Google email address.
* The authentication architecture should allow additional authentication providers to be added in the future.

### User data

Users may have different:

* musical instruments;
* catalogs;
* catalog customizations;
* practice histories;
* statistics;
* preferences;
* goals and tags.

Private user data must be isolated from other users.

---

# 3. Musical Instruments

The system must support multiple musical instruments.

Initial instruments:

* Guitar
* Piano

The architecture must allow additional instruments to be added without fundamental changes to the system.

The same musical work may have different learning/practice content for different instruments.

For example, a particular song might have:

* guitar content in Yousician;
* piano content in Yousician;
* guitar content in Songsterr.

Instrument-specific content may have different structures, characteristics and statistics.

---

# 4. Music Content and Sources

The application must support content originating from multiple external learning platforms or sources.

Initial examples include:

* Yousician
* Songsterr

Different sources may represent music differently.

A source may provide concepts such as:

* songs;
* versions;
* fragments;
* lessons;
* exercises;
* tracks;
* sections;
* levels;
* techniques;
* scores/statistics;

but these concepts should **not be assumed to have identical structures across sources**.

The architecture must identify the common domain concepts required by the application while allowing source-specific structures and metadata.

### Requirements

* Practice records must be able to refer to content from any supported source.
* Source-specific metadata must not unnecessarily couple the common practice-history model to one particular source.
* Adding another source should not require a fundamental redesign of the application.
* The same musical work may have different content depending on source and instrument.
* The system should distinguish shared/catalog information from user-specific information.

The exact domain model for representing songs, versions, fragments, practice items and source-specific structures is an architectural decision.

---

# 5. Shared and User-Specific Catalog

The system should distinguish between globally/shared catalog information and user-specific content.

Conceptually, there may be:

1. **Shared catalog**

   * generally reusable content;
   * potentially curated or contributed by users in the future.
2. **User-specific catalog**

   * content created by an individual user;
   * private additions or customizations.
3. **User-specific customization**

   * personal tags;
   * goals;
   * characteristics;
   * statistics;
   * other metadata associated with shared content.

Users must be able to customize their own experience without unintentionally changing another user's data.

The architecture should preserve a clear distinction between:

* catalog/content data;
* user customization;
* practice history.

Future versions may support explicit sharing or community contributions, but this is not an MVP requirement.

---

# 6. Practice Calendar and Sessions

The main application experience should be calendar-based.

For each day, the user should be able to define a small number of training/practice sessions, typically 1–2.

Each practice session can contain multiple pieces of music or practice items.

For each item practiced during a session, the user should be able to record:

* amount of time spent;
* applicable performance statistics;
* notes or other relevant information;
* optionally, a short audio or video recording.

The system should allow users to:

* view previous days;
* view the sessions belonging to a particular day;
* view the contents of a session;
* navigate from a practice record to the associated content.

The architecture should distinguish a catalog/content entity from an individual historical practice event.

---

# 7. Practice History

The application must preserve a historical record of practice.

Users should be able to navigate history at least in two directions:

### Calendar → History

For a particular date:

```text
Date
  → Practice sessions
    → Practiced items
      → Recorded statistics/media
```

### Content → History

For a particular piece of content/practice item:

```text
Content
  → All historical practice records
```

Historical practice records must remain meaningful even if the associated catalog metadata is subsequently changed.

The architecture should therefore consider how catalog evolution affects historical records.

---

# 8. Performance Statistics

Different sources, instruments and content types may expose different statistics.

For example:

* maximum points received;
* score;
* accuracy;
* level;
* completion status;
* other source-specific performance measurements.

Some content may have no applicable performance statistics.

The system must therefore:

* allow different statistics for different types of content;
* allow absence of a statistic without inventing meaningless values;
* support adding new statistics without fundamental redesign;
* allow user-specific statistics where appropriate;
* avoid making the common practice-history model dependent on Yousician-specific fields.

The exact representation of extensible statistics is an architectural decision.

---

# 9. Content Characteristics

Content may have characteristics describing the technique or type of material being practiced.

Initial examples for guitar include:

* Cowboy Chords
* Power Chords
* Finger Picking
* Melody

The list must be configurable/extensible.

Characteristics may differ depending on:

* instrument;
* source;
* content type.

The architecture should avoid assuming that these initial guitar characteristics are universally applicable.

---

# 10. Media

Users should optionally be able to attach short audio or video recordings to practice activity.

Media should be associated with the relevant practice context/history rather than becoming an intrinsic requirement of the catalog model.

The architecture should consider:

* object/media storage;
* upload and download;
* authorization;
* supported formats;
* file-size limits;
* deletion;
* lifecycle/retention;
* future media processing if required.

Media storage should be designed independently from the application's primary relational/domain data where appropriate.

---

# 11. Security

Security must be considered from the architecture stage rather than added after implementation.

Requirements include:

* Google-based authentication;
* secure authentication flows appropriate to each client;
* server-side authorization;
* strict user-data isolation;
* secure handling of authentication tokens and sessions;
* secrets must not be stored in source control;
* sensitive configuration must use appropriate secret management;
* HTTPS for application communication;
* API endpoints must enforce authorization server-side;
* clients must not be trusted to enforce access restrictions.

The system should request only the authentication information/scopes actually required.

Security-sensitive architecture must receive an independent security review before implementation.

---

# 12. Privacy and Data Ownership

The application may contain personal information and user-created audio/video.

The system should therefore support clear ownership of user data.

The architecture must consider:

* account deletion;
* deletion of user practice history;
* deletion of user media;
* deletion or handling of private catalog content;
* data export;
* data retention;
* storage location;
* privacy requirements applicable to the deployed system.

User data should not become inaccessible or impossible to delete because of unnecessary coupling between catalog and practice-history data.

Detailed privacy/legal requirements can be refined before production deployment.

---

# 13. Multi-Client Architecture

The initial client should be a web application.

Future clients may include:

* Android application;
* Telegram bot;
* potentially other clients.

The backend architecture should therefore expose functionality in a way that is not fundamentally coupled to the web UI.

Client requirements must be considered during the initial architecture phase rather than added after the backend has been designed.

Different clients may have different interaction models while sharing the same underlying user, catalog and practice-history concepts.

---

# 14. Offline and Connectivity

Offline operation is **not an initial requirement**.

However, the architecture should explicitly evaluate whether mobile/offline support would materially affect the design.

If offline support is not implemented, the decision should be documented rather than left implicit.

---

# 15. Search and Navigation

Users should be able to find and navigate their music/practice data.

The system should support appropriate ways to:

* find songs/content;
* filter content by source;
* filter by instrument;
* navigate to versions/practice items where applicable;
* find historical practice records;
* find all practice records associated with particular content.

The exact search implementation is an architectural decision and does not require a dedicated search infrastructure for the MVP unless justified.

---

# 16. Data Integrity and Evolution

The system must preserve the integrity of historical practice data.

The architecture must consider:

* database schema evolution;
* migrations;
* catalog changes;
* changes to content structure;
* changes to statistics;
* deletion or replacement of catalog entities;
* preservation of historical records.

A change to the catalog should not silently corrupt or invalidate historical practice information.

---

# 17. Reliability, Backup and Recovery

The application should provide reasonable reliability for personal practice data.

The architecture should define:

* database backup strategy;
* media backup/lifecycle strategy;
* recovery approach;
* handling of accidental deletion;
* acceptable data-loss expectations.

Enterprise-level disaster recovery is not an MVP requirement.

---

# 18. Observability and Operations

The deployed system should have basic operational visibility.

The architecture should provide appropriate mechanisms for:

* structured application logging;
* error reporting;
* basic metrics;
* health/readiness checks;
* monitoring;
* operational alerts where appropriate;
* request/correlation identifiers where useful.

The goal is to make failures diagnosable without requiring direct inspection of production infrastructure.

---

# 19. Deployment and Environments

The project should support at least separate development/test and production environments.

The architecture should define:

* CI/CD;
* automated testing;
* deployment process;
* configuration management;
* secret management;
* database migrations;
* production deployment permissions;
* infrastructure management.

GitHub should remain the primary source of truth for:

* source code;
* project requirements;
* architecture documentation;
* architectural decisions;
* agent instructions;
* tests;
* issues and work tracking.

---

# 20. Non-Functional Requirements

The application should prioritize:

### Security

User data must be isolated and protected.

### Reliability

Confirmed practice records should not be silently lost.

### Maintainability

The project should have clear architecture, automated tests and documented decisions.

### Extensibility

It should be possible to add:

* users;
* instruments;
* content sources;
* content structures;
* statistics;
* clients;

without fundamental redesign.

### Scalability

The system must support multiple users, but no enterprise-scale capacity target is required for the MVP.

### Portability

The architecture should avoid unnecessary vendor lock-in where this does not add meaningful complexity.

### Performance

The application should provide responsive interactive behavior, with concrete performance targets proposed by the architecture phase where appropriate.

---

# 21. Technology Constraints and Preferences

The architecture must stay within the approved technology constraints.

### Backend

Allowed:

* Python
* Java

The architecture team may select either according to the project's needs.

### Android

Allowed:

* Kotlin
* Java

Kotlin is preferred for new Android development.

### Cloud

* GCP is preferred.

The specific cloud services should be selected during architecture design.

### Other technologies

Database engines, frameworks, libraries, messaging systems, storage technologies and other infrastructure components should be selected during architecture design.

Agents must not introduce technologies outside the approved technology constraints without explicit human approval.

If an agent believes an excluded technology would provide a significant benefit, it should document the proposal and reasoning as an architectural decision for human review rather than silently adopting it.

---

# 22. Architecture Questions

The architecture phase must explicitly address at least the following:

1. What is the common domain model across different music/content sources?
2. How should source-specific structures and metadata be represented?
3. How should instrument-specific content be represented?
4. How should shared catalog data, user-created content and user customizations be separated?
5. How should historical practice records remain valid as catalog data evolves?
6. How should extensible performance statistics be represented?
7. What authentication architecture should be used for web, Android and future clients?
8. How should authorization and user-data isolation be enforced?
9. How should media be stored and accessed securely?
10. What API architecture best supports multiple clients?
11. What deployment and infrastructure architecture is appropriate?
12. What observability, backup and recovery mechanisms are appropriate?
13. Which parts of the system should be designed for future extensibility now, and which should deliberately remain simple?
14. How should the system support additional content sources and instruments without premature abstraction?
15. How should the security agent participate in architecture design, threat modeling, security requirements, and review?
16. Which security-sensitive decisions require independent security-agent approval before implementation?
17. How should security findings, exceptions, and remediation decisions be documented and tracked?

These questions are inputs to architecture, not predetermined implementation decisions.

---

# 23. Initial MVP Scope

The first usable version should aim to provide:

* Google authentication;
* multi-user foundations;
* guitar and piano;
* a music/content catalog;
* at least one supported content source;
* calendar-based practice tracking;
* practice sessions;
* practice records;
* basic/extensible statistics;
* configurable content characteristics;
* practice-history views;
* appropriate security and authorization;
* automated tests;
* deployment to the chosen cloud environment;
* basic operational monitoring.

The following are intentionally future scope:

* additional content sources;
* community/shared catalog contributions;
* advanced catalog sharing;
* Android application;
* Telegram bot;
* recommendations;
* automated imports;
* advanced analytics;
* sophisticated offline functionality;
* media attachments and account-deletion behavior, deferred from the first
  increment;

The architecture should allow these future capabilities without requiring fundamental redesign, but they should not drive unnecessary complexity into the MVP.

The first increment excludes media support, account-deletion behavior and
offline capabilities unless their later addition would require database
migrations. Stable foundations that prevent disruptive ownership, identifier or
existing-data changes are included initially. Ordinary additive migrations for
later requirements are allowed under ADR-006.

---

# 24. Architecture and Development Process

This project is also intended to validate a multi-agent software-development workflow.

The development process should follow:

```text
Project Definition
        ↓
Architecture Design
        ↓
Independent Architecture Review
        ↓
Security Review
        ↓
Human Approval
        ↓
Test Design
        ↓
Independent Test Review
        ↓
Implementation
        ↓
Automated Tests
        ↓
Independent Code Review
        ↓
Security Review of Security-Sensitive Changes
        ↓
Deployment / Validation
```

The project should include a dedicated security agent or security specialist responsible for:

* participating in architecture design from the beginning;
* identifying security requirements and trust boundaries;
* performing threat modeling;
* reviewing authentication, authorization, data isolation, media access, secrets, and deployment decisions;
* reviewing security-sensitive implementation changes;
* identifying vulnerabilities and required mitigations;
* documenting security risks, accepted exceptions, and remediation status;
* confirming that security gates are complete before relevant implementation or deployment.

Specialist reviews should be invoked when relevant, including:

* Security
* Database/Data
* API
* Web/UI
* Android
* Telegram
* Infrastructure/Operations
* Testing

The Lead/Orchestrator should involve only the specialists relevant to a particular architectural or implementation decision rather than requiring every specialist for every task.

No feature implementation should begin before the relevant architecture, security, and test-design gates have been completed.

---

# 25. Out of Scope for the Project Definition

This document intentionally does **not** prescribe:

* database schema;
* exact backend framework;
* exact frontend framework;
* exact API style;
* exact authentication implementation;
* exact Google Cloud services;
* exact media-storage implementation;
* exact deployment architecture;
* exact statistics representation;
* exact catalog hierarchy;
* exact security tooling or security-agent implementation details.

These are responsibilities of the architecture phase.

Any significant architectural decision must be documented and independently reviewed before implementation.
---

# Owner Clarifications — 2026-09-26

These clarifications were supplied by the human owner while reviewing Issue #1
and are part of the approved project definition:

1. The stray text `de to` in the user-specific customization list is removed;
   the intended bullet is `personal tags`.
2. The MVP supports Yousician as its initial source and Songsterr as a second
   source used to validate multi-source behavior. Catalog data is manually
   managed. Automated import is not planned.
3. The MVP catalog is personal to each user. The design must permit shared
   catalogs to be introduced later without a database upgrade or another
   backward-incompatible change.
4. Account deletion is provisionally handled through anonymization. The final
   deletion, retention, and historical-integrity policy is deferred and must be
   decided before production deployment.
5. In the MVP, a user can add songs and record a practice session against the
   manually managed Yousician catalog. Yousician content has this hierarchy:
   `Song (name) → Version (name and level) → Fragment (name)`. The domain design
   must also accommodate different hierarchy structures for other catalogs,
   including Songsterr, without assuming the Yousician hierarchy is universal.
6. The first increment does not include media support, account-deletion behavior
   or offline capabilities unless their later addition would require database
   migrations. The owner confirmed that ordinary additive migrations are
   allowed; ADR-006 requires only stable foundations that avoid disruptive
   ownership, identifier or existing-data changes.
7. The first increment uses Google OIDC for allowlisted or invited accounts and
   does not request or store email. Google issuer and subject map to an internal
   application-owned user ID. Web sessions use the approved server-side defaults
   in ADR-007; Android and Telegram identity remain deferred.
