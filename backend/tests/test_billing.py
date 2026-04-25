from datetime import date

from app.billing import BillingInput, psychotherapy_code, select_cpt_codes


def test_psychotherapy_minute_thresholds():
    assert psychotherapy_code(15, False) is None
    assert psychotherapy_code(16, False) == "90832"
    assert psychotherapy_code(38, False) == "90834"
    assert psychotherapy_code(53, False) == "90837"
    assert psychotherapy_code(53, True) == "90838"


def test_modifier_25_applied_for_em_plus_add_on():
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


def test_evaluation_ranks_em_add_on_above_90792_when_higher():
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
