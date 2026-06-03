from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.config import router as config_router
from src.api.routers.health import router as health_router
from src.api.routers.robot import router as robot_router
from src.api.routers.safety import router as safety_router
from src.api.routers.trajectory import router as trajectory_router


def create_app() -> FastAPI:
    tags_metadata = [
        {"name": "health", "description": "Service health and basic metadata."},
        {"name": "config", "description": "Read/update runtime configuration."},
        {"name": "robot", "description": "Robot connectivity, status, and motion."},
        {"name": "trajectory", "description": "Trajectory previews from shapes, SVG, or text."},
        {"name": "safety", "description": "Safety validation for poses."},
    ]
    app = FastAPI(
        title="robot-ong-do",
        version="0.1.0",
        description="FastAPI wrapper for Fairino robot and trajectory utilities.",
        openapi_tags=tags_metadata,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"^https?://("
            r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?$"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(config_router, prefix="/config", tags=["config"])
    app.include_router(robot_router, prefix="/robot", tags=["robot"])
    app.include_router(trajectory_router, prefix="/trajectory", tags=["trajectory"])
    app.include_router(safety_router, prefix="/safety", tags=["safety"])
    return app


app = create_app()
