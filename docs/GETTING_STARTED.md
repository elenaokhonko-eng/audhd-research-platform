# Local platform foundation

## Activate Python

```powershell
.\.venv\Scripts\Activate.ps1
```

## Start local infrastructure

```powershell
docker compose up -d postgres redis minio
```

## Start the API

```powershell
uvicorn platform_app.api:app --reload --port 8000
```

## Start the worker

```powershell
celery -A platform_app.worker.celery_app worker --loglevel=INFO
```

On Windows development machines, Celery may require `--pool=solo`. Production workers should run in Linux containers.

## Start the dashboard

```powershell
streamlit run streamlit_app.py
```

The current dashboard is a validated foundation. Database migrations, authentication, literature connectors, claim verification, artifact generation, and the publishing adapter are the next implementation slices.
