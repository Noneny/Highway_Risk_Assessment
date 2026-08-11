"""高速公路风险评估 REST 接口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.application import AssessmentCommand
from src.api.task_manager import AssessmentTaskManager


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prepare_input: bool = Field(default=True, description="执行ETC合并与MySQL输入数据导出")
    update_config: bool = Field(default=False, description="先从配置数据库同步INI配置")
    compare: bool = Field(default=False, description="评估完成后执行两期对比")
    recalculate: bool = Field(default=True, description="重新执行点、线、网风险评估")

    @model_validator(mode="after")
    def validate_options(self) -> "AssessmentRequest":
        if not self.recalculate and not self.compare:
            raise ValueError("recalculate=false 时必须同时设置 compare=true")
        return self

    def to_command(self) -> AssessmentCommand:
        return AssessmentCommand(**self.model_dump())


class ArtifactResponse(BaseModel):
    kind: str
    path: str
    size_bytes: int
    modified_at: str


class ResultResponse(BaseModel):
    elapsed_seconds: float
    artifacts: list[ArtifactResponse]


class TaskResponse(BaseModel):
    task_id: str
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    phase: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[ResultResponse] = None
    error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.task_manager = AssessmentTaskManager()
    yield
    app.state.task_manager.shutdown(wait=False)


app = FastAPI(
    title="Highway Risk Assessment API",
    version="3.0.0",
    description="重庆山区高速公路点、线、网三级风险评估异步任务接口",
    lifespan=lifespan,
)


def get_task_manager(request: Request) -> AssessmentTaskManager:
    return request.app.state.task_manager


@app.get("/health", tags=["operations"])
def health(request: Request) -> dict:
    return {"status": "UP", "busy": get_task_manager(request).is_busy()}


@app.post(
    "/api/v1/assessments",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["assessments"],
)
def create_assessment(payload: AssessmentRequest, request: Request) -> dict:
    task = get_task_manager(request).submit(payload.to_command())
    return task.to_dict()


@app.get(
    "/api/v1/assessments/{task_id}",
    response_model=TaskResponse,
    tags=["assessments"],
)
def get_assessment(task_id: str, request: Request) -> dict:
    try:
        task = get_task_manager(request).get(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="评估任务不存在") from exc
    return task.to_dict()
