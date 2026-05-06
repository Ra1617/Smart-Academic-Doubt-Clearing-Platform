from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.core.config import settings
from app.db.database import engine, init_schema_compat
from app.models import models

# Include routers
from app.api.routes import auth, doubts, faculty, admin

# Ensure legacy schema compatibility, then create any missing tables.
init_schema_compat()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Academic Doubt Platform API",
    description="API for managing academic doubts, users, and AI resolutions.",
    version="1.0.0",
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "*"],  # Allow specific or all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(doubts.router, prefix="/doubts", tags=["Students & Doubts"])
app.include_router(faculty.router, prefix="/faculty", tags=["Faculty Actions"])
app.include_router(admin.router, prefix="/admin", tags=["Admin Actions"])

@app.get("/")
def root():
    return {"message": "Welcome to Smart Academic Doubt Platform API"}

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Error handler for unexpected errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "details": str(exc)},
    )
