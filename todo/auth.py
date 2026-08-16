# Recommended for Your Learning Project
# For now, keeping JWT in auth.py is fine.
# But for better architecture, here's how a separate Auth Service would look:
# todo/auth/service.py

# sample:
# class AuthService:
#     def __init__(self):
#         self.secret_key = "your-secret-key"
#         self.algorithm = "HS256"
#         self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
#
#     def create_access_token(self, username: str) -> str:
#         expire = datetime.utcnow() + timedelta(minutes=30)
#         to_encode = {"sub": username, "exp": expire}
#         return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
#
#     def verify_token(self, token: str) -> str:
#         payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
#         return payload.get("sub")

# NOTE: in python
# If a function is defined without self at the module level (not inside a class),
# then it is just a regular function — not a method.
# eg. def create_access_token(data: dict) -> str:   # No 'self'
# This is not a static method. It is a plain module-level function.
# If we add 'self' in the function where there is no 'class', Python will not throw error
# when we define the function. But weh we try to call it, we will get error.

# Best Recommendation:
# for utilities:
# def create_access_token(data: dict):  # no self
# if we want inside a class:
# class AuthService:
#   def create_access_token(self, data: dict):

from datetime import datetime, timedelta
from fastapi import HTTPException, status
from typing import Optional

from jose import JWTError, jwt
from argon2 import PasswordHasher, exceptions as argon2_exceptions

# ================== Argon2 Configuration ==================
# Argon2 is more secure and resistant to GPU attacks than bcrypt

ph = PasswordHasher(
    time_cost=3,  # Number of iterations
    memory_cost=65536,  # 64 MB (higher = more secure) very resitant to GPU attacks
    parallelism=4,  # Parallel threads
    hash_len=32,
    salt_len=16
)

SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

FAKE_USER = {
    "username": "dipen",
    # This is the Argon2 hash of password = "password"
    "password": "$argon2id$v=19$m=65536,t=3,p=4$r+VhnKISh2iR5FC5pr16pA$UeKicZSOqW8v5tb4t8dOUT0xAles5Bq+ciPaTDSeIQI"
}


# FAKE_USER = {
#     "username": "dipen",
#     "password": "$2b$12$KQXIHQe6VroVwQisZ./RruDouNV9SaDDqhrurcidLR/ycURuL7.TK",  # bcrypt hash of "password"
#     "id": 1
# }


# this was for using bcrypt with passlib
# from passlib.context import CryptContext

# high-level wrapper (smart manager from passlib library)
# that makes password hashing and verification easier and safer
# check below for password hash info
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     # pwd_context.verify() uses "salt" in the hashed_password
#     # # to encrypt the plain_password and compare them
#     return pwd_context.verify(plain_password, hashed_password)
#
#
# def get_password_hash(password):
#     return pwd_context.hash(password)  # hash password

def hash_password(password: str) -> str:
    """Hash a plain password using Argon2id"""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its Argon2 hash"""
    try:
        return ph.verify(hashed_password, plain_password)
    except (argon2_exceptions.VerifyMismatchError,
            argon2_exceptions.InvalidHash,
            argon2_exceptions.VerifyMismatchError):
        # Wrong password - do NOT reveal any info
        return False
    except Exception as e:  # Catch any unexpected argon2 errors
        # Log the error in production, but never expose details to user
        print(f"Argon2 verification error: {type(e).__name__}")  # temporary debug
        return False

    # except (argon2_exceptions.InvalidHash, argon2_exceptions.VerifyMismatchError):
    # Invalid hash format or other verification issues
    # In production, you might want to log this
    # return False


# eg. creating token (during login): access_token = create_access_token({"sub": user.email})
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()  # make a shallow copy
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))  # set expiry
    to_encode.update({"exp": expire})  # add / updates key-value pairs. in this case, expiry time
    # Encodes a claims set and returns a JWT string.
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # encode into token


def get_current_user(token: str):
    """Decode JWT and return current user (demo version)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        # verifies a JWT string's signature and validates reserved claims
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # decode token
        username: str = payload.get("sub")  # extract username
        if username is None:
            raise credentials_exception
    except JWTError:  # if token is invalid/expired
        raise credentials_exception

    if username != FAKE_USER["username"]:  # is username not the same
        raise credentials_exception

    return username

# ============================

# What is JWT?

# JWT (JSON Web Token) is a secure way to send user information between client and server.
# It looks like this:
# texteyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaXBlbiIsImV4cCI6MTcyMDAwMDAwMH0.abc123
#
# JWT Flow in Your API:

# 1. User Login (POST /token)
# Python@app.post("/token")
# async def login(form_data: OAuth2PasswordRequestForm = Depends()):
#     # Check username and password
#     if form_data.username != FAKE_USER["username"] or not verify_password(...):
#         raise HTTPException(401, "Incorrect credentials")
#
#     # Create JWT token
#     access_token = create_access_token(data={"sub": form_data.username})
#     return {"access_token": access_token, "token_type": "bearer"}

# What happens:
#
# User sends username + password
# Server verifies credentials
# Server creates a JWT token containing user info
# Token is sent back to the client
#
#
# 2. Using the Token in Protected Endpoints:

# Client sends the token in the Authorization header:

# textAuthorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# FastAPI automatically extracts it using OAuth2PasswordBearer.
# OAuth2PasswordBearer extracts the token from the HTTP Authorization header.
# The client (fronted, Postman, curl etc.) must send the token like for eg.
# Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# FastAPI automatically:
#
# Looks for the Authorization header
# Checks that it starts with Bearer
# Extracts the token part after Bearer

# Example request from client:

# curl -X GET "http://127.0.0.1:8000/tasks" \
#   -H "Authorization: Bearer your-jwt-token-here"

# In Swagger UI (/docs):
# You will see a button "Authorize" at the top right. Click it and paste the token.

# In your code:
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# The tokenUrl="token" tells Swagger UI where the login endpoint is (/token).

# 3. Verifying the Token:

# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username = payload.get("sub")
#         return username
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# What happens:
#
# FastAPI gets the token from header
# jwt.decode() verifies the signature and expiration
# If valid → returns username
# If invalid → returns 401 Unauthorized
#
#
# Full Flow Summary:
#
# User logs in → POST /token → gets JWT token
# User makes request to protected endpoint → sends token in header
# FastAPI verifies token using get_current_user
# If valid → request proceeds
# If invalid → 401 error

# CryptContext:

# simple usage:

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
#
# # Hash a password
# hashed_password = pwd_context.hash("MySecret123")
#
# # Verify password
# is_correct = pwd_context.verify("MySecret123", hashed_password)

# ============================

# Password hash and compare:

# to generate own hash - we can do:

# from passlib.context import CryptContext
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# print(pwd_context.hash("yourpassword"))
# The output of print will have the hashed password
# pwd_context.hash("yourpassword") will generate a "different hash" each time you run

# Process of storing password hash:

# Bcrypt (algorithm used) automatically adds a random "salt" every time you hash a password
# eg. $2b$12$abc123... (different every time)

# Adavnatges of this method (It's good for security):
# 1. in that it makes it much harder for attackers (protects against rainbow table attacks)
# 2. each user's password hash is unique even if they use the "same" password
# 3. we never store the plain password, instead we store the hashed password (in database server)

# How does it verify Password later?

# You don't compare the hashes directly. you use:
# pwd_context.verify(plain_password, hashed_password)

# since bcrypt stores the "salt" inside the hash itself, that "salt" is used to check

# How pwd_context.verify(plain_password, hashed_password) works:
# When you call:
# Pythonpwd_context.verify(plain_password, hashed_password)
# bcrypt does the following behind the scenes:
#
# Extracts the salt from the hashed_password.
# The salt is stored inside the hashed password string itself.
#
# Takes the plain_password and uses the same salt to hash it again.
# Compares the newly generated hash with the stored hashed_password.
# Returns True if they match, False if they don't.

# Also note:
# We never store
# For simplicity, we use a hardcoded user
# In production, use a real User model and database,
# and we need actual bcrypt hash of the password

# Full Flow:
# 1. When user "registers":
#
# User enters plain password → "MySecret123"
# We hash it using bcrypt → "$2b$12$7f...longhash..."
# We save only the hashed version in the database.
#
# 2. When user logs in (days or months later):
#
# User enters plain password again → "MySecret123"
# We take the stored hashed_password from database
# pwd_context.verify(plain_password, hashed_password) compares them
# If it matches → login successful

# # During registration:

# user.hashed_password = pwd_context.hash(plain_password)
# db.add(user)
# db.commit()
#
# # During login:
# user = db.query(User).filter(User.email == email).first()
#
# if not pwd_context.verify(plain_password, user.hashed_password):
#     raise HTTPException(status_code=401, detail="Incorrect password")

# This is the standard, secure way used in almost all professional applications.

# ============================

# Bcrypt Hash Format:

# A bcrypt hash has this structure:

# $2b$12$3pvehQEhK2Ge.1Lh3uXjze5Z825JTeuu6LehtBLcXQiMCrg5cyeJ2

# $2b$12$9v9v9v9v9v9v9v9v9v9v9u9v9v9v9v9v9v9v9v9v9v9v9v9v9v9v9v9v

# It is divided into 4 parts:

# Part,                             Meaning,                        Example from your hash
# $2b$,                             Algorithm version,              $2b$
# 12,                               Cost factor (how slow it is),   12
# 9v9v9v9v9v9v9v9v9v9v9u,           The Salt (22 characters),       9v9v9v9v9v9v9v9v9v9v9u
# 9v9v9v9v9v9v9v9v9v9v9v9v9v9v9v9v, The actual hash,                the rest

# The salt is this part:
# 9v9v9v9v9v9v9v9v9v9v9u

# Important Point:

# When you store the hash, you store the entire string (including the salt).
# When verify() runs, it automatically:
#
# Extracts the salt from the stored hash
# Uses that salt to hash the password the user just entered
# Compares the result
#
# You never have to handle the salt manually.

# ============================

# Argon2:

# argon2id → Algorithm variant
# v=19 → Version
# m=65536 → Memory (in KB) — very important for security
# t=3 → Time / iterations
# p=4 → Parallelism (threads)
# V8Lmlg6kcSBviACcqedvqQ → Salt (base64 encoded)
# gMim2up+YDL6ifiv6mVW9tI09+CN5wpq1c30FpHtHkg → Hash (the actual password hash)
