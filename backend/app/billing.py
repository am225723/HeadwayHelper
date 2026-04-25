import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import get_settings
from .database import SessionLocal
from .models import AppSetting, BillingRule, ReimbursementRate


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

APPROVED_PAYERS = [
    "Aetna",
    "Anthem Blue Cross and Blue Shield Connecticut",
    "Carelon Behavioral Health",
    "Cigna",
    "Oscar (Optum)",
    "Oxford (Optum)",
    "Quest Behavioral Health",
    "United Healthcare (Optum)",
]


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
    thresholds = load_billing_rules().get("psychotherapy_minute_thresholds", {"30": [16, 37], "45": [38, 52], "60": [53, None]})
    if minutes < 16:
        return None
    if minutes <= thresholds.get("30", [16, 37])[1]:
        return "90833" if with_em else "90832"
    if minutes <= thresholds.get("45", [38, 52])[1]:
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
    rates = load_reimbursement_table()
    value = rates.get(payer, {}).get(code.replace("-25", ""))
    if value is None:
        raise ValueError(f"Missing reimbursement value for {payer} {code.replace('-25', '')}")
    return float(value)


def _total(payer: str, codes: list[str]) -> float:
    return sum(_rate(payer, code) for code in codes)


def load_reimbursement_table() -> dict[str, dict[str, float]]:
    db = SessionLocal()
    try:
        rows = db.query(ReimbursementRate).filter(ReimbursementRate.is_active.is_(True)).all()
        if rows:
            table: dict[str, dict[str, float]] = {payer: {} for payer in APPROVED_PAYERS}
            for row in rows:
                table.setdefault(row.payer_name, {})[row.cpt_code] = float(row.amount)
            return table
    finally:
        db.close()
    path = Path(get_settings().reimbursement_table_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    if not path.exists():
        return {payer: {} for payer in APPROVED_PAYERS}
    raw = json.loads(path.read_text())
    return {payer: {code: amount for code, amount in raw.get(payer, {}).items() if amount is not None} for payer in APPROVED_PAYERS}


def load_billing_rules() -> dict[str, dict]:
    db = SessionLocal()
    try:
        rows = db.query(BillingRule).all()
        return {row.rule_key: row.rule_value_json for row in rows}
    finally:
        db.close()


def default_payer() -> str:
    db = SessionLocal()
    try:
        row = db.query(AppSetting).filter(AppSetting.setting_key == "default_payer").first()
        if row:
            return str(row.setting_value_json.get("payer") or "Aetna")
    finally:
        db.close()
    return "Aetna"


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
        allowed = set(load_billing_rules().get("allowed_cpt_codes", {}).get("codes", sorted(ALLOWED_CPT_CODES)))
        if em not in allowed:
            return _result(data, [], {"error": f"Unsupported E/M code {em}"}, f"Unsupported E/M code {em}")
        candidates.append([em])
        modifier_enabled = load_billing_rules().get("modifier_25_rule", {}).get("enabled", True)
        if add_on:
            candidates.append([f"{em}-25" if modifier_enabled else em, add_on])

    if standalone:
        candidates.append([standalone])

    if "psychiatric evaluation" in service:
        candidates.append(["90792"])

    if not candidates:
        return _result(data, [], {"error": "No supported CPT code from documented service"}, "No supported CPT code from documented service")

    try:
        ranked = sorted(candidates, key=lambda codes: _total(data.payer, codes), reverse=True)
        notes = _notes(data, candidates)
    except ValueError as exc:
        return _result(data, [], {"error": str(exc)}, str(exc))
    return _result(data, ranked[0], notes)


def _notes(data: BillingInput, candidates: list[list[str]]) -> dict:
    rows = []
    for codes in candidates:
        rows.append({"codes": codes, "payer": data.payer, "total": _total(data.payer, codes)})
    sorted_rows = sorted(rows, key=lambda row: row["total"], reverse=True)
    return {"candidates": sorted_rows, "recommended": sorted_rows[0] if sorted_rows else None}


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
        f"Patient Name: {patient_name}\n"
        f"Date of Service: {dos:%m/%d/%Y}\n"
        f"Service Name: {service_name}\n"
        f"ICD-10 Codes: {', '.join(icd10_codes)}\n"
        f"CPT Codes: {', '.join(cpt_codes)}\n"
        f"Length of Psychotherapy: {minutes} minutes"
    )


def psychiatric_evaluation_comparison(data: BillingInput) -> list[dict]:
    add_on = psychotherapy_code(data.psychotherapy_minutes, with_em=True)
    em = data.em_level or "99205"
    option_a = ["90792"]
    option_b = [f"{em}-25", add_on] if add_on else [em]
    rows: list[dict] = []
    for payer in APPROVED_PAYERS:
        try:
            a_total = _total(payer, option_a)
            b_total = _total(payer, option_b)
            diff = b_total - a_total
            recommendation = "Option B" if diff > 0 else "Option A"
            reason = "Higher reimbursement with documented E/M and psychotherapy add-on." if diff > 0 else "90792 is equal or higher for this payer."
        except ValueError as exc:
            a_total = b_total = diff = None
            recommendation = "Needs rate configuration"
            reason = str(exc)
        rows.append(
            {
                "payer": payer,
                "option_a_total": a_total,
                "option_b_total": b_total,
                "difference": diff,
                "option_a_codes": option_a,
                "option_b_codes": option_b,
                "recommendation": recommendation,
                "reason": reason,
            }
        )
    return rows
