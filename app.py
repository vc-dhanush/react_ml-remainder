
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from datetime import datetime
import hashlib
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
import models, schemas, ml

app = FastAPI(title="Smart Reminder API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","http://127.0.0.1:5500/frontend/index.html" "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    init_db()

class AuthIn(BaseModel):
    email: str
    password: str

class AuthOut(BaseModel):
    email: str
    token: str

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

@app.post("/auth/signup", response_model=AuthOut)
def signup(auth: AuthIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=auth.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = models.User(email=auth.email, password=hash_password(auth.password))
    db.add(user)
    db.commit()
    return AuthOut(email=user.email, token=hash_password(user.email + user.password))

@app.post("/auth/login", response_model=AuthOut)
def login(auth: AuthIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=auth.email, password=hash_password(auth.password)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return AuthOut(email=user.email, token=hash_password(user.email + user.password))

@app.get("/tasks", response_model=List[schemas.Task])
def list_tasks(email: str, db: Session = Depends(get_db)):
    q = db.query(models.Task).filter_by(email=email).order_by(models.Task.id.desc()).all()
    return [schemas.Task.from_orm(t) for t in q]

@app.post("/tasks", response_model=schemas.Task)
def add_task(task_in: schemas.TaskCreate, db: Session = Depends(get_db)):
    t = models.Task(**task_in.dict())
    deadline_dt = datetime.strptime(t.deadline, "%d-%m-%Y %H:%M")
    send_time = ml.choose_smart_send_time(db, t.email, deadline_dt)
    t.scheduled_reminder = send_time.isoformat()
    db.add(t); db.commit(); db.refresh(t)
    ml.log_event(db, t.email, t.title, "created", deadline=t.deadline, scheduled=t.scheduled_reminder)
    return schemas.Task.from_orm(t)

@app.put("/tasks/{task_id}", response_model=schemas.Task)
def update_task(task_id: int, task_upd: schemas.TaskUpdate, db: Session = Depends(get_db)):
    t = db.query(models.Task).get(task_id)
    if not t: raise HTTPException(status_code=404, detail="Task not found")
    for k, v in task_upd.dict(exclude_unset=True).items():
        setattr(t, k, v)
    if task_upd.deadline is not None:
        deadline_dt = datetime.strptime(t.deadline, "%d-%m-%Y %H:%M")
        send_time = ml.choose_smart_send_time(db, t.email, deadline_dt)
        t.scheduled_reminder = send_time.isoformat()
    db.commit(); db.refresh(t)
    return schemas.Task.from_orm(t)

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    t = db.query(models.Task).get(task_id)
    if not t: raise HTTPException(status_code=404, detail="Task not found")
    ml.log_event(db, t.email, t.title, "deleted")
    db.delete(t); db.commit()
    return {"ok": True}

@app.post("/tasks/{task_id}/complete", response_model=schemas.Task)
def mark_complete(task_id: int, db: Session = Depends(get_db)):
    t = db.query(models.Task).get(task_id)
    if not t: raise HTTPException(status_code=404, detail="Task not found")
    t.completed = True; db.commit()
    deadline_dt = datetime.strptime(t.deadline, "%d-%m-%Y %H:%M")
    send_dt = datetime.fromisoformat(t.scheduled_reminder) if t.scheduled_reminder else deadline_dt
    success = datetime.now() <= deadline_dt
    ml.record_bandit(db, t.email, send_dt.hour, success)
    ml.log_event(db, t.email, t.title, "completed", success=success)
    db.refresh(t)
    return schemas.Task.from_orm(t)

from schemas import ParseOut, PredOut, RecoOut, TaskMinimal

@app.post("/ai/parse", response_model=ParseOut)
def parse_text(payload: dict):
    text = payload.get("text","")
    return ml.parse_text(text)

@app.post("/ai/predict", response_model=PredOut)
def predict(task: TaskMinimal, db: Session = Depends(get_db)):
    pri = ml.predict_priority(db, task.dict())
    prob = ml.predict_completion(db, task.dict())
    return PredOut(pred_priority=pri, prob_complete_on_time=prob)

@app.get("/schedule/recommend", response_model=RecoOut)
def recommend_hour(email: str, db: Session = Depends(get_db)):
    return {"hour": ml.best_hour(db, email)}
