from dataclasses import dataclass
from datetime import date


ALLOWED_CPT_CODES = {
    "90785",
    "90792",
    "90832",
    "90833",
    "90834",
    "90836",
    "90837",
    "90838",
    "90839",
    "90840",
    "99202",
    "99203",
    "99204",
    "99205",
    "99212",
    "99213",
    "99214",
    "99215",
}

DEFAULT_REIMBURSEMENT = {
    "Aetna": {"90792": 210, "99205": 250, "99215": 180, "99214": 145, "90838": 150, "90837": 170, "90836": 118, "90834": 125, "90833": 82, "90832": 90, "90839": 210, "90840": 95},
    "Anthem": {"90792": 220, "99205": 245, "99215": 175, "99214": 140, "90838": 160, "90837": 175, "90836": 120, "90834": 130, "90833": 85, "90832": 92, "90839": 215, "90840": 98},
    "Cigna": {"90792": 205, "99205": 240, "99215": 170, "99214": 138, "90838": 145, "90837": 165, "90836": 112, "90834": 120, "90833": 80, "90832": 88, "90839": 205, "90840": 90},
    "United/Optum": {"90792": 200, "99205": 235, "99215": 168, "99214": 135, "90838": 148, "90837": 162, "90836": 110, "90834": 118, "90833": 78, "90832": 86, "90839": 200, "90840": 88},
}


@dataclass(frozen=True)
class BillingInput:
    patient_name: str
    date_of_service: date
    service_name: str
    icd10_codes: list[str]
    psychotherapy_minutes: int = 0
    em_level: str | None = None
    is_new_patient: bool = False
    has_medical_decision_making: bool = False
    payer: str = "Aetna"


@dataclass(frozen=True)
class BillingResult:
    cpt_codes: list[str]
    headway_block: str
    reimbursement_notes: dict
    incomplete_reason: str | None = None


def psychotherapy_code(minutes: int, with_em: bool) -> str | None:
    if minutes < 16:
        return None
    if minutes <= 37:
        return "90833" if with_em else "90832"
    if minutes <= 52:
        return "90836" if with_em else "90834"
    return "90838" if with_em else "90837"


def crisis_codes(minutes: int) -> list[str]:
    if minutes < 60:
        return []
    codes = ["90839"]
    extra = max(0, minutes - 60)
    codes.extend(["90840"] * ((extra + 29) // 30))
    return codes


def _rate(payer: str, code: str) -> float:
    return float(DEFAULT_REIMBURSEMENT.get(payer, DEFAULT_REIMBURSEMENT["Aetna"]).get(code.replace("-25", ""), 0))


def _total(payer: str, codes: list[str]) -> float:
    return sum(_rate(payer, code) for code in codes)


def select_cpt_codes(data: BillingInput) -> BillingResult:
    if not data.icd10_codes:
        return _result(data, [], {"error": "Missing ICD-10 codes"}, "Missing ICD-10 codes")

    service = data.service_name.lower()
    if "crisis" in service:
        codes = crisis_codes(data.psychotherapy_minutes)
        if not codes:
            return _result(data, [], {"error": "Crisis requires at least 60 minutes"}, "Crisis requires at least 60 minutes")
        return _result(data, codes, _notes(data, [codes]))

    add_on = psychotherapy_code(data.psychotherapy_minutes, with_em=True)
    standalone = psychotherapy_code(data.psychotherapy_minutes, with_em=False)
    candidates: list[list[str]] = []

    if data.has_medical_decision_making:
        em = data.em_level or ("99205" if data.is_new_patient else "99214")
        if em not in ALLOWED_CPT_CODES:
            return _result(data, [], {"error": f"Unsupported E/M code {em}"}, f"Unsupported E/M code {em}")
        candidates.append([em])
        if add_on:
            candidates.append([f"{em}-25", add_on])

    if standalone:
        candidates.append([standalone])

    if "psychiatric evaluation" in service:
        candidates.append(["90792"])

    if not candidates:
        return _result(data, [], {"error": "No supported CPT code from documented service"}, "No supported CPT code from documented service")

    ranked = sorted(candidates, key=lambda codes: _total(data.payer, codes), reverse=True)
    return _result(data, ranked[0], _notes(data, candidates))


def _notes(data: BillingInput, candidates: list[list[str]]) -> dict:
    rows = []
    for codes in candidates:
        rows.append({"codes": codes, "payer": data.payer, "total": _total(data.payer, codes)})
    return {"candidates": sorted(rows, key=lambda row: row["total"], reverse=True), "recommended": rows[0] if rows else None}


def _result(data: BillingInput, codes: list[str], notes: dict, incomplete: str | None = None) -> BillingResult:
    headway = create_headway_block(
        data.patient_name,
        data.date_of_service,
        data.service_name,
        data.icd10_codes,
        codes,
        data.psychotherapy_minutes,
    )
    return BillingResult(cpt_codes=codes, headway_block=headway, reimbursement_notes=notes, incomplete_reason=incomplete)


def create_headway_block(patient_name: str, dos: date, service_name: str, icd10_codes: list[str], cpt_codes: list[str], minutes: int) -> str:
    return (
        f"Patient Name: {patient_name} | Date of Service: {dos:%m/%d/%Y} | "
        f"Service Name: {service_name} | ICD-10 Codes: {', '.join(icd10_codes)} | "
        f"CPT Codes: {', '.join(cpt_codes)} | Length of Psychotherapy: {minutes} minutes"
    )
