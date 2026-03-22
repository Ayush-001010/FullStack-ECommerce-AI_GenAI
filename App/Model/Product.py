from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import declarative_base
from Database import Base

class ProductDetails(Base):
    __tablename__ = "ProductDetails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String, nullable=False)
    Description = Column(String, nullable=False)
    Price = Column(Float, nullable=False)
    ImageKey = Column(String, nullable=False)
    IsDiscounted = Column(Boolean, default=False)
    DiscountPercentage = Column(Integer, default=0)
    Rating = Column(Float, default=0.0)
    NoOfRatings = Column(Integer, default=0)
    IsBestSeller = Column(Boolean, default=False)
    Quantity = Column(Integer, default=0)
    IsActive = Column(Boolean, default=True)
    categoryId = Column(Integer, nullable=False)
    SubCategory = Column(String, nullable=False)
