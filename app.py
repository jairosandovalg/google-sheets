import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Control de Taller - Audi", layout="wide")
st.title("📊 Panel de Incremento de Paso Vehicular")

# 1. Conexión nativa con Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Lee los datos mapeando directamente la URL de tus secrets
    df = conn.read(ttl="10m") # Se actualiza la caché cada 10 minutos
    st.success("Conexión exitosa con Google Sheets: 'Ordenes Trabajo'")
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# 2. Limpieza y preparación de datos iniciales
# Asegúrate de cambiar los nombres de columnas si en tu Excel varían las mayúsculas/minúsculas
df['Fec Factura'] = pd.to_datetime(df['Fec Factura'], errors='coerce')
df['Kilometraje'] = pd.to_numeric(df['Kilometraje'], errors='coerce')

# Mostrar vista previa de los datos recolectados
with st.expander("👀 Ver Datos en Bruto de Google Sheets"):
    st.dataframe(df.head(10))

# 3. Lógica Analítica de Negocio (Ejemplo: Clientes por única vez - Última Visita)
st.subheader("📈 Estrategia 1: Próximos Mantenimientos Predictivos")

# Filtrar solo mantenimientos periódicos como en tu consulta DAX
df_mantenimientos = df[df['Tipo OT'] == 'MANTENIMIENTO PERIODICO'].copy()

if not df_mantenimientos.empty:
    # Obtener la última visita por Placa (Equivalente al TOPN 1 DESC que corregimos)
    df_ultima_visita = df_mantenimientos.sort_values('Fec Factura').groupby('Placa').last().reset_index()
    
    # Calcular días transcurridos desde su última visita hasta hoy
    hoy = datetime.now()
    df_ultima_visita['Dias Desde Ultima OT'] = (hoy - df_ultima_visita['Fec Factura']).dt.days
    
    # Segmentación básica para alertas
    # Clientes con mantenimientos vencidos hace más de 360 días
    clientes_vencidos = df_ultima_visita[df_ultima_visita['Dias Desde Ultima OT'] >= 360]
    
    # Clientes próximos a vencer (Beneficio gratuito de los primeros años, ej: entre 300 y 355 días)
    clientes_por_vencer = df_ultima_visita[(df_ultima_visita['Dias Desde Ultima OT'] >= 300) & (df_ultima_visita['Dias Desde Ultima OT'] < 360)]

    # Métricas clave en pantalla
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Vehículos Únicos", len(df_ultima_visita))
    col2.metric("Alertas: Mantenimiento Vencido (+1 Año)", len(clientes_vencidos), delta_color="inverse")
    col3.metric("Por Vencer (Mantenimiento Gratuito)", len(clientes_por_vencer))

    # Pestañas visuales para el equipo del taller
    tab1, tab2 = st.tabs(["🔴 Clientes Vencidos para Reactivación", "🟡 Clientes por Vencer (Seguimiento Beneficio)"])
    
    with tab1:
        st.write("Estos clientes tienen más de un año sin ingresar. Ofréceles un descuento estacional o check-up gratuito.")
        st.dataframe(clientes_vencidos[['Placa', 'Nombre Cliente', 'Contacto', 'Correo', 'Teléfono', 'Fec Factura', 'Dias Desde Ultima OT']])
        
    with tab2:
        st.write("Recordarles que si no ingresan a la concesionaria pronto, perderán sus beneficios de mantenimiento gratuito.")
        st.dataframe(clientes_por_vencer[['Placa', 'Nombre Cliente', 'Contacto', 'Correo', 'Teléfono', 'Fec Factura', 'Dias Desde Ultima OT']])
else:
    st.warning("No se encontraron registros con el Tipo OT = 'MANTENIMIENTO PERIODICO'")
