"""Lightweight upload-file checks (filename / extension), used by the endpoints
before the heavier content parsing in excel_reader (which also verifies the real
file signature)."""


def validate_xlsx_filename(filename: str | None) -> None:
    """Raise ValueError (-> HTTP 400) if the upload is not a named .xlsx file."""
    if not filename or not filename.strip():
        raise ValueError("No file was provided.")
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("File must be a .xlsx file.")
