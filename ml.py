
from datetime import datetime, timedelta, time as dtime
from sqlalchemy.orm import Session
from dateparser import parse as dateparse
import re, json
from models import Interaction, Bandit

URGENCY_WORDS = {
    "High": ["urgent", "asap", "immediately", "critical", "important", "today", "now"],
    "Medium": ["soon", "tomorrow", "before", "by", "priority"],
    "Low": ["whenever", "later", "someday", "nice to have"]
}

CATEGORY_KEYWORDS = {
    "work": ["project", "client", "meeting", "report", "office", "deadline"],
    "health": ["doctor", "medicine", "exercise", "gym", "yoga"],
    "finance": ["bill", "invoice", "payment", "bank", "tax"],
    "personal": ["birthday", "call", "family", "shopping"]
}

def parse_deadline(text: str):
    if text:
        dt = dateparse(text, settings={"PREFER_DATES_FROM":"future"})
        if dt: return dt
    text_l = (text or "").lower()
    now = datetime.now()
    if "tomorrow" in text_l:
        return datetime.combine(now.date() + timedelta(days=1), dtime(hour=9))
    m = re.search(r"in (\d+)\s*(minutes|minute|hours|hour|days|day)", text_l)
    if m:
        qty = int(m.group(1)); unit = m.group(2)
        if "minute" in unit: return now + timedelta(minutes=qty)
        if "hour" in unit: return now + timedelta(hours=qty)
        if "day" in unit: return now + timedelta(days=qty)
    if "today" in text_l:
        return datetime.combine(now.date(), dtime(hour=18))
    return None

def infer_category(text: str) -> str:
    if not text: return "other"
    t = text.lower()
    best_cat, best_hits = "other", 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        hits = sum(1 for k in kws if k in t)
        if hits > best_hits: best_hits, best_cat = hits, cat
    return best_cat

def infer_priority_from_words(text: str) -> str:
    if not text: return "Medium"
    t = text.lower()
    for w in URGENCY_WORDS["High"]:
        if w in t: return "High"
    for w in URGENCY_WORDS["Medium"]:
        if w in t: return "Medium"
    return "Low"

def predict_priority(db: Session, task: dict) -> str:
    pri = infer_priority_from_words((task.get("description","") + " " + task.get("title","")).strip())
    try:
        ddl = datetime.strptime(task["deadline"], "%d-%m-%Y %H:%M")
        hours = (ddl - datetime.now()).total_seconds()/3600
        if hours is not None and hours < 6: pri = "High"
        elif hours is not None and hours < 24 and pri == "Low": pri = "Medium"
    except Exception:
        pass
    return pri

def predict_completion(db: Session, task: dict) -> float:
    desc_len = len(task.get("description","").split())
    try:
        ddl = datetime.strptime(task["deadline"], "%d-%m-%Y %H:%M")
        hours = (ddl - datetime.now()).total_seconds()/3600
    except Exception:
        hours = 12.0
    base = 0.6 if task.get("priority","Medium") != "High" else 0.4
    score = base + min(max(hours/48.0, -0.3), 0.3) - (desc_len/200.0)
    return max(0.05, min(0.95, score))

def init_bandit(db: Session, email: str):
    for h in range(24):
        row = db.query(Bandit).filter_by(email=email, hour_slot=h).first()
        if not row:
            db.add(Bandit(email=email, hour_slot=h, successes=1, trials=2))
    db.commit()

def record_bandit(db: Session, email: str, hour_slot: int, success: bool):
    row = db.query(Bandit).filter_by(email=email, hour_slot=hour_slot).first()
    if not row:
        from models import Bandit as B
        row = B(email=email, hour_slot=hour_slot, successes=1, trials=2)
        db.add(row)
    row.successes += 1 if success else 0
    row.trials += 1
    db.commit()

def thompson_like(db: Session, email: str) -> int:
    best_score, best_hour = -1, 9
    for h in range(24):
        row = db.query(Bandit).filter_by(email=email, hour_slot=h).first()
        if not row: continue
        score = (row.successes + 1) / (row.trials + 2)
        if score > best_score: best_score, best_hour = score, h
    return best_hour

def choose_smart_send_time(db: Session, email: str, deadline_dt):
    init_bandit(db, email)
    best_hour = thompson_like(db, email)
    candidate = datetime.combine(deadline_dt.date(), dtime(hour=best_hour))
    if candidate > deadline_dt: candidate = deadline_dt - timedelta(hours=2)
    if candidate < datetime.now(): candidate = datetime.now() + timedelta(minutes=1)
    return candidate

def best_hour(db: Session, email: str) -> int:
    init_bandit(db, email)
    return thompson_like(db, email)

def log_event(db: Session, email: str, title: str, event_type: str, **meta):
    evt = Interaction(email=email, task_title=title, event_type=event_type,
                      event_time=datetime.now().isoformat(), meta=json.dumps(meta))
    db.add(evt); db.commit()

def parse_text(text: str):
    ddl = parse_deadline(text)
    return {
        "detected_deadline": ddl.strftime("%d-%m-%Y %H:%M") if ddl else None,
        "inferred_category": infer_category(text),
        "priority_hint": infer_priority_from_words(text)
    }
