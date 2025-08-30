
from sqlalchemy import Column, Integer, String, Boolean, Text, UniqueConstraint
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="other")
    priority = Column(String, default="Medium")
    recurring = Column(Boolean, default=False)
    deadline = Column(String, nullable=False)
    scheduled_reminder = Column(String, nullable=True)
    reminder_sent = Column(Boolean, default=False)
    completed = Column(Boolean, default=False)

class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    task_title = Column(String)
    event_type = Column(String)
    event_time = Column(String)
    meta = Column(Text)

class Bandit(Base):
    __tablename__ = "bandit_stats"
    email = Column(String, primary_key=True)
    hour_slot = Column(Integer, primary_key=True)
    successes = Column(Integer, default=1)
    trials = Column(Integer, default=2)
    __table_args__ = (UniqueConstraint('email', 'hour_slot', name='_email_hour_uc'),)
