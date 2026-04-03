import { useMemo, useState } from "react";

const initialMessages = [
  {
    id: 1,
    role: "assistant",
    text: "Вставьте текст. Я покажу только итог проверки, а детали детекции выведу в консоль.",
  },
];

function getResultView(result) {
  if (result.decision === "allow") {
    return {
      title: "ПРОШЛО",
      subtitle: "Явительных признаков конфиденциальных данных не найдено.",
      tone: "allow",
    };
  }

  if (result.decision === "review") {
    return {
      title: "НЕ ПРОШЛО",
      subtitle: "Нужна дополнительная ручная проверка.",
      tone: "review",
    };
  }

  return {
    title: "НЕ ПРОШЛО",
    subtitle: "Обнаружены признаки конфиденциальных данных.",
    tone: "block",
  };
}

function logDetection(result, text) {
  const probability = Number(result.risk_score).toFixed(3);
  console.groupCollapsed(`[detector] ${result.decision.toUpperCase()} | score=${probability}`);
  console.log("text", text);
  console.log("detector_used", result.detector_used ?? "unknown");
  console.log("probability", probability);
  console.log("reason", result.reason);
  console.log("details", result.detector_details ?? {});
  console.groupEnd();
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

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        text,
      },
    ]);

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
      const view = getResultView(result);
      logDetection(result, text);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          decision: result.decision,
          title: view.title,
          subtitle: view.subtitle,
          tone: view.tone,
        },
      ]);
    } catch (requestError) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          title: "СБОЙ",
          subtitle: "Не удалось получить ответ от backend API.",
          tone: "error",
        },
      ]);
      setError(requestError instanceof Error ? requestError.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <section className="chat-card">
        <header className="hero">
          <p className="hero-kicker">Confidential Filter</p>
          <h1>Проверка текста на конфиденциальные данные</h1>
          <p className="hero-text">
            Интерфейс показывает только итог. Технические детали детекции и вероятность
            выводятся в консоль браузера.
          </p>
        </header>

        <main className="chat-messages" aria-live="polite">
          {messages.map((message) =>
            message.role === "user" ? (
              <article key={message.id} className="message-row message-row-user">
                <div className="message message-user">
                  <span className="message-role">Запрос</span>
                  <p>{message.text}</p>
                </div>
              </article>
            ) : (
              <article key={message.id} className="message-row message-row-assistant">
                <div className={`result-card result-${message.tone ?? "neutral"}`}>
                  <span className="message-role">Результат</span>
                  <h2>{message.title ?? "ГОТОВО"}</h2>
                  <p>{message.subtitle ?? message.text}</p>
                </div>
              </article>
            )
          )}
        </main>

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Введите сообщение для проверки"
            rows={4}
            disabled={loading}
          />
          <button type="submit" disabled={!canSend}>
            {loading ? "Проверяем" : "Проверить"}
          </button>
        </form>

        {error && <p className="error">Ошибка запроса: {error}</p>}
      </section>
    </div>
  );
}

export default App;
