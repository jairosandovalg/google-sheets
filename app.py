import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuración de la interfaz
st.set_page_config(page_title="KPI Taller - Audi", layout="wide", initial_sidebar_state="expanded")
st.title("🚗 Sistema Inteligente de Incremento de Paso Vehicular")
st.markdown("---")

# 1. Conexión con tu Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # ttl="5m" actualiza los datos de la hoja cada 5 minutos automáticamente
    df = conn.read(ttl="5m")
    st.sidebar.success("📊 Base de datos conectada en tiempo real")
except Exception as e:
    st.sidebar.error(f"Error de conexión: {e}")
    st.stop()

# 2. Formateo y Limpieza de Datos según tus columnas exactas
df['Fec Factura'] = pd.to_datetime(df['Fec Factura'], errors='coerce')
df['Kil Real'] = pd.to_numeric(df['Kil Real'], errors='coerce')

# Filtro lateral por Local y Asesor (aprovechando tus columnas)
locales = df['Local'].dropna().unique()
local_seleccionado = st.sidebar.multiselect("Filtrar por Local", options=locales, default=locales)

asesores = df['Asesor'].dropna().unique()
asesor_seleccionado = st.sidebar.multiselect("Filtrar por Asesor", options=asesores, default=asesores)

# Aplicar filtros globales de la barra lateral
df_filtrado = df[df['Local'].isin(local_seleccionado) & df['Asesor'].isin(asesor_seleccionado)]

# 3. Procesamiento: Obtener el ÚLTIMO histórico por vehículo (Igual al DAX corregido)
# Filtramos solo por Mantenimiento Periódico
df_mantenimientos = df_filtrado[df_filtrado['Tipo OT'] == "MANTENIMIENTO PERIODICO"].copy()

if not df_mantenimientos.empty:
    # Ordenamos por fecha y nos quedamos con el último registro por Placa
    df_ultima_visita = df_mantenimientos.sort_values('Fec Factura').groupby('Placa').last().reset_index()
    
    # Calcular días transcurridos desde la última factura hasta hoy
    hoy = datetime.now()
    df_ultima_visita['Dias Transcurridos'] = (hoy - df_ultima_visita['Fec Factura']).dt.days
    
    # ----------------------------------------------------
    # ESTRATEGIA 1 Y 2: ALERTAS POR TIEMPO (Vencidos y Por Vencer)
    # ----------------------------------------------------
    # Mantenimiento vencido (+1 año o 360 días)
    clientes_vencidos = df_ultima_visita[df_ultima_visita['Dias Transcurridos'] >= 360]
    
    # Mantenimiento por vencer (Beneficio gratuito de primeros años, ej: entre 300 y 359 días)
    clientes_por_vencer = df_ultima_visita[(df_ultima_visita['Dias Transcurridos'] >= 300) & (df_ultima_visita['Dias Transcurridos'] < 360)]
    
    # ----------------------------------------------------
    # NUEVA ESTRATEGIA: PREDICCIÓN POR KILOMETRAJE
    # ----------------------------------------------------
    # Para calcular el recorrido diario, necesitamos al menos 2 registros del mismo auto
    df_historico_km = df_mantenimientos.sort_values(['Placa', 'Fec Factura'])
    df_historico_km['Fec Factura_Ant'] = df_historico_km.groupby('Placa')['Fec Factura'].shift(1)
    df_historico_km['Km_Ant'] = df_historico_km.groupby('Placa')['Kil Real'].shift(1)
    
    # Filtrar solo donde sí tengamos el registro anterior
    df_calculo_km = df_historico_km.dropna(subset=['Fec Factura_Ant', 'Km_Ant']).copy()
    df_calculo_km['Dias_Entre_Visitas'] = (df_calculo_km['Fec Factura'] - df_calculo_km['Fec Factura_Ant']).dt.days
    df_calculo_km['Km_Recorridos'] = df_calculo_km['Kil Real'] - df_calculo_km['Km_Ant']
    
    # Calcular Km diarios (evitando divisiones por cero o negativos raros)
    df_calculo_km = df_calculo_km[df_calculo_km['Dias_Entre_Visitas'] > 0]
    df_calculo_km['Km_Diario'] = df_calculo_km['Km_Recorridos'] / df_calculo_km['Dias_Entre_Visitas']
    
    # Obtener el promedio de Km Diario por Placa
    df_km_promedio_placa = df_calculo_km.groupby('Placa')['Km_Diario'].mean().reset_index()
    
    # Cruzar el promedio diario con nuestra tabla de última visita
    df_predictivo = pd.merge(df_ultima_visita, df_km_promedio_placa, on='Placa', how='left')
    
    # Si no tiene suficiente historial, le asignamos un promedio estándar de la industria (ej. 35 Km al día)
    df_predictivo['Km_Diario'] = df_predictivo['Km_Diario'].fillna(35)
    
    # Calcular los kilómetros que ha recorrido desde su última visita en teoría
    df_predictivo['Km_Actual_Estimado'] = df_predictivo['Kil Real'] + (df_predictivo['Km_Diario'] * df_predictivo['Dias Transcurridos'])
    # Estimación de cuándo llegará a los siguientes 10,000 km
    df_predictivo['Km_Para_Siguiente_Mant'] = 10000 - (df_predictivo['Km_Actual_Estimado'] % 10000)
    df_predictivo['Dias_Para_Siguiente_Mant'] = df_predictivo['Km_Para_Siguiente_Mant'] / df_predictivo['Km_Diario']
    
    # Clientes que por Kilometraje ya les toca (les faltan menos de 15 días o ya se pasaron)
    alertas_kilometraje = df_predictivo[df_predictivo['Dias_Para_Siguiente_Mant'] <= 15]

    # ----------------------------------------------------
    # RENDERIZADO DE CONTENEDORES EN STREAMLIT
    # ----------------------------------------------------
    
    # Fila de Indicadores (Métricas superiores)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Unidades Únicas Filt.", len(df_ultima_visita))
    m2.metric("Alertas por Tiempo (+1 Año)", len(clientes_vencidos), delta_color="inverse")
    m3.metric("Beneficios por Vencer", len(clientes_por_vencer))
    m4.metric("Alertas por Km Predictivo", len(alertas_kilometraje))

    # Pestañas de Trabajo para el Call Center / Asesores
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔴 Recuperación (+1 Año)", 
        "🟡 Retención (Beneficios por Vencer)", 
        "🔮 Predictivo por Kilometraje",
        "🛠️ Recomendaciones de Inspección Anteriores"
    ])
    
    with tab1:
        st.subheader("Clientes con Mantenimiento Vencido hace más de 1 año")
        columnas_mostrar = ['Placa', 'Nombre Cliente', 'Contacto', 'Teléfono', 'Correo', 'Fec Factura', 'Dias Transcurridos', 'Asesor']
        st.dataframe(clientes_vencidos[columnas_mostrar], use_container_width=True)
        
    with tab2:
        st.subheader("Clientes cerca del límite de días para perder Mantenimiento Gratuito")
        st.dataframe(clientes_por_vencer[columnas_mostrar], use_container_width=True)
        
    with tab3:
        st.subheader("Clientes que ya alcanzaron el kilometraje ideal de su próximo servicio (Predicción)")
        st.write("Calculado en base al ritmo de manejo individual de cada conductor:")
        columnas_pred = ['Placa', 'Nombre Cliente', 'Teléfono', 'Kil Real', 'Km_Actual_Estimado', 'Km_Diario', 'Dias_Para_Siguiente_Mant', 'Asesor']
        st.dataframe(alertas_kilometraje[columnas_pred], use_container_width=True)

    with tab4:
        st.subheader("Oportunidad de Cross-Selling: Clientes con Notas / Recomendaciones")
        # Aprovechamos tu columna 'Recomendaciones' para buscar textos útiles
        df_recomendaciones = df_ultima_visita[df_ultima_visita['Recomendaciones'].notna() & (df_ultima_visita['Recomendaciones'] != "")]
        if not df_recomendaciones.empty:
            st.dataframe(df_recomendaciones[['Placa', 'Nombre Cliente', 'Teléfono', 'Fec Factura', 'Recomendaciones', 'Asesor']], use_container_width=True)
        else:
            st.info("No hay recomendaciones registradas en las últimas visitas.")

else:
    st.warning("No se encontraron registros con 'Tipo OT' igual a 'MANTENIMIENTO PERIODICO' en la base de datos.")
