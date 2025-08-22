from fastapi import FastAPI
from .api import router

# Create the main FastAPI application instance
app = FastAPI(
    title="Crawler C2 Server",
    description="Phase 1 - Core C2 functionality with ethical governance frameworks.",
    version="1.0.0"
)

# Include the API router defined in api.py
# All routes from the router will be prefixed with /api
app.include_router(router, prefix="/api")

@app.get("/", tags=["Root"])
def read_root():
    """
    Root endpoint for the C2 server.
    Provides a simple status check to confirm the server is operational.
    """
    return {"message": "Crawler C2 Server is operational. Refer to /docs for API documentation."}
