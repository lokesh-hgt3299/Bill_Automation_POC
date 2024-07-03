# Bill_Automation_POC

Run the FastAPI application using uvicorn:
    uvicorn app:app --reload --port 8006

Run Celery worker for tasks:
    celery -A tasks worker --loglevel=info --logfile logs/celery.log -P threads