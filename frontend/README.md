# Frontend (React)

Небольшой чат-интерфейс для отправки текста в backend endpoint `POST /v1/assess`.

## Запуск

1. Убедитесь, что backend запущен на `http://localhost:8000`.
2. Установите зависимости фронта:

```bash
cd frontend
npm install
```

3. Запустите dev-сервер:

```bash
npm run dev
```

4. Откройте `http://localhost:5173`.

В `vite.config.js` уже настроен proxy на backend, поэтому запросы из браузера к `/v1/assess` пойдут на `http://localhost:8000`.
