"""将现有点、线、网风险评估流程封装为可复用的应用模块。"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional

import main as assessment_main


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ProgressCallback = Callable[[str], None]


class RiskAssessmentExecutionError(RuntimeError):
    """风险评估某个阶段执行失败。"""

    def __init__(self, phase: str):
        super().__init__(f"风险评估阶段执行失败: {phase}")
        self.phase = phase


@dataclass(frozen=True)
class AssessmentCommand:
    """一次风险评估任务的调用参数。"""

    prepare_input: bool = True
    update_config: bool = False
    compare: bool = False
    recalculate: bool = True

    def validate(self) -> None:
        if not self.recalculate and not self.compare:
            raise ValueError("recalculate=false 时必须同时设置 compare=true")


@dataclass(frozen=True)
class AssessmentArtifact:
    kind: str
    path: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class AssessmentResult:
    elapsed_seconds: float
    artifacts: tuple[AssessmentArtifact, ...]

    def to_dict(self) -> dict:
        return {
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
        }


@contextmanager
def _project_working_directory() -> Iterator[None]:
    """兼容仍使用相对路径的旧模块。任务执行器保证同一时刻仅运行一个任务。"""

    previous = Path.cwd()
    os.chdir(BASE_DIR)
    try:
        yield
    finally:
        os.chdir(previous)


class RiskAssessmentRunner:
    """在一个小接口后编排现有风险评估实现。"""

    def run(
        self,
        command: AssessmentCommand,
        progress: Optional[ProgressCallback] = None,
    ) -> AssessmentResult:
        command.validate()
        notify = progress or (lambda _phase: None)
        started_at = time.time()

        with _project_working_directory():
            if command.update_config:
                self._run_phase("CONFIG_UPDATE", assessment_main.run_config_update_step, notify)

            if command.prepare_input:
                self._run_phase("INPUT_PREPARATION", assessment_main.run_input, notify)

            if command.recalculate:
                self._run_phase("RISK_ASSESSMENT", assessment_main.run_risk_assessment, notify)

            if command.compare:
                self._run_phase("PERIOD_COMPARISON", assessment_main.run_compare, notify)

        notify("COLLECTING_ARTIFACTS")
        return AssessmentResult(
            elapsed_seconds=time.time() - started_at,
            artifacts=tuple(self._collect_artifacts(started_at, command.compare)),
        )

    @staticmethod
    def _run_phase(
        phase: str,
        operation: Callable[[], bool],
        notify: ProgressCallback,
    ) -> None:
        notify(phase)
        if not operation():
            raise RiskAssessmentExecutionError(phase)

    @staticmethod
    def _collect_artifacts(started_at: float, include_compare: bool) -> list[AssessmentArtifact]:
        output_dir = BASE_DIR / "data" / "output"
        candidates: list[tuple[str, Path]] = [
            ("POINT_RISK", output_dir / "全结构点通行风险值评价表.xlsx"),
            ("LINE_RISK", output_dir / "路段通行风险评价总表.xlsx"),
        ]

        net_outputs = sorted(
            output_dir.glob("路网通行风险评估结果_*.xlsx"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if net_outputs:
            candidates.append(("NETWORK_RISK", net_outputs[0]))
        if include_compare:
            candidates.append(("PERIOD_COMPARISON", output_dir / "风险评价对比结果.xlsx"))

        artifacts: list[AssessmentArtifact] = []
        for kind, path in candidates:
            if not path.is_file():
                continue
            stat = path.stat()
            # 固定文件名可能来自历史任务；仅返回本次执行期间产生或更新的文件。
            if stat.st_mtime + 1 < started_at:
                continue
            artifacts.append(
                AssessmentArtifact(
                    kind=kind,
                    path=str(path.relative_to(BASE_DIR)),
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                )
            )
        return artifacts
