"""Audit phase 1 (jetable) : tests plateforme exécutés DANS un job serverless.

Argument : b4 | b9 | b10 | b11. Aucune valeur secrète n'est jamais affichée.
"""
import json
import sys
import time

TEST = sys.argv[1]
t0 = time.time()


def report(**kw):
    kw["test"] = TEST
    kw["elapsed_s"] = round(time.time() - t0, 2)
    print("AUDIT_RESULT " + json.dumps(kw, default=str))


if TEST == "b4":
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    spark.sql("INSERT INTO atlas.bronze.audit_test VALUES (2, 'serverless-job', current_timestamp())")
    n = spark.sql("SELECT count(*) AS n FROM atlas.bronze.audit_test").collect()[0]["n"]
    report(status="OK", rows_in_table=n, spark_version=spark.version)

elif TEST == "b9":
    import mlflow

    mlflow.set_tracking_uri("databricks")
    exp_name = "/Users/axelcedrickaboua@gmail.com/atlas-audit-mlflow"
    mlflow.set_experiment(exp_name)
    with mlflow.start_run(run_name="audit-b9") as run:
        mlflow.log_param("audit_param", "phase1")
        mlflow.log_metric("audit_metric", 0.42)
        mlflow.log_dict({"hello": "atlas"}, "audit_artifact.json")
    got = mlflow.get_run(run.info.run_id)
    report(status="OK", mlflow_version=mlflow.__version__, experiment=exp_name,
           run_id=run.info.run_id, params=got.data.params, metrics=got.data.metrics)

elif TEST == "b10":
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

    w = WorkspaceClient()
    name = sys.argv[2] if len(sys.argv) > 2 else "databricks-meta-llama-3-1-8b-instruct"
    resp = w.serving_endpoints.query(
        name=name,
        messages=[ChatMessage(role=ChatMessageRole.USER, content="Reply with the single word: pong")],
        max_tokens=10,
    )
    report(status="OK", endpoint=name, answer=resp.choices[0].message.content[:50],
           usage=resp.usage.as_dict() if resp.usage else None)

elif TEST == "b11":
    from databricks.sdk.runtime import dbutils

    dummy = dbutils.secrets.get("atlas-audit-dummy", "dummy_value")
    key = dbutils.secrets.get("atlas-audit", "twelvedata_api_key")
    # On ne publie que des propriétés non sensibles.
    report(status="OK", dummy_matches=(dummy == "valeur-factice-audit"),
           provider_key_present=bool(key), provider_key_length=len(key))
