from fastapi import APIRouter
import yaml
import os

router = APIRouter()


@router.get("/rules")
async def get_rules():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "rules")
    result = {}
    for fname in ("_base.yaml", "melvor_idle.yaml"):
        path = os.path.join(base, fname)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    result[fname] = yaml.safe_load(f)
            except Exception as e:
                result[fname] = {"error": str(e)}
    if not result:
        return {"rules": {}, "error": "Rules files not found"}
    return {"rules": result}
