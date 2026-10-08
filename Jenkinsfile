pipeline {
    agent { label 'linux-docker' }
    
    environment {
        ACR_NAME = "cyberforensicsacr"
        IMAGE_NAME = "${ACR_NAME}.azurecr.io/digital-forensics-platform"
        IMAGE_TAG = "build-${BUILD_NUMBER}"
        REGISTRY_CREDENTIALS = "acr-credentials"
        APP_SECRET_CREDENTIALS = "forensics-secret-key"
        DATABASE_CREDENTIALS = "forensics-database-uri"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Install Dependencies') {
            steps {
                sh 'python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt'
            }
        }
        
        stage('Unit Tests') {
            steps {
                sh '.venv/bin/python -m pytest tests/'
            }
        }
        
        stage('Build Docker Image') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
            }
        }
        
        stage('Security Scanning') {
            steps {
                sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL ${IMAGE_NAME}:${IMAGE_TAG}'
            }
        }
        
        stage('Push to Azure Container Registry') {
            steps {
                withCredentials([usernamePassword(credentialsId: "${REGISTRY_CREDENTIALS}", passwordVariable: 'ACR_PASSWORD', usernameVariable: 'ACR_USERNAME')]) {
                    sh 'printf %s "$ACR_PASSWORD" | docker login ${ACR_NAME}.azurecr.io --username "$ACR_USERNAME" --password-stdin'
                    sh 'docker push ${IMAGE_NAME}:${IMAGE_TAG}'
                }
            }
        }
        
        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    string(credentialsId: "${APP_SECRET_CREDENTIALS}", variable: 'APP_SECRET_KEY'),
                    string(credentialsId: "${DATABASE_CREDENTIALS}", variable: 'DATABASE_URI')
                ]) {
                    sh '''
                        set +x
                        set -eu
                        if [ "${#APP_SECRET_KEY}" -lt 32 ]; then
                            echo "The configured application secret must be at least 32 characters." >&2
                            exit 1
                        fi
                        case "$DATABASE_URI" in
                            postgresql://*|postgresql+psycopg2://*) ;;
                            *)
                                echo "The configured database URI must use PostgreSQL." >&2
                                exit 1
                                ;;
                        esac
                        kubectl apply -f k8s/namespace.yaml
                        kubectl apply -f k8s/configmap.yaml
                        kubectl apply -f k8s/pvc.yaml

                        secret_file="$(mktemp)"
                        trap 'rm -f "$secret_file"' EXIT
                        chmod 600 "$secret_file"
                        printf 'SECRET_KEY=%s\\nDATABASE_URI=%s\\n' "$APP_SECRET_KEY" "$DATABASE_URI" > "$secret_file"
                        kubectl create secret generic forensics-secrets \
                            --namespace digital-forensics \
                            --from-env-file="$secret_file" \
                            --dry-run=client -o yaml | kubectl apply -f -

                        sed "s|image: .*|image: ${IMAGE_NAME}:${IMAGE_TAG}|" k8s/deployment.yaml | kubectl apply -f -
                        kubectl apply -f k8s/service.yaml
                        kubectl apply -f k8s/ingress.yaml
                        kubectl rollout status deployment/forensics-app \
                            --namespace digital-forensics --timeout=180s
                    '''
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        success {
            echo "Pipeline executed successfully!"
        }
        failure {
            echo "Pipeline failed. Check logs for details."
        }
    }
}
