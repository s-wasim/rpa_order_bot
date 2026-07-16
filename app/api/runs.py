import json
import threading
import time
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    RunListItem, RunDetailOut, RunStepOut, PlanItemOut, RunSummaryOut,
    ItemResultOut, StartRunResponse,
)
from app.db import get_session, Run, Inventory
from app.graph.runner import run_agent

router = APIRouter()


def _run_worker(run_id: int) -> None:
    try:
        run_agent(run_id)
    except Exception as e:
        with get_session() as session:
            run = session.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "failed"
                run.summary_json = {
                    "ordered": 0, "skipped": 0, "failed": 0, "total": 0,
                    "order_number": None, "item_results": [], "error": str(e),
                }


@router.post("/api/runs", response_model=StartRunResponse)
def start_run():
    with get_session() as session:
        active = session.query(Run).filter(Run.status == "running").first()
        if active:
            return StartRunResponse(ok=False, reason="A reorder run is already in progress.")

        low_count = session.query(Inventory).filter(
            (Inventory.qty + Inventory.on_order) < Inventory.reorder_threshold
        ).count()
        if low_count == 0:
            return StartRunResponse(ok=False, reason="All inventory items are adequately stocked. No reorder needed.")

        run = Run(status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    threading.Thread(target=_run_worker, args=(run_id,), daemon=True).start()
    return StartRunResponse(ok=True, run_id=run_id)


@router.get("/api/runs", response_model=list[RunListItem])
def list_runs():
    with get_session() as session:
        runs = session.query(Run).order_by(Run.created_at.desc()).limit(20).all()
        return [RunListItem(id=r.id, created_at=r.created_at, status=r.status) for r in runs]


def _screenshot_url_path(run_id: int, screenshot_path: Optional[str]) -> Optional[str]:
    if not screenshot_path:
        return None
    filename = screenshot_path.replace("\\", "/").rsplit("/", 1)[-1]
    return f"{run_id}/{filename}"


def _serialize_run(run: Run) -> RunDetailOut:
    steps = sorted(run.steps, key=lambda s: (s.seq, s.id))
    return RunDetailOut(
        id=run.id, created_at=run.created_at, status=run.status,
        plan_json=[PlanItemOut(**item) for item in run.plan_json] if run.plan_json else None,
        summary_json=RunSummaryOut(
            ordered=run.summary_json["ordered"], skipped=run.summary_json["skipped"],
            failed=run.summary_json["failed"], total=run.summary_json["total"],
            order_number=run.summary_json.get("order_number"),
            item_results=[ItemResultOut(**r) for r in run.summary_json.get("item_results", [])],
        ) if run.summary_json else None,
        steps=[
            RunStepOut(
                id=s.id, seq=s.seq, label=s.label, detail=s.detail, status=s.status,
                screenshot_path=_screenshot_url_path(run.id, s.screenshot_path),
                reasoning=s.reasoning,
            )
            for s in steps
        ],
    )


@router.get("/api/runs/{run_id}", response_model=Optional[RunDetailOut])
def get_run(run_id: int):
    with get_session() as session:
        run = session.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None
        return _serialize_run(run)


def _sse_frame(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/api/runs/{run_id}/stream")
def stream_run(run_id: int):
    def generate():
        seen_plan = False
        seen_summary = False
        last_status = None
        seen_step_versions = {}

        while True:
            with get_session() as session:
                run = session.query(Run).filter(Run.id == run_id).first()
                if not run:
                    yield _sse_frame("status", {"status": "not_found"})
                    return

                if run.status != last_status:
                    yield _sse_frame("status", {"status": run.status})
                    last_status = run.status

                if run.plan_json and not seen_plan:
                    yield _sse_frame("plan", run.plan_json)
                    seen_plan = True

                steps = sorted(run.steps, key=lambda s: (s.seq, s.id))
                for s in steps:
                    version = (s.status, s.detail, s.screenshot_path, s.reasoning)
                    if seen_step_versions.get(s.id) != version:
                        seen_step_versions[s.id] = version
                        yield _sse_frame("step", {
                            "id": s.id, "seq": s.seq, "label": s.label, "detail": s.detail,
                            "status": s.status,
                            "screenshot_path": _screenshot_url_path(run.id, s.screenshot_path),
                            "reasoning": s.reasoning,
                        })

                if run.summary_json and not seen_summary:
                    yield _sse_frame("summary", run.summary_json)
                    seen_summary = True

                terminal = run.status in ("succeeded", "failed")

            if terminal:
                return
            time.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")
