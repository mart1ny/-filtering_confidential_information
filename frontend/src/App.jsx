import { useMemo, useState } from "react";

const initialMessages = [
  {
    id: 1,
    role: "assistant",
    text: "Отправьте текст, и я покажу решение модели: allow / review / block.",
  },
];

function formatResult(result) {
  return [
    `decision: ${result.decision}`,
    `risk_score: ${Number(result.risk_score).toFixed(3)}`,
    `reason: ${result.reason}`,
  ].join("\n");
}

function App() {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const text = input.trim();

    if (!text || loading) {
      return;
    }

    setError("");
    setLoading(true);
    setInput("");

    const userMessage = {
      id: Date.now(),
      role: "user",
      text,
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await fetch("/v1/assess", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      const assistantMessage = {
        id: Date.now() + 1,
        role: "assistant",
        text: formatResult(result),
        decision: result.decision,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (requestError) {
      const fallbackMessage = {
        id: Date.now() + 1,
        role: "assistant",
        text: "Не удалось получить ответ от API. Проверьте, что backend запущен на http://localhost:8000.",
      };
      setMessages((prev) => [...prev, fallbackMessage]);
      setError(requestError instanceof Error ? requestError.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="chat-card">
        <header className="chat-header">
          <h1>Confidential Filter Chat</h1>
          <p>Интерфейс для быстрой проверки текста через `/v1/assess`.</p>
        </header>

        <main className="chat-messages" aria-live="polite">
          {messages.map((message) => (
            <article
              key={message.id}
              className={`bubble bubble-${message.role} ${message.decision ? `bubble-${message.decision}` : ""}`.trim()}
            >
              <span className="bubble-role">{message.role === "user" ? "Вы" : "Сервис"}</span>
              <pre>{message.text}</pre>
            </article>
          ))}
        </main>

        <form className="chat-input" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Введите текст для проверки..."
            rows={3}
            disabled={loading}
          />
          <button type="submit" disabled={!canSend}>
            {loading ? "Проверяем..." : "Отправить"}
          </button>
        </form>

        {error && <p className="error">Ошибка запроса: {error}</p>}
      </div>
    </div>
  );
}

export default App;
