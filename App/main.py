from fastapi import FastAPI
from Controllers import Testing
from dotenv import load_dotenv
from Database import Base, engine

# Base.metadata.create_all(bind=engine) # Uncomment this line to create tables in the database based on the defined models. Run it once and then comment it out again to avoid recreating tables.

load_dotenv()
app = FastAPI()

app.include_router(Testing.router)