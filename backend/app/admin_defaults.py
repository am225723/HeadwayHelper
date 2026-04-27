from pathlib import Path
from sqlalchemy.orm import Session

from .billing import ALLOWED_CPT_CODES, APPROVED_PAYERS
from .models import AppSetting, BillingRule, ClassificationRule, DocumentTemplate, ReimbursementRate, ServiceType, User
from .auth import hash_password
from .config import get_settings
from .templates import extract_placeholder_inventory


DEFAULT_SERVICE_TYPES = ["Psychiatric Evaluation", "Psychotherapy", "Medication Management", "Follow-up", "Crisis"]
DEFAULT_CLASSIFICATION_RULES = [
    ("INTAKE", "intake"),
    ("INTAKE", "headway intake"),
    ("ASSESSMENT", "asrs"),
    ("ASSESSMENT", "phq9"),
    ("ASSESSMENT", "phq-9"),
    ("ASSESSMENT", "gad7"),
    ("ZOOM_NOTE", r"^\d{6}-zoomn?note\.pdf$"),
]
DEFAULT_BILLING_RULES = {
    "allowed_cpt_codes": {"codes": sorted(ALLOWED_CPT_CODES)},
    "modifier_25_rule": {"enabled": True, "apply_to_em_with_psychotherapy_add_on": True},
    "psychotherapy_minute_thresholds": {"30": [16, 37], "45": [38, 52], "60": [53, None]},
    "evaluation_comparison": {"enabled": True, "include_90792": True, "default_strategy": "highest_reimbursing_valid"},
}
DEFAULT_APP_SETTINGS = {
    "default_payer": {"payer": "Aetna"},
    "workflow_defaults": {"summary_auto_save_pdf": True, "session_note_default_mode": "draft", "treatment_plan_default_mode": "draft", "review_required": True},
    "drive_scan_interval": {"seconds": 300},
    "enable_safer_preview_flow": {"enabled": True},
}
DEFAULT_TEMPLATES = [
    ("SUMMARY", "Clinical Summary", "Clinical_Summary_Template.html", "dollar", {"remove_not_documented_lines": False, "strip_instruction_blocks": True}),
    ("SESSION_NOTE", "Session Note", "Session_Notes_Template.html", "mustache", {"remove_not_documented_lines": True, "strip_instruction_blocks": True}),
    ("TREATMENT_PLAN", "Treatment Plan", "Clinical_Treatment_Plan.html", "mustache", {"remove_not_documented_lines": True, "strip_instruction_blocks": True}),
]


def seed_admin_defaults(db: Session) -> None:
    settings = get_settings()
    if not db.query(ServiceType).first():
        for index, name in enumerate(DEFAULT_SERVICE_TYPES):
            db.add(ServiceType(name=name, display_order=index))
    if not db.query(ClassificationRule).first():
        for category, keyword in DEFAULT_CLASSIFICATION_RULES:
            db.add(ClassificationRule(category=category, keyword_or_pattern=keyword))
    if not db.query(BillingRule).first():
        for key, value in DEFAULT_BILLING_RULES.items():
            db.add(BillingRule(rule_key=key, rule_value_json=value, description=f"Default {key.replace('_', ' ')}"))
    if not db.query(AppSetting).first():
        for key, value in DEFAULT_APP_SETTINGS.items():
            db.add(AppSetting(setting_key=key, setting_value_json=value, description=f"Default {key.replace('_', ' ')}"))
    template_dir = Path(__file__).parent / "templates"
    if not db.query(DocumentTemplate).first():
        for doc_type, name, filename, style, cleanup in DEFAULT_TEMPLATES:
            db.add(
                DocumentTemplate(
                    document_type=doc_type,
                    template_name=name,
                    template_source=(template_dir / filename).read_text(errors="ignore"),
                    placeholder_style=style,
                    cleanup_rules_json=cleanup,
                    is_active=True,
                )
            )
    else:
        for doc_type, name, filename, style, cleanup in DEFAULT_TEMPLATES:
            active = db.query(DocumentTemplate).filter(DocumentTemplate.document_type == doc_type, DocumentTemplate.is_active.is_(True)).order_by(DocumentTemplate.updated_at.desc()).first()
            bundled_source = (template_dir / filename).read_text(errors="ignore")
            bundled_inventory = extract_placeholder_inventory(bundled_source)
            active_inventory = extract_placeholder_inventory(active.template_source) if active else []
            needs_backfill = not active or _template_inventory_is_underpowered(doc_type, active_inventory, bundled_inventory)
            if not needs_backfill:
                continue
            db.query(DocumentTemplate).filter(DocumentTemplate.document_type == doc_type, DocumentTemplate.is_active.is_(True)).update({"is_active": False})
            db.add(
                DocumentTemplate(
                    document_type=doc_type,
                    template_name=f"{name} Bundled Default",
                    template_source=bundled_source,
                    placeholder_style="mixed",
                    cleanup_rules_json=cleanup,
                    is_active=True,
                    version=(active.version + 1 if active and active.version else 1),
                )
            )
    if not db.query(ReimbursementRate).first():
        for payer in APPROVED_PAYERS:
            for code in sorted(ALLOWED_CPT_CODES):
                db.add(ReimbursementRate(payer_name=payer, cpt_code=code, amount=0, is_active=False, notes="Set exact contracted reimbursement before production use."))
    db.commit()


def _template_inventory_is_underpowered(doc_type: str, active_inventory: list, bundled_inventory: list) -> bool:
    if not bundled_inventory:
        return False
    active_prompt_count = len([item for item in active_inventory if item.placeholder_type == "ai_prompt"])
    bundled_prompt_count = len([item for item in bundled_inventory if item.placeholder_type == "ai_prompt"])
    if doc_type == "TREATMENT_PLAN":
        return len(active_inventory) < 20 or active_prompt_count < max(10, bundled_prompt_count // 2) or bundled_prompt_count > active_prompt_count
    if doc_type == "SUMMARY":
        return len(active_inventory) < 15 or len(bundled_inventory) > len(active_inventory)
    return len(active_inventory) == 0


def seed_bootstrap_admin(db: Session) -> User | None:
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        return None
    user = db.query(User).filter(User.email == settings.admin_email).first()
    if user:
        return user
    user = User(email=settings.admin_email, password_hash=hash_password(settings.admin_password), full_name=settings.admin_full_name, role="ADMIN", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
