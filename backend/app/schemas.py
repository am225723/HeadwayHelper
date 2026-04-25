from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = Field(pattern="^(ADMIN|PROVIDER)$")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PatientCreate(BaseModel):
    name: str = Field(min_length=1)
    drive_folder_id: str = Field(min_length=1)


class SourceDocumentOut(BaseModel):
    id: str
    patient_id: str
    drive_file_id: str
    name: str
    file_type: str
    uploaded_at: datetime
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OutputDocumentOut(BaseModel):
    id: str
    patient_id: str
    doc_type: str
    drive_file_id: str | None
    summary_id: str | None
    session_note_id: str | None
    source_document_id: str | None
    content: str
    structured_data: dict | None
    created_at: datetime
    status: str
    error_message: str | None

    model_config = {"from_attributes": True}


class BillingSummaryOut(BaseModel):
    id: str
    output_document_id: str
    patient_name: str
    date_of_service: date
    service_name: str
    icd10_codes: str
    cpt_codes: str
    psychotherapy_minutes: int
    headway_block: str
    reimbursement_notes: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientDetail(BaseModel):
    id: str
    name: str
    drive_folder_id: str
    created_at: datetime
    updated_at: datetime
    source_documents: list[SourceDocumentOut] = Field(default_factory=list)
    output_documents: list[OutputDocumentOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PatientList(BaseModel):
    items: list[PatientDetail]
    page: int
    size: int
    total: int


class SourceDocumentsResponse(BaseModel):
    patient_id: str
    grouped: dict[str, list[SourceDocumentOut]]


class GenerateSummaryRequest(BaseModel):
    save_pdf: bool = False


class GenerateSessionNoteRequest(BaseModel):
    source_document_id: str
    save_pdf: bool = False


class GenerateTreatmentPlanRequest(BaseModel):
    save_pdf: bool = False


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    output_document_id: str | None = None


class BillingRecalculateRequest(BaseModel):
    output_document_id: str


class ReviewRequest(BaseModel):
    status: str = Field(pattern="^(APPROVED|REJECTED)$")
    comments: str | None = None


class ReviewItem(BaseModel):
    output_id: str
    patient_id: str
    patient_name: str
    doc_type: str
    status: str
    created_at: datetime


class DriveFileIn(BaseModel):
    id: str
    name: str
    mime_type: str | None = None
    modified_time: datetime | None = None


class LocalResyncRequest(BaseModel):
    files: list[DriveFileIn] = Field(default_factory=list)


class ClassificationUpdate(BaseModel):
    file_type: str = Field(pattern="^(INTAKE|ASSESSMENT|ZOOM_NOTE|UNKNOWN)$")


class BillingComparisonResponse(BaseModel):
    payer: str
    option_a_total: float | None
    option_b_total: float | None
    difference: float | None
    option_a_codes: list[str]
    option_b_codes: list[str]
    recommendation: str
    reason: str


class AdminBaseModel(BaseModel):
    model_config = {"from_attributes": True}


class ReimbursementRateIn(BaseModel):
    payer_name: str
    cpt_code: str
    amount: float
    is_active: bool = True
    notes: str | None = None


class ReimbursementRateOut(ReimbursementRateIn, AdminBaseModel):
    id: str
    created_at: datetime
    updated_at: datetime


class BillingRuleIn(BaseModel):
    rule_value_json: dict
    description: str | None = None


class BillingRuleOut(BillingRuleIn, AdminBaseModel):
    id: str
    rule_key: str
    updated_at: datetime


class ServiceTypeIn(BaseModel):
    name: str
    is_active: bool = True
    display_order: int = 0


class ServiceTypeOut(ServiceTypeIn, AdminBaseModel):
    id: str
    created_at: datetime
    updated_at: datetime


class ClassificationRuleIn(BaseModel):
    category: str = Field(pattern="^(INTAKE|ASSESSMENT|ZOOM_NOTE|UNKNOWN)$")
    keyword_or_pattern: str
    is_active: bool = True


class ClassificationRuleOut(ClassificationRuleIn, AdminBaseModel):
    id: str
    created_at: datetime
    updated_at: datetime


class AppSettingIn(BaseModel):
    setting_value_json: dict
    description: str | None = None


class AppSettingOut(AppSettingIn, AdminBaseModel):
    id: str
    setting_key: str
    updated_at: datetime


class DocumentTemplateIn(BaseModel):
    document_type: str
    template_name: str
    template_source: str
    placeholder_style: str = "mixed"
    cleanup_rules_json: dict = Field(default_factory=dict)
    is_active: bool = True


class DocumentTemplateOut(DocumentTemplateIn, AdminBaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    placeholders: list[str] = Field(default_factory=list)


class TemplatePreviewRequest(BaseModel):
    values: dict = Field(default_factory=dict)


class TemplatePreviewResponse(BaseModel):
    html: str
    placeholders: list[str]
