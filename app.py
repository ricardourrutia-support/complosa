import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.datavalidation import DataValidation

st.set_page_config(page_title="Compensaciones y Contactabilidad", layout="wide")
st.title("📦 Compensaciones y Contactabilidad — Cabify Style")

# ------------------------------
# Funciones de Negocio y Compensación
# ------------------------------
def calcular_compensacion(minutos):
    if pd.isna(minutos):
        return 9000
    try:
        minutos = float(minutos)
    except:
        return 9000

    if minutos >= 50:
        return 9000
    elif minutos >= 40:
        return 6000
    elif minutos >= 35:
        return 3000
    else:
        return 0

# ------------------------------
# Función para arreglar fechas en Español
# ------------------------------
MESES_ES_EN = {
    'enero': 'january', 'febrero': 'february', 'marzo': 'march',
    'abril': 'april', 'mayo': 'may', 'junio': 'june',
    'julio': 'july', 'agosto': 'august', 'septiembre': 'september',
    'octubre': 'october', 'noviembre': 'november', 'diciembre': 'december'
}

def convertir_fecha_espanol(fecha_str):
    if pd.isna(fecha_str):
        return pd.NaT
    
    s = str(fecha_str).lower().strip()
    s = s.replace(' de ', ' ')
    
    for es, en in MESES_ES_EN.items():
        if es in s:
            s = s.replace(es, en)
            break
            
    try:
        return pd.to_datetime(s).date()
    except:
        return pd.NaT

# ------------------------------
# Funciones de Validación (Contactabilidad y Desempeño)
# ------------------------------
def es_email_contactable(email):
    if pd.isna(email): return False
    email = str(email).strip().lower()
    if email == "11@gmail.com": return False
    patron = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
    if not re.match(patron, email): return False
    parte_local = email.split('@')[0]
    if len(parte_local) < 2: return False
    return True

def es_email_cumplimiento(email):
    if pd.isna(email): return False
    email = str(email).strip().lower()
    if email == "11@gmail.com": return True
    return es_email_contactable(email)

def es_telefono_contactable(telefono):
    if pd.isna(telefono): return False
    telefono = str(telefono).strip().replace("+", "").replace(" ", "")
    if not telefono.isdigit(): return False
    if telefono == "111111111": return False
    if len(telefono) < 8 or len(telefono) > 15: return False
    if len(set(telefono)) == 1: return False
    return True

def es_telefono_cumplimiento(telefono):
    if pd.isna(telefono): return False
    telefono_limpio = str(telefono).strip().replace("+", "").replace(" ", "")
    if telefono_limpio == "111111111": return True
    return es_telefono_contactable(telefono)

# ------------------------------
# Subir archivo CSV
# ------------------------------
uploaded_file = st.file_uploader("📤 Sube tu archivo CSV", type=["csv"])

if uploaded_file is not None:

    try:
        df = pd.read_csv(uploaded_file, dtype=str, sep=';', on_bad_lines='skip')
        st.success("Archivo cargado correctamente 🎉 (Las filas con errores de formato fueron omitidas)")
    except Exception as e:
        st.error(f"❌ Error al leer el CSV: {e}")
        st.stop()

    columnas = [
        "Día de tm_start_local_at",
        "Segmento Tiempo en Losa",
        "End State",
        "id_reservation_id",
        "Service Channel",
        "Minutes Creation - Pickup",
        "User Fullname",
        "User Email",
        "User Phone Number",
        "Service Agent"
    ]

    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        st.error(f"❌ Faltan columnas requeridas en tu CSV: {faltantes}")
        st.stop()

    df = df[columnas].copy()

    # Convertir la fecha en texto español a fecha real
    df["Día de tm_start_local_at"] = df["Día de tm_start_local_at"].apply(convertir_fecha_espanol)

    if df["Día de tm_start_local_at"].isna().all():
        st.error("❌ No hay fechas válidas. Revisa el formato de la columna 'Día de tm_start_local_at'.")
        st.stop()

    # Filtro de fechas
    fecha_min = df["Día de tm_start_local_at"].min()
    fecha_max = df["Día de tm_start_local_at"].max()

    fecha_desde, fecha_hasta = st.date_input(
        "📅 Selecciona rango de fechas:",
        value=(fecha_min, fecha_max)
    )

    df = df[
        (df["Día de tm_start_local_at"] >= fecha_desde) &
        (df["Día de tm_start_local_at"] <= fecha_hasta)
    ]

    if df.empty:
        st.warning("⚠️ No hay registros en ese rango.")
        st.stop()

    # ------------------------------
    # ANALÍTICA DE AGENTES (Contactabilidad y Desempeño)
    # ------------------------------
    st.markdown("---")
    st.subheader("🕵️‍♂️ Analítica de Agentes: Contactabilidad vs Desempeño")
    st.write("**Desempeño:** % de veces que el agente ingresó un dato válido o el dato por defecto (111111111 / 11@gmail.com).")
    st.write("**Contactabilidad:** % de veces que obtuvimos un dato real al que podemos contactar.")
    
    df["Email Contactable"] = df["User Email"].apply(es_email_contactable)
    df["Email Cumplimiento"] = df["User Email"].apply(es_email_cumplimiento)
    df["Teléfono Contactable"] = df["User Phone Number"].apply(es_telefono_contactable)
    df["Teléfono Cumplimiento"] = df["User Phone Number"].apply(es_telefono_cumplimiento)
    
    resumen_agentes = df.groupby("Service Agent").agg(
        Total_Casos=("id_reservation_id", "count"),
        Desempeño_Email=("Email Cumplimiento", "sum"),
        Contactables_Email=("Email Contactable", "sum"),
        Desempeño_Tel=("Teléfono Cumplimiento", "sum"),
        Contactables_Tel=("Teléfono Contactable", "sum")
    ).reset_index()
    
    resumen_agentes["% Desempeño Email"] = (resumen_agentes["Desempeño_Email"] / resumen_agentes["Total_Casos"]) * 100
    resumen_agentes["% Contactabilidad Email"] = (resumen_agentes["Contactables_Email"] / resumen_agentes["Total_Casos"]) * 100
    resumen_agentes["% Desempeño Teléfono"] = (resumen_agentes["Desempeño_Tel"] / resumen_agentes["Total_Casos"]) * 100
    resumen_agentes["% Contactabilidad Teléfono"] = (resumen_agentes["Contactables_Tel"] / resumen_agentes["Total_Casos"]) * 100
    
    resumen_display = resumen_agentes.copy()
    for col in ["% Desempeño Email", "% Contactabilidad Email", "% Desempeño Teléfono", "% Contactabilidad Teléfono"]:
        resumen_display[col] = resumen_display[col].round(1).astype(str) + "%"
    
    st.dataframe(resumen_display, use_container_width=True)

    output_agentes = BytesIO()
    resumen_agentes.to_excel(output_agentes, index=False, engine='openpyxl')
    output_agentes.seek(0)
    
    st.download_button(
        "⬇️ Descargar Analítica de Agentes (Excel)",
        data=output_agentes,
        file_name="analitica_agentes_cabify.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.markdown("---")

    # ------------------------------
    # SECCIÓN DE COMPENSACIONES
    # ------------------------------
    df["Estado Pago"] = "No Pagado"
    df["Minutes Creation - Pickup"] = pd.to_numeric(df["Minutes Creation - Pickup"], errors="coerce")
    df["Monto a Reembolsar"] = df["Minutes Creation - Pickup"].apply(calcular_compensacion)

    df_compensaciones = df[df["Monto a Reembolsar"] > 0].copy()

    if df_compensaciones.empty:
        st.warning("⚠️ No hay compensaciones > 0 para mostrar en este rango.")
        st.stop()

    st.subheader("📊 Registros procesados para Compensación")
    
    cols_a_borrar = ["Email Contactable", "Email Cumplimiento", "Teléfono Contactable", "Teléfono Cumplimiento"]
    df_compensaciones = df_compensaciones.drop(columns=cols_a_borrar)
    
    st.dataframe(df_compensaciones, use_container_width=True)

    st.subheader("📈 Resumen de compensaciones")
    resumen = df_compensaciones["Monto a Reembolsar"].value_counts().sort_index()
    
    st.write("### 🧮 Cantidad de casos por monto:")
    for monto, cantidad in resumen.items():
        st.write(f"- **${monto:,}** → {cantidad} casos")

    st.write("### 💰 Total compensaciones:")
    st.write(f"- **Total de casos:** {len(df_compensaciones)}")
    st.write(f"- **Total en dinero:** ${df_compensaciones['Monto a Reembolsar'].sum():,}")

    # ------------------------------
    # CREAR EXCEL ESTILIZADO CABIFY PARA COMPENSACIONES
    # ------------------------------
    
    # 1. Preparar el DataFrame exactamente como lo pidieron
    columnas_excel = [
        "Día de tm_start_local_at", 
        "Segmento Tiempo en Losa", 
        "End State", 
        "id_reservation_id", 
        "Service Channel", 
        "Minutes Creation - Pickup", 
        "User Fullname", 
        "User Email", 
        "User Phone Number", 
        "Estado Pago", 
        "Monto a Reembolsar"
    ]
    df_excel = df_compensaciones[columnas_excel].copy()
    
    # Renombrar "Día" por "Day" solo para el Excel
    df_excel = df_excel.rename(columns={"Día de tm_start_local_at": "Day of tm_start_local_at"})

    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Compensaciones"

    header_fill = PatternFill("solid", fgColor="5B34AC")
    header_font = Font(color="FFFFFF", bold=True)
    border_side = Side(style="thin", color="362065")
    border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)

    color_no_pagado = PatternFill("solid", fgColor="EA8C2E")
    color_pagado = PatternFill("solid", fgColor="0C936B")

    fill_3000 = PatternFill("solid", fgColor="EFBD03")
    fill_6000 = PatternFill("solid", fgColor="EA8C2E")
    fill_9000 = PatternFill("solid", fgColor="E83C96")
    alt_fill = PatternFill("solid", fgColor="FAF8FE")

    # Escribir el DataFrame filtrado al Excel
    for r in dataframe_to_rows(df_excel, index=False, header=True):
        ws.append(r)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.auto_filter.ref = f"A1:{chr(64 + len(df_excel.columns))}1"

    # Estilos dinámicos basados en la nueva estructura de df_excel
    col_idx_estado = df_excel.columns.get_loc("Estado Pago")
    col_idx_monto = df_excel.columns.get_loc("Monto a Reembolsar")

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        idx = row[0].row

        if idx % 2 == 0:
            for cell in row:
                cell.fill = alt_fill

        estado = row[col_idx_estado].value
        if estado == "No Pagado":
            row[col_idx_estado].fill = color_no_pagado
        else:
            row[col_idx_estado].fill = color_pagado

        monto = float(row[col_idx_monto].value)
        if monto == 3000:
            row[col_idx_monto].fill = fill_3000
        elif monto == 6000:
            row[col_idx_monto].fill = fill_6000
        elif monto == 9000:
            row[col_idx_monto].fill = fill_9000

        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    dv = DataValidation(type="list", formula1='"Pagado,No Pagado"', allow_blank=False)
    col_estado_pago = col_idx_estado + 1
    col_letter = chr(64 + col_estado_pago)
    dv.add(f"{col_letter}2:{col_letter}1048576")
    ws.add_data_validation(dv)

    wb.save(output)
    output.seek(0)

    st.download_button(
        "⬇️ Descargar Excel Compensaciones",
        output,
        file_name="compensaciones_losa_cabify.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Sube un archivo CSV para comenzar.")
