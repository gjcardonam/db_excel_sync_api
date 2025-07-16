# Imagen base ligera con Python
FROM python:3.11-slim

# Evita preguntas interactivas al instalar paquetes
ENV DEBIAN_FRONTEND=noninteractive

# Establece el directorio de trabajo en el contenedor
WORKDIR /app

# Copia solo el archivo de requisitos y lo instala primero (mejor cache)
COPY requirements.txt .

# Instala dependencias del sistema necesarias para pandas, psycopg2 y Excel
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        python3-dev \
        build-essential \
        libffi-dev \
        libssl-dev \
        curl \
        && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove gcc build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copia el resto del código
COPY . .

# Expone el puerto de FastAPI
EXPOSE 8484

# Comando de inicio (ajustado al path de tu app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8484"]
