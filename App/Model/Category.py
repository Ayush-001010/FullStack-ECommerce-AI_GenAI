from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base
from Database import Base

class CategoryDetails(Base):
    __tablename__ = "CategoryDetails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String, nullable=False)
    ImageKey = Column(String, nullable=False)
    RouteURL = Column(String, nullable=False)
    OrderNumber = Column(Integer, nullable=False)
    IsActive = Column(Boolean, default=True)
