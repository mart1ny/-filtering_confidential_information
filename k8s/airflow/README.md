# Airflow on Kubernetes

Минимальный single-node набор для Airflow:
- `airflow-postgres`
- `airflow-init` job
- `airflow-webserver`
- `airflow-scheduler`

UI публикуется через `NodePort`:
- `30082`

Манифесты используют `hostPath` и рассчитаны на текущий single-node стенд.
