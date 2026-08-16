# Day 8: Authentication, Database & Production Features
# Goal: Add real backend features — User authentication, persistent database, and production readiness.
# Topics for Day 8
#
# SQLAlchemy + Alembic (Database migrations)
# FastAPI Users / JWT Authentication
# Environment variables & .env
# CORS, Rate Limiting, Logging
# Basic CI/CD concepts
#
#
# Day 8 Project: Secure Todo API with Database
# We will upgrade your FastAPI app to use:
#
# SQLite (or PostgreSQL later)
# User registration & login (JWT)
# Protected endpoints
#
#
# Step-by-Step Setup
# First, create a new folder for Day 8:
# Bash

# cd python-mastery
# mkdir -p day8-secure-todo
# cd day8-secure-todo
#
# uv venv
# uv pip install "python-jose[cryptography]" "passlib[bcrypt]" python-multipart sqlalchemy alembic

# Project Structure

# day8-secure-todo/
# ├── todo/
# │   ├── __init__.py
# │   ├── models.py
# │   ├── schemas.py
# │   ├── database.py
# │   ├── auth.py
# │   └── crud.py
# ├── main.py
# ├── alembic.ini
# ├── pyproject.toml
# ├── .env.example
# └── README.md
# This follows FastAPI best practices:
#
# Clean separation of layers (API → Service → Database)
# Per-request database session (recommended by FastAPI)
# Service layer owns all business logic
# No DB session visible in API layer

# Run the project:

# Step-by-Step
#
# Start the FastAPI serverOpen terminal and run:
# cd /Users/dipenlimbu/Documents/Projects/Python-Prac/python-mastery/day8-secure-todo
#
# uv run uvicorn main:app --reload

# Run in Debug Mode:

# uv run uvicorn main:app --reload --log-level debug

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from todo.auth import FAKE_USER, verify_password, create_access_token, get_current_user as verify_token

from todo.database import get_db, engine, Base
from todo.models import Task as TaskModel
from todo.schemas import TaskCreate, Task
from todo.service import TodoService

# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Secure Todo API", version="0.1.0")

# Create tables on startup, NO NEED: Have created table manually using DB Browser for SQL Lite
# @app.on_event("startup")
# def create_tables():
#     Base.metadata.create_all(bind=engine)
#     print("Database tables created successfully!")


# using OAuth2Password flow for authentication. detail below
# tokenUrl specifies login endpoint eg. "/login"
oauth2_schema = OAuth2PasswordBearer(tokenUrl="/login")


# NOTE: don't call here, call in database class
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# ====================== Dependencies ======================
# Dependency that creates a TodoService with a database session

# Depends(get_db) tells FastAPI, before running this endpoint,
# call the get_db function and inject the result here i.e., the db session
def get_todo_service(db: Session = Depends(get_db)):
    return TodoService(db)


# ====================== Auth Endpoints ======================
# Login endpoint to get JWT token
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # check username and password
    # In reality, the hashed password has been stored in database server
    # when user first creates it
    if (form_data.username != FAKE_USER["username"] or
            not verify_password(form_data.password, FAKE_USER["password"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    # create JWT token
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}


# Protected dependency
async def get_current_user(token: str = Depends(oauth2_schema)):
    try:
        username = verify_token(token)  # from auth.py, note: we are using 'alias' since names being same
        return username
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


# ====================== Protected Endpoints ======================
# Protected endpoint example
@app.get("/tasks", response_model=list[Task])
# async def list_tasks(db: Session = Depends(get_db)):
async def list_tasks(
        show_all: bool = False,
        service: TodoService = Depends(get_todo_service),
        current_user: str = Depends(get_current_user)  # JWT protection: check below
):
    return service.get_all( show_all)


@app.post("/tasks", response_model=Task, status_code=201)
# NOTE: we don't call function - get_todo_service(), we are passing it as reference
# and not calling it so No ()
async def create_new_task(
        task: TaskCreate,
        service: TodoService = Depends(get_todo_service),
        current_user: str = Depends(get_current_user)):
    """Create a new task"""
    return service.create(task)


@app.patch("/tasks/{task_id}/done", response_model=Task)
async def mark_task_done(task_id: int, service: TodoService = Depends(get_todo_service),
                         current_user: str = Depends(get_current_user)):  # JWT protection
    """Mark a task as done"""
    task = service.mark_done(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int,
                      service: TodoService = Depends(get_todo_service),
                      current_user: str = Depends(get_current_user)):
    """Delete a task"""
    success = service.delete(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}

# ============================

# How Protection Works:
#
# eg. current_user: str = Depends(get_current_user)
#
# get_current_user dependency runs first
# It extracts the token from the Authorization: Bearer <token> header
# It verifies the JWT signature and expiration
# If valid → current_user gets the username
# If invalid → returns 401 Unauthorized automatically
#
# You don’t need to write any extra code inside the function — FastAPI handles the protection via the dependency.

# To Protect All Endpoints

# You can protect multiple endpoints by adding the same dependency:
# Pythoncurrent_user: str = Depends(get_current_user)

# ============================

# "Depends" is one of the most powerful features in FastAPI.

# Simple Explanation:
# def read_users_me(current_user: str = Depends(get_current_user)):
# Depends(get_current_user) tells FastAPI:
# "Before running this endpoint, please call the get_current_user function and inject its result here."
#
# What "Depends" actually does:
#
# Automatically calls the function you pass to it (get_current_user)
# Injects the returned value into your endpoint parameter (current_user)
# Handles all the complexity (like getting the token from headers, error handling, etc.)
#
#
# Real Example:
# @app.get("/users/me")
# def read_users_me(current_user: str = Depends(get_current_user)):
#     return {"message": f"Hello {current_user}, welcome back!"}
# Flow when someone calls this endpoint:
#
# User sends request with Authorization: Bearer <token> header
# FastAPI sees Depends(get_current_user)
# It automatically runs get_current_user(token)
# If token is valid → current_user gets the username
# If token is invalid → returns 401 automatically

# Why is "Depends" so powerful?
#
# Clean code (no manual token extraction in every endpoint)
# Reusable (you can use the same dependency in many endpoints)
# Supports nested dependencies
# Automatic OpenAPI documentation (Swagger)

# Why use Depends() instead of calling the function manually?

# Bad Way (Manual call inside function):

# @app.get("/users/me")
# def read_users_me(token: str = Header(None)):
#     try:
#         current_user = get_current_user(token)   # Manual call
#         ...
#     except:
#         raise HTTPException(401, "Invalid token")

# Problems:
#
# You have to manually extract the token from headers every time.
# Repetitive code in every protected endpoint.
# Harder to maintain.
# Less clean.

# Best Way (Using "Depends"):

# @app.get("/users/me")
# def read_users_me(current_user: str = Depends(get_current_user)):
#     return {"message": f"Hello {current_user}"}

# Advantages of "Depends":
#
# Automatic – FastAPI handles token extraction from header automatically.
# Clean & Readable – Your endpoint logic stays very clean.
# Reusable – You can use Depends(get_current_user) in 50 different endpoints easily.
# Composability – You can create complex dependency chains.
# Automatic Documentation – Swagger UI shows it properly.
# Error Handling – If authentication fails, it stops before entering the function.

# Real World Benefit:

# Imagine you have 20+ protected endpoints. With Depends, you write the authentication logic once.
# With manual calls, you would repeat the same boilerplate code everywhere.
# This is one of the reasons FastAPI is loved by developers — it makes Dependency Injection very elegant.

# ============================

# oauth2_schema = OAuth2PasswordBearer(tokenUrl="token")

# This creates a security scheme that tells FastAPI:
#
# "I want to use OAuth2 Password Flow for authentication"
# "Users will send the token in the Authorization header"
# "The login endpoint is located at /token"
#
#
# What it actually does:
#
# 1. Expects the client to send the token like this:

# Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 2. Automatically extracts the token from the request header.
# 3. Adds a nice "Authorize" button in Swagger UI (the automatic documentation).
# 4. Works together with Depends().

# Full Typical Usage:

# oauth2_schema = OAuth2PasswordBearer(tokenUrl="token")
#
# # Use it in protected routes
# @app.get("/users/me")
# def read_users_me(current_user: str = Depends(get_current_user)):
#     ...

# Where get_current_user usually looks like:

# def get_current_user(token: str = Depends(oauth2_schema)):
#     ...

# Why tokenUrl="token"?
# This tells Swagger UI / FastAPI that when the user clicks the "Authorize" button, it should try to
# login by calling the /token endpoint.
#
# Summary:
# OAuth2PasswordBearer is FastAPI’s clean way to define "I expect a Bearer token in the Authorization header".
# Would you like me to show you the complete, clean setup with:
#
# oauth2_schema
# login endpoint (/token)
# get_current_user

# ============================

# not preferred but can also be called like this: async def login(form_data: OAuth2PasswordRequestForm = Depends(OAuth2PasswordRequestForm)):
