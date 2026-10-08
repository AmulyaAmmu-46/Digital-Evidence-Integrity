# Cloud-Native Digital Evidence Integrity and Chain-of-Custody Framework

## Project Overview
This project is an academic prototype for managing the lifecycle of digital forensic evidence. It emphasizes **evidence integrity**, **chain of custody**, **role-based access control (RBAC)**, and a comprehensive **audit trail** in a cloud-native architecture.

**Note:** This is an academic project and is *not* intended to replace certified commercial forensic software or ensure legal admissibility on its own.

## Technical Architecture
The application follows a modular, cloud-native architecture:
*   **Frontend:** HTML5, CSS3, Bootstrap 5 (Dark theme), Jinja2 templates.
*   **Backend:** Python 3.9+, Flask, Flask-SQLAlchemy, Flask-Login.
*   **Database:** PostgreSQL (Production/Docker) / SQLite (Local dev).
*   **Integrity Verification:** SHA-256 cryptographic hashing.
*   **Storage:** Local Persistent Volumes (abstracted for future Azure Blob Storage migration).

## Cloud/DevOps Workflow
This project is designed for modern cloud deployments:
1.  **Version Control:** Git & GitHub.
2.  **CI/CD (Jenkins):** A Jenkins pipeline (`Jenkinsfile`) automates checking out code, installing dependencies, running `pytest`, building the Docker image, and pushing to a registry.
3.  **Containerization (Docker):** A lightweight `Dockerfile` uses Gunicorn to serve the Flask app securely via a non-root user. `docker-compose.yml` provides easy local orchestration.
4.  **Container Registry (Azure ACR):** Images are pushed to Azure Container Registry.
5.  **Orchestration (Kubernetes):** Declarative YAML manifests (`k8s/`) handle Namespaces, ConfigMaps, Secrets, PVCs, Deployments, Services, and Ingress routing for scalable deployment (e.g., on Azure Kubernetes Service - AKS).

## Features
*   **Role-Based Access Control:** Admin, Investigator, Auditor, Viewer.
*   **Case Management:** Create, assign, and track investigation cases.
*   **Evidence Registration & Secure Upload:** Safe file handling, automatic SHA-256 calculation.
*   **Integrity Verification:** On-demand recalculation of evidence hashes to detect tampering.
*   **Chain of Custody:** Immutable timeline tracking all evidence lifecycle events.
*   **Audit Logging:** Centralized tracking of authentication, resource access, and system events.

## Local Setup (Without Docker)
In PowerShell, run from the project directory. For a first-time setup, create a virtual environment, install dependencies, and create the administrator account before starting the server:

```powershell
Set-Location F:\Cyber\project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python scripts/seed.py
python run.py
```

The seed command creates missing database tables and prompts for administrator credentials. On later runs, activate the existing environment and start the server with `python run.py`. The local SQLite database and upload directory use development defaults; set `SECRET_KEY` in `.env` for a stable local session key.

The application listens on `0.0.0.0:5000` by default. Set `HOST` or `PORT` in the environment to override those values.

## Docker Setup (Local)
1. Copy `.env.example` to `.env`; set a random `SECRET_KEY` and a strong `POSTGRES_PASSWORD` there. Keep the same `SECRET_KEY` when restarting or recreating the container: all Gunicorn workers must use the same key to preserve login sessions. `.env` is local configuration and must not be committed.
2. Run `docker-compose up --build -d`.
3. For a new database, create the administrator with `docker-compose exec web python -m scripts.seed` and enter your credentials when prompted.
4. For an existing database upgraded from an older version, run `docker-compose exec web python scripts/upgrade_case_viewer_grants.py` once.
5. Access the application at `http://localhost:5000`.

To run the image directly with local SQLite instead of Compose/PostgreSQL:

```powershell
docker build -t cloud-evidence:local .
$secret = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
docker run --rm --name cloud-evidence -p 5000:5000 `
  -e APP_ENV=development `
  -e "SECRET_KEY=$secret" `
  -e DATABASE_URI=sqlite:////app/data/forensics.db `
  -e UPLOAD_FOLDER=/app/uploads `
  -v evidence_database:/app/data `
  -v evidence_uploads:/app/uploads `
  cloud-evidence:local
```

In another terminal, create the initial schema and administrator account:

```powershell
docker exec -it cloud-evidence python -m scripts.seed
```

## Azure Container Registry (ACR) Instructions
```bash
# 1. Create ACR
az acr create --resource-group MyResourceGroup --name cyberforensicsacr --sku Basic

# 2. Authenticate
az acr login --name cyberforensicsacr

# 3. Build & Tag
docker build -t cyberforensicsacr.azurecr.io/digital-forensics-platform:build-local .

# 4. Push
docker push cyberforensicsacr.azurecr.io/digital-forensics-platform:build-local
```

## Azure Kubernetes Service (AKS) Deployment
The Jenkins pipeline expects a Linux agent labeled `linux-docker` with Python 3, Docker, Trivy, `kubectl`, and `sed`. Configure its `kubectl` context for the target AKS cluster and grant it permission to deploy into the `digital-forensics` namespace.

1. Create an Azure resource group, an ACR named `cyberforensicsacr` (or update the `ACR_NAME` in `Jenkinsfile`), an AKS cluster, and a PostgreSQL database reachable from AKS. Attach ACR to AKS: `az aks update -n MyCluster -g MyResourceGroup --attach-acr cyberforensicsacr`.
2. Configure the AKS default storage class for persistent `ReadWriteOnce` volumes. This initial deployment intentionally runs one replica because evidence is stored on that volume. Do not scale it to multiple replicas unless evidence storage is moved to a shared storage service with suitable multi-writer semantics.
3. Install and configure an NGINX Ingress controller in AKS. Point a DNS name at its endpoint and configure TLS before exposing production data. The manifest's `nginx` ingress class is not installed by this project.
4. In Jenkins, create:
   - Username/password credential ID `acr-credentials` with permission to push to the registry.
   - Secret Text credential ID `forensics-secret-key` containing a random secret of at least 32 characters.
   - Secret Text credential ID `forensics-database-uri` containing the PostgreSQL SQLAlchemy URI.
5. Push the project to the configured GitHub repository and configure Jenkins SCM/webhook integration. Run the pipeline. It runs tests, builds the image, blocks on Trivy HIGH/CRITICAL findings, pushes a build-tagged image, creates/updates the Kubernetes Secret from Jenkins credentials, applies the non-secret manifests, and waits for the deployment's HTTP readiness probe.

## Account Setup
The application does not include default login credentials. Create the administrator account with `python scripts/seed.py` and provide the credentials interactively. Use a unique password of at least 12 characters. The setup command creates missing tables, preserves existing cases and evidence, and disables accounts from the old demo seed. It also resets the supplied administrator's password, so use it only for initial setup or an intentional password reset. Existing databases must run `python scripts/upgrade_case_viewer_grants.py` once to add the Viewer-grant table and explicit custody result column.

After the first successful deployment and database creation, initialize a new database once with `kubectl exec -it deployment/forensics-app -n digital-forensics -- python scripts/seed.py`. For an existing database, run `kubectl exec deployment/forensics-app -n digital-forensics -- python scripts/upgrade_case_viewer_grants.py` once instead of reseeding. Do not run either command on every deployment. The Jenkins pipeline provisions the Kubernetes Secret from its protected credentials; do not commit secret values or apply a placeholder Secret manifest.

Administrators can grant and revoke Viewer access per case. Investigators can access cases they created or that are assigned to them; Auditors can review all investigation records but cannot edit them.

## Future Enhancements
*   Azure Blob Storage integration for evidence files.
*   Azure Key Vault for secret management.
*   Advanced SIEM integration (e.g., Azure Sentinel).
*   Multi-factor authentication (MFA).
*   AI-assisted log and evidence classification.
# Digital-Evidence-Integrity
