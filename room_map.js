(() => {
  const ROOM_LABELS = {
    TVroom: "Study Room",
    computers: "Computers",
    fire_exit: "Fire Exit",
    elevator: "Elevators",
    jittery_joes: "Cafe",
    first_floor: "First Floor"
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

  function buildMap(completedRooms, current) {
    const container = document.createElement("div");
    container.id = "roomMapWidget";
    container.innerHTML = `
      <div class="map-title">Room Map</div>
      <div class="map-track"></div>
    `;

    const track = container.querySelector(".map-track");

    sequence.forEach((room) => {
      const step = document.createElement("div");
      const done = completedRooms.includes(room);
      const isCurrent = room === current;
      step.className = "map-step";
      if (done) step.classList.add("done");
      if (isCurrent) step.classList.add("current");
      step.textContent = ROOM_LABELS[room];
      track.appendChild(step);
    });

    document.body.appendChild(container);
  }

  function addStyles() {
    const style = document.createElement("style");
    style.textContent = `
      #roomMapWidget {
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 9999;
        background: rgba(22, 33, 52, 0.9);
        border: 2px solid #9eb7dd;
        border-radius: 10px;
        width: min(260px, 45vw);
        color: white;
        font-family: "Pixelify Sans", sans-serif;
        padding: 8px;
      }
      #roomMapWidget .map-title {
        font-size: 18px;
        margin-bottom: 6px;
      }
      #roomMapWidget .map-track {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      #roomMapWidget .map-step {
        font-size: 13px;
        opacity: 0.5;
        border-left: 3px solid #5f7396;
        padding-left: 8px;
      }
      #roomMapWidget .map-step.done {
        opacity: 0.85;
        border-left-color: #4ed37a;
      }
      #roomMapWidget .map-step.current {
        opacity: 1;
        border-left-color: #ffd166;
        font-weight: bold;
      }
      @media (max-width: 700px) {
        #roomMapWidget {
          width: 55vw;
          padding: 6px;
        }
        #roomMapWidget .map-step {
          font-size: 12px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  async function init() {
    const room = currentRoom();
    if (!room || !window.SmartScapesAPI) {
      return;
    }

    const session = SmartScapesAPI.requireSession();
    if (!session) {
      return;
    }

    addStyles();

    const state = await SmartScapesAPI.getMapState();
    const completedRooms = state?.completedRooms || [];
    buildMap(completedRooms, room);
  }

  window.addEventListener("load", init);
})();
