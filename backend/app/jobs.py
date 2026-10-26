import os
import threading


def env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def max_syllabi_per_day() -> int:
    return env_int("MAX_SYLLABI_PER_USER_PER_DAY", 3)


def max_active_jobs_per_user() -> int:
    return env_int("MAX_ACTIVE_JOBS_PER_USER", 1)


class JobGate:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._active = 0

    def _limit(self) -> int:
        return env_int("MAX_CONCURRENT_JOBS", 2)

    def try_acquire(self) -> bool:
        with self._condition:
            if self._active >= self._limit():
                return False
            self._active += 1
            return True

    def acquire(self) -> None:
        with self._condition:
            while self._active >= self._limit():
                self._condition.wait()
            self._active += 1

    def release(self) -> None:
        with self._condition:
            if self._active > 0:
                self._active -= 1
            self._condition.notify_all()


job_gate = JobGate()
limits_lock = threading.Lock()
