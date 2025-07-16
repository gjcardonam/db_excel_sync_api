from app.utils.excel_reader import read_excel
from app.core.config import load_db_config
from app.core.database import create_pg_engine
from sqlalchemy import text, inspect
from datetime import datetime
import pandas as pd

def obtener_columnas(engine, schema, tabla):
    inspector = inspect(engine)
    return [c['name'] for c in inspector.get_columns(tabla, schema=schema)]

def actualizar_tabla(engine, df, schema, tabla, clave):
    if df.empty:
        return "DataFrame vacío. No se actualizó nada."

    columnas_tabla = obtener_columnas(engine, schema, tabla)
    comunes = [c for c in df.columns if c in columnas_tabla]
    if not comunes:
        return "Sin columnas comunes entre DataFrame y tabla."

    df = df[comunes]
    valores_clave = df[clave].unique().tolist()

    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {schema}.{tabla} WHERE {clave} = ANY(:vals)"),
            {"vals": valores_clave}
        )
        df.to_sql(tabla, con=conn, schema=schema, if_exists="append", index=False)

    return f"Tabla {tabla} actualizada con {len(df)} registros."

def actualizar_welltest(engine, df, schema, tabla="welltest"):
    if df.empty or "well" not in df.columns:
        return "Faltan columnas necesarias."

    if 'running' not in df.columns:
        if 'INSTALL DATE' in df.columns:
            df.rename(columns={'INSTALL DATE': 'running'}, inplace=True)
            print("Se ha renombrado la columna 'INSTALL DATE' a 'running'.")
        else:
            print("El DataFrame debe contener la columna 'running' o 'INSTALL DATE'.")
            return "Columna 'running' o 'INSTALL DATE' no encontrada."

    df["running"] = pd.to_datetime(df["running"], errors="coerce")
    hoy = datetime.now()

    with engine.begin() as conn:
        for _, row in df.iterrows():
            if pd.isnull(row["running"]):
                continue
            conn.execute(
                text(f"""
                    UPDATE {schema}.{tabla}
                    SET process = 'x'
                    WHERE well = :well
                    AND time_stamp > :start AND time_stamp <= :end
                """),
                {"well": row["well"], "start": row["running"], "end": hoy}
            )

    return "Tabla welltest actualizada."


def process_excel_and_update_db(file, empresa, produccion):
    config = load_db_config(empresa)
    engine = create_pg_engine(config)
    schema = config["schema"]

    hoja = {"ESP": "ESP", "GL": "GAS LIFT"}[produccion]
    tabla = {"ESP": "dbesp", "GL": "dbgl"}[produccion]

    df = read_excel(file, hoja)
    df = df[df['well'] != 'COPIAFORMATO']

    if produccion == "ESP":
        df['gassepef'] = 90
        df['wearfactor1'] = 1

    resultado1 = actualizar_tabla(engine, df, schema, tabla, "well")
    resultado2 = actualizar_welltest(engine, df, schema)

    return f"{resultado1} | {resultado2}"
