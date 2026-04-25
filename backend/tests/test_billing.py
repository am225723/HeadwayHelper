from datetime import date

from app import billing
from app.billing import BillingInput, create_headway_block, psychiatric_evaluation_comparison, psychotherapy_code, select_cpt_codes


TEST_RATES = {
    payer: {"90792": 200, "99205": 260, "99214": 140, "90838": 170, "90836": 120, "90834": 110, "90837": 150}
    for payer in billing.APPROVED_PAYERS
}


def test_psychotherapy_minute_thresholds():
    assert psychotherapy_code(15, False) is None
    assert psychotherapy_code(16, False) == "90832"
    assert psychotherapy_code(38, False) == "90834"
    assert psychotherapy_code(53, False) == "90837"
    assert psychotherapy_code(53, True) == "90838"


def test_modifier_25_applied_for_em_plus_add_on(monkeypatch):
    monkeypatch.setattr(billing, "load_reimbursement_table", lambda: TEST_RATES)
    result = select_cpt_codes(
        BillingInput(
            patient_name="Jane Doe",
            date_of_service=date(2026, 4, 25),
            service_name="Follow-up",
            icd10_codes=["F41.1"],
            psychotherapy_minutes=45,
            em_level="99214",
            has_medical_decision_making=True,
        )
    )
    assert result.cpt_codes == ["99214-25", "90836"]
    assert "99214-25, 90836" in result.headway_block
    assert "Patient Name: Jane Doe\n" in result.headway_block


def test_evaluation_ranks_em_add_on_above_90792_when_higher(monkeypatch):
    monkeypatch.setattr(billing, "load_reimbursement_table", lambda: TEST_RATES)
    result = select_cpt_codes(
        BillingInput(
            patient_name="Jane Doe",
            date_of_service=date(2026, 4, 25),
            service_name="Psychiatric Evaluation",
            icd10_codes=["F90.2"],
            psychotherapy_minutes=60,
            em_level="99205",
            has_medical_decision_making=True,
            is_new_patient=True,
        )
    )
    assert result.cpt_codes == ["99205-25", "90838"]
    candidate_codes = [row["codes"] for row in result.reimbursement_notes["candidates"]]
    assert ["90792"] in candidate_codes
    assert result.reimbursement_notes["recommended"]["codes"] == ["99205-25", "90838"]


def test_exact_reimbursement_values_are_loaded_from_config(monkeypatch):
    monkeypatch.setattr(billing, "load_reimbursement_table", lambda: TEST_RATES)
    result = select_cpt_codes(
        BillingInput(
            patient_name="Jane Doe",
            date_of_service=date(2026, 4, 25),
            service_name="Psychiatric Evaluation",
            icd10_codes=["F90.2"],
            psychotherapy_minutes=60,
            em_level="99205",
            has_medical_decision_making=True,
            is_new_patient=True,
        )
    )
    assert result.reimbursement_notes["recommended"]["total"] == 430


def test_psych_eval_reimbursement_comparison(monkeypatch):
    monkeypatch.setattr(billing, "load_reimbursement_table", lambda: TEST_RATES)
    rows = psychiatric_evaluation_comparison(
        BillingInput(
            patient_name="Jane Doe",
            date_of_service=date(2026, 4, 25),
            service_name="Psychiatric Evaluation",
            icd10_codes=["F90.2"],
            psychotherapy_minutes=60,
            em_level="99205",
            has_medical_decision_making=True,
            is_new_patient=True,
        )
    )
    assert rows[0]["option_a_total"] == 200
    assert rows[0]["option_b_total"] == 430
    assert rows[0]["difference"] == 230
    assert rows[0]["recommendation"] == "Option B"


def test_one_line_per_field_headway_block():
    block = create_headway_block("Jane Doe", date(2026, 4, 25), "Follow-up", ["F41.1"], ["99214-25", "90836"], 45)
    assert block.splitlines() == [
        "Patient Name: Jane Doe",
        "Date of Service: 04/25/2026",
        "Service Name: Follow-up",
        "ICD-10 Codes: F41.1",
        "CPT Codes: 99214-25, 90836",
        "Length of Psychotherapy: 45 minutes",
    ]
