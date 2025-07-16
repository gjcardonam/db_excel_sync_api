# Imagen base ligera con Python
FROM python:3.11-slim

# Establece el directorio de trabajo en el contenedor
WORKDIR /app

# Copia los archivos de requisitos primero para aprovechar el cache
COPY requirements.txt .

# Instala dependencias del sistema necesarias para pandas, psycopg2 y Excel
RUN apt-get update && \
    apt-get install -y gcc libpq-dev python3-dev build-essential && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get remove -y gcc build-essential && \
    apt-get autoremove -y && \
    apt-get clean

# Copia el resto del código
COPY . .

# Expone el puerto por defecto de la API
EXPOSE 8484

# Comando de inicio (puedes usar main:app o app.main:app según tu estructura)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8484"]