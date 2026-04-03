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

  async function enterRoom(roomId) {
    const session = getSession();
    if (!session || !session.sessionId) return;
    // Store entry time client-side for the live timer in the sidebar
    localStorage.setItem("ss_roomEnter_" + roomId, String(Date.now()));
    try {
      await fetch("/api/game/room-enter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: session.sessionId, roomId })
      });
    } catch (_) {}
  }

  async function markVisited(roomId) {
    const session = getSession();
    if (!session || !session.sessionId) return;
    try {
      await fetch("/api/game/mark-visited", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: session.sessionId, roomId })
      });
    } catch (_) {}
  }

  async function completeGame() {
    const session = getSession();
    if (!session || !session.sessionId) return;
    try {
      await fetch("/api/game/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: session.sessionId })
      });
    } catch (_) {}
  }

  async function getRoomQuestion(roomId) {
    const session = getSession();
    if (!session || !session.sessionId) return null;
    const url = `/api/game/question?sessionId=${encodeURIComponent(session.sessionId)}&roomId=${encodeURIComponent(roomId)}`;
    const response = await fetch(url);
    if (!response.ok) return null;
    return response.json();
  }

  async function submitAttempt(roomId, answer) {
    const session = getSession();
    if (!session || !session.sessionId) return null;
    const response = await fetch("/api/game/attempt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: session.sessionId, roomId, answer })
    });
    if (!response.ok) return null;
    return response.json();
  }

  async function getMapState() {
    const session = getSession();
    if (!session || !session.sessionId) return null;
    const response = await fetch(`/api/game/map-state?sessionId=${encodeURIComponent(session.sessionId)}`);
    if (!response.ok) return null;
    return response.json();
  }

  async function getStats() {
    const session = getSession();
    if (!session || !session.sessionId) return null;
    const response = await fetch(`/api/game/stats?sessionId=${encodeURIComponent(session.sessionId)}`);
    if (!response.ok) return null;
    return response.json();
  }

  function normalize(value) {
    return (value || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  async function resolveQuestion(roomId, fallbackQuestion, fallbackAnswers, questionElementId = "question") {
    const payload = await getRoomQuestion(roomId);
    const el = document.getElementById(questionElementId);

    let hint = "";
    if (payload && payload.question) {
      // Use roomContext as the displayed prompt if available, otherwise the plain question
      const displayText = payload.roomContext || payload.question;
      if (el) el.textContent = displayText;
      hint = payload.hint || "";
    }

    return {
      question: payload?.question || fallbackQuestion,
      hint,
      fallbackAnswers: (fallbackAnswers || []).map((a) => normalize(a))
    };
  }

  // Returns { correct: boolean, attemptCount: number }
  async function validateAnswer(roomId, answer, fallbackAnswers) {
    const attempt = await submitAttempt(roomId, answer);
    if (attempt && typeof attempt.correct === "boolean") {
      return { correct: attempt.correct, attemptCount: attempt.attemptCount || 1 };
    }
    const normalized = normalize(answer);
    const normalizedFallbacks = (fallbackAnswers || []).map((a) => normalize(a));
    return { correct: normalizedFallbacks.includes(normalized), attemptCount: 1 };
  }

  return {
    join,
    getSession,
    requireSession,
    enterRoom,
    markVisited,
    completeGame,
    resolveQuestion,
    validateAnswer,
    getMapState,
    getStats,
  };
})();
