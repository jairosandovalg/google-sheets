import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuración de la interfaz
st.set_page_config(page_title="KPI Taller - Audi", layout="wide", initial_sidebar_state="expanded")
st.title("🚗 Sistema Inteligente de Incremento de Paso Vehicular")
st.markdown("---")

# 1. Conexión con tu Google Sheets (Lectura de ambas pestañas)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer la pestaña principal de Órdenes
    df_ordenes = conn.read(worksheet="Ordenes", ttl="5m")
    
    # Leer la segunda pestaña de Clientes
    df_clientes = conn.read(worksheet="Cliente", ttl="5m")
    
    # Realizar el INNER JOIN por la columna 'Placa'
    # Esto solo mantendrá los registros de las órdenes cuyas placas existan en la pestaña de Clientes
    df = pd.merge(df_ordenes, df_clientes, on="Placa", how="inner")
    
    st.sidebar.success("📊 Tablas combinadas (Inner Join) en tiempo real")
except Exception as e:
    st.sidebar.error(f"Error de conexión o combinación: {e}")
    st.stop()

# 2. Formateo y Limpieza de Datos según tus columnas exactas
df['Fec Factura'] = pd.to_datetime(df['Fec Factura'], errors='coerce')
df['Kil Real'] = pd.to_numeric(df['Kil Real'], errors='coerce')

# ... El resto de tu código de filtros y procesamiento de estrategias se mantiene EXACTAMENTE IGUAL ...
# Ejemplo si solo quieres traer el DNI y la Dirección de la pestaña Cliente:
df_clientes_reducido = df_clientes[['Placa', 'DNI', 'Direccion']]
df = pd.merge(df_ordenes, df_clientes_reducido, on="Placa", how="inner")
