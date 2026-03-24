import streamlit as st
import pandas as pd

st.set_page_config(page_title="Steel Design Tool - UNAM", layout="wide")

@st.cache_data
def load_data():
    # Cargamos el CSV saltando la fila de índices
    df = pd.read_csv("AISC Shapes Database v13 (Estructurada) (1).csv", skiprows=[0])
    df.columns = df.columns.str.strip()
    return df

df = load_data()

# --- Interfaz de Usuario ---
st.title("🏗️ Consultor de Perfiles Estructurales")
st.sidebar.header("Selección de Perfil")

perfil_sel = st.sidebar.selectbox(
    "Nombre del Perfil (AISC_MANUAL_LABEL):", 
    df['AISC_MANUAL_LABEL'].unique(),
    index=list(df['AISC_MANUAL_LABEL']).index('W10X49') if 'W10X49' in list(df['AISC_MANUAL_LABEL']) else 0
)

# Filtramos los datos del perfil seleccionado
d = df[df['AISC_MANUAL_LABEL'] == perfil_sel].iloc[0]

# --- Layout Principal (Siguiendo tu imagen) ---
st.header(f"Resultados para: {perfil_sel}")

# Fila 1: Geometría y Peso
st.subheader("📏 Geometría y Áreas")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Peralte (d)", f"{d['D']}\"")
c2.metric("Ancho Patín (bf)", f"{d['BF']}\"")
c3.metric("Espesor Alma (tw)", f"{d['TW']}\"")
c4.metric("Espesor Patín (tf)", f"{d['TF']}\"")
c5.metric("Área (A)", f"{d['A']} in²")

# Fila 2: Eje X y Eje Y
st.subheader("⚙️ Propiedades Mecánicas")
col_x, col_y = st.columns(2)

with col_x:
    st.info("**Eje Fuerte (X-X)**")
    cx1, cx2 = st.columns(2)
    cx1.write(f"**Ix:** {d['IX']} in⁴")
    cx1.write(f"**Sx:** {d['SX']} in³")
    cx2.write(f"**Rx:** {d['RX']} in")
    cx2.write(f"**Zx:** {d['ZX']} in³")

with col_y:
    st.info("**Eje Débil (Y-Y)**")
    cy1, cy2 = st.columns(2)
    cy1.write(f"**Iy:** {d['IY']} in⁴")
    cy1.write(f"**Sy:** {d['SY']} in³")
    cy2.write(f"**Ry:** {d['RY']} in")
    cy2.write(f"**Zy:** {d['ZY']} in³")

# Fila 3: Torsión y Relaciones de Esbeltez
st.subheader("🔄 Torsión y Relaciones Ancho-Espesor")
ct1, ct2, ct3, ct4 = st.columns(4)
ct1.metric("J (Torsión)", f"{d['J']} in⁴")
ct2.metric("Cw (Alabeo)", f"{d['CW']} in⁶")
ct3.metric("λf (bf/2tf)", d['BF_2TF'])
ct4.metric("λw (h/tw)", d['H_TW'])

st.divider()
st.caption(f"Peso Nominal (W): {d['W']} lb/ft | Fuente: AISC v13")1