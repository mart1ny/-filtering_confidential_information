# Kubernetes deploy (backend + frontend)

Этот набор манифестов переносит только online-часть проекта в Kubernetes:
- backend (`app`)
- frontend (`frontend`)

Airflow пока остается вне Kubernetes.

## Что нужно перед применением

1. Скопировать `secret.example.yaml` в `secret.yaml` и заполнить значения.
2. Убедиться, что кластер может тянуть образы из GHCR.
3. Открыть `NodePort` порты на сервере, если включен firewall:
   - `30080/tcp` для backend
   - `30081/tcp` для frontend

## Применение

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -k k8s/
```

## Что внутри

- `ConfigMap` хранит не-секретные runtime-параметры.
- `Secret` хранит ключи S3, DB и остальные чувствительные переменные.
- `app` получает env через `envFrom`.
- `frontend` продолжает проксировать запросы в service `app:8000`.
- `Service` опубликованы как `NodePort`, чтобы не зависеть от ingress-контроллера.

## Проверка

```bash
kubectl get pods -n confidential-filter
kubectl get svc -n confidential-filter
kubectl logs deployment/app -n confidential-filter
kubectl logs deployment/frontend -n confidential-filter
```

Внешние адреса после запуска:

```bash
http://<SERVER_IP>:30080/health
http://<SERVER_IP>:30080/docs
http://<SERVER_IP>:30081
```

Если позже потребуется ingress, можно отдельно применить `ingress.example.yaml`,
но для первого запуска он не нужен.
