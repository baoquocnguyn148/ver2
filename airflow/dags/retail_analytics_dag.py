from __future__ import annotations

import os
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/opt/airflow/project")
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")

DEFAULT_ENV = {
    "LOCAL_MODE": os.getenv("LOCAL_MODE", "false"),
    "PYTHONIOENCODING": "utf-8",
    "PYTHONPATH": PROJECT_ROOT,
}


def task(task_id: str, command: str) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON_BIN} {command}",
        env=DEFAULT_ENV,
    )


with DAG(
    dag_id="retail_analytics_cloud_pipeline",
    description="Optional Airflow DAG for the Retail Analytics ETL/ELT pipeline.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["retail", "aws", "etl", "elt"],
) as dag:
    run_etl = task("run_python_etl", "data_process.py")
    run_quality = task("run_data_quality", "scripts/run_data_quality.py")
    run_ml = task("run_ml_pipeline", "ml_pipeline.py")
    register_glue = task("register_glue_tables", "scripts/register_glue_tables.py")
    repair_athena = task("repair_athena_partitions", "scripts/repair_athena_tables.py")
    create_views = task("create_athena_views", "scripts/create_athena_views.py")
    validate_athena = task("validate_athena", "scripts/validate_athena.py")

    run_etl >> run_quality >> run_ml >> register_glue >> repair_athena >> create_views >> validate_athena

