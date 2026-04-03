(() => {
  const ROOM_LABELS = {
    TVroom: "Study Room",
    computers: "Computer Lab",
    fire_exit: "Fire Exit",
    elevator: "Elevators",
    jittery_joes: "Jittery Joe's",
    first_floor: "First Floor"
  };

  const ROOM_ICONS = {
    TVroom: "📺",
    computers: "💻",
    fire_exit: "🚨",
    elevator: "🛗",
    jittery_joes: "☕",
    first_floor: "🚪"
  };

  const PAGE_TO_ROOM = {
    "TVroom.html": "TVroom",
    "computers.html": "computers",
    "fire_exit.html": "fire_exit",
    "elevator.html": "elevator",
    "jittery_joes.html": "jittery_joes",
    "first_floor.html": "first_floor"
  };

  const sequence = ["TVroom", "computers", "fire_exit", "elevator", "jittery_joes", "first_floor"];

  function currentRoom() {
    const file = window.location.pathname.split("/").pop();
    return PAGE_TO_ROOM[file] || null;
  }

  function fmtTime(seconds) {
    if (seconds == null || seconds < 0) return "--";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  }

  function buildMap(state, current) {
    const completedRooms = state?.completedRooms || [];
    const visitedRooms = state?.visitedRooms || [];
    const roomAttempts = state?.roomAttempts || {};

    const existing = document.getElementById("roomMapWidget");
    if (existing) existing.remove();

    const widget = document.createElement("div");
    widget.id = "roomMapWidget";

    const toggle = document.createElement("button");
    toggle.id = "mapToggle";
    toggle.title = "Toggle map";
    toggle.textContent = "🗺";
    document.body.appendChild(toggle);

    let collapsed = localStorage.getItem("ss_mapCollapsed") === "1";

    const header = document.createElement("div");
    header.className = "map-header";
    header.innerHTML = `<span>Progress Map</span><button id="mapClose">✕</button>`;
    widget.appendChild(header);

    const track = document.createElement("div");
    track.className = "map-track";

    sequence.forEach((room) => {
      const done = completedRooms.includes(room) || visitedRooms.includes(room);
      const isCurrent = room === current;
      const atts = roomAttempts[room] || { total: 0, correct: 0 };

      const step = document.createElement("div");
      step.className = "map-step" + (done ? " done" : "") + (isCurrent ? " current" : "");

      let statusIcon = done ? "✅" : (isCurrent ? "▶" : "🔒");
      let attText = atts.total > 0 ? `<span class="map-att">${atts.total} attempt${atts.total !== 1 ? "s" : ""}</span>` : "";

      // Live timer for current room
      let timerHtml = "";
      if (isCurrent) {
        const enterMs = parseInt(localStorage.getItem("ss_roomEnter_" + room) || "0", 10);
        if (enterMs) {
          const elapsed = Math.floor((Date.now() - enterMs) / 1000);
          timerHtml = `<span class="map-timer" id="mapTimer_${room}">${fmtTime(elapsed)}</span>`;
        }
      }

      step.innerHTML = `
        <span class="map-icon">${ROOM_ICONS[room]}</span>
        <span class="map-label">${ROOM_LABELS[room]}</span>
        <span class="map-status">${statusIcon}</span>
        ${attText}${timerHtml}
      `;
      track.appendChild(step);
    });

    widget.appendChild(track);
    document.body.appendChild(widget);

    function applyCollapsed() {
      widget.style.display = collapsed ? "none" : "block";
    }
    applyCollapsed();

    toggle.addEventListener("click", () => {
      collapsed = !collapsed;
      localStorage.setItem("ss_mapCollapsed", collapsed ? "1" : "0");
      applyCollapsed();
    });

    document.getElementById("mapClose").addEventListener("click", () => {
      collapsed = true;
      localStorage.setItem("ss_mapCollapsed", "1");
      applyCollapsed();
    });

    // Live timer tick every second
    if (current) {
      setInterval(() => {
        const timerEl = document.getElementById("mapTimer_" + current);
        if (!timerEl) return;
        const enterMs = parseInt(localStorage.getItem("ss_roomEnter_" + current) || "0", 10);
        if (!enterMs) return;
        const elapsed = Math.floor((Date.now() - enterMs) / 1000);
        timerEl.textContent = fmtTime(elapsed);
      }, 1000);
    }
  }

  function addStyles() {
    const style = document.createElement("style");
    style.textContent = `
      #mapToggle {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 10000;
        background: rgba(22, 33, 52, 0.92);
        border: 2px solid #9eb7dd;
        border-radius: 8px;
        color: white;
        font-size: 20px;
        width: 40px;
        height: 40px;
        cursor: pointer;
        padding: 0;
        line-height: 1;
      }
      #roomMapWidget {
        position: fixed;
        top: 56px;
        right: 10px;
        z-index: 9999;
        background: rgba(12, 20, 36, 0.95);
        border: 2px solid #9eb7dd;
        border-radius: 12px;
        width: min(230px, 48vw);
        color: white;
        font-family: "Pixelify Sans", sans-serif;
        padding: 8px 10px 10px;
        backdrop-filter: blur(4px);
      }
      #roomMapWidget .map-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 14px;
        font-weight: bold;
        margin-bottom: 8px;
        color: #a8c4e8;
        letter-spacing: 1px;
      }
      #roomMapWidget #mapClose {
        background: none;
        border: none;
        color: #a8c4e8;
        cursor: pointer;
        font-size: 14px;
        padding: 0;
        line-height: 1;
      }
      #roomMapWidget .map-track {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      #roomMapWidget .map-step {
        display: grid;
        grid-template-columns: 20px 1fr auto;
        align-items: center;
        column-gap: 6px;
        font-size: 13px;
        opacity: 0.45;
        border-left: 3px solid #3a4f6e;
        padding: 3px 0 3px 7px;
        border-radius: 0 4px 4px 0;
        position: relative;
      }
      #roomMapWidget .map-step.done {
        opacity: 0.85;
        border-left-color: #4ed37a;
      }
      #roomMapWidget .map-step.current {
        opacity: 1;
        border-left-color: #ffd166;
        background: rgba(255, 209, 102, 0.08);
      }
      #roomMapWidget .map-icon { font-size: 14px; }
      #roomMapWidget .map-label { font-size: 12px; }
      #roomMapWidget .map-status { font-size: 11px; }
      #roomMapWidget .map-att {
        grid-column: 2 / 4;
        font-size: 10px;
        color: #7fa8cc;
        margin-top: 1px;
      }
      #roomMapWidget .map-timer {
        font-size: 10px;
        color: #ffd166;
        margin-left: 4px;
      }
      @media (max-width: 600px) {
        #roomMapWidget { width: 56vw; }
        #roomMapWidget .map-step { font-size: 11px; }
      }
    `;
    document.head.appendChild(style);
  }

  async function init() {
    const room = currentRoom();
    if (!room || !window.SmartScapesAPI) return;
    const session = SmartScapesAPI.requireSession();
    if (!session) return;

    addStyles();

    const state = await SmartScapesAPI.getMapState();
    buildMap(state, room);
  }

  window.addEventListener("load", init);
})();
