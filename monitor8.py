import streamlit as st
from datetime import datetime
from PIL import Image
import os
import base64
from io import BytesIO

def initialize_session_state():
    """Inicializa el estado de la sesión con los servicios y personal"""
    if 'servicios' not in st.session_state:
        st.session_state.servicios = {
            "Urgencias": [
                {"nombre": "Ana López", "rol": "especialista", "color": "#ff5252"},
                {"nombre": "Carlos Ruiz", "rol": "general-a", "color": "#4caf50"},
                {"nombre": "María González", "rol": "general-b", "color": "#2196f3"}
            ],
            "Quirófano": [
                {"nombre": "Pedro Sánchez", "rol": "especialista", "color": "#ff5252"},
                {"nombre": "Lucía Martín", "rol": "general-a", "color": "#4caf50"}
            ],
            "Pediatría": [
                {"nombre": "Sofía Pérez", "rol": "especialista", "color": "#ff5252"},
                {"nombre": "Javier Díaz", "rol": "general-c", "color": "#9c27b0"}
            ],
            "UCI": [
                {"nombre": "Elena Castro", "rol": "especialista", "color": "#ff5252"}
            ],
            "Planta": [
                {"nombre": "Miguel Ángel Flores", "rol": "general-b", "color": "#2196f3"},
                {"nombre": "Rosa Jiménez", "rol": "general-a", "color": "#4caf50"},
                {"nombre": "David Torres", "rol": "camillero", "color": "#ff9800"}
            ]
        }

    if 'seleccion' not in st.session_state:
        st.session_state.seleccion = {"nombre": None, "servicio": None}
        
    if 'log_movimientos' not in st.session_state:
        st.session_state.log_movimientos = []

def setup_page_config():
    """Configura la página de Streamlit"""
    st.set_page_config(layout="wide", page_title="Supervisión de Enfermería por Turno")

def load_custom_styles():
    """Carga los estilos CSS personalizados"""
    st.markdown("""
        <style>
        .header-container {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }
        .logo-img {
            max-height: 80px;
        }
        .servicio-container {
            border: 2px solid #4a8cff;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            background-color: #f8fbff;
        }
        .servicio-header {
            font-size: 1.3em;
            font-weight: bold;
            color: #2c5fd1;
            margin-bottom: 15px;
            text-align: center;
        }
        .profesional-container {
            display: flex;
            align-items: center;
            padding: 10px;
            margin: 5px 0;
            background-color: white;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        .profesional-container:hover {
            background-color: #f0f6ff;
        }
        .selected {
            background-color: #fff8e1 !important;
            border: 2px solid #ffd54f !important;
        }
        .role-badge {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-left: auto;
        }
        .profesional-name {
            flex-grow: 1;
        }
        .historial-item {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 10px;
            border-left: 4px solid #4a8cff;
            font-size: 0.85em;
        }
        .leyenda-horizontal {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 15px;
            justify-content: center;
            padding: 10px;
            background-color: #f0f8ff;
            border-radius: 5px;
        }
        .leyenda-item {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.85em;
            white-space: nowrap;
        }
        .sumario-cambios {
            margin-top: 30px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #4a8cff;
        }
        .seleccionado-box {
            background-color: #fff8e1;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        </style>
    """, unsafe_allow_html=True)

def image_to_base64(image):
    """Convierte una imagen a base64"""
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def show_logo():
    """Muestra el logo en la parte superior"""
    logo_path = "escudo_COLOR.jpg"
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path)
            st.markdown(
                """
                <div class="header-container">
                    <img src="data:image/png;base64,{}" class="logo-img">
                </div>
                """.format(image_to_base64(logo)),
                unsafe_allow_html=True
            )
        except Exception as e:
            st.markdown('<div class="header-container"><h2>Supervisión de Enfermería por Turno</h2></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="header-container"><h2>Supervisión de Enfermería por Turno</h2></div>', unsafe_allow_html=True)

def mover_personal(servicio_destino):
    """Mueve el personal seleccionado al servicio destino"""
    origen = st.session_state.seleccion["servicio"]
    nombre = st.session_state.seleccion["nombre"]
    
    if origen and servicio_destino != origen:
        for idx, p in enumerate(st.session_state.servicios[origen]):
            if p["nombre"] == nombre:
                profesional = st.session_state.servicios[origen].pop(idx)
                st.session_state.servicios[servicio_destino].append(profesional)
                
                st.session_state.log_movimientos.insert(0, {
                    "fecha": datetime.now().strftime("%H:%M:%S"),
                    "nombre": nombre,
                    "desde": origen,
                    "hacia": servicio_destino,
                    "rol": profesional["rol"]
                })
                break
        
        st.session_state.seleccion = {"nombre": None, "servicio": None}
        st.rerun()

def show_role_legend():
    """Muestra la leyenda de roles en la parte superior"""
    st.markdown("""
    <div class="leyenda-horizontal">
        <div class="leyenda-item">
            <div class="role-badge" style="background-color: #ff5252;"></div>
            <span>Especialista</span>
        </div>
        <div class="leyenda-item">
            <div class="role-badge" style="background-color: #4caf50;"></div>
            <span>General-A</span>
        </div>
        <div class="leyenda-item">
            <div class="role-badge" style="background-color: #2196f3;"></div>
            <span>General-B</span>
        </div>
        <div class="leyenda-item">
            <div class="role-badge" style="background-color: #9c27b0;"></div>
            <span>General-C</span>
        </div>
        <div class="leyenda-item">
            <div class="role-badge" style="background-color: #ff9800;"></div>
            <span>Camillero</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def show_main_content():
    """Muestra el contenido principal de la aplicación"""
    
    # Mostrar leyenda de roles en la parte superior
    show_role_legend()
    
    # Mostrar selección actual si hay alguna
    if st.session_state.seleccion["nombre"]:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
                <div class="seleccionado-box">
                    <b>Profesional seleccionado:</b> {st.session_state.seleccion["nombre"]}
                </div>
            """, unsafe_allow_html=True)
        with col2:
            if st.button("❌ Cancelar selección", use_container_width=True):
                st.session_state.seleccion = {"nombre": None, "servicio": None}
                st.rerun()
    
    st.markdown("""
        <div style="background-color: #f0f8ff; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-size: 0.9em;">
            <b>Instrucciones:</b><br>
            1. Haz clic en un profesional para seleccionarlo<br>
            2. Haz clic en "Mover aquí" del servicio destino
        </div>
    """, unsafe_allow_html=True)

    # Mostrar servicios en columnas
    cols = st.columns(3)
    for i, (servicio, profesionales) in enumerate(st.session_state.servicios.items()):
        with cols[i % 3]:
            st.markdown(f"### {servicio}")
            for p in profesionales:
                selected = (st.session_state.seleccion["nombre"] == p["nombre"] and 
                          st.session_state.seleccion["servicio"] == servicio)
                
                # Contenedor clickeable para cada profesional
                container = st.container()
                with container:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f'<div class="profesional-name">{p["nombre"]}</div>', unsafe_allow_html=True)
                    with col2:
                        st.markdown(f'<div class="role-badge" style="background-color: {p["color"]};"></div>', unsafe_allow_html=True)
                
                # Manejar el clic en el contenedor
                if container.button("", key=f"btn_{servicio}_{p['nombre']}", help=p['nombre']):
                    if selected:
                        st.session_state.seleccion = {"nombre": None, "servicio": None}
                    else:
                        st.session_state.seleccion = {"nombre": p["nombre"], "servicio": servicio}
                    st.rerun()
                
                # Aplicar estilo de selección
                if selected:
                    st.markdown(
                        f"""
                        <style>
                            div[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] > div[data-testid="stMarkdown"] > div[data-testid="stMarkdownContainer"] > div {{
                                background-color: #fff8e1 !important;
                                border: 2px solid #ffd54f !important;
                            }}
                        </style>
                        """,
                        unsafe_allow_html=True
                    )
            
            # Botón para mover al servicio actual
            if (st.session_state.seleccion["nombre"] and 
                st.session_state.seleccion["servicio"] and 
                servicio != st.session_state.seleccion["servicio"]):
                
                if st.button(f"Mover {st.session_state.seleccion['nombre'].split()[0]} aquí", 
                           key=f"mover_{servicio}", use_container_width=True):
                    mover_personal(servicio)

def show_summary():
    """Muestra el resumen de movimientos al final de la página"""
    st.markdown("""
    <div class="sumario-cambios">
        <h3>Resumen de Movimientos</h3>
    """, unsafe_allow_html=True)
    
    if st.session_state.log_movimientos:
        # Mostrar los últimos 5 movimientos
        for mov in st.session_state.log_movimientos[:5]:
            color_rol = {
                "especialista": "#ff5252",
                "general-a": "#4caf50",
                "general-b": "#2196f3",
                "general-c": "#9c27b0",
                "camillero": "#ff9800"
            }.get(mov["rol"], "#000000")
            
            st.markdown(f"""
                <div class="historial-item">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                        <span style="font-weight: bold; color: #666;">{mov["fecha"]}</span>
                        <div class="role-badge" style="background-color: {color_rol};"></div>
                    </div>
                    <div style="font-weight: bold; margin: 3px 0;">{mov["nombre"]}</div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.8em;">
                        <span style="color: #d32f2f;">{mov["desde"]}</span>
                        <span>→</span>
                        <span style="color: #388e3c;">{mov["hacia"]}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Estadísticas resumidas
        st.markdown(f"""
            <div style="margin-top: 15px; font-size: 0.9em;">
                <b>Total movimientos:</b> {len(st.session_state.log_movimientos)}<br>
                <b>Último movimiento:</b> {st.session_state.log_movimientos[0]["fecha"]}
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No hay movimientos registrados", icon="ℹ️")
    
    st.markdown("</div>", unsafe_allow_html=True)

def main():
    """Función principal que ejecuta la aplicación"""
    setup_page_config()
    load_custom_styles()
    initialize_session_state()
    show_logo()  # Mostrar logo primero
    show_main_content()
    show_summary()

if __name__ == "__main__":
    main()
