# Service and support agreement — DRAFT, NOT LEGAL ADVICE

> **This is a working draft prepared by an engineer, not a lawyer.** It must be
> reviewed by counsel before being offered to any customer. Jurisdiction,
> liability limits and consumer-law interaction are all left deliberately blank
> or flagged, because getting them wrong is worse than leaving them open.

## Why this is not a EULA

TinyMRP is released under The Unlicense — a dedication to the public domain.
That is a deliberate choice by the owner, and it decides the shape of this
document.

You cannot impose use restrictions on software you have placed in the public
domain. A clause saying the customer may not redistribute, may not exceed a
seat count, or may only use it in a certain field would contradict the licence
and would not hold. Writing one anyway produces a document that reads binding
and is not, which is the worst of both outcomes.

So this agreement covers **everything that is not the software**: hosting,
installation, support, availability, and the handling of the customer's data.
Those are real services, and an agreement about them is enforceable.

Practical consequence for sales: the customer is not buying permission to use
TinyMRP. They already have that, and so does everyone else. They are buying
somebody to run it and answer the phone.

---

## 1. Parties and scope

**Provider:** [legal entity name, registered address, company number]
**Customer:** [legal entity name, registered address]

The Provider will supply the services described in Section 3 for the TinyMRP
instance(s) listed in Schedule A.

The software itself is public domain and is supplied without warranty under
The Unlicense. Nothing in this agreement grants or restricts rights in the
software, because none are needed and none can be imposed.

## 2. What the software does

The functional scope is defined in `PRODUCT_SCOPE.md` and is incorporated by
reference. In particular the Customer acknowledges that **TinyMRP does not
provide inventory, stock control, costing, capacity planning or accounting
integration**, and has not been represented as doing so.

This clause exists to prevent a dispute about the name.

## 3. Services provided

- **Hosting** of the Customer's instance on Provider-managed infrastructure,
  or installation on Customer-provided infrastructure. Schedule A states which.
- **Installation and configuration**, including initial roles and users.
- **Updates** to the TinyMRP software as they are released.
- **Backups** taken [FREQUENCY — currently daily where the backup job is
  installed] and retained for [RETENTION].
- **Support** as described in Section 4.

## 4. Support

| Severity | Meaning | Response target |
| --- | --- | --- |
| 1 — Down | Nobody can log in, or data loss is suspected | [X] working hours |
| 2 — Impaired | A core workflow fails; a workaround exists | [X] working days |
| 3 — Question | How-to, configuration, advice | [X] working days |

*Response* means a human has read it and replied. It is not a commitment to
resolve within that time, and the table should not imply one.

Support hours: [DAYS, TIMES, TIMEZONE].
Support channel: [EMAIL / PORTAL].

**Not included:** CAD support, SolidWorks licensing or configuration beyond the
TinyMRP add-in, data entry, recovery of data the Customer deleted, or changes
to the Customer's own network and firewall.

## 5. Availability

Target availability: [X]% measured monthly, excluding scheduled maintenance
notified [N] days in advance.

> **Counsel to advise.** Do not offer an availability figure with a service
> credit attached until the deployment has been measured over a real period.
> As of 2026-08-07 no such measurement exists — the readiness endpoint is in
> place, but nothing has been recording uptime. Committing to a number now
> would be a guess with financial consequences.

## 6. Customer data

- The Customer owns all data it places in TinyMRP: parts, BOMs, files,
  comments and user records.
- The Provider processes that data only to deliver the services in Section 3.
- On termination, the Provider will supply an export in a documented format
  within [N] days, and delete the Customer's data within [N] days thereafter.
  See `RETENTION_AND_DELETION.md`.
- Data handling detail, including sub-processors, is in `PRIVACY.md` and the
  data-processing addendum.

## 7. Confidentiality

Each party will keep the other's non-public information confidential and use it
only for this agreement. For the Provider this expressly includes the
Customer's engineering data, which is typically the Customer's most
commercially sensitive material.

## 8. Warranties and liability

The software is public domain and supplied **as is**, without warranty of any
kind, as stated in The Unlicense.

The Provider warrants only that the **services** will be performed with
reasonable skill and care.

> **Counsel to complete.** Liability cap, exclusions, and the interaction with
> non-excludable statutory rights depend on jurisdiction. Left blank
> deliberately.

## 9. Term and termination

Initial term [N] months, continuing thereafter until terminated by either party
on [N] days' notice. On termination Section 6 governs data return and deletion.

## 10. Security

The Provider will maintain the security measures described in
`docs/PRODUCTION_HARDENING_BASELINE.md`, and will notify the Customer without
undue delay of any breach affecting the Customer's data.

Security issues may be reported as described in `SECURITY_DISCLOSURE.md`.

---

## Schedule A — instances covered

| Instance | Hosted by | Domain | Backup schedule | Notes |
| --- | --- | --- | --- | --- |
| | | | | |

---

## Open items before this can be used

1. Counsel review of the whole document, especially Sections 5 and 8.
2. Legal entity details, jurisdiction and governing law.
3. Support hours and response targets the Provider can actually meet.
4. An availability figure backed by measurement, or no figure at all.
5. Confirmation that the public-domain framing in "Why this is not a EULA"
   matches the owner's commercial intent — it follows from the licence choice,
   but counsel should confirm it reads as intended to a customer.
