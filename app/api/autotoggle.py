from fastapi import APIRouter, HTTPException
from app.pipeline.autotoggle import step
from app.schemas import AutoToggleStepRequest, AutoToggleStepResponse

router = APIRouter()


@router.post("/autotoggle/step", response_model=AutoToggleStepResponse)
def autotoggle_step(request: AutoToggleStepRequest):
    try:
        return step(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
