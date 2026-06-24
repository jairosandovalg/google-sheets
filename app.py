import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN DE LA INTERFAZ
# ==============================================================================
st.set_page_config(page_title="KPI Taller - Audi", layout="wide", initial_sidebar_state="expanded")
st.title("🚗 Sistema Inteligente de Incremento de Paso Vehicular")
st.markdown("---")

# ==============================================================================
# 1. CONEXIÓN CON GOOGLE SHEETS Y UNIÓN DE TABLAS (INNER JOIN)
# ==============================================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer la pestaña principal de Órdenes
    df_ordenes = conn.read(worksheet="Ordenes", ttl="5m")
    
    # Leer la segunda pestaña de Clientes
    df_clientes = conn.read(worksheet="Cliente", ttl="5m")
    
    # Realizar el INNER JOIN por la columna 'Placa'
    # Consolida ambas estructuras de datos y guarda el resultado en 'df'
    df = pd.merge(df_ordenes, df_clientes, on="Placa", how="inner")
    
    st.sidebar.success("📊 Tablas combinadas (Inner Join) en tiempo real")
except Exception as e:
    st.sidebar.error(f"Error de conexión o combinación: {e}")
    st.stop()

# ==============================================================================
# 2. FORMATEO Y LIMPIEZA DE DATOS
# ==============================================================================
df['Fec Factura'] = pd.to_datetime(df['Fec Factura'], errors='coerce')
df['Kil Real'] = pd.to_numeric(df['Kil Real'], errors='coerce')

# Filtro lateral por Local y Asesor
locales = df['Local'].dropna().unique()
local_seleccionado = st.sidebar.multiselect("Filtrar por Local", options=locales, default=locales)

asesores = df['Asesor'].dropna().unique()
asesor_seleccionado = st.sidebar.multiselect("Filtrar por Asesor", options=asesores, default=asesores)

# Aplicar filtros globales de la barra lateral
df_filtrado = df[df['Local'].isin(local_seleccionado) & df['Asesor'].isin(asesor_seleccionado)]

# ==============================================================================
# 3. PROCESAMIENTO: HISTÓRICO Y ALERTAS PREDICTIVAS
# ==============================================================================
df_mantenimientos = df_filtrado.copy()

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
    
    # Mantenimiento por vencer (Entre 300 y 359 días)
    clientes_por_vencer = df_ultima_visita[(df_ultima_visita['Dias Transcurridos'] >= 300) & (df_ultima_visita['Dias Transcurridos'] < 360)]
    
    # ----------------------------------------------------
    # NUEVA ESTRATEGIA: PREDICCIÓN POR KILOMETRAJE
    # ----------------------------------------------------
    df_historico_km = df_mantenimientos.sort_values(['Placa', 'Fec Factura'])
    df_historico_km['Fec Factura_Ant'] = df_historico_km.groupby('Placa')['Fec Factura'].shift(1)
    df_historico_km['Km_Ant'] = df_historico_km.groupby('Placa')['Kil Real'].shift(1)
    
    # Filtrar solo donde sí tengamos el registro anterior
    df_calculo_km = df_historico_km.dropna(subset=['Fec Factura_Ant', 'Km_Ant']).copy()
    df_calculo_km['Dias_Entre_Visitas'] = (df_calculo_km['Fec Factura'] - df_calculo_km['Fec Factura_Ant']).dt.days
    df_calculo_km['Km_Recorridos'] = df_calculo_km['Kil Real'] - df_calculo_km['Km_Ant']
    
    # Calcular Km diarios válidos
    df_calculo_km = df_calculo_km[df_calculo_km['Dias_Entre_Visitas'] > 0]
    df_calculo_km['Km_Diario'] = df_calculo_km['Km_Recorridos'] / df_calculo_km['Dias_Entre_Visitas']
    
    # Obtener el promedio de Km Diario por Placa
    df_km_promedio_placa = df_calculo_km.groupby('Placa')['Km_Diario'].mean().reset_index()
    
    # Cruzar el promedio diario con nuestra tabla de última visita
    df_predictive = pd.merge(df_ultima_visita, df_km_promedio_placa, on='Placa', how='left')
    df_predictive['Km_Diario'] = df_predictive['Km_Diario'].fillna(35) # Promedio estándar de la industria
    
    # Calcular estimaciones de Kilometraje actual
    df_predictive['Km_Actual_Estimado'] = df_predictive['Kil Real'] + (df_predictive['Km_Diario'] * df_predictive['Dias Transcurridos'])
    df_predictive['Km_Para_Siguiente_Mant'] = 10000 - (df_predictive['Km_Actual_Estimado'] % 10000)
    df_predictive['Dias_Para_Siguiente_Mant'] = df_predictive['Km_Para_Siguiente_Mant'] / df_predictive['Km_Diario']
    
    # Alertas por Kilometraje inminente (menos de 15 días)
    alertas_kilometraje = df_predictive[df_predictive['Dias_Para_Siguiente_Mant'] <= 15]

    # ==============================================================================
    # 4. RENDERIZADO DE CONTENEDORES EN STREAMLIT
    # ==============================================================================
    
    # Fila de Indicadores Superiores
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Unidades Únicas Filt.", len(df_ultima_visita))
    m2.metric("Alertas por Tiempo (+1 Año)", len(clientes_vencidos), delta_color="inverse")
    m3.metric("Beneficios por Vencer", len(clientes_por_vencer))
    m4.metric("Alertas por Km Predictivo", len(alertas_kilometraje))

    # Pestañas de Navegación del Call Center / Asesores
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔴 Recuperación (+1 Año)", 
        "🟡 Retención (Beneficios por Vencer)", 
        "🔮 Predictivo por Kilometraje",
        "🛠️ Recomendaciones de Inspección Anteriores"
    ])
    
    # Columnas universales a mostrar en las tablas
    columnas_mostrar = ['Placa', 'Nombre Cliente', 'Teléfono', 'Correo', 'Fec Factura', 'Dias Transcurridos', 'Asesor']
    
    with tab1:
        st.subheader("Clientes con Mantenimiento Vencido hace más de 1 año")
        # Validar la presencia de las columnas seleccionadas para evitar fallos de renderizado
        cols_tab1 = [c for c in columnas_mostrar if c in clientes_vencidos.columns]
        st.dataframe(clientes_vencidos[cols_tab1], use_container_width=True)
        
    with tab2:
        st.subheader("Clientes cerca del límite de días para perder Mantenimiento Gratuito")
        cols_tab2 = [c for c in columnas_mostrar if c in clientes_por_vencer.columns]
        st.dataframe(clientes_por_vencer[cols_tab2], use_container_width=True)
        
    with tab3:
        st.subheader("Clientes que ya alcanzaron el kilometraje ideal de su próximo servicio (Predicción)")
        st.write("Calculado con base en el ritmo de manejo individual de cada conductor:")
        columnas_pred = ['Placa', 'Nombre Cliente', 'Teléfono', 'Kil Real', 'Km_Actual_Estimado', 'Km_Diario', 'Dias_Para_Siguiente_Mant', 'Asesor']
        cols_tab3 = [c for c in columnas_pred if c in alertas_kilometraje.columns]
        st.dataframe(alertas_kilometraje[cols_tab3], use_container_width=True)

    with tab4:
        st.subheader("Oportunidad de Cross-Selling: Clientes con Notas / Recomendaciones")
        if 'Recomendaciones' in df_ultima_visita.columns:
            df_recomendaciones = df_ultima_visita[df_ultima_visita['Recomendaciones'].notna() & (df_ultima_visita['Recomendaciones'] != "")]
            if not df_recomendaciones.empty:
                columnas_rec = ['Placa', 'Nombre Cliente', 'Teléfono', 'Fec Factura', 'Recomendaciones', 'Asesor']
                cols_tab4 = [c for c in columnas_rec if c in df_recomendaciones.columns]
                st.dataframe(df_recomendaciones[cols_tab4], use_container_width=True)
            else:
                st.info("No hay recomendaciones registradas en las últimas visitas.")
        else:
            st.info("La columna 'Recomendaciones' no se encuentra disponible en las hojas.")

else:
    st.warning("No se encontraron registros de datos operativos con los filtros seleccionados.")
