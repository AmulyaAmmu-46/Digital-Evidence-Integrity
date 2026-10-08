pipeline {
    agent { label 'windows-docker' }

    options {
        skipDefaultCheckout(true)
    }

    environment {
        ACR_NAME = "cyberforensicsacr"
        IMAGE_NAME = "${ACR_NAME}.azurecr.io/digital-forensics-platform"
        IMAGE_TAG = "build-${BUILD_NUMBER}"
        TRIVY_IMAGE = "aquasec/trivy:0.75.0"
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

        stage('Validate Windows Docker Agent') {
            steps {
                bat '''
@echo off
docker version
if errorlevel 1 exit /b %errorlevel%
'''
            }
        }

        stage('Unit Tests') {
            steps {
                bat '''
@echo off
docker run --rm --mount "type=bind,source=%WORKSPACE%,target=/workspace,readonly" --workdir /workspace python:3.12-slim sh -c "python -m venv /tmp/venv && /tmp/venv/bin/python -m pip install --disable-pip-version-check -r requirements-dev.txt && /tmp/venv/bin/python -m pytest -p no:cacheprovider --basetemp /tmp/pytest-tmp tests/"
if errorlevel 1 exit /b %errorlevel%
'''
            }
        }

        stage('Build Docker Image') {
            steps {
                bat '''
@echo off
docker build -t "%IMAGE_NAME%:%IMAGE_TAG%" .
if errorlevel 1 exit /b %errorlevel%
'''
            }
        }

        stage('Security Scanning') {
            steps {
                bat '''
@echo off
docker save --output "%WORKSPACE%\\digital-evidence-image.tar" "%IMAGE_NAME%:%IMAGE_TAG%"
if errorlevel 1 exit /b %errorlevel%
docker run --rm --mount "type=bind,source=%WORKSPACE%,target=/work,readonly" "%TRIVY_IMAGE%" image --input /work/digital-evidence-image.tar --exit-code 1 --severity HIGH,CRITICAL
if errorlevel 1 exit /b %errorlevel%
'''
            }
        }

        stage('Push to Azure Container Registry') {
            steps {
                withCredentials([usernamePassword(credentialsId: "${REGISTRY_CREDENTIALS}", passwordVariable: 'ACR_PASSWORD', usernameVariable: 'ACR_USERNAME')]) {
                    bat 'powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts\\jenkins-push-acr.ps1'
                    bat 'docker push "%IMAGE_NAME%:%IMAGE_TAG%"'
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    string(credentialsId: "${APP_SECRET_CREDENTIALS}", variable: 'APP_SECRET_KEY'),
                    string(credentialsId: "${DATABASE_CREDENTIALS}", variable: 'DATABASE_URI')
                ]) {
                    bat 'powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts\\jenkins-deploy-k8s.ps1'
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
