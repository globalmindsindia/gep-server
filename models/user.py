# models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)

    # new explicit columns mapped from front-end extra
    mobile = Column(String(20), nullable=True, index=True)
    qualification = Column(String(200), nullable=True)
    experience = Column(Text, nullable=True)

    # keep a generic extra field in case you want expandability
    extra = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
