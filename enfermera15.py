import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import os
import logging
from PIL import Image
import tempfile
import paramiko
import time
import base64

# Configuración de logging
logging.basicConfig(
    filename='viewer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configuración de la aplicación
class Config:
    def __init__(self):
        self.CSV_FILENAME = st.secrets["csv_materias_file"]     
        self.ECG_FOLDER = st.secrets["ecg_folder"]              
        self.LOGO_PATH = "escudo_COLOR.jpg"                    
        self.HIGHLIGHT_COLOR = "#90EE90"
        self.TIMEOUT = 30
        self.ROW_HEIGHT = 35  # Altura de cada fila en píxeles
        self.HEADER_HEIGHT = 70  # Altura del encabezado en píxeles

        self.REMOTE = {
            'HOST': st.secrets["remote_host"],
            'USER': st.secrets["remote_user"],
            'PASSWORD': st.secrets["remote_password"],
            'PORT': int(st.secrets.get("remote_port", 22)),
            'DIR': st.secrets["remote_dir"],
            'ECG_DIR': st.secrets.get("remote_ecg_dir", st.secrets["ecg_folder"])
        }

CONFIG = Config()

# Clase para manejo SSH mejorado
class SSHManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # segundos entre reintentos

    @staticmethod
    def get_connection():
        """Establece conexión SSH con reintentos"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        for attempt in range(SSHManager.MAX_RETRIES):
            try:
                ssh.connect(
                    hostname=CONFIG.REMOTE['HOST'],
                    port=CONFIG.REMOTE['PORT'],
                    username=CONFIG.REMOTE['USER'],
                    password=CONFIG.REMOTE['PASSWORD'],
                    timeout=CONFIG.TIMEOUT
                )
                logging.info("Conexión SSH establecida")
                return ssh
            except Exception as e:
                logging.warning(f"Intento {attempt + 1} fallido: {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logging.error("Fallo definitivo al conectar via SSH")
                    return None

    @staticmethod
    def download_file(remote_path, local_path):
        """Descarga un archivo remoto con manejo de errores"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return False
            
        try:
            with ssh.open_sftp() as sftp:
                sftp.get(remote_path, local_path)
                logging.info(f"Archivo descargado: {remote_path} -> {local_path}")
                return True
        except Exception as e:
            logging.error(f"Error en download_file: {str(e)}")
            return False
        finally:
            ssh.close()

    @staticmethod
    def get_all_ecgs(patient_id):
        """Obtiene todos los ECGs para un paciente"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return None
            
        try:
            remote_ecg_dir = f"{CONFIG.REMOTE['DIR']}/{CONFIG.REMOTE['ECG_DIR']}"
            ecg_list = []
            
            with ssh.open_sftp() as sftp:
                try:
                    ecg_files = sftp.listdir(remote_ecg_dir)
                    logging.info(f"Archivos encontrados en {remote_ecg_dir}: {ecg_files}")
                except FileNotFoundError:
                    logging.error(f"Carpeta ECG no encontrada: {remote_ecg_dir}")
                    st.error(f"No se encontró la carpeta de ECGs en el servidor: {remote_ecg_dir}")
                    return None
                
                # Filtrar archivos que coincidan con el patient_id (formato más flexible)
                patient_ecgs = [f for f in ecg_files if str(patient_id) in f and f.lower().endswith('.pdf')]
                
                logging.info(f"ECGs encontrados para paciente {patient_id}: {patient_ecgs}")
                
                if not patient_ecgs:
                    st.warning(f"No se encontraron ECGs para el paciente {patient_id}")
                    return None
                
                # Ordenar por timestamp (asumiendo que el nombre comienza con timestamp)
                patient_ecgs.sort(reverse=True)
                
                # Descargar temporalmente cada archivo
                for ecg_file in patient_ecgs:
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                            remote_path = f"{remote_ecg_dir}/{ecg_file}"
                            logging.info(f"Intentando descargar: {remote_path}")
                            
                            sftp.get(remote_path, tmp_file.name)
                            
                            # Extraer timestamp del nombre del archivo (formato más flexible)
                            filename_parts = ecg_file.split('_')
                            timestamp_str = ' '.join(filename_parts[:2]) if len(filename_parts) >= 2 else filename_parts[0]
                            timestamp_str = timestamp_str.replace("-", ":").split('.')[0]  # Remover extensión
                            
                            try:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                timestamp = datetime.fromtimestamp(os.path.getmtime(tmp_file.name))
                            
                            ecg_list.append({
                                'path': tmp_file.name,
                                'timestamp': timestamp,
                                'filename': ecg_file
                            })
                    except Exception as e:
                        logging.error(f"Error procesando archivo {ecg_file}: {str(e)}")
                        continue
                
                return ecg_list if ecg_list else None
                    
        except Exception as e:
            logging.error(f"Error en get_all_ecgs: {str(e)}")
            st.error(f"Error al obtener ECGs: {str(e)}")
            return None
        finally:
            ssh.close()

def load_data():
    """Carga los datos del CSV remoto"""
    remote_csv_path = f"{CONFIG.REMOTE['DIR']}/{CONFIG.CSV_FILENAME}"
    local_csv = "temp_signos.csv"
    
    if SSHManager.download_file(remote_csv_path, local_csv):
        try:
            df = pd.read_csv(local_csv)
            # Convertir timestamp a datetime para ordenamiento
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Ordenar por timestamp descendente
            df = df.sort_values('timestamp', ascending=False)
            # Limpiar archivo temporal
            os.remove(local_csv)
            return df
        except Exception as e:
            logging.error(f"Error al leer CSV: {str(e)}")
            st.error("Error al cargar los datos")
            return pd.DataFrame()
    else:
        st.error("No se pudo conectar al servidor remoto")
        return pd.DataFrame()

def display_ecg_table(ecg_list):
    """Muestra una tabla con todos los ECGs del paciente"""
    if not ecg_list:
        st.warning("No se encontraron ECGs para este paciente")
        return
    
    # Crear DataFrame para mostrar
    ecg_data = []
    for ecg in ecg_list:
        ecg_data.append({
            'Fecha/Hora': ecg['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
            'Archivo': ecg['filename'],
            'Estado': 'Disponible',  # Nueva columna de estado
            'Acción': "📄 Ver"
        })
    
    ecg_df = pd.DataFrame(ecg_data)
    
    # Mostrar tabla
    st.dataframe(
        ecg_df,
        column_config={
            "Fecha/Hora": st.column_config.Column(width="medium"),
            "Archivo": st.column_config.Column(width="large"),
            "Estado": st.column_config.Column(width="small"),
            "Acción": st.column_config.Column(width="small")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Mostrar cada ECG seleccionado
    for idx, ecg in enumerate(ecg_list):
        with st.expander(f"ECG {idx + 1} - {ecg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} - Estado: Disponible"):
            try:
                # Opción de descarga
                with open(ecg['path'], "rb") as f:
                    st.download_button(
                        label=f"Descargar ECG {idx + 1}",
                        data=f,
                        file_name=ecg['filename'],
                        mime="application/pdf",
                        key=f"download_{idx}"
                    )
                
                # Mostrar PDF directamente
                st.markdown(f"**Visualización del ECG:** {ecg['filename']}")
                
                # Intentar con streamlit-pdf-viewer si está instalado
                try:
                    from streamlit_pdf_viewer import pdf_viewer
                    pdf_viewer(ecg['path'], width=700)
                except ImportError:
                    # Alternativa nativa de Streamlit para mostrar PDFs
                    with open(ecg['path'], "rb") as f:
                        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Error al mostrar ECG: {str(e)}")
                logging.error(f"Error al mostrar ECG {ecg['path']}: {str(e)}")
            finally:
                # Eliminar archivo temporal
                try:
                    if os.path.exists(ecg['path']):
                        os.unlink(ecg['path'])
                except Exception as e:
                    logging.error(f"Error al eliminar temporal {ecg['path']}: {str(e)}")

def main():
    st.set_page_config(
        page_title="Visualizador de Signos Vitales",
        page_icon="📊",
        layout="wide"
    )

    # Logo
    if Path(CONFIG.LOGO_PATH).exists():
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.image(Image.open(CONFIG.LOGO_PATH), width=200)

    st.title("📊 Visualizador de Signos Vitales")
    st.markdown("---")

    # Cargar datos con indicador de progreso
    with st.spinner("Cargando datos desde el servidor..."):
        data = load_data()
    
    if data.empty:
        st.warning("No hay registros disponibles")
        return

    # Mostrar tabla con registros
    st.subheader("📋 Registros de Pacientes")
    
    # Filtrar columnas y agregar columna de ECG
    display_cols = ['timestamp', 'id_paciente', 'nombre_paciente', 
                   'presion_arterial', 'temperatura', 'oximetria', 'estado']
    
    # Formatear datos para visualización
    display_data = data[display_cols].copy()
    
    # Agregar columna de selección
    display_data['Seleccionar'] = False
    
    # Convertir timestamp a string para visualización
    display_data['timestamp'] = display_data['timestamp'].dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Calcular altura de la tabla
    table_height = CONFIG.HEADER_HEIGHT + (len(display_data) * CONFIG.ROW_HEIGHT)
    
    # Mostrar tabla con registros usando st.data_editor
    edited_df = st.data_editor(
        display_data,
        column_config={
            "timestamp": "Fecha/Hora",
            "id_paciente": "ID Paciente",
            "nombre_paciente": "Nombre",
            "presion_arterial": "Presión (mmHg)",
            "temperatura": "Temp. (°C)",
            "oximetria": "Oximetría (%)",
            "estado": st.column_config.Column(  # Ahora visible con formato condicional
                "Estado",
                help="Estado del registro del paciente",
                width="small"
            ),
            "Seleccionar": st.column_config.CheckboxColumn(
                "Ver ECG",
                help="Seleccione para ver los ECGs del paciente",
                width="small"
            )
        },
        hide_index=True,
        use_container_width=True,
        height=table_height,
        disabled=["timestamp", "id_paciente", "nombre_paciente", 
                 "presion_arterial", "temperatura", "oximetria", "estado"],
        key="patients_table"
    )

    # Obtener paciente seleccionado
    selected_rows = edited_df[edited_df['Seleccionar']]
    if not selected_rows.empty:
        selected_row = selected_rows.iloc[0]
        selected_ecg_patient = selected_row['id_paciente']
        
        # Mostrar estado del paciente seleccionado
        st.markdown("---")
        st.subheader(f"📄 ECGs del Paciente: {selected_ecg_patient}")
        st.markdown(f"**Estado actual:** {selected_row['estado']}")
        
        with st.spinner(f"Buscando ECGs para paciente {selected_ecg_patient}..."):
            ecg_list = SSHManager.get_all_ecgs(selected_ecg_patient)
            display_ecg_table(ecg_list)

if __name__ == "__main__":
    main()
