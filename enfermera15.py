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
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import io

# Configuración de logging
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
            self.CSV_FILENAME = st.secrets["csv_signos_file"]     
            self.ECG_FOLDER = st.secrets["ecg_folder"]              
            self.LOGO_PATH = "escudo_COLOR.jpg"                    
            self.HIGHLIGHT_COLOR = "#90EE90"
            self.TIMEOUT = 45
            self.ROW_HEIGHT = 35
            self.HEADER_HEIGHT = 70

            self.REMOTE = {
                'HOST': st.secrets["remote_host"],
                'USER': st.secrets["remote_user"],
                'PASSWORD': st.secrets["remote_password"],
                'PORT': int(st.secrets["remote_port"]),
                'DIR': st.secrets["remote_dir"],
                'ECG_DIR': st.secrets["ecg_folder"]
            }
            
            # Configuración de correo
            self.SMTP_SERVER = st.secrets["smtp_server"]
            self.SMTP_PORT = st.secrets["smtp_port"]
            self.EMAIL_USER = st.secrets["email_user"]
            self.EMAIL_PASSWORD = st.secrets["email_password"]
            self.NOTIFICATION_EMAIL = st.secrets["notification_email"]
            
        except Exception as e:
            logger.error(f"Error al cargar configuración: {str(e)}")
            raise

CONFIG = Config()

# Conjunto global para llevar registro de los pacientes que ya han recibido notificación
notified_patients = set()

# Funciones auxiliares
def validate_phone_number(phone):
    """Valida que el número tenga 10 dígitos"""
    if not phone or not isinstance(phone, str):
        return False
    cleaned = ''.join(filter(str.isdigit, phone))
    return len(cleaned) == 10

def format_phone_number(phone):
    """Formato: 55-1234-5678"""
    if not validate_phone_number(phone):
        return phone
    cleaned = ''.join(filter(str.isdigit, phone))
    return f"{cleaned[:2]}-{cleaned[2:6]}-{cleaned[6:]}"

# Función para enviar correos con datos del registro
def send_variation_email(patient_id, all_patient_data):
    """Envía un correo con todos los registros del paciente cuando se detectan variaciones"""
    global notified_patients
    
    # Verificar si ya se ha enviado un correo para este paciente
    if patient_id in notified_patients:
        logger.info(f"Ya se ha enviado un correo para el paciente {patient_id}. No se enviará otro.")
        return
    
    try:
        mensaje = MIMEMultipart()
        mensaje['From'] = CONFIG.EMAIL_USER
        mensaje['To'] = CONFIG.NOTIFICATION_EMAIL
        mensaje['Subject'] = f"Variación en signos vitales - Paciente {patient_id}"
        
        # Crear cuerpo del mensaje
        body = f"""
        Se ha detectado una variación significativa en los signos vitales del paciente {patient_id}.
        
        Adjunto encontrará todos los registros de este paciente.
        """
        
        mensaje.attach(MIMEText(body, 'plain'))
        
        # Crear archivo CSV con todos los registros del paciente
        csv_buffer = io.StringIO()
        all_patient_data.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        # Adjuntar el CSV
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(csv_buffer.getvalue().encode('utf-8'))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="registros_paciente_{patient_id}.csv"')
        mensaje.attach(part)
        
        context = ssl.create_default_context()
        with smtplib.SMTP(CONFIG.SMTP_SERVER, CONFIG.SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(CONFIG.EMAIL_USER, CONFIG.EMAIL_PASSWORD)
            server.sendmail(CONFIG.EMAIL_USER, CONFIG.NOTIFICATION_EMAIL, mensaje.as_string())
            
        # Marcar al paciente como notificado
        notified_patients.add(patient_id)
            
        logger.info(f"Correo enviado por variación en paciente {patient_id} con {len(all_patient_data)} registros")
        
    except Exception as e:
        logger.error(f"Error al enviar correo: {str(e)}")
        st.error("Error al enviar notificación por correo")

class SSHManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 5

    @staticmethod
    def get_connection():
        """Establece conexión SSH"""
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
                return ssh
            except Exception as e:
                if attempt == SSHManager.MAX_RETRIES - 1:
                    st.error(f"Error de conexión SSH: {str(e)}")
                    return None
                time.sleep(SSHManager.RETRY_DELAY)

    @staticmethod
    def download_file(remote_path, local_path):
        """Descarga archivo remoto"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return False
            
        try:
            with ssh.open_sftp() as sftp:
                sftp.get(remote_path, local_path)
                return True
        except Exception as e:
            st.error(f"Error al descargar: {str(e)}")
            return False
        finally:
            ssh.close()

    @staticmethod
    def get_all_ecgs(patient_id):
        """Obtiene ECGs del paciente"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return None
            
        try:
            remote_ecg_dir = f"{CONFIG.REMOTE['DIR']}/{CONFIG.REMOTE['ECG_DIR']}"
            ecg_list = []
            
            with ssh.open_sftp() as sftp:
                ecg_files = [f for f in sftp.listdir(remote_ecg_dir) 
                           if str(patient_id) in f and f.lower().endswith('.pdf')]
                
                if not ecg_files:
                    st.warning(f"No hay ECGs para el paciente {patient_id}")
                    return None
                
                for ecg_file in sorted(ecg_files, reverse=True):
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                        sftp.get(f"{remote_ecg_dir}/{ecg_file}", tmp_file.name)
                        
                        try:
                            timestamp = datetime.strptime(
                                '_'.join(ecg_file.split('_')[:2]).replace("-", ":"),
                                "%Y-%m-%d_%H:%M:%S"
                            )
                        except:
                            timestamp = datetime.now()
                        
                        ecg_list.append({
                            'path': tmp_file.name,
                            'timestamp': timestamp,
                            'filename': ecg_file
                        })
                
                return ecg_list
        except Exception as e:
            st.error(f"Error al obtener ECGs: {str(e)}")
            return None
        finally:
            ssh.close()

def analyze_vital_signs(df):
    """Analiza variaciones en signos vitales por paciente"""
    # Convertir a numéricos y limpiar datos
    df['temperatura'] = pd.to_numeric(df['temperatura'], errors='coerce')
    df['oximetria'] = pd.to_numeric(df['oximetria'], errors='coerce')

    # Limpiar presión arterial (ejemplo: "120/80" -> calcular media)
    def clean_pressure(pressure):
        if isinstance(pressure, str) and '/' in pressure:
            try:
                systolic, diastolic = map(float, pressure.split('/'))
                return (systolic + diastolic) / 2
            except:
                return None
        return pd.to_numeric(pressure, errors='coerce')

    df['presion_media'] = df['presion_arterial'].apply(clean_pressure)

    # Ordenar el DataFrame completo por paciente y timestamp primero
    df_sorted = df.sort_values(['id_paciente', 'timestamp'], ascending=True)

    # Calcular variaciones porcentuales
    variations = []
    
    # Iterar por cada paciente
    for patient_id in df_sorted['id_paciente'].unique():
        patient_data = df_sorted[df_sorted['id_paciente'] == patient_id]
        
        if len(patient_data) < 2:
            continue

        # Calcular cambios porcentuales entre mediciones consecutivas
        for i in range(1, len(patient_data)):
            prev_row = patient_data.iloc[i-1]
            curr_row = patient_data.iloc[i]

            altered_signs = []

            # Verificar temperatura (T:)
            if not pd.isna(prev_row['temperatura']) and not pd.isna(curr_row['temperatura']):
                temp_change = abs(curr_row['temperatura'] - prev_row['temperatura']) / prev_row['temperatura'] * 100
                if temp_change >= 3:
                    altered_signs.append(f"T: +{temp_change:.1f}%")

            # Verificar oximetría (O:)
            if not pd.isna(prev_row['oximetria']) and not pd.isna(curr_row['oximetria']):
                oxi_change = abs(curr_row['oximetria'] - prev_row['oximetria']) / prev_row['oximetria'] * 100
                if oxi_change >= 3:
                    altered_signs.append(f"O: +{oxi_change:.1f}%")

            # Verificar presión arterial (P:)
            if not pd.isna(prev_row['presion_media']) and not pd.isna(curr_row['presion_media']):
                pres_change = abs(curr_row['presion_media'] - prev_row['presion_media']) / prev_row['presion_media'] * 100
                if pres_change >= 3:
                    altered_signs.append(f"P: +{pres_change:.1f}%")

            if altered_signs:
                variations.append({
                    'id_paciente': patient_id,
                    'timestamp': curr_row['timestamp'],
                    'signos_alterados': ', '.join(altered_signs)
                })

    # Crear DataFrame con las variaciones
    if variations:
        variations_df = pd.DataFrame(variations)
        # Unir con el DataFrame original
        df = pd.merge(df, variations_df, on=['id_paciente', 'timestamp'], how='left')
        
        # Enviar correo con todos los registros del paciente cuando se detecta variación
        for patient_id in variations_df['id_paciente'].unique():
            all_patient_data = df[df['id_paciente'] == patient_id].sort_values('timestamp', ascending=False)
            send_variation_email(patient_id, all_patient_data)
    else:
        df['signos_alterados'] = None

    return df

def load_data():
    """Carga datos del CSV"""
    remote_csv_path = f"{CONFIG.REMOTE['DIR']}/{CONFIG.CSV_FILENAME}"

    with tempfile.NamedTemporaryFile(suffix='.csv') as tmp_file:
        if not SSHManager.download_file(remote_csv_path, tmp_file.name):
            return pd.DataFrame()

        try:
            df = pd.read_csv(tmp_file.name)
            # Extraer solo dígitos del ID
            df['id_paciente'] = df['id_paciente'].astype(str).str.extract(r'(\d+)')[0].str[:10]
            # Crear columna formateada
            df['id_paciente_formatted'] = df['id_paciente'].apply(format_phone_number)
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            # Analizar variaciones en signos vitales
            df = analyze_vital_signs(df)
            
            return df.dropna(subset=['timestamp']).sort_values('timestamp', ascending=False)
        except Exception as e:
            st.error(f"Error al leer CSV: {str(e)}")
            return pd.DataFrame()

def display_ecg_table(ecg_list):
    """Muestra tabla de ECGs"""
    if not ecg_list:
        return
    
    for ecg in ecg_list:
        with st.expander(f"ECG - {ecg['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.metric("Paciente", ecg['filename'].split('_')[2])
                st.metric("Fecha", ecg['timestamp'].strftime('%Y-%m-%d'))
                
                with open(ecg['path'], "rb") as f:
                    st.download_button(
                        "Descargar ECG",
                        data=f,
                        file_name=ecg['filename'],
                        mime="application/pdf"
                    )
            
            with col2:
                with open(ecg['path'], "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000"></iframe>',
                        unsafe_allow_html=True
                    )
            
            try:
                os.unlink(ecg['path'])
            except:
                pass

def main():
    st.set_page_config(
        page_title="Visualizador de Signos Vitales",
        layout="wide"
    )

    # Logo y título
    if Path(CONFIG.LOGO_PATH).exists():
        st.image(Image.open(CONFIG.LOGO_PATH), width=200)

    st.title("📊 Visualizador de Signos Vitales")
    st.markdown("---")

    # Carga de datos
    data = load_data()
    if data.empty:
        st.warning("No hay registros disponibles")
        return

    # Tabla principal
    st.subheader("Registros de Pacientes")
    display_data = data.assign(
        Seleccionar=False,
        timestamp=data['timestamp'].dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    # Columnas a mostrar (añadimos 'signos_alterados')
    columns_to_show = [
        'timestamp', 'id_paciente_formatted', 'nombre_paciente',
        'presion_arterial', 'temperatura', 'oximetria', 'estado', 
        'signos_alterados', 'Seleccionar'
    ]

    edited_df = st.data_editor(
        display_data[columns_to_show],
        column_config={
            "timestamp": "Fecha/Hora",
            "id_paciente_formatted": "Teléfono",
            "nombre_paciente": "Nombre",
            "presion_arterial": "Presión (mmHg)",
            "temperatura": "Temp. (°C)",
            "oximetria": "Oximetría (%)",
            "estado": "Estado",
            "signos_alterados": "Variación",
            "Seleccionar": st.column_config.CheckboxColumn("Ver ECG")
        },
        hide_index=True,
        disabled=["timestamp", "id_paciente_formatted", "nombre_paciente",
                 "presion_arterial", "temperatura", "oximetria", "estado", "signos_alterados"]
    )

    # Mostrar ECGs seleccionados
    selected = edited_df[edited_df['Seleccionar']].iloc[:1]
    if not selected.empty:
        patient_id = ''.join(filter(str.isdigit, selected['id_paciente_formatted'].iloc[0]))
        st.markdown("---")
        st.subheader(f"ECGs del Paciente: {patient_id}")

        if ecg_list := SSHManager.get_all_ecgs(patient_id):
            display_ecg_table(ecg_list)

if __name__ == "__main__":
    main()
