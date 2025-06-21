from fastapi import APIRouter
import os
import sys

router = APIRouter(tags=["debug"])

@router.get("/debug-paths")
def debug_paths():
    return {
        "cwd": os.getcwd(),
        "sys_path": sys.path,
        "files": os.listdir(".")
    } 