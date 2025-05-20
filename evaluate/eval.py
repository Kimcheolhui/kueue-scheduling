import argparse, os, time, uuid, yaml, requests
from string import Template

# ────────── 환경 변수 ──────────
GATEWAY_URL      = os.getenv("GATEWAY_URL",
                             "http://192.168.10.105")
JOB_TEMPLATE     = os.getenv("JOB_TEMPLATE", "job-template.yaml")

QUOTA_API_SVC    = os.getenv("QUOTA_API_SVC", "http://192.168.10.104")
GPU_CQ           = os.getenv("GPU_CQ",  "gpu-cluster-queue")
CPU_CQ           = os.getenv("CPU_CQ",  "cpu-cluster-queue")
GPU_FLAVOR       = os.getenv("GPU_FLAVOR", "gpu-flavor")
CPU_FLAVOR       = os.getenv("CPU_FLAVOR", "cpu-flavor")

POLL_SEC         = int(os.getenv("POLL_SEC", "5"))      # 폴링 주기
CONFIRM_TIMES    = int(os.getenv("CONFIRM_TIMES", "3")) # 연속 확인 횟수
TIMEOUT_SEC      = int(os.getenv("TIMEOUT_SEC", "3600"))

TOTAL_JOBS       = 30

# ────────── 템플릿 로딩 ──────────
with open(JOB_TEMPLATE) as f:
    template = Template(f.read())

def build_yaml(job_name, workload_type, steps):
    return template.substitute(
        JOB_NAME      = job_name,
        WORKLOAD_TYPE = workload_type,
        STEPS         = steps,
    )

def submit_yaml(yaml_text, job_name, job_type, steps):
    print(f"Submitted job: {job_name} [type={job_type}, steps={steps}]")

    files = {"job_file": ("job.yaml", yaml_text, "application/x-yaml")}
    # r = requests.post(f"{GATEWAY_URL}/job-submit", files=files, timeout=10)
    r = requests.post(f"{GATEWAY_URL}/job-submit-no-eval", files=files, timeout=10)
    r.raise_for_status()

# ────────── CQ 상태 확인 ──────────
def cq_idle(cq, flavor, resource):
    quota = requests.get(f"{QUOTA_API_SVC}/quota",
                         params={"clusterqueue": cq,
                                 "flavor": flavor,
                                 "resource": resource},
                         timeout=3).json()
    pend  = requests.get(f"{QUOTA_API_SVC}/pending",
                         params={"clusterqueue": cq},
                         timeout=3).json()

    print(f"[{cq}] used={quota['used']}, reserved={quota['reserved']}, "
          f"pending={pend['pendingWorkloads']}")

    return (quota["used"] == 0 and quota["reserved"] == 0 and
            pend["pendingWorkloads"] == 0)

def wait_all_complete():
    stable = 0
    start  = time.time()
    while True:
        idle_gpu = cq_idle(GPU_CQ, GPU_FLAVOR, "gpu")
        idle_cpu = cq_idle(CPU_CQ, CPU_FLAVOR, "cpu")

        stable = stable + 1 if (idle_gpu and idle_cpu) else 0
        if stable >= CONFIRM_TIMES:
            return time.time() - start

        if time.time() - start > TIMEOUT_SEC:
            raise TimeoutError("TIMEOUT: Job 완료를 확인하지 못했습니다.")
        time.sleep(POLL_SEC)

# ────────── 메인 로직 ──────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="20 Job 제출 후 총 완료 시간 측정")
    ap.add_argument("--scenario", choices=["uniform", "burst"], required=True,
                    help="uniform: 번갈아 1개씩 제출 / burst: 10+10개 버스트")
    args = ap.parse_args()

    start_submit = time.time()

    if args.scenario == "uniform":
        for i in range(TOTAL_JOBS):
            kind, steps = ("gpu", 30) if i % 2 == 0 else ("light-gpu", 5)
            name = f"job-{kind}-{i}-{uuid.uuid4().hex[:6]}"
            submit_yaml(build_yaml(name, kind, steps), name, kind, steps)
            time.sleep(1)   # 1초 간격
    else:  # burst
        for i in range(TOTAL_JOBS // 2):
            name = f"job-gpu-{i}-{uuid.uuid4().hex[:6]}"
            submit_yaml(build_yaml(name, "gpu", 30), name, "gpu", 30)
        for i in range(TOTAL_JOBS // 2):
            name = f"job-light-{i}-{uuid.uuid4().hex[:6]}"
            submit_yaml(build_yaml(name, "light-gpu", 5), name, "light-gpu", 5)

    elapsed = wait_all_complete()
    print(f"[{args.scenario}] {TOTAL_JOBS}개 Job 완료까지 {elapsed:.1f} 초 소요")
