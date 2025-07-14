
from utils.excel_reader import read_excel
from config import load_db_config
from database import create_pg_engine
import pandas as pd
from sqlalchemy import text, inspect
from datetime import datetime

JSON_CONFIG_PATH = "CONFIG/db_connections.json"
EMPRESA = "Permian"
PRODUCCION = "ESP"

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
        delete_q = text(f"DELETE FROM {schema}.{tabla} WHERE {clave} = ANY(:vals)")
        conn.execute(delete_q, {"vals": valores_clave})
        df.to_sql(tabla, conn, schema=schema, if_exists="append", index=False)

    return f"Tabla {tabla} actualizada con {len(df)} registros."

def actualizar_welltest(engine, df, schema, tabla="welltest"):
    if df.empty or "well" not in df.columns or "INSTALL DATE" not in df.columns:
        return "Faltan columnas necesarias."

    df = df.rename(columns={"INSTALL DATE": "running"})
    df["running"] = pd.to_datetime(df["running"], errors="coerce")
    hoy = datetime.now()

    with engine.begin() as conn:
        for _, row in df.iterrows():
            if pd.isnull(row["running"]): continue
            q = text(f"""
                UPDATE {schema}.{tabla}
                SET process = 'x'
                WHERE well = :well AND time_stamp > :start AND time_stamp <= :end
            """)
            conn.execute(q, {"well": row["well"], "start": row["running"], "end": hoy})

    return "Tabla welltest actualizada."

def process_excel_and_update_db(file):
    config = load_db_config(JSON_CONFIG_PATH, EMPRESA)
    engine = create_pg_engine(config)
    schema = config["schema"]

    if PRODUCCION == "ESP":
        db_df = read_excel(file, "ESP")
        motor_df = read_excel(file, "MOTORS")
        db_df['gassepef'] = 90
        db_df['wearfactor1'] = 1
        db_df = db_df[db_df['well'] != 'COPIAFORMATO']
        motor_df['company'] = EMPRESA
        motor_df = motor_df[motor_df['wellname'] != 'COPIAFORMATO']
        r1 = actualizar_tabla(engine, motor_df, schema, "wells_motors", "wellname")
        r2 = actualizar_tabla(engine, db_df, schema, "dbesp", "well")
        r3 = actualizar_welltest(engine, db_df, schema)
        return f"{r1} | {r2} | {r3}"

    raise ValueError("Producción no soportada.")
