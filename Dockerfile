# 1. Usamos Alpine Linux con Python 3.9 (Muy ligero, ~50MB base)
FROM python:3.9-alpine

# 2. Variables de entorno para que Python no genere archivos caché (.pyc)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. INSTALACIÓN DE DEPENDENCIAS DEL SISTEMA
# - git: Para clonar el repo
# - gcc, g++, musl-dev: Compiladores necesarios para instalar 'pandas' en Alpine
# - libffi-dev, openssl-dev: Necesarios para 'spotipy' (criptografía)
RUN apk add --no-cache \
    git \
    gcc \
    g++ \
    musl-dev \
    libffi-dev \
    openssl-dev \
    make

# 5. CLONAR EL REPOSITORIO
# Clona la rama 'main' de tu repositorio en la carpeta actual (/app)
# IMPORTANTE: Asegúrate de que la URL es correcta y el repo es público.
RUN git clone https://github.com/glmbxecurity/ultimate-spotibot.git .

# 6. INSTALAR LIBRERÍAS PYTHON
# Actualizamos pip e instalamos lo que diga requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 7. PREPARAR SISTEMA DE ARCHIVOS
# Creamos la carpeta para la persistencia de datos
RUN mkdir /data

# 8. COMANDO DE INICIO
# Al iniciar el contenedor, ejecuta el script del bot.
# Como hemos clonado el repo, la ruta relativa es "docker/bot_spotibot_docker.py"
CMD ["python3", "docker/bot_spotibot_docker.py"]
