# Billing Engine Specification

This document defines the rules for determining ICD‑10 and CPT codes, calculating reimbursement estimates, and producing billing summaries for Headway.  The goal is to select the highest reimbursing valid code combination for each clinical encounter while complying with the practice’s policies and payer requirements.

## Overview

The billing engine operates on AI‑generated clinical content (summary, session note, treatment plan) and optional structured inputs (psychotherapy minutes, service type, diagnoses).  It uses the following information to produce billing codes:

* **Service type** – One of `Psychiatric Evaluation`, `Psychotherapy`, `Medication Management`, `Follow‑up`, or `Crisis`.
* **Psychotherapy minutes** – Total minutes of psychotherapy documented in the note.
* **E/M level** – Derived from documented medical decision making complexity: `99202`–`99205` for new patients; `99212`–`99215` for established patients.
* **Diagnoses** – One or more ICD‑10 codes provided by the clinician or derived from the note.
* **Allowed CPT codes** – A defined set appropriate for an MD in psychiatry.
* **Reimbursement table** – Payer‑specific reimbursement rates for each CPT code.【184629542025788†L120-L168】

## Allowed CPT codes

The engine may use only the following CPT codes, drawn from the practice’s reimbursement sheet:

| Code   | Description                                                    |
|------- |---------------------------------------------------------------|
| 90785 | Interactive complexity (optional when documented)              |
| 90792 | Psychiatric diagnostic evaluation with medical services         |
| 90832 | Psychotherapy, 30 minutes (16–37 min)                           |
| 90833 | Psychotherapy add‑on, 30 minutes with E/M (16–37 min)          |
| 90834 | Psychotherapy, 45 minutes (38–52 min)                           |
| 90836 | Psychotherapy add‑on, 45 minutes with E/M (38–52 min)          |
| 90837 | Psychotherapy, 60 minutes (53 min or more)                      |
| 90838 | Psychotherapy add‑on, 60 minutes with E/M (53 min or more)     |
| 90839 | Crisis psychotherapy, first 60 minutes                          |
| 90840 | Crisis psychotherapy, each additional 30 minutes               |
| 99202–99205 | New patient E/M codes                                    |
| 99212–99215 | Established patient E/M codes                            |

Codes outside this set should not be suggested by the engine.

## CPT selection rules

The engine follows these steps to select CPT codes:

1. **Determine visit type** – Identify whether the encounter is a psychiatric evaluation, psychotherapy‑only visit, medication management/follow‑up, or crisis based on the service name.
2. **Check documentation** – Extract psychotherapy minutes from the note and detect whether medical decision making is documented.  If no psychotherapy is documented, do not apply psychotherapy codes.
3. **Evaluation visits** – For psychiatric evaluations, the engine should default to **E/M + psychotherapy add‑on** rather than `90792`.  It should examine the documentation to assign the highest supported new‑patient E/M level and pair it with the appropriate psychotherapy add‑on code (90833/90836/90838).  Modifier 25 must be appended to the E/M code because psychotherapy is an additional significant and separately identifiable service.
4. **Follow‑up/medication management** – For established patients, follow the same logic as evaluations but choose from `99212`–`99215` plus the appropriate psychotherapy add‑on.
5. **Psychotherapy‑only** – When no medical decision making is documented, select a standalone psychotherapy code (`90832`, `90834`, or `90837`) based on psychotherapy minutes.
6. **Crisis** – Use `90839` for the first 60 minutes and add `90840` for each additional 30 minutes.
7. **Interactive complexity** – Apply `90785` only when the documentation supports it and payers allow it.  Do not apply by default.
8. **Minute thresholds** – Use these minute ranges to choose psychotherapy codes:
   * 16–37 min → `90832` (or `90833` when billed with E/M)
   * 38–52 min → `90834` (or `90836` when billed with E/M)
   * 53+ min   → `90837` (or `90838` when billed with E/M)【184629542025788†L120-L168】

## Reimbursement ranking

To choose the highest reimbursing valid combination, the engine uses the reimbursement table from the practice’s sheet.  For each valid code or code combination:

* Look up the reimbursement amount for the selected payer (e.g., Aetna, Anthem, Carelon, Cigna, Oscar/Optum, Oxford/Optum, Quest, United/Optum).
* Sum the values for combined codes (e.g., `99214` + `90836`).
* Compare all valid options and pick the one with the highest total reimbursement.

When comparing `90792` versus E/M + psychotherapy add‑on for evaluations, always show the reimbursement difference to the user.  Even if E/M + add‑on is higher (as is often the case), the engine should still display `90792` as a fallback option for completeness.

## Modifier 25 rule

When both an E/M code and a psychotherapy add‑on code are billed together, append modifier 25 to the E/M code.  For example:

* `99214-25, 90836`
* `99205-25, 90838`

The modifier indicates that the E/M service was significant and separately identifiable from the psychotherapy provided.

## Billing summary format

After selecting the codes, the engine constructs a one‑line billing summary for Headway in the following format:

```
Patient Name: <name> | Date of Service: <MM/DD/YYYY> | Service Name: <service> | ICD-10 Codes: <codes> | CPT Codes: <codes> | Length of Psychotherapy: <minutes> minutes
```

* **Patient Name** – Taken from the patient record.
* **Date of Service** – Taken from the document metadata.
* **Service Name** – One of the allowed service names (Psychiatric Evaluation, Psychotherapy, Medication Management, Follow‑up, Crisis).
* **ICD‑10 Codes** – Comma‑separated list of diagnosis codes documented.
* **CPT Codes** – Comma‑separated codes with `-25` appended to E/M codes when psychotherapy add‑ons are present.
* **Length of Psychotherapy** – Total minutes documented (0 if none).

## Evaluation reimbursement comparison panel

For psychiatric evaluations, display a comparison table showing reimbursement for:

1. `90792`
2. Highest reimbursing valid E/M + psychotherapy add‑on combination (e.g., `99205-25 + 90838`)【184629542025788†L120-L168】

Include columns for each payer (Aetna, Anthem, Carelon, Cigna, Oscar/Optum, Oxford/Optum, Quest, United/Optum) and show the total reimbursement.  Provide a recommendation based on the highest reimbursing option.

## ICD‑10 coding

The engine does not determine ICD‑10 codes automatically.  These must be provided by the clinician or extracted from the AI output with clinician review.  The engine should validate that at least one code is present.  It should also support multiple codes separated by commas.

## Error handling

If required information is missing (no documented psychotherapy minutes, missing E/M complexity, no ICD‑10 codes), the engine should not guess.  Instead, it should mark the billing summary as incomplete and require clinician input before finalising.

## Notes

* The engine must be transparent and never hallucinate codes or minutes.  It should always base decisions on actual documented content or clinician input.
* Modifier 25 should be applied only when both E/M and psychotherapy codes are billed and documentation supports it.
* The reimbursement table may change.  Load it from a configuration file or database, and allow updates without code changes.
* Future enhancements could include telehealth modifiers (e.g., `-95`, `-GT`) when payers require them.

Implementing this specification will ensure that billing codes are accurate, compliant and maximally reimbursing.
