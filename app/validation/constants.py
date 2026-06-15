"""Column constants shared by the reader and the validation rules."""

# Sentinel value of the reference/template row that users must copy from and
# must NOT delete or alter.
COPIAFORMATO = "COPIAFORMATO"

REQUIRED_PUMP_COEFFICIENTS = [
    "x5", "x4", "x3", "x2", "x1", "x0",
    "x51", "x41", "x31", "x21", "x11", "x01",
]

PUMP2_COEFFICIENTS = [
    "x52x", "x42x", "x32x", "x22x", "x12x", "x02x",
    "x53x", "x43x", "x33x", "x23x", "x13x", "x03x",
]

# All numeric coefficient columns (used by the Excel reader for type coercion).
NUMERIC_COLS = REQUIRED_PUMP_COEFFICIENTS + PUMP2_COEFFICIENTS
