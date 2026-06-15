pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds() }
  environment {
    IMAGE      = "excel-api:latest"
    CONTAINER  = "excel-api"
    NETWORK    = "well_config_net"
    GIT_URL    = "git@github-db-excel:gjcardonam/db_excel_sync_api.git"
    GIT_BRANCH = "master"
  }
  stages {
    stage('Checkout') {
      steps { git branch: "${GIT_BRANCH}", url: "${GIT_URL}" }
    }
    stage('Build image') {
      steps { sh 'docker build -t ${IMAGE} .' }
    }
    stage('Deploy (swap)') {
      steps {
        withCredentials([file(credentialsId: 'db-excel-sync-api-env', variable: 'ENVFILE')]) {
          sh '''
            set -e
            docker rm -f ${CONTAINER} 2>/dev/null || true
            docker run -d --name ${CONTAINER} \
              --network ${NETWORK} -p 8484:8484 \
              --env-file "$ENVFILE" --restart always ${IMAGE}

            sleep 4
            if [ "$(docker inspect -f '{{.State.Running}}' ${CONTAINER})" != "true" ]; then
              echo "El contenedor nuevo no quedó arriba. Logs:"
              docker logs --tail 40 ${CONTAINER} || true
              exit 1
            fi
            docker ps --filter name=^/${CONTAINER}$ --format '{{.Names}} | {{.Status}} | {{.Ports}}'
          '''
        }
      }
    }
  }
}