from fastapi import APIRouter
import yaml
import os

router = APIRouter()

@router.get("/rules")
async def get_rules():
    # 读取 config/rules/melvor_idle.yaml 并返回
    rules_path = os.path.join("config", "rules", "melvor_idle.yaml")
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return {"rules": data}
    except FileNotFoundError:
        return {"rules": {}, "error": "Rules file not found"}
