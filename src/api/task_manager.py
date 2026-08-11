"""风险评估后台任务管理。"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Optional
from uuid import uuid4

from src.application import AssessmentCommand, AssessmentResult, RiskAssessmentRunner


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class AssessmentTask:
    task_id: str
    command: AssessmentCommand
    status: TaskStatus = TaskStatus.QUEUED
    phase: str = "QUEUED"
    created_at: datetime = field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[AssessmentResult] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "phase": self.phase,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
        }


class AssessmentTaskManager:
    """串行执行评估任务，保护共享输入、临时文件和输出文件。"""

    def __init__(self, runner: Optional[RiskAssessmentRunner] = None, max_history: int = 100):
        self._runner = runner or RiskAssessmentRunner()
        self._max_history = max_history
        self._tasks: OrderedDict[str, AssessmentTask] = OrderedDict()
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="risk-assessment")

    def submit(self, command: AssessmentCommand) -> AssessmentTask:
        command.validate()
        task = AssessmentTask(task_id=str(uuid4()), command=command)
        with self._lock:
            self._prune_history()
            self._tasks[task.task_id] = task
        self._executor.submit(self._execute, task.task_id)
        return self.get(task.task_id)

    def get(self, task_id: str) -> AssessmentTask:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            return AssessmentTask(**task.__dict__)

    def is_busy(self) -> bool:
        with self._lock:
            return any(
                task.status in (TaskStatus.QUEUED, TaskStatus.RUNNING)
                for task in self._tasks.values()
            )

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _execute(self, task_id: str) -> None:
        self._mutate(
            task_id,
            status=TaskStatus.RUNNING,
            phase="STARTING",
            started_at=utc_now(),
        )
        try:
            result = self._runner.run(
                self.get(task_id).command,
                progress=lambda phase: self._mutate(task_id, phase=phase),
            )
        except Exception as exc:
            self._mutate(
                task_id,
                status=TaskStatus.FAILED,
                phase="FAILED",
                finished_at=utc_now(),
                error=str(exc),
            )
        else:
            self._mutate(
                task_id,
                status=TaskStatus.SUCCEEDED,
                phase="COMPLETED",
                finished_at=utc_now(),
                result=result,
            )

    def _mutate(self, task_id: str, **changes) -> None:
        with self._lock:
            task = self._tasks[task_id]
            for name, value in changes.items():
                setattr(task, name, value)

    def _prune_history(self) -> None:
        while len(self._tasks) >= self._max_history:
            oldest_id, oldest = next(iter(self._tasks.items()))
            if oldest.status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
                break
            self._tasks.pop(oldest_id)
