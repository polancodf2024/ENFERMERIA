import streamlit as st
import pandas as pd
import datetime
import os
from PIL import Image
import warnings
import paramiko
from io import StringIO, BytesIO

# Configuración inicial
LOGO = "escudo_COLOR.jpg"

# Cargar configuración desde secrets.toml
try:
    # Configuración SFTP
    REMOTE_HOST = st.secrets["remote_host"]
    REMOTE_USER = st.secrets["remote_user"]
    REMOTE_PASSWORD = st.secrets["remote_password"]
    REMOTE_PORT = st.secrets["remote_port"]
    REMOTE_BASE_DIR = st.secrets["remote_dir"]
    REMOTE_CSV_FILE = f"{REMOTE_BASE_DIR}/{st.secrets['csv_materias_file']}"
    REMOTE_ECG_DIR = f"{REMOTE_BASE_DIR}/ecg_pdfs"
    
    # Configuración de email
    SMTP_SERVER = st.secrets["smtp_server"]
    SMTP_PORT = st.secrets["smtp_port"]
    EMAIL_USER = st.secrets["email_user"]
    EMAIL_PASSWORD = st.secrets["email_password"]
    NOTIFICATION_EMAIL = st.secrets["notification_email"]
    
except KeyError as e:
    st.error(f"Error de configuración: Falta la clave {e} en secrets.toml")
    st.stop()

# Suprimir advertencias
warnings.filterwarnings('ignore', category=FutureWarning)

# Conexión SFTP (con manejo de errores mejorado)
def get_sftp_connection():
    try:
        transport = paramiko.Transport((REMOTE_HOST, REMOTE_PORT))
        transport.connect(username=REMOTE_USER, password=REMOTE_PASSWORD)
        return paramiko.SFTPClient.from_transport(transport)
    except Exception as e:
        st.error(f"Error de conexión SFTP: {str(e)}")
        return None

# Verificar/crear estructura remota
def init_remote_structure(sftp):
    try:
        # Crear directorio ECG si no existe
        try:
            sftp.stat(REMOTE_ECG_DIR)
        except IOError:
            sftp.mkdir(REMOTE_ECG_DIR)
        
        # Crear archivo CSV si no existe
        try:
            sftp.stat(REMOTE_CSV_FILE)
        except IOError:
            with sftp.open(REMOTE_CSV_FILE, 'w') as f:
                f.write("Fecha_Hora,ID_Paciente,Nombre_Completo,Presion_Arterial,Temperatura,Oximetria,ECG\n")
    except Exception as e:
        st.error(f"Error al inicializar estructura remota: {str(e)}")
        raise

# Mostrar logo
def mostrar_logo():
    try:
        imagen = Image.open(LOGO)
        col1, col2, col3 = st.columns([1,3,1])
        with col2:
            st.image(imagen, width=150)
    except FileNotFoundError:
        st.warning("Logo no encontrado")
    except Exception as e:
        st.error(f"Error al cargar el logo: {str(e)}")

# Guardar registro en servidor remoto
def guardar_registro_remoto(datos):
    sftp = get_sftp_connection()
    if sftp is None:
        return False
    
    try:
        init_remote_structure(sftp)
        
        # Leer CSV existente
        try:
            with sftp.open(REMOTE_CSV_FILE, 'r') as f:
                df = pd.read_csv(f)
        except:
            df = pd.DataFrame(columns=datos.keys())
        
        # Añadir nuevo registro
        nuevo_df = pd.DataFrame([datos])
        df = pd.concat([df, nuevo_df], ignore_index=True)
        
        # Guardar CSV actualizado
        with sftp.open(REMOTE_CSV_FILE, 'w') as f:
            df.to_csv(f, index=False)
        
        return True
    except Exception as e:
        st.error(f"Error al guardar registro: {str(e)}")
        return False
    finally:
        sftp.close()

# Subir archivo PDF al servidor remoto
def subir_pdf_remoto(file_buffer, filename):
    sftp = get_sftp_connection()
    if sftp is None:
        return False
    
    try:
        remote_path = f"{REMOTE_ECG_DIR}/{filename}"
        with sftp.open(remote_path, 'wb') as f:
            f.write(file_buffer.getvalue())
        return True
    except Exception as e:
        st.error(f"Error al subir archivo ECG: {str(e)}")
        return False
    finally:
        sftp.close()

# Interfaz de usuario
mostrar_logo()
st.title("📊 Sistema de Registro Médico")
st.subheader("Ingrese los datos del paciente")

with st.form("registro_form"):
    # Datos personales
    id_paciente = st.text_input("Identificación del Paciente", placeholder="Ej: 593991234567")
    nombre_completo = st.text_input("Nombre Completo", placeholder="Ej: Juan Pérez")
    
    # Signos vitales
    col1, col2, col3 = st.columns(3)
    with col1:
        presion_arterial = st.text_input("Presión Arterial", placeholder="Ej: 120/80")
    with col2:
        temperatura = st.number_input("Temperatura (°C)", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
    with col3:
        oximetria = st.number_input("Oximetría (%)", min_value=70, max_value=100, value=98)
    
    # ECG
    ecg_pdf = st.file_uploader("Subir Electrocardiograma", type=["pdf"])
    
    submitted = st.form_submit_button("Guardar Datos")
    
    if submitted:
        if not id_paciente or not nombre_completo:
            st.error("❌ La identificación y nombre completo son obligatorios")
        else:
            ahora = datetime.datetime.now()
            estado_ecg = "N"
            
            # Procesamiento del ECG
            if ecg_pdf is not None:
                nombre_archivo = f"{ahora.strftime('%Y%m%d%H%M')}_{id_paciente}_ECG.pdf"
                if subir_pdf_remoto(ecg_pdf, nombre_archivo):
                    estado_ecg = "E"
                else:
                    estado_ecg = "Error"
            
            # Crear registro
            datos_registro = {
                "Fecha_Hora": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                "ID_Paciente": id_paciente,
                "Nombre_Completo": nombre_completo,
                "Presion_Arterial": presion_arterial,
                "Temperatura": temperatura,
                "Oximetria": oximetria,
                "ECG": estado_ecg
            }
            
            if guardar_registro_remoto(datos_registro):
                st.success("✅ Datos guardados exitosamente en el servidor remoto")
                st.balloons()

# Visualización de datos
if st.checkbox("Mostrar registros almacenados"):
    try:
        sftp = get_sftp_connection()
        if sftp:
            with sftp.open(REMOTE_CSV_FILE, 'r') as f:
                df = pd.read_csv(f)
            
            if not df.empty:
                # Función para resaltar ECG
                def resaltar_ecg(val):
                    color = '#90EE90' if val == 'E' else '#FFCCCB'
                    return f'background-color: {color}'
                
                st.dataframe(
                    df.style.applymap(resaltar_ecg, subset=['ECG']),
                    height=400
                )
                
                # Estadísticas
                st.subheader("Resumen de Datos")
                total = len(df)
                con_ecg = (df['ECG'] == 'E').sum()
                
                cols = st.columns(3)
                cols[0].metric("Total Pacientes", total)
                cols[1].metric("Con ECG", f"{con_ecg} ({con_ecg/total*100:.1f}%)")
                cols[2].metric("Sin ECG", f"{total-con_ecg} ({(total-con_ecg)/total*100:.1f}%)")
                
                # Gráfico
                st.bar_chart(df['ECG'].value_counts())
            else:
                st.warning("No hay registros almacenados aún")
            sftp.close()
    except Exception as e:
        st.error(f"No se pudieron cargar los datos: {str(e)}")

# Información del sistema
if st.checkbox("Mostrar información del sistema"):
    st.write("**Configuración actual:**")
    
    st.write("📁 **Almacenamiento remoto:**")
    st.write(f"- Servidor: {REMOTE_HOST}:{REMOTE_PORT}")
    st.write(f"- Directorio: {REMOTE_BASE_DIR}")
    
    st.write("📧 **Notificaciones:**")
    st.write(f"- Servidor SMTP: {SMTP_SERVER}")
    st.write(f"- Email de notificación: {NOTIFICATION_EMAIL[:3]}•••@{NOTIFICATION_EMAIL.split('@')[-1]}")
    
    try:
        sftp = get_sftp_connection()
        if sftp:
            try:
                csv_info = sftp.stat(REMOTE_CSV_FILE)
                st.write(f"\n**Archivo de datos:** {csv_info.st_size} bytes, {len(pd.read_csv(sftp.open(REMOTE_CSV_FILE, 'r')))} registros")
            except:
                st.write("\n**Archivo de datos:** No encontrado")
            
            try:
                ecg_files = sftp.listdir(REMOTE_ECG_DIR)
                st.write(f"**Archivos ECG almacenados:** {len(ecg_files)}")
            except:
                st.write("**Directorio ECG:** No encontrado")
            
            sftp.close()
    except:
        st.write("\n⚠️ No se pudo conectar al servidor remoto")
