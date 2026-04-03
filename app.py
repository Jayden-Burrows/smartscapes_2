from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STORE_FILE = Path(os.environ.get("STORE_FILE", str(DATA_DIR / "store.json")))

ROOM_SEQUENCE = [
    "TVroom",
    "computers",
    "fire_exit",
    "elevator",
    "jittery_joes",
    "first_floor",
]

# Rooms where students answer an academic question
ACTIVE_QUESTION_ROOMS = ["computers", "fire_exit", "elevator", "jittery_joes"]

ROOM_DESCRIPTIONS = {
    "computers": "Computer Lab — the student tries to log into the building manager's computer",
    "fire_exit": "Fire Exit Hallway — the student must answer a question on the fire alarm panel to unlock the door",
    "elevator": "Elevator Lobby — a bulletin board quiz unlocks the elevator",
    "jittery_joes": "Jittery Joe's Cafe — the cash register is locked by a quiz",
}

DEFAULT_PUBLISHED_QUESTIONS: dict[str, Any] = {
    "computers": {
        "question": "What does CPU stand for?",
        "answers": ["central processing unit"],
        "hint": "Think about the main processing chip inside every computer.",
        "roomContext": "The screen blinks: 'Enter Building Manager password. Security check: what is the full name of the chip that executes instructions in a computer?'",
    },
    "fire_exit": {
        "question": "Name the four CSS box model layers from outer to inner.",
        "answers": ["margin border padding content", "margin,border,padding,content"],
        "hint": "There are four layers. The outermost creates space between elements; the innermost is the actual content.",
        "roomContext": "The fire alarm panel flashes: 'Override requires web knowledge — name the four CSS box model layers from outermost to innermost.'",
    },
    "elevator": {
        "question": "Which data structure follows Last In, First Out (LIFO) order?",
        "answers": ["stack", "a stack", "the stack"],
        "hint": "Think of a stack of plates — you always take from the top.",
        "roomContext": "The bulletin board quiz reads: 'What data structure processes the last item added as the first item removed?'",
    },
    "jittery_joes": {
        "question": "Which number system uses only 0 and 1?",
        "answers": ["binary", "base 2", "base-2", "base two"],
        "hint": "Computers only understand two states — on and off.",
        "roomContext": "The register screen asks: 'Security question — what number system do computers use at the hardware level?'",
    },
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_store() -> dict[str, Any]:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_FILE.exists():
        initial = {
            "activities": {},
            "published": {
                "DEMO123": {
                    "activityName": "Demo Activity",
                    "questionsByRoom": DEFAULT_PUBLISHED_QUESTIONS,
                    "createdAt": utc_iso(),
                }
            },
            "sessions": {},
            "attempts": [],
        }
        STORE_FILE.write_text(json.dumps(initial, indent=2), encoding="utf-8")
    return load_store()


def seconds_between(iso_start: str, iso_end: str) -> int | None:
    try:
        t1 = datetime.fromisoformat(iso_start)
        t2 = datetime.fromisoformat(iso_end)
        return max(0, int((t2 - t1).total_seconds()))
    except Exception:
        return None


def load_store() -> dict[str, Any]:
    return json.loads(STORE_FILE.read_text(encoding="utf-8"))


def save_store(data: dict[str, Any]) -> None:
    STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def generate_draft_questions(prompt: str) -> list[dict[str, Any]]:
    """Generate one question per active question room using Gemini, with context + hint."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            room_descriptions = "\n".join(
                f"- roomId \"{rid}\": {desc}" for rid, desc in ROOM_DESCRIPTIONS.items()
            )
            gemini_prompt = (
                "You are writing quiz questions for an educational escape room game set in a university building. "
                "Students play as someone locked in the building who must answer academic questions to escape.\n\n"
                f"The teacher's topic/instructions:\n{prompt}\n\n"
                f"Generate exactly one question for each of these 4 rooms:\n{room_descriptions}\n\n"
                "Requirements per question:\n"
                "- answerable in 1-4 words (short answers only)\n"
                "- must relate to the teacher's topic\n"
                "- must feel natural within the room's story setting\n"
                "- include a 1-sentence hint for students who are stuck\n"
                "- include a 1-2 sentence roomContext: in-character text that frames the question "
                "as if the room environment is delivering it (e.g. the computer screen, fire alarm panel, bulletin board, cash register)\n"
                "- list up to 3 accepted answer variants (e.g. abbreviations, synonyms)\n\n"
                "Return ONLY this JSON:\n"
                "{\"questions\": ["
                "{\"roomId\": \"computers\", \"question\": \"...\", \"roomContext\": \"...\", "
                "\"answers\": [\"primary\", \"alt1\"], \"hint\": \"...\", \"difficulty\": \"easy|medium|hard\"},"
                "{\"roomId\": \"fire_exit\", ...},"
                "{\"roomId\": \"elevator\", ...},"
                "{\"roomId\": \"jittery_joes\", ...}"
                "]}"
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=gemini_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            parsed = json.loads(response.text)
            raw_list = parsed.get("questions") or []
            if not isinstance(raw_list, list):
                raw_list = []
            result: list[dict[str, Any]] = []
            for q in raw_list:
                if not isinstance(q, dict) or not str(q.get("question", "")).strip():
                    continue
                answers = q.get("answers") or [q.get("answer", "")]
                if isinstance(answers, str):
                    answers = [answers]
                result.append({
                    "id": str(uuid.uuid4()),
                    "roomId": str(q.get("roomId", "")).strip(),
                    "question": str(q["question"]).strip(),
                    "roomContext": str(q.get("roomContext", "")).strip(),
                    "answers": [str(a).strip() for a in answers if str(a).strip()],
                    "hint": str(q.get("hint", "")).strip(),
                    "difficulty": str(q.get("difficulty", "medium")),
                    "source": "generated",
                })
            if len(result) >= len(ACTIVE_QUESTION_ROOMS):
                return result
        except Exception:
            pass  # Fall through to defaults

    # Fallback: return well-formed default questions
    return [
        {
            "id": str(uuid.uuid4()),
            "roomId": room_id,
            "question": q["question"],
            "roomContext": q["roomContext"],
            "answers": list(q["answers"]),
            "hint": q["hint"],
            "difficulty": "medium",
            "source": "default",
        }
        for room_id, q in DEFAULT_PUBLISHED_QUESTIONS.items()
    ]


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    ensure_store()

    @app.get("/")
    def root() -> Any:
        return send_from_directory(BASE_DIR, "index.html")

    @app.get("/<path:filename>")
    def serve_file(filename: str) -> Any:
        full = BASE_DIR / filename
        if full.exists() and full.is_file():
            return send_from_directory(BASE_DIR, filename)
        return jsonify({"error": "Not found"}), 404

    @app.post("/api/teacher/generate-questions")
    def api_generate_questions() -> Any:
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt", "")).strip()
        activity_name = str(payload.get("activityName", "Untitled Activity")).strip() or "Untitled Activity"

        if not prompt:
            return jsonify({"error": "Please enter a prompt."}), 400

        drafts = generate_draft_questions(prompt)
        activity_id = str(uuid.uuid4())

        store = load_store()
        store["activities"][activity_id] = {
            "activityName": activity_name,
            "prompt": prompt,
            "draftQuestions": drafts,
            "publishedCode": None,
            "createdAt": utc_iso(),
        }
        save_store(store)

        return jsonify({"activityId": activity_id, "questions": drafts})

    @app.post("/api/teacher/upload-text")
    def api_upload_text() -> Any:
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file uploaded"}), 400
        filename = (f.filename or "").lower()
        try:
            if filename.endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(f)
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                except ImportError:
                    return jsonify({"error": "PDF support unavailable on server. Please paste text manually."}), 500
            else:
                raw = f.read()
                text = raw.decode("utf-8", errors="replace")
        except Exception as e:
            return jsonify({"error": f"Could not read file: {e}"}), 400
        return jsonify({"text": text[:8000]})

    @app.put("/api/teacher/activities/<activity_id>/questions")
    def api_update_questions(activity_id: str) -> Any:
        payload = request.get_json(silent=True) or {}
        questions = payload.get("questions", [])
        if not isinstance(questions, list):
            return jsonify({"error": "questions must be a list"}), 400

        store = load_store()
        activity = store["activities"].get(activity_id)
        if not activity:
            return jsonify({"error": "activity not found"}), 404

        activity["draftQuestions"] = questions
        save_store(store)
        return jsonify({"ok": True})

    @app.post("/api/teacher/activities/<activity_id>/publish")
    def api_publish_activity(activity_id: str) -> Any:
        store = load_store()
        activity = store["activities"].get(activity_id)
        if not activity:
            return jsonify({"error": "activity not found"}), 404

        drafts = activity.get("draftQuestions", [])

        # Index drafts by roomId; fall back to sequential for any unassigned rooms
        drafts_by_room: dict[str, Any] = {}
        for d in drafts:
            rid = d.get("roomId", "")
            if rid in ACTIVE_QUESTION_ROOMS and rid not in drafts_by_room:
                drafts_by_room[rid] = d

        unassigned = [d for d in drafts if d.get("roomId") not in ACTIVE_QUESTION_ROOMS]
        for room in ACTIVE_QUESTION_ROOMS:
            if room not in drafts_by_room:
                if unassigned:
                    drafts_by_room[room] = unassigned.pop(0)
                else:
                    return jsonify({"error": f"Missing question for room: {room}"}), 400

        publish_code = uuid.uuid4().hex[:8].upper()
        by_room: dict[str, Any] = {}
        for room in ACTIVE_QUESTION_ROOMS:
            draft = drafts_by_room[room]
            answers = draft.get("answers") or []
            normalized_answers = [normalize(str(a)) for a in answers if str(a).strip()]
            if not normalized_answers:
                normalized_answers = ["sample answer"]
            by_room[room] = {
                "question": str(draft.get("question", "")).strip() or f"Question for {room}",
                "roomContext": str(draft.get("roomContext", "")).strip(),
                "answers": normalized_answers,
                "hint": str(draft.get("hint", "")).strip(),
                "difficulty": draft.get("difficulty", "medium"),
                "source": draft.get("source", "teacher-edited"),
            }

        store["published"][publish_code] = {
            "activityName": activity.get("activityName", "Untitled Activity"),
            "questionsByRoom": by_room,
            "activityId": activity_id,
            "createdAt": utc_iso(),
        }
        activity["publishedCode"] = publish_code
        save_store(store)

        return jsonify({"ok": True, "activityCode": publish_code})

    @app.post("/api/student/join")
    def api_student_join() -> Any:
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()
        activity_code = str(payload.get("activityCode", "")).strip().upper()

        if len(name) < 2:
            return jsonify({"error": "Please enter your name."}), 400

        store = load_store()
        if activity_code not in store["published"]:
            return jsonify({"error": "Invalid activity code."}), 400

        session_id = uuid.uuid4().hex
        store["sessions"][session_id] = {
            "name": name,
            "activityCode": activity_code,
            "completedRooms": [],
            "visitedRooms": [],
            "roomTimings": {},
            "startedAt": None,
            "completedAt": None,
            "createdAt": utc_iso(),
        }
        save_store(store)

        return jsonify({"sessionId": session_id, "name": name, "activityCode": activity_code})

    @app.post("/api/game/room-enter")
    def api_room_enter() -> Any:
        payload = request.get_json(silent=True) or {}
        session_id = str(payload.get("sessionId", ""))
        room_id = str(payload.get("roomId", ""))

        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        now = utc_iso()
        if not session.get("startedAt"):
            session["startedAt"] = now
        if "roomTimings" not in session:
            session["roomTimings"] = {}
        if room_id not in session["roomTimings"]:
            session["roomTimings"][room_id] = {"enteredAt": now, "completedAt": None}
        save_store(store)
        return jsonify({"ok": True})

    @app.post("/api/game/mark-visited")
    def api_mark_visited() -> Any:
        """Mark a narrative room (no question) as visited."""
        payload = request.get_json(silent=True) or {}
        session_id = str(payload.get("sessionId", ""))
        room_id = str(payload.get("roomId", ""))

        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        now = utc_iso()
        if "visitedRooms" not in session:
            session["visitedRooms"] = []
        if room_id not in session["visitedRooms"]:
            session["visitedRooms"].append(room_id)
        if "roomTimings" not in session:
            session["roomTimings"] = {}
        timing = session["roomTimings"].setdefault(room_id, {"enteredAt": now, "completedAt": None})
        if not timing.get("completedAt"):
            timing["completedAt"] = now
        save_store(store)
        return jsonify({"ok": True})

    @app.get("/api/game/question")
    def api_game_question() -> Any:
        session_id = request.args.get("sessionId", "")
        room_id = request.args.get("roomId", "")

        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        published = store["published"].get(session["activityCode"])
        if not published:
            return jsonify({"error": "activity not found"}), 404

        q = published["questionsByRoom"].get(room_id)
        if not q:
            return jsonify({"error": "question not found"}), 404
        return jsonify({
            "roomId": room_id,
            "question": q["question"],
            "roomContext": q.get("roomContext", ""),
            "hint": q.get("hint", ""),
        })

    @app.post("/api/game/attempt")
    def api_game_attempt() -> Any:
        payload = request.get_json(silent=True) or {}
        session_id = str(payload.get("sessionId", ""))
        room_id = str(payload.get("roomId", ""))
        answer = normalize(str(payload.get("answer", "")))

        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        published = store["published"].get(session["activityCode"])
        if not published:
            return jsonify({"error": "activity not found"}), 404

        room_q = published["questionsByRoom"].get(room_id)
        if not room_q:
            return jsonify({"error": "question not found"}), 404

        accepted = [normalize(str(a)) for a in room_q.get("answers", [])]
        is_correct = answer in accepted

        now = utc_iso()
        if is_correct and room_id not in session["completedRooms"]:
            session["completedRooms"].append(room_id)
            if "roomTimings" not in session:
                session["roomTimings"] = {}
            timing = session["roomTimings"].setdefault(room_id, {"enteredAt": now, "completedAt": None})
            if not timing.get("completedAt"):
                timing["completedAt"] = now

        store["attempts"].append({
            "sessionId": session_id,
            "roomId": room_id,
            "answer": answer,
            "correct": is_correct,
            "timestamp": now,
        })
        save_store(store)

        attempt_count = sum(
            1 for a in store["attempts"]
            if a["sessionId"] == session_id and a["roomId"] == room_id
        )
        return jsonify({"correct": is_correct, "attemptCount": attempt_count})

    @app.post("/api/game/complete")
    def api_game_complete() -> Any:
        payload = request.get_json(silent=True) or {}
        session_id = str(payload.get("sessionId", ""))

        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        if not session.get("completedAt"):
            session["completedAt"] = utc_iso()
        save_store(store)
        return jsonify({"ok": True})

    @app.get("/api/game/map-state")
    def api_map_state() -> Any:
        session_id = request.args.get("sessionId", "")
        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        completed = session.get("completedRooms", [])
        visited = session.get("visitedRooms", [])

        room_attempts: dict[str, dict] = {}
        for room in ROOM_SEQUENCE:
            atts = [a for a in store["attempts"] if a["sessionId"] == session_id and a["roomId"] == room]
            room_attempts[room] = {
                "total": len(atts),
                "correct": sum(1 for a in atts if a["correct"]),
            }

        return jsonify({
            "name": session["name"],
            "completedRooms": completed,
            "visitedRooms": visited,
            "roomSequence": ROOM_SEQUENCE,
            "activeQuestionRooms": ACTIVE_QUESTION_ROOMS,
            "roomTimings": session.get("roomTimings", {}),
            "roomAttempts": room_attempts,
            "startedAt": session.get("startedAt"),
        })

    @app.get("/api/game/stats")
    def api_game_stats() -> Any:
        session_id = request.args.get("sessionId", "")
        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        activity_code = session.get("activityCode", "")
        published = store["published"].get(activity_code, {})
        all_attempts = [a for a in store["attempts"] if a["sessionId"] == session_id]

        per_room: list[dict] = []
        for room in ROOM_SEQUENCE:
            room_att = [a for a in all_attempts if a["roomId"] == room]
            timing = session.get("roomTimings", {}).get(room, {})
            time_secs = seconds_between(timing.get("enteredAt", ""), timing.get("completedAt", ""))
            per_room.append({
                "roomId": room,
                "totalAttempts": len(room_att),
                "correctAttempts": sum(1 for a in room_att if a["correct"]),
                "timeSeconds": time_secs,
            })

        total_secs = seconds_between(session.get("startedAt", ""), session.get("completedAt", ""))

        return jsonify({
            "name": session["name"],
            "activityName": published.get("activityName", ""),
            "perRoom": per_room,
            "totalAttempts": len(all_attempts),
            "correctAttempts": sum(1 for a in all_attempts if a["correct"]),
            "totalTimeSeconds": total_secs,
            "startedAt": session.get("startedAt"),
            "completedAt": session.get("completedAt"),
        })

    @app.get("/api/teacher/export-csv")
    def api_export_csv() -> Any:
        store = load_store()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "sessionId", "studentName", "activityCode", "activityName",
            "roomId", "answer", "correct", "timestamp",
            "roomEnteredAt", "roomCompletedAt",
        ])
        published_names = {code: v.get("activityName", "") for code, v in store["published"].items()}
        for attempt in store["attempts"]:
            sid = attempt["sessionId"]
            sess = store["sessions"].get(sid, {})
            ac = sess.get("activityCode", "")
            timing = sess.get("roomTimings", {}).get(attempt["roomId"], {})
            writer.writerow([
                sid, sess.get("name", ""), ac, published_names.get(ac, ""),
                attempt["roomId"], attempt["answer"], attempt["correct"],
                attempt["timestamp"],
                timing.get("enteredAt", ""), timing.get("completedAt", ""),
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=smartscapes_data.csv"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
