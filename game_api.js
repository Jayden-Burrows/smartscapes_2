const SmartScapesAPI = (() => {
  const SESSION_KEY = "smartscapesSession";

  function getSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    } catch {
      return null;
    }
  }

  function setSession(session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  async function join(name, activityCode) {
    const response = await fetch("/api/student/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, activityCode })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not join activity");
    }
    setSession(data);
    return data;
  }

  function requireSession() {
    const session = getSession();
    if (!session || !session.sessionId) {
      window.location.href = "student_join.html";
      return null;
    }
    return session;
  }

  async function getRoomQuestion(roomId) {
    const session = getSession();
    if (!session || !session.sessionId) {
      return null;
    }
    const url = `/api/game/question?sessionId=${encodeURIComponent(session.sessionId)}&roomId=${encodeURIComponent(roomId)}`;
    const response = await fetch(url);
    if (!response.ok) {
      return null;
    }
    return response.json();
  }

  async function submitAttempt(roomId, answer) {
    const session = getSession();
    if (!session || !session.sessionId) {
      return null;
    }
    const response = await fetch("/api/game/attempt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: session.sessionId,
        roomId,
        answer
      })
    });
    if (!response.ok) {
      return null;
    }
    return response.json();
  }

  async function getMapState() {
    const session = getSession();
    if (!session || !session.sessionId) {
      return null;
    }
    const response = await fetch(`/api/game/map-state?sessionId=${encodeURIComponent(session.sessionId)}`);
    if (!response.ok) {
      return null;
    }
    return response.json();
  }

  function normalize(value) {
    return (value || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  async function resolveQuestion(roomId, fallbackQuestion, fallbackAnswers, questionElementId = "question") {
    const payload = await getRoomQuestion(roomId);
    const el = document.getElementById(questionElementId);

    let activeQuestion = fallbackQuestion;
    if (payload && payload.question) {
      activeQuestion = payload.question;
      if (el) {
        el.textContent = payload.question;
      }
    }

    return {
      question: activeQuestion,
      fallbackAnswers: (fallbackAnswers || []).map((a) => normalize(a))
    };
  }

  async function validateAnswer(roomId, answer, fallbackAnswers) {
    const attempt = await submitAttempt(roomId, answer);
    if (attempt && typeof attempt.correct === "boolean") {
      return attempt.correct;
    }
    const normalized = normalize(answer);
    const normalizedFallbacks = (fallbackAnswers || []).map((a) => normalize(a));
    return normalizedFallbacks.includes(normalized);
  }

  return {
    join,
    getSession,
    requireSession,
    resolveQuestion,
    validateAnswer,
    getMapState
  };
})();
