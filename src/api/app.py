from fastapi import FastAPI

from src.api.routers.config import router as config_router
from src.api.routers.gripper import router as gripper_router
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
        {"name": "gripper", "description": "Gripper status and motion (guarded by config)."},
    ]
    app = FastAPI(
        title="robot-ong-do",
        version="0.1.0",
        description="FastAPI wrapper for Fairino robot and trajectory utilities.",
        openapi_tags=tags_metadata,
    )
    app.include_router(health_router)
    app.include_router(config_router, prefix="/config", tags=["config"])
    app.include_router(robot_router, prefix="/robot", tags=["robot"])
    app.include_router(trajectory_router, prefix="/trajectory", tags=["trajectory"])
    app.include_router(safety_router, prefix="/safety", tags=["safety"])
    app.include_router(gripper_router, prefix="/gripper", tags=["gripper"])
    return app


app = create_app()
