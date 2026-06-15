pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds() }
  environment {
    IMAGE     = "excel-api:latest"
    CONTAINER = "excel-api"
    NETWORK   = "well_config_net"
    GIT_URL   = "git@github-db-excel:gjcardonam/db_excel_sync_api.git"
    GIT_BRANCH= "master"
  }
  stages {
    stage('Checkout') {
      steps { git branch: "${GIT_BRANCH}", url: "${GIT_URL}" }
    }
    stage('Build image') {
      steps { sh 'docker build -t ${IMAGE} .' }
    }
    stage('Smoke-test (sin tocar el viejo)') {
      steps {
        withCredentials([file(credentialsId: 'db-excel-sync-api-env', variable: 'ENVFILE')]) {
          sh '''
            set -e
            docker rm -f ${CONTAINER}-smoke 2>/dev/null || true
            docker run -d --name ${CONTAINER}-smoke --network ${NETWORK} \
              --env-file "$ENVFILE" ${IMAGE}
            echo "Esperando que la imagen nueva levante uvicorn..."
            OK=0
            for i in $(seq 1 20); do
              if docker exec ${CONTAINER}-smoke sh -c \
                'python - <<PY
import urllib.request,urllib.error,sys
try: urllib.request.urlopen("http://localhost:8484/",timeout=3); sys.exit(0)
except urllib.error.HTTPError: sys.exit(0)
except Exception: sys.exit(1)
PY'; then OK=1; echo "Imagen nueva OK"; break; fi
              sleep 2
            done
            docker logs --tail 30 ${CONTAINER}-smoke || true
            docker rm -f ${CONTAINER}-smoke || true
            [ "$OK" = "1" ] || { echo "Imagen nueva NO levanta. Abortando, viejo intacto."; exit 1; }
          '''
        }
      }
    }
    stage('Promote (swap)') {
      steps {
        withCredentials([file(credentialsId: 'db-excel-sync-api-env', variable: 'ENVFILE')]) {
          sh '''
            set -e
            docker rm -f ${CONTAINER} 2>/dev/null || true
            docker run -d --name ${CONTAINER} \
              --network ${NETWORK} -p 8484:8484 \
              --env-file "$ENVFILE" --restart always ${IMAGE}
            echo "Verificando el contenedor promovido..."
            sleep 3
            docker ps --filter name=^/${CONTAINER}$ --format '{{.Names}} {{.Status}} {{.Ports}}'
          '''
        }
      }
    }
  }
  post {
    failure { echo "Deploy FALLÓ. Revisa logs; el servicio previo pudo quedar activo." }
    success { echo "Deploy OK." }
  }
}