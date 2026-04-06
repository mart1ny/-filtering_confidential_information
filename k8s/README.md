# Kubernetes deploy (backend + frontend)

Этот набор манифестов переносит только online-часть проекта в Kubernetes:
- backend (`app`)
- frontend (`frontend`)

Airflow пока остается вне Kubernetes.

## Что нужно перед применением

1. Скопировать `secret.example.yaml` в `secret.yaml` и заполнить значения.
2. При необходимости отредактировать хост в `ingress.example.yaml`.
3. Убедиться, что кластер может тянуть образы из GHCR.

## Применение

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -k k8s/
```

Если нужен Ingress:

```bash
kubectl apply -f k8s/ingress.example.yaml
```

## Что внутри

- `ConfigMap` хранит не-секретные runtime-параметры.
- `Secret` хранит ключи S3, DB и остальные чувствительные переменные.
- `app` получает env через `envFrom`.
- `frontend` продолжает проксировать запросы в service `app:8000`.

## Проверка

```bash
kubectl get pods -n confidential-filter
kubectl get svc -n confidential-filter
kubectl logs deployment/app -n confidential-filter
kubectl logs deployment/frontend -n confidential-filter
```
