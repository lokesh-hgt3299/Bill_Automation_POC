# Bill_Automation_POC

Run app.py using this command uvicorn app:app --reload --port 8006
Run tasks.py using this command celery -A tasks worker --loglevel=info --logfile logs/celery.log -P threads