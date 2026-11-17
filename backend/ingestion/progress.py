import asyncio
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ActiveDocumentInfo(BaseModel):
    title: str = ""
    filename: str = ""
    url: str = ""
    source_type: str = "pdf"
    page: int | None = None
    total_pages: int | None = None
    size_kb: float | None = None


class PipelineLogEntry(BaseModel):
    timestamp: str
    level: Literal[
        "info", "fetch", "ocr", "chunk", "embed", "bypass", "warn", "error", "success"
    ] = "info"
    message: str
    tag: str | None = None


class PipelineProgressState(BaseModel):
    source_id: str | None = None
    source_name: str = "Idle"
    status: Literal["idle", "fetching", "completed", "error"] = "idle"
    phase: str = (
        "idle"  # "portal_fetch", "pdf_download", "hash_check", "ocr_inference", "chunking", "embedding", "completed"
    )
    step_index: int = 0  # 1 to 5
    total_steps: int = 5
    current_action: str = "Awaiting ingestion trigger"
    next_action: str = "Scheduled or manual trigger"
    active_document: ActiveDocumentInfo | None = None
    stats: dict[str, int] = Field(
        default_factory=lambda: {
            "checked": 0,
            "total": 0,
            "ocr_count": 0,
            "chunks_count": 0,
            "bypassed_count": 0,
            "created_count": 0,
            "updated_count": 0,
        }
    )
    logs: list[PipelineLogEntry] = Field(default_factory=list)
    started_at: str | None = None
    updated_at: str | None = None


class PipelineProgressTracker:
    """Thread-safe and async-compatible live progress tracker for EduSync ingestion pipelines."""

    def __init__(self, max_logs: int = 150) -> None:
        self.max_logs = max_logs
        self._states: dict[str, PipelineProgressState] = {}
        self._global_state: PipelineProgressState = PipelineProgressState()
        self._lock = asyncio.Lock()

    def _now_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _now_iso(self) -> str:
        return datetime.now().isoformat()

    def start_source(
        self,
        source_id: str | UUID,
        source_name: str,
        total_items: int = 0,
    ) -> None:
        """Initialize progress tracking when an ingestion source starts processing."""
        sid = str(source_id)
        now_time = self._now_time()
        state = PipelineProgressState(
            source_id=sid,
            source_name=source_name,
            status="fetching",
            phase="portal_fetch",
            step_index=1,
            total_steps=5,
            current_action=f"Connecting to portal: {source_name}",
            next_action="Retrieve notice index & circular entries",
            stats={
                "checked": 0,
                "total": total_items,
                "ocr_count": 0,
                "chunks_count": 0,
                "bypassed_count": 0,
                "created_count": 0,
                "updated_count": 0,
            },
            logs=[
                PipelineLogEntry(
                    timestamp=now_time,
                    level="info",
                    tag="START",
                    message=f"Started ingestion for source '{source_name}'",
                )
            ],
            started_at=self._now_iso(),
            updated_at=self._now_iso(),
        )
        self._states[sid] = state
        self._global_state = state

    def update_step(
        self,
        phase: str,
        step_index: int,
        current_action: str,
        next_action: str,
        source_id: str | UUID | None = None,
        active_document: dict[str, Any] | None = None,
        log_message: str | None = None,
        log_level: Literal[
            "info", "fetch", "ocr", "chunk", "embed", "bypass", "warn", "error", "success"
        ] = "info",
        log_tag: str | None = None,
        stats_update: dict[str, int] | None = None,
    ) -> None:
        """Update active pipeline step, next anticipated action, and append live log."""
        sid = str(source_id) if source_id else self._global_state.source_id
        target = self._states.get(sid) if sid else self._global_state
        if not target:
            target = self._global_state

        target.phase = phase
        target.step_index = step_index
        target.current_action = current_action
        target.next_action = next_action
        target.updated_at = self._now_iso()

        if active_document is not None:
            target.active_document = ActiveDocumentInfo(**active_document)

        if stats_update:
            for k, v in stats_update.items():
                if k in target.stats:
                    target.stats[k] = v

        if log_message:
            self._append_log(target, log_message, level=log_level, tag=log_tag)

        # Synchronize global state pointer
        self._global_state = target

    def log(
        self,
        message: str,
        level: Literal[
            "info", "fetch", "ocr", "chunk", "embed", "bypass", "warn", "error", "success"
        ] = "info",
        tag: str | None = None,
        source_id: str | UUID | None = None,
    ) -> None:
        """Append an isolated log entry to the active source."""
        sid = str(source_id) if source_id else self._global_state.source_id
        target = self._states.get(sid) if sid else self._global_state
        if target:
            self._append_log(target, message, level=level, tag=tag)

    def _append_log(
        self,
        state: PipelineProgressState,
        message: str,
        level: Literal[
            "info", "fetch", "ocr", "chunk", "embed", "bypass", "warn", "error", "success"
        ] = "info",
        tag: str | None = None,
    ) -> None:
        entry = PipelineLogEntry(
            timestamp=self._now_time(),
            level=level,
            tag=tag or level.upper(),
            message=message,
        )
        state.logs.append(entry)
        if len(state.logs) > self.max_logs:
            state.logs = state.logs[-self.max_logs :]

    def finish_source(
        self,
        summary_message: str,
        source_id: str | UUID | None = None,
        stats: dict[str, int] | None = None,
    ) -> None:
        """Mark ingestion as completed and append final summary."""
        sid = str(source_id) if source_id else self._global_state.source_id
        target = self._states.get(sid) if sid else self._global_state
        if target:
            target.status = "completed"
            target.phase = "completed"
            target.step_index = 5
            target.current_action = "Ingestion pipeline completed successfully"
            target.next_action = "Standing by for next scheduled interval or manual trigger"
            target.active_document = None
            target.updated_at = self._now_iso()
            if stats:
                target.stats.update(stats)
            self._append_log(
                target,
                summary_message,
                level="success",
                tag="DONE",
            )
            self._global_state = target

    def fail_source(
        self,
        error_message: str,
        source_id: str | UUID | None = None,
    ) -> None:
        """Mark ingestion as failed with error details."""
        sid = str(source_id) if source_id else self._global_state.source_id
        target = self._states.get(sid) if sid else self._global_state
        if target:
            target.status = "error"
            target.phase = "error"
            target.current_action = f"Failed: {error_message}"
            target.next_action = "Admin review / retry"
            target.updated_at = self._now_iso()
            self._append_log(
                target,
                f"Error during ingestion: {error_message}",
                level="error",
                tag="ERROR",
            )
            self._global_state = target

    def get_state(self, source_id: str | UUID | None = None) -> PipelineProgressState:
        """Retrieve progress state for a specific source ID or current active global state."""
        if source_id:
            sid = str(source_id)
            if sid in self._states:
                return self._states[sid]
        return self._global_state


# Shared singleton progress tracker
progress_tracker = PipelineProgressTracker()
