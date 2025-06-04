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

# Configuración de logging mejorada
logging.basicConfig(
    filename='viewer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuración de la aplicación
class Config:
    def __init__(self):
        try:
            self.CSV_FILENAME = st.secrets["csv_materias_file"]     
            self.ECG_FOLDER = st.secrets["ecg_folder"]              
            self.LOGO_PATH = "escudo_COLOR.jpg"                    
            self.HIGHLIGHT_COLOR = "#90EE90"
            self.TIMEOUT = 45  # Aumentado de 30 a 45 segundos
            self.ROW_HEIGHT = 35
            self.HEADER_HEIGHT = 70

            self.REMOTE = {
                'HOST': st.secrets["remote_host"],
                'USER': st.secrets["remote_user"],
                'PASSWORD': st.secrets["remote_password"],
                'PORT': int(st.secrets.get("remote_port", 22)),
                'DIR': st.secrets["remote_dir"],
                'ECG_DIR': st.secrets.get("remote_ecg_dir", st.secrets["ecg_folder"])
            }
        except Exception as e:
            logger.error(f"Error al cargar configuración: {str(e)}")
            raise

CONFIG = Config()

# Clase para manejo SSH mejorado con más logging
class SSHManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # segundos entre reintentos

    @staticmethod
    def get_connection():
        """Establece conexión SSH con reintentos y mejor logging"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        for attempt in range(SSHManager.MAX_RETRIES):
            try:
                logger.info(f"Intentando conexión SSH (intento {attempt + 1}) a {CONFIG.REMOTE['HOST']}:{CONFIG.REMOTE['PORT']}")
                ssh.connect(
                    hostname=CONFIG.REMOTE['HOST'],
                    port=CONFIG.REMOTE['PORT'],
                    username=CONFIG.REMOTE['USER'],
                    password=CONFIG.REMOTE['PASSWORD'],
                    timeout=CONFIG.TIMEOUT,
                    banner_timeout=30
                )
                logger.info("Conexión SSH establecida exitosamente")
                return ssh
            except paramiko.AuthenticationException as e:
                logger.error(f"Error de autenticación SSH: {str(e)}")
                st.error("Error de autenticación con el servidor remoto")
                return None
            except paramiko.SSHException as e:
                logger.warning(f"Intento {attempt + 1} fallido (SSHException): {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logger.error("Fallo definitivo al conectar via SSH (SSHException)")
                    st.error("No se pudo establecer conexión SSH después de varios intentos")
                    return None
            except Exception as e:
                logger.warning(f"Intento {attempt + 1} fallido (Error general): {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logger.error(f"Fallo definitivo al conectar via SSH (Error general): {str(e)}")
                    st.error(f"Error de conexión: {str(e)}")
                    return None

    @staticmethod
    def download_file(remote_path, local_path):
        """Descarga un archivo remoto con manejo robusto de errores"""
        logger.info(f"Intentando descargar: {remote_path} -> {local_path}")
        ssh = SSHManager.get_connection()
        if not ssh:
            st.error("No se pudo establecer conexión SSH para descarga")
            return False
            
        try:
            with ssh.open_sftp() as sftp:
                # Verificar si el archivo remoto existe
                try:
                    file_info = sftp.stat(remote_path)
                    logger.info(f"Archivo remoto encontrado. Tamaño: {file_info.st_size} bytes")
                except FileNotFoundError:
                    st.error(f"Archivo remoto no encontrado: {remote_path}")
                    logger.error(f"Archivo remoto no encontrado: {remote_path}")
                    return False
                
                # Descargar archivo con barra de progreso
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def progress_callback(bytes_transferred, total_bytes):
                    progress = bytes_transferred / total_bytes
                    progress_bar.progress(progress)
                    status_text.text(f"Descargando... {bytes_transferred}/{total_bytes} bytes ({progress:.1%})")
                
                sftp.get(remote_path, local_path, callback=progress_callback)
                
                progress_bar.empty()
                status_text.empty()
                logger.info(f"Archivo descargado exitosamente: {remote_path} -> {local_path}")
                st.success("Descarga completada")
                return True
                
        except Exception as e:
            st.error(f"Error al descargar archivo: {str(e)}")
            logger.error(f"Error en download_file: {str(e)}")
            return False
        finally:
            ssh.close()

    @staticmethod
    def test_connection():
        """Prueba la conexión SSH y lista archivos"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return False
        
        try:
            with ssh.open_sftp() as sftp:
                try:
                    remote_dir = CONFIG.REMOTE['DIR']
                    files = sftp.listdir(remote_dir)
                    logger.info(f"Conexión SSH exitosa. Archivos en {remote_dir}: {files}")
                    st.success(f"Conexión SSH exitosa. Se encontraron {len(files)} archivos en el directorio remoto.")
                    return True
                except Exception as e:
                    st.error(f"No se pudo listar directorio remoto: {str(e)}")
                    logger.error(f"Error al listar directorio remoto: {str(e)}")
                    return False
        finally:
            ssh.close()

    @staticmethod
    def get_all_ecgs(patient_id):
        """Obtiene todos los ECGs para un paciente con mejor manejo de errores"""
        logger.info(f"Buscando ECGs para paciente {patient_id}")
        ssh = SSHManager.get_connection()
        if not ssh:
            return None
            
        try:
            remote_ecg_dir = f"{CONFIG.REMOTE['DIR']}/{CONFIG.REMOTE['ECG_DIR']}"
            ecg_list = []
            
            with ssh.open_sftp() as sftp:
                try:
                    ecg_files = sftp.listdir(remote_ecg_dir)
                    logger.info(f"Archivos encontrados en {remote_ecg_dir}: {ecg_files}")
                except FileNotFoundError:
                    logger.error(f"Carpeta ECG no encontrada: {remote_ecg_dir}")
                    st.error(f"No se encontró la carpeta de ECGs en el servidor: {remote_ecg_dir}")
                    return None
                
                # Filtrar archivos que coincidan con el patient_id
                patient_ecgs = [f for f in ecg_files if str(patient_id) in f and f.lower().endswith('.pdf')]
                logger.info(f"ECGs encontrados para paciente {patient_id}: {patient_ecgs}")
                
                if not patient_ecgs:
                    st.warning(f"No se encontraron ECGs para el paciente {patient_id}")
                    return None
                
                # Ordenar por timestamp (asumiendo que el nombre comienza con timestamp)
                patient_ecgs.sort(reverse=True)
                
                # Descargar temporalmente cada archivo con manejo de errores
                for ecg_file in patient_ecgs:
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                            remote_path = f"{remote_ecg_dir}/{ecg_file}"
                            logger.info(f"Descargando ECG: {remote_path}")
                            
                            # Barra de progreso para cada descarga
                            with st.spinner(f"Descargando {ecg_file}..."):
                                sftp.get(remote_path, tmp_file.name)
                            
                            # Extraer timestamp del nombre del archivo
                            filename_parts = ecg_file.split('_')
                            timestamp_str = ' '.join(filename_parts[:2]) if len(filename_parts) >= 2 else filename_parts[0]
                            timestamp_str = timestamp_str.replace("-", ":").split('.')[0]
                            
                            try:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                logger.warning(f"No se pudo parsear timestamp, usando hora de modificación")
                                timestamp = datetime.fromtimestamp(os.path.getmtime(tmp_file.name))
                            
                            ecg_list.append({
                                'path': tmp_file.name,
                                'timestamp': timestamp,
                                'filename': ecg_file
                            })
                    except Exception as e:
                        logger.error(f"Error procesando archivo {ecg_file}: {str(e)}")
                        st.warning(f"Error al procesar ECG {ecg_file}: {str(e)}")
                        continue
                
                return ecg_list if ecg_list else None
                    
        except Exception as e:
            logger.error(f"Error en get_all_ecgs: {str(e)}")
            st.error(f"Error al obtener ECGs: {str(e)}")
            return None
        finally:
            ssh.close()


def load_data():
    """Carga los datos del CSV remoto con mejor manejo de errores"""
    remote_csv_path = f"{CONFIG.REMOTE['DIR']}/{CONFIG.CSV_FILENAME}"
    local_csv = "temp_signos.csv"
    
    logger.info(f"Intentando cargar datos desde {remote_csv_path}")
    st.info(f"Conectando al servidor para obtener datos...")
    
    if not SSHManager.download_file(remote_csv_path, local_csv):
        st.error("No se pudo descargar el archivo CSV desde el servidor")
        return pd.DataFrame()
    
    try:
        # Leer CSV con manejo de errores
        try:
            df = pd.read_csv(local_csv)
            logger.info(f"Datos cargados. Columnas: {df.columns.tolist()}")
        except pd.errors.EmptyDataError:
            st.warning("El archivo CSV está vacío")
            logger.warning("Archivo CSV descargado pero vacío")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error al leer el archivo CSV: {str(e)}")
            logger.error(f"Error al leer CSV: {str(e)}")
            return pd.DataFrame()
        
        # Verificar columnas requeridas
        required_columns = ['timestamp', 'id_paciente', 'nombre_paciente', 
                           'presion_arterial', 'temperatura', 'oximetria', 'estado']
        missing_cols = [col for col in required_columns if col not in df.columns]
        
        if missing_cols:
            st.error(f"El CSV no tiene las columnas requeridas. Faltan: {missing_cols}")
            logger.error(f"Columnas faltantes en CSV: {missing_cols}")
            return pd.DataFrame()
        
        # Convertir timestamp a datetime con múltiples formatos de prueba
        try:
            # Primero intentamos con el formato exacto
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Si falla, probamos con formato ISO8601
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
                except ValueError:
                    # Si sigue fallando, probamos inferir el formato para cada elemento
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
            
            # Verificar que todas las fechas se hayan convertido
            if df['timestamp'].isnull().any():
                st.warning("Algunas fechas no pudieron ser convertidas. Se intentará corregir...")
                logger.warning("Algunas fechas no se convirtieron correctamente")
                
                # Intentar limpiar los strings de fecha antes de convertir
                df['timestamp'] = df['timestamp'].astype(str).str.replace(r'[^0-9\-:\s]', '', regex=True)
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                
                # Eliminar filas con fechas inválidas
                initial_count = len(df)
                df = df.dropna(subset=['timestamp'])
                if len(df) < initial_count:
                    st.warning(f"Se eliminaron {initial_count - len(df)} registros con fechas inválidas")
                    logger.warning(f"Registros eliminados por fechas inválidas: {initial_count - len(df)}")
            
            df = df.sort_values('timestamp', ascending=False)
            logger.info(f"Datos procesados correctamente. Registros: {len(df)}")
            
        except Exception as e:
            st.error(f"Error al procesar fechas: {str(e)}")
            logger.error(f"Error al procesar timestamp: {str(e)}")
            return pd.DataFrame()
        
        return df
        
    finally:
        # Limpiar archivo temporal
        try:
            if os.path.exists(local_csv):
                os.remove(local_csv)
        except Exception as e:
            logger.error(f"Error al eliminar archivo temporal: {str(e)}")

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
            'Estado': 'Disponible',
            'Acción': "📄 Ver"
        })
    
    ecg_df = pd.DataFrame(ecg_data)
    
    # Mostrar tabla con opción de selección
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
    
    # Mostrar cada ECG con mejor manejo de visualización
    for idx, ecg in enumerate(ecg_list):
        with st.expander(f"ECG {idx + 1} - {ecg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
            try:
                # Mostrar información del ECG
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.metric("Paciente", ecg['filename'].split('_')[2])
                    st.metric("Fecha", ecg['timestamp'].strftime('%Y-%m-%d'))
                    
                    # Botón de descarga
                    with open(ecg['path'], "rb") as f:
                        st.download_button(
                            label="Descargar ECG",
                            data=f,
                            file_name=ecg['filename'],
                            mime="application/pdf",
                            key=f"download_{idx}"
                        )
                
                with col2:
                    st.markdown("**Visualización del ECG**")
                    
                    # Intentar mostrar el PDF
                    try:
                        from streamlit_pdf_viewer import pdf_viewer
                        pdf_viewer(ecg['path'], width=700)
                    except ImportError:
                        # Alternativa si no está instalado streamlit-pdf-viewer
                        with open(ecg['path'], "rb") as f:
                            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Error al mostrar ECG: {str(e)}")
                logger.error(f"Error al mostrar ECG {ecg['path']}: {str(e)}")
            finally:
                # Eliminar archivo temporal
                try:
                    if os.path.exists(ecg['path']):
                        os.unlink(ecg['path'])
                except Exception as e:
                    logger.error(f"Error al eliminar temporal {ecg['path']}: {str(e)}")

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

    # Prueba de conexión SSH
    if st.sidebar.button("Probar conexión SSH"):
        if SSHManager.test_connection():
            st.sidebar.success("✅ Conexión SSH exitosa")
        else:
            st.sidebar.error("❌ Fallo en conexión SSH")

    # Cargar datos con mejor manejo de estado
    data_status = st.empty()
    data_status.info("Conectando al servidor para obtener datos...")
    
    try:
        data = load_data()
        data_status.empty()
        
        if data.empty:
            st.warning("No hay registros disponibles o no se pudieron cargar los datos")
            logger.warning("DataFrame vacío retornado por load_data()")
            return

        # Mostrar estadísticas rápidas
        st.sidebar.markdown("### 📈 Estadísticas")
        st.sidebar.metric("Total de registros", len(data))
        st.sidebar.metric("Última actualización", data['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Mostrar tabla con registros
        st.subheader("📋 Registros de Pacientes")
        
        # Filtrar columnas y agregar columna de ECG
        display_cols = ['timestamp', 'id_paciente', 'nombre_paciente', 
                       'presion_arterial', 'temperatura', 'oximetria', 'estado']
        
        # Formatear datos para visualización
        display_data = data[display_cols].copy()
        display_data['Seleccionar'] = False
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
                "estado": st.column_config.Column(
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

    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        logger.error(f"Error en main(): {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
