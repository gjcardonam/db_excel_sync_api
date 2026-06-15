from app.validation.base import ValidationIssue


class ExcelValidationError(Exception):
    """Raised when an upload fails one or more blocking (ERROR) validations.

    Carries the structured issues so the API can return them and the UI can
    render them individually (in red).
    """

    def __init__(self, issues: list[ValidationIssue]):
        self.issues = list(issues)
        super().__init__("; ".join(i.message for i in self.issues) or "Validation failed")
