from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Controllers import Testing , UserChatRoute
from dotenv import load_dotenv
from Database import Base, engine
from openai import OpenAI

# Base.metadata.create_all(bind=engine) # Uncomment this line to create tables in the database based on the defined models. Run it once and then comment it out again to avoid recreating tables.

load_dotenv()
app = FastAPI()


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],          # allow all HTTP methods
    allow_headers=["*"],          # allow all headers
)




app.include_router(Testing.router)
app.include_router(UserChatRoute.router)