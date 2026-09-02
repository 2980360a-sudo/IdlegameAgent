# IdleAgent v0.4.0 - core/scheduler.py
# Agent 调度器：诊断 / 决策 / 执行 / 紧急检查的定时任务

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Callable


class AgentScheduler:
    """Agent 调度器。"""

    def __init__(self, diagnosis_interval_min: int = 60,
                 decision_interval_min: int = 10,
                 emergency_check_sec: int = 30):
        self.diagnosis_interval = diagnosis_interval_min
        self.decision_interval = decision_interval_min
        self.emergency_check = emergency_check_sec
        self.scheduler = AsyncIOScheduler()
        self.jobs = {}

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()

    def schedule_diagnosis(self, callback: Callable):
        self.jobs['diagnosis'] = self.scheduler.add_job(
            callback, IntervalTrigger(minutes=self.diagnosis_interval),
            id='diagnosis', replace_existing=True
        )

    def schedule_decision(self, callback: Callable):
        self.jobs['decision'] = self.scheduler.add_job(
            callback, IntervalTrigger(minutes=self.decision_interval),
            id='decision', replace_existing=True
        )

    def schedule_emergency(self, callback: Callable):
        self.jobs['emergency'] = self.scheduler.add_job(
            callback, IntervalTrigger(seconds=self.emergency_check),
            id='emergency', replace_existing=True
        )

    def schedule_patrol(self, callback: Callable):
        self.jobs['patrol'] = self.scheduler.add_job(
            callback, IntervalTrigger(minutes=60),
            id='patrol', replace_existing=True
        )

    def pause_job(self, job_id: str):
        if job_id in self.jobs:
            self.jobs[job_id].pause()

    def resume_job(self, job_id: str):
        if job_id in self.jobs:
            self.jobs[job_id].resume()
