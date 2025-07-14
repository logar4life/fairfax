from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import subprocess
import sys
import threading
import os

app = FastAPI()

# Store status in memory (for demo purposes)
status = {"running": False, "last_result": None}

def run_scripts():
    status["running"] = True
    try:
        # Run fairfax.py
        result1 = subprocess.run([sys.executable, "fairfax.py"], capture_output=True, text=True)
        if result1.returncode != 0:
            status["last_result"] = {
                "success": False,
                "step": "fairfax.py",
                "stdout": result1.stdout,
                "stderr": result1.stderr,
                "exit_code": result1.returncode
            }
            status["running"] = False
            return
        # Run fairfax_image_analyzer.py
        result2 = subprocess.run([sys.executable, "fairfax_image_analyzer.py"], capture_output=True, text=True)
        if result2.returncode != 0:
            status["last_result"] = {
                "success": False,
                "step": "fairfax_image_analyzer.py",
                "stdout": result2.stdout,
                "stderr": result2.stderr,
                "exit_code": result2.returncode
            }
            status["running"] = False
            return
        status["last_result"] = {
            "success": True,
            "fairfax_stdout": result1.stdout,
            "fairfax_image_analyzer_stdout": result2.stdout
        }
    finally:
        status["running"] = False

@app.post("/run")
def run_all(background_tasks: BackgroundTasks):
    if status["running"]:
        return JSONResponse({"status": "already running"}, status_code=409)
    background_tasks.add_task(run_scripts)
    return {"status": "started"}

@app.get("/status")
def get_status():
    return status
