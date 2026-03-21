from fastapi import APIRouter , Depends
from sqlalchemy.orm import Session
from Database import SessionLocal
from Model.Product import ProductDetails

router = APIRouter()

# Dependency: get a DB session per request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/test")
async def test(db: Session = Depends(get_db)):
    # This db session is auutomatically passing by the dependency injection system of FastAPI
    products = db.query(ProductDetails).all()
    return products