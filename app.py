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
# Funciones de Validación (Contactabilidad y Desempeño)
# ------------------------------
def es_email_contactable(email):
    if pd.isna(email): return False
    email = str(email).strip().lower()
    
    # Si es el correo por defecto de la instrucción, NO es contactable
    if email == "11@gmail.com": return False
        
    patron = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
    if not re.match(patron, email): return False
        
    parte_local = email.split('@')[0]
    if len(parte_local) < 2: return False
        
    return True

def es_email_cumplimiento(email):
    if pd.isna(email): return False
    email = str(email).strip().lower()
    # Cumple si es el correo por defecto (agente siguió la regla)
    if email == "11@gmail.com": return True
    # O si es un correo contactable válido
    return es_email_contactable(email)

def es_telefono_contactable(telefono):
    if pd.isna(telefono): return False
    telefono = str(telefono).strip().replace("+", "").replace(" ", "")
    
    if not telefono.isdigit(): return False
    # Si es el número por defecto de la instrucción, NO es contactable
    if telefono == "111111111": return False
        
    if len(telefono) < 8 or len(telefono) > 15: return False
    if len(set(telefono)) == 1: return False
        
    return True

def es_telefono_cumplimiento(telefono):
    if pd.isna(telefono): return False
    telefono_limpio = str(telefono).strip().replace("+", "").replace(" ", "")
    # Cumple si es el número por defecto (agente siguió la regla)
    if telefono_limpio == "111111111": return True
    # O si es un teléfono contactable válido
    return es_telefono_contactable(telefono)

# ------------------------------
# Subir archivo CSV
# ------------------------------
uploaded_file = st.file_uploader("📤 Sube tu archivo CSV", type=["csv"])

if uploaded_file is not None:

    try:
        # CORRECCIÓN APLICADA: on_bad_lines='skip' ignora las filas con errores de formato
        df = pd.read_csv(uploaded_file, dtype=str, sep=';', on_bad_lines='skip')
        st.success("Archivo cargado correctamente 🎉 (Las filas con errores de formato fueron omitidas)")
    except Exception as e:
        st.error(f"❌ Error al leer el CSV: {e}")
        st.stop()

    columnas = [
        "Day of tm_start_local_at",
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

    # Convertir fecha
    df["Day of tm_start_local_at"] = pd.to_datetime(
        df["Day of tm_start_local_at"], errors="coerce"
    ).dt.date

    if df["Day of tm_start_local_at"].isna().all():
        st.error("❌ No hay fechas válidas.")
        st.stop()

    # Filtro de fechas
    fecha_min = df["Day of tm_start_local_at"].min()
    fecha_max = df["Day of tm_start_local_at"].max()

    fecha_desde, fecha_hasta = st.date_input(
        "📅 Selecciona rango de fechas:",
        value=(fecha_min, fecha_max)
    )

    df = df[
        (df["Day of tm_start_local_at"] >= fecha_desde) &
        (df["Day of tm_start_local_at"] <= fecha_hasta)
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
    
    # Aplicar validaciones
    df["Email Contactable"] = df["User Email"].apply(es_email_contactable)
    df["Email Cumplimiento"] = df["User Email"].apply(es_email_cumplimiento)
    df["Teléfono Contactable"] = df["User Phone Number"].apply(es_telefono_contactable)
    df["Teléfono Cumplimiento"] = df["User Phone Number"].apply(es_telefono_cumplimiento)
    
    # Agrupar datos por agente
    resumen_agentes = df.groupby("Service Agent").agg(
        Total_Casos=("id_reservation_id", "count"),
        Desempeño_Email=("Email Cumplimiento", "sum"),
        Contactables_Email=("Email Contactable", "sum"),
        Desempeño_Tel=("Teléfono Cumplimiento", "sum"),
        Contactables_Tel=("Teléfono Contactable", "sum")
    ).reset_index()
    
    # Calcular porcentajes
    resumen_agentes["% Desempeño Email"] = (resumen_agentes["Desempeño_Email"] / resumen_agentes["Total_Casos"]) * 100
    resumen_agentes["% Contactabilidad Email"] = (resumen_agentes["Contactables_Email"] / resumen_agentes["Total_Casos"]) * 100
    resumen_agentes["% Desempeño Teléfono"] = (resumen_agentes["Desempeño_Tel"] / resumen_agentes["Total_Casos"]) * 100
    resumen_agentes["% Contactabilidad Teléfono"] = (resumen_agentes["Contactables_Tel"] / resumen_agentes["Total_Casos"]) * 100
    
    # Crear una copia para visualizar bonito en Streamlit
    resumen_display = resumen_agentes.copy()
    for col in ["% Desempeño Email", "% Contactabilidad Email", "% Desempeño Teléfono", "% Contactabilidad Teléfono"]:
        resumen_display[col] = resumen_display[col].round(1).astype(str) + "%"
    
    # Mostrar tabla de agentes
    st.dataframe(resumen_display, use_container_width=True)

    # Botón de descarga para las analíticas de los agentes
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

    # Filtrar solo los que aplican para compensación
    df_compensaciones = df[df["Monto a Reembolsar"] > 0].copy()

    if df_compensaciones.empty:
        st.warning("⚠️ No hay compensaciones > 0 para mostrar en este rango.")
        st.stop()

    st.subheader("📊 Registros procesados para Compensación")
    
    # Limpiar columnas de validación que ya no necesitamos ver
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

    for r in dataframe_to_rows(df_compensaciones, index=False, header=True):
        ws.append(r)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.auto_filter.ref = f"A1:{chr(64 + len(df_compensaciones.columns))}1"

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        idx = row[0].row

        if idx % 2 == 0:
            for cell in row:
                cell.fill = alt_fill

        estado = row[df_compensaciones.columns.get_loc("Estado Pago")].value
        if estado == "No Pagado":
            row[df_compensaciones.columns.get_loc("Estado Pago")].fill = color_no_pagado
        else:
            row[df_compensaciones.columns.get_loc("Estado Pago")].fill = color_pagado

        monto = float(row[df_compensaciones.columns.get_loc("Monto a Reembolsar")].value)
        if monto == 3000:
            row[df_compensaciones.columns.get_loc("Monto a Reembolsar")].fill = fill_3000
        elif monto == 6000:
            row[df_compensaciones.columns.get_loc("Monto a Reembolsar")].fill = fill_6000
        elif monto == 9000:
            row[df_compensaciones.columns.get_loc("Monto a Reembolsar")].fill = fill_9000

        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    dv = DataValidation(type="list", formula1='"Pagado,No Pagado"', allow_blank=False)
    col_estado_pago = df_compensaciones.columns.get_loc("Estado Pago") + 1
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
