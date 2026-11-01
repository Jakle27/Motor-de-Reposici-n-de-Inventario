FROM apache/airflow:3.1.0-python3.11

COPY requirements-airflow.txt /tmp/requirements-airflow.txt

RUN pip install --no-cache-dir \
    "apache-airflow==3.1.0" \
    -r /tmp/requirements-airflow.txt

WORKDIR /opt/project
