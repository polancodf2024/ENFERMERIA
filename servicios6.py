import streamlit as st
from datetime import datetime
from PIL import Image
import os
import base64
from io import BytesIO
import uuid

def initialize_session_state():
    """Inicializa el estado de la sesión con las habitaciones, pacientes y enfermeras"""
    if 'habitaciones' not in st.session_state:
        st.session_state.habitaciones = {
            "Habitación 101": {
                "pacientes": [
                    {"id": str(uuid.uuid4()), "tipo": "paciente", "nombre": "Pas: Juan Pérez", "diagnostico": "Infarto agudo de miocardio", "estado": "crítico", "color": "#ff5252"},
                    {"id": str(uuid.uuid4()), "tipo": "paciente", "nombre": "Pas: María Gómez", "diagnostico": "Arritmia ventricular", "estado": "observación", "color": "#ff9800"}
                ],
                "enfermeras": [
                    {"id": str(uuid.uuid4()), "tipo": "enfermera", "nombre": "Enf: Laura Díaz", "rol": "Especialista", "color": "#9c27b0"}
                ]
            },
            "Habitación 102": {
                "pacientes": [
                    {"id": str(uuid.uuid4()), "tipo": "paciente", "nombre": "Pas: Carlos Ruiz", "diagnostico": "Cardiopatía isquémica", "estado": "estable", "color": "#4caf50"},
                    {"id": str(uuid.uuid4()), "tipo": "paciente", "nombre": "Pas: Ana López", "diagnostico": "Insuficiencia cardíaca", "estado": "estable", "color": "#4caf50"}
                ],
                "enfermeras": [
                    {"id": str(uuid.uuid4()), "tipo": "enfermera", "nombre": "Enf: Pedro Sánchez", "rol": "General A", "color": "#2196f3"},
                    {"id": str(uuid.uuid4()), "tipo": "enfermera", "nombre": "Enf: Sofía Martínez", "rol": "Especialista", "color": "#9c27b0"}
                ]
            },
            "Habitación 103": {
                "pacientes": [
                    {"id": str(uuid.uuid4()), "tipo": "paciente", "nombre": "Pas: Sofía Martínez", "diagnostico": "Miocardiopatía dilatada", "estado": "mejorando", "color": "#2196f3"}
                ],
                "enfermeras": []
            },
            "Habitación 104": {
                "pacientes": [],
                "enfermeras": []
            },
            "Habitación 105": {
                "pacientes": [
                    {"id": str(uuid.uuid4()), "tipo": "paciente", "nombre": "Pas: Pedro Sánchez", "diagnostico": "Postoperatorio bypass", "estado": "alta pendiente", "color": "#9c27b0"}
                ],
                "enfermeras": [
                    {"id": str(uuid.uuid4()), "tipo": "enfermera", "nombre": "Enf: Miguel Ángel", "rol": "General B", "color": "#ff9800"}
                ]
            }
        }

    if 'seleccion' not in st.session_state:
        st.session_state.seleccion = {"id": None, "tipo": None, "nombre": None, "habitacion": None, "diagnostico": None, "rol": None}
        
    if 'log_movimientos' not in st.session_state:
        st.session_state.log_movimientos = []
        
    if 'log_atenciones' not in st.session_state:
        st.session_state.log_atenciones = []
    
    if 'nuevo_nombre' not in st.session_state:
        st.session_state.nuevo_nombre = ""
    
    if 'nuevo_diagnostico' not in st.session_state:
        st.session_state.nuevo_diagnostico = "Diagnóstico por definir"
    
    if 'nuevo_rol' not in st.session_state:
        st.session_state.nuevo_rol = "General A"
    
    if 'mostrar_modal' not in st.session_state:
        st.session_state.mostrar_modal = False
    
    if 'tipo_nuevo' not in st.session_state:
        st.session_state.tipo_nuevo = ""
    
    if 'habitacion_nuevo' not in st.session_state:
        st.session_state.habitacion_nuevo = ""

def setup_page_config():
    """Configura la página de Streamlit"""
    st.set_page_config(
        layout="wide",
        page_title="Asignación de Pacientes y Enfermeras en el Servicio de Urgencias",
        page_icon="🏥"
    )

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
        .habitacion-container {
            border: 2px solid #4a8cff;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            background-color: #f8fbff;
        }
        .habitacion-header {
            font-size: 1.3em;
            font-weight: bold;
            color: #2c5fd1;
            margin-bottom: 15px;
            text-align: center;
        }
        .persona-container {
            display: flex;
            flex-direction: column;
            padding: 12px;
            margin: 8px 0;
            background-color: white;
            border-radius: 8px;
            border: 1px solid #ddd;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .persona-container:hover {
            background-color: #f0f6ff;
        }
        .selected {
            background-color: #fff8e1 !important;
            border: 2px solid #ffd54f !important;
        }
        .estado-badge {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            display: inline-block;
            margin-left: 8px;
        }
        .persona-name {
            font-weight: bold;
            font-size: 1.05em;
            margin-bottom: 4px;
        }
        .persona-info {
            font-size: 0.85em;
            color: #555;
            margin-bottom: 6px;
        }
        .historial-item {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
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
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
            border: 1px solid #ffd54f;
        }
        .boton-accion {
            margin: 5px 0;
            width: 100%;
        }
        .badge-container {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-top: 4px;
        }
        .seccion-enfermeras {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px dashed #ccc;
        }
        .seccion-enfermeras-title {
            font-size: 0.9em;
            font-weight: bold;
            color: #555;
            margin-bottom: 10px;
        }
        .boton-agregar {
            margin-top: 10px;
        }
        .formulario-alta {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            border-left: 4px solid #4a8cff;
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
            st.markdown('<div class="header-container"><h2>Asignación de Pacientes y Enfermeras en el Servicio de Urgencias</h2></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="header-container"><h2>Asignación de Pacientes y Enfermeras en el Servicio de Urgencias</h2></div>', unsafe_allow_html=True)

def agregar_persona():
    """Agrega un nuevo paciente o enfermera según el formulario"""
    if st.session_state.nuevo_nombre.strip():
        nuevo_id = str(uuid.uuid4())
        
        if st.session_state.tipo_nuevo == "paciente":
            nuevo_item = {
                "id": nuevo_id,
                "tipo": "paciente",
                "nombre": f"Pas: {st.session_state.nuevo_nombre}",
                "diagnostico": st.session_state.nuevo_diagnostico,
                "estado": "estable",
                "color": "#4caf50"
            }
        else:
            # Asignar color según el rol de la enfermera
            colores_roles = {
                "Especialista": "#9c27b0",
                "General A": "#2196f3",
                "General B": "#ff9800",
                "General C": "#4caf50",
                "Camillero": "#607d8b"
            }
            
            nuevo_item = {
                "id": nuevo_id,
                "tipo": "enfermera",
                "nombre": f"Enf: {st.session_state.nuevo_nombre}",
                "rol": st.session_state.nuevo_rol,
                "color": colores_roles.get(st.session_state.nuevo_rol, "#9c27b0")
            }
        
        st.session_state.habitaciones[st.session_state.habitacion_nuevo][
            "pacientes" if st.session_state.tipo_nuevo == "paciente" else "enfermeras"
        ].append(nuevo_item)
        
        # Resetear valores
        st.session_state.nuevo_nombre = ""
        st.session_state.nuevo_diagnostico = "Diagnóstico por definir"
        st.session_state.nuevo_rol = "General A"
        st.rerun()
    else:
        st.warning("Por favor ingrese un nombre válido")

def mover_persona(habitacion_destino):
    """Mueve la persona seleccionada (paciente o enfermera) a la habitación destino"""
    origen = st.session_state.seleccion["habitacion"]
    id_persona = st.session_state.seleccion["id"]
    tipo = st.session_state.seleccion["tipo"]
    
    if origen and habitacion_destino != origen:
        # Buscar y mover al paciente o enfermera
        lista_origen = st.session_state.habitaciones[origen]["pacientes"] if tipo == "paciente" else st.session_state.habitaciones[origen]["enfermeras"]
        lista_destino = st.session_state.habitaciones[habitacion_destino]["pacientes"] if tipo == "paciente" else st.session_state.habitaciones[habitacion_destino]["enfermeras"]
        
        for idx, p in enumerate(lista_origen):
            if p["id"] == id_persona:
                persona = lista_origen.pop(idx)
                lista_destino.append(persona)
                
                st.session_state.log_movimientos.insert(0, {
                    "fecha": datetime.now().strftime("%H:%M:%S"),
                    "tipo": tipo,
                    "nombre": persona["nombre"],
                    "info": persona["diagnostico"] if tipo == "paciente" else persona["rol"],
                    "desde": origen,
                    "hacia": habitacion_destino,
                    "color": persona["color"]
                })
                break
        
        st.session_state.seleccion = {"id": None, "tipo": None, "nombre": None, "habitacion": None, "diagnostico": None, "rol": None}
        st.rerun()

def registrar_atencion(tipo):
    """Registra una atención médica para el paciente seleccionado"""
    if st.session_state.seleccion["nombre"] and st.session_state.seleccion["tipo"] == "paciente":
        st.session_state.log_atenciones.insert(0, {
            "fecha": datetime.now().strftime("%H:%M:%S"),
            "nombre": st.session_state.seleccion["nombre"],
            "habitacion": st.session_state.seleccion["habitacion"],
            "diagnostico": st.session_state.seleccion["diagnostico"],
            "tipo": tipo,
            "realizado_por": "Cardiólogo"
        })
        st.rerun()

def main():
    """Función principal que ejecuta la aplicación"""
    setup_page_config()
    load_custom_styles()
    initialize_session_state()
    show_logo()
    show_main_content()
    show_forms()
    show_summary()

def show_main_content():
    """Muestra el contenido principal de la aplicación"""

    # Mostrar leyenda de estados
    show_estado_legend()

    # Mostrar selección actual si hay alguna
    if st.session_state.seleccion["nombre"]:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            if st.session_state.seleccion["tipo"] == "paciente":
                st.markdown(f"""
                    <div class="seleccionado-box">
                        <div style="font-weight: bold; font-size: 1.1em;">{st.session_state.seleccion["nombre"]}</div>
                        <div style="margin: 8px 0;"><b>Diagnóstico:</b> {st.session_state.seleccion["diagnostico"]}</div>
                        <div><b>Habitación:</b> {st.session_state.seleccion["habitacion"]}</div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="seleccionado-box">
                        <div style="font-weight: bold; font-size: 1.1em;">{st.session_state.seleccion["nombre"]}</div>
                        <div style="margin: 8px 0;"><b>Rol:</b> {st.session_state.seleccion["rol"]}</div>
                        <div><b>Habitación:</b> {st.session_state.seleccion["habitacion"]}</div>
                    </div>
                """, unsafe_allow_html=True)

        with col2:
            if st.session_state.seleccion["tipo"] == "paciente":
                if st.button("💊 Administrar medicación",
                           key=f"med_{st.session_state.seleccion['id']}",
                           use_container_width=True,
                           help="Registrar medicación administrada"):
                    registrar_atencion("Medicación administrada")

        with col3:
            if st.button("❌ Cancelar selección",
                        key=f"cancel_{st.session_state.seleccion['id']}",
                        use_container_width=True):
                st.session_state.seleccion = {"id": None, "tipo": None, "nombre": None, "habitacion": None, "diagnostico": None, "rol": None}
                st.rerun()

    st.markdown("""
        <div style="background-color: #f0f8ff; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 0.9em;">
            <b>Instrucciones:</b><br>
            1. Haz clic en un paciente o enfermera para seleccionarlo<br>
            2. Haz clic en "Mover aquí" de la habitación destino para trasladarlo<br>
            3. Para pacientes: usa el botón para registrar atenciones médicas<br>
            4. Usa los formularios abajo para dar de alta nuevos pacientes o enfermeras
        </div>
    """, unsafe_allow_html=True)

    # Mostrar habitaciones en columnas
    cols = st.columns(3)
    for i, (habitacion, datos) in enumerate(st.session_state.habitaciones.items()):
        with cols[i % 3]:
            st.markdown(f"### {habitacion}")

            # Mostrar número de pacientes y enfermeras
            st.caption(f"{len(datos['pacientes'])} paciente(s) • {len(datos['enfermeras'])} enfermera(s)")

            # Mostrar pacientes
            for p in datos["pacientes"]:
                selected = (st.session_state.seleccion["id"] == p["id"])

                container = st.container()
                with container:
                    st.markdown(f"""
                        <div class="persona-container" style="{'border: 2px solid #ffd54f; background-color: #fff8e1;' if selected else ''}">
                            <div class="persona-name">{p["nombre"]}</div>
                            <div class="persona-info">{p["diagnostico"]}</div>
                            <div class="badge-container">
                                <div style="width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid {p["color"]};"></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                if container.button("",
                                 key=f"btn_p_{p['id']}",
                                 help=f"Seleccionar {p['nombre']}"):
                    if selected:
                        st.session_state.seleccion = {"id": None, "tipo": None, "nombre": None, "habitacion": None, "diagnostico": None, "rol": None}
                    else:
                        st.session_state.seleccion = {
                            "id": p["id"],
                            "tipo": "paciente",
                            "nombre": p["nombre"],
                            "habitacion": habitacion,
                            "diagnostico": p["diagnostico"],
                            "rol": None
                        }
                    st.rerun()

            # Mostrar enfermeras
            if datos["enfermeras"]:
                st.markdown('<div class="seccion-enfermeras"><div class="seccion-enfermeras-title">Enfermeras asignadas</div></div>', unsafe_allow_html=True)

                for e in datos["enfermeras"]:
                    selected = (st.session_state.seleccion["id"] == e["id"])

                    container = st.container()
                    with container:
                        st.markdown(f"""
                            <div class="persona-container" style="{'border: 2px solid #ffd54f; background-color: #fff8e1;' if selected else ''}">
                                <div class="persona-name">{e["nombre"]}</div>
                                <div class="persona-info">{e["rol"]}</div>
                                <div class="badge-container">
                                    <div style="width: 14px; height: 14px; background-color: {e["color"]}; border-radius: 3px;"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                    if container.button("",
                                     key=f"btn_e_{e['id']}",
                                     help=f"Seleccionar {e['nombre']}"):
                        if selected:
                            st.session_state.seleccion = {"id": None, "tipo": None, "nombre": None, "habitacion": None, "diagnostico": None, "rol": None}
                        else:
                            st.session_state.seleccion = {
                                "id": e["id"],
                                "tipo": "enfermera",
                                "nombre": e["nombre"],
                                "habitacion": habitacion,
                                "diagnostico": None,
                                "rol": e["rol"]
                            }
                        st.rerun()

            # Botón para mover a la habitación actual
            if (st.session_state.seleccion["nombre"] and
                st.session_state.seleccion["habitacion"] and
                habitacion != st.session_state.seleccion["habitacion"]):

                tipo_seleccionado = "paciente" if st.session_state.seleccion["tipo"] == "paciente" else "enfermera"
                nombre_corto = st.session_state.seleccion["nombre"].split(": ")[1].split()[0]

                if st.button(f"⇨ Mover {tipo_seleccionado} {nombre_corto} aquí",
                           key=f"mover_{habitacion}_{st.session_state.seleccion['id']}",
                           use_container_width=True):
                    mover_persona(habitacion)

def show_estado_legend():
    """Muestra la leyenda de estados y roles en la parte superior"""
    st.markdown("""
    <div class="leyenda-horizontal">
        <div class="leyenda-item">
            <div style="width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid #ff0000;"></div>
            <span>Crítico</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid #ff6600;"></div>
            <span>Observación</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid #0066ff;"></div>
            <span>Mejorando</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 14px solid #00aa00;"></div>
            <span>Estable</span>
        </div>
    </div>
    <div class="leyenda-horizontal" style="margin-top: 10px;">
        <div class="leyenda-item">
            <div style="width: 14px; height: 14px; background-color: #9c27b0; border-radius: 3px;"></div>
            <span>Especialista</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 14px; height: 14px; background-color: #2196f3; border-radius: 3px;"></div>
            <span>General A</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 14px; height: 14px; background-color: #ff9800; border-radius: 3px;"></div>
            <span>General B</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 14px; height: 14px; background-color: #4caf50; border-radius: 3px;"></div>
            <span>General C</span>
        </div>
        <div class="leyenda-item">
            <div style="width: 14px; height: 14px; background-color: #607d8b; border-radius: 3px;"></div>
            <span>Camillero</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def show_forms():
    """Muestra los formularios para dar de alta nuevos pacientes y enfermeras"""
    st.markdown("---")
    st.markdown("## Dar de alta")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Nuevo Paciente")
        with st.form(key="form_paciente"):
            st.session_state.nuevo_nombre = st.text_input(
                "Nombre completo:",
                value=st.session_state.nuevo_nombre,
                key="input_nombre_paciente"
            )
            
            st.session_state.habitacion_nuevo = st.selectbox(
                "Habitación:",
                list(st.session_state.habitaciones.keys()),
                key="select_habitacion_paciente"
            )
            
            st.session_state.nuevo_diagnostico = st.text_input(
                "Diagnóstico:",
                value=st.session_state.nuevo_diagnostico,
                key="input_diagnostico_paciente"
            )
            
            if st.form_submit_button("Dar de alta paciente"):
                st.session_state.tipo_nuevo = "paciente"
                agregar_persona()
    
    with col2:
        st.markdown("### Nueva Enfermera")
        with st.form(key="form_enfermera"):
            st.session_state.nuevo_nombre = st.text_input(
                "Nombre completo:",
                value=st.session_state.nuevo_nombre,
                key="input_nombre_enfermera"
            )
            
            st.session_state.habitacion_nuevo = st.selectbox(
                "Habitación:",
                list(st.session_state.habitaciones.keys()),
                key="select_habitacion_enfermera"
            )
            
            st.session_state.nuevo_rol = st.selectbox(
                "Rol:",
                ["Especialista", "General A", "General B", "General C", "Camillero"],
                key="select_rol_enfermera"
            )
            
            if st.form_submit_button("Dar de alta enfermera"):
                st.session_state.tipo_nuevo = "enfermera"
                agregar_persona()

def show_summary():
    """Muestra el resumen de movimientos al final de la página"""
    st.markdown("""
    <div class="sumario-cambios">
        <h3>Historial de Movimientos</h3>
    """, unsafe_allow_html=True)

    if st.session_state.log_movimientos:
        for mov in st.session_state.log_movimientos[:10]:
            st.markdown(f"""
                <div class="historial-item">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                        <span style="font-weight: bold; color: #666;">{mov["fecha"]}</span>
                        <div class="estado-badge" style="background-color: {mov["color"]};"></div>
                    </div>
                    <div style="font-weight: bold; margin: 3px 0;">{mov["nombre"]}</div>
                    <div style="font-size: 0.85em; color: #555; margin-bottom: 5px;">{mov["info"]}</div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.8em;">
                        <span style="color: #d32f2f;">{mov["desde"]}</span>
                        <span>→</span>
                        <span style="color: #388e3c;">{mov["hacia"]}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style="margin-top: 15px; font-size: 0.9em;">
                <b>Total movimientos:</b> {len(st.session_state.log_movimientos)}<br>
                <b>Último movimiento:</b> {st.session_state.log_movimientos[0]["fecha"]}
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No hay movimientos registrados", icon="ℹ️")

    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
