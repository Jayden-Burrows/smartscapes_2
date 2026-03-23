from __future__ import annotations

import json
import os
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STORE_FILE = DATA_DIR / "store.json"

ROOM_SEQUENCE = [
    "TVroom",
    "computers",
    "fire_exit",
    "elevator",
    "jittery_joes",
    "first_floor",
]

DEFAULT_PUBLISHED_QUESTIONS = {
    "TVroom": {
        "question": "Before entering deeper, what does AI stand for?",
        "answers": ["artificial intelligence"],
    },
    "computers": {
        "question": "What does CPU stand for?",
        "answers": ["central processing unit"],
    },
    "fire_exit": {
        "question": "What is the CSS box model order from outer to inner?",
        "answers": ["margin border padding content", "margin,border,padding,content"],
    },
    "elevator": {
        "question": "In programming, which data structure follows LIFO order?",
        "answers": ["stack", "a stack", "the stack"],
    },
    "jittery_joes": {
        "question": "Which number system uses only 0 and 1?",
        "answers": ["binary", "base 2", "base-2", "base two"],
    },
    "first_floor": {
        "question": "What protocol secures most websites with encryption?",
        "answers": ["https"],
    },
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_store() -> dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
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


def load_store() -> dict[str, Any]:
    return json.loads(STORE_FILE.read_text(encoding="utf-8"))


def save_store(data: dict[str, Any]) -> None:
    STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def generate_draft_questions(prompt: str, syllabus: str, count: int = 8) -> list[dict[str, Any]]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_+-]*", f"{prompt} {syllabus}")
    words: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if len(lowered) < 3:
            continue
        if lowered not in words:
            words.append(lowered)

    if not words:
        words = ["algorithms", "data structures", "networking", "security", "databases", "web"]

    templates = [
        "Define {topic} in one clear sentence.",
        "Which option best describes {topic}?",
        "Give one real-world use case of {topic}.",
        "What is the main purpose of {topic}?",
        "What mistake do beginners make with {topic}?",
        "Compare {topic} with another related concept.",
        "Why is {topic} important in computer science?",
    ]

    drafts: list[dict[str, Any]] = []
    for idx in range(count):
        topic = words[idx % len(words)]
        q_text = templates[idx % len(templates)].format(topic=topic)
        drafts.append(
            {
                "id": str(uuid.uuid4()),
                "question": q_text,
                "answers": [topic],
                "difficulty": random.choice(["easy", "medium", "hard"]),
                "source": "generated",
            }
        )
    return drafts


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
        prompt = str(payload.get("prompt", ""))
        syllabus = str(payload.get("syllabus", ""))
        activity_name = str(payload.get("activityName", "Untitled Activity")).strip() or "Untitled Activity"

        drafts = generate_draft_questions(prompt, syllabus, 8)
        activity_id = str(uuid.uuid4())

        store = load_store()
        store["activities"][activity_id] = {
            "activityName": activity_name,
            "prompt": prompt,
            "syllabus": syllabus,
            "draftQuestions": drafts,
            "publishedCode": None,
            "createdAt": utc_iso(),
        }
        save_store(store)

        return jsonify({"activityId": activity_id, "questions": drafts})

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

        drafts = activity.get("draftQuestions", [])[:7]
        if len(drafts) < 6:
            return jsonify({"error": "Please keep at least 6 questions before publishing."}), 400

        publish_code = uuid.uuid4().hex[:8].upper()
        by_room: dict[str, Any] = {}
        for idx, room in enumerate(ROOM_SEQUENCE):
            draft = drafts[idx % len(drafts)]
            answers = draft.get("answers") or []
            normalized_answers = [normalize(str(a)) for a in answers if str(a).strip()]
            if not normalized_answers:
                normalized_answers = ["sample answer"]
            by_room[room] = {
                "question": str(draft.get("question", "")).strip() or f"Question for {room}",
                "answers": normalized_answers,
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
            "createdAt": utc_iso(),
        }
        save_store(store)

        return jsonify({"sessionId": session_id, "name": name, "activityCode": activity_code})

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
        return jsonify({"roomId": room_id, "question": q["question"]})

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

        if is_correct and room_id not in session["completedRooms"]:
            session["completedRooms"].append(room_id)

        store["attempts"].append(
            {
                "sessionId": session_id,
                "roomId": room_id,
                "answer": answer,
                "correct": is_correct,
                "timestamp": utc_iso(),
            }
        )
        save_store(store)

        return jsonify({"correct": is_correct})

    @app.get("/api/game/map-state")
    def api_map_state() -> Any:
        session_id = request.args.get("sessionId", "")
        store = load_store()
        session = store["sessions"].get(session_id)
        if not session:
            return jsonify({"error": "invalid session"}), 400

        return jsonify(
            {
                "name": session["name"],
                "completedRooms": session["completedRooms"],
                "roomSequence": ROOM_SEQUENCE,
            }
        )

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
