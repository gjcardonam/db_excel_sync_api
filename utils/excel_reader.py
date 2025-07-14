
import pandas as pd

def read_excel(file, sheet_name):
    try:
        return pd.read_excel(file.file, sheet_name=sheet_name)
    except Exception as e:
        raise RuntimeError(f"Error al leer el archivo: {e}")
