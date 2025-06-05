import os, copy, yaml, requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from kubernetes import client, config

# ----- 환경변수 -----
GPU_CQ   = os.getenv("GPU_CQ",   "gpu-cluster-queue")
CPU_CQ   = os.getenv("CPU_CQ",   "cpu-cluster-queue")
GPU_LQ   = os.getenv("GPU_LQ",   "user-gpu-queue")
CPU_LQ   = os.getenv("CPU_LQ",   "user-cpu-queue")
QUOTA_API_SVC = os.getenv("QUOTA_API_SVC", "http://quota-svc.quota-api.svc")
JOB_NAMESPACE = os.getenv("JOB_NAMESPACE", "research")
PENDING_THRESHOLD = int(os.getenv("PENDING_THRESHOLD", "10"))
CPU_RUNNING_THRESHOLD = int(os.getenv("CPU_RUNNING_THRESHOLD", "3")) # CPU Cluster의 Worker nodes 수

# ----- K8s Client -----
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
batch_api = client.BatchV1Api()

app = FastAPI()

# ----- 외부 API 호출 -----
def available_quota(clusterqueue, flavor, resource):
    r = requests.get(f"{QUOTA_API_SVC}/quota",
                     params={"clusterqueue": clusterqueue,
                             "flavor": flavor,
                             "resource": resource}, timeout=3)
    r.raise_for_status()
    return r.json()["available"]

def check_pending(clusterqueue):
    r = requests.get(f"{QUOTA_API_SVC}/workloads",
                     params={"clusterqueue": clusterqueue}, timeout=3)
    r.raise_for_status()
    return r.json()["pendingWorkloads"]

def check_reserving(clusterqueue):
    r = requests.get(f"{QUOTA_API_SVC}/workloads",
                     params={"clusterqueue": clusterqueue}, timeout=3)
    r.raise_for_status()
    return r.json()["reservingWorkloads"]

# ----- Job 제출 API -----
@app.post("/job-submit")
async def job_submit(job_file: UploadFile = File(...)):
    job = yaml.safe_load(await job_file.read())
    labels = job.setdefault("metadata", {}).setdefault("labels", {})

    # GPU Job or Light GPU Job
    workload_type = labels.get("workload-type", "gpu")

    # 1) GPU Job -> 바로 제출
    # CPU에서 실행할 수 없는 Job이므로, GPU ClusterQueue에 바로 제출
    if workload_type == "gpu":
        batch_api.create_namespaced_job(JOB_NAMESPACE, job)
        return {"message": "GPU Job submitted", "queued": GPU_LQ}
        
    # 2) Light GPU Job -> 추가 로직
    # CPU에서 실행할 수 있는 Job이므로, 추가 로직을 거쳐 CPU or GPU ClusterQueue에 제출
    gpu_available = available_quota(GPU_CQ, "gpu-flavor", "nvidia.com/gpu")
    if gpu_available > 0:
        batch_api.create_namespaced_job(JOB_NAMESPACE, job)
        return {"message": "Light GPU Job submitted", "queued": GPU_LQ}
            
    # Available GPU가 없는 경우, pendingWorkload 수를 확인
    gpu_wait = check_pending(GPU_CQ)
    # 기준치보다 적은 경우, GPU ClusterQueue에 제출
    if gpu_wait < PENDING_THRESHOLD:
        batch_api.create_namespaced_job(JOB_NAMESPACE, job)
        return {"message": "Light GPU Job submitted", "queued": GPU_LQ}

    # 기준치보다 많은 경우, CPU ClusterQueue의 available quota를 확인
    cpu_available = available_quota(CPU_CQ, "cpu-flavor", "cpu")
    cont = job["spec"]["template"]["spec"]["containers"][0]
    cpu_need = int(cont["resources"]["requests"]["cpu"]) * job["spec"].get("completions", 1)

    # Available CPU가 충분해 CPU ClusterQueue에 제출할 수 있는 경우
    if cpu_available >= cpu_need:

        cpu_running = check_reserving(CPU_CQ)
        
        if cpu_running >= CPU_RUNNING_THRESHOLD:
            batch_api.create_namespaced_job(JOB_NAMESPACE, job)
            return {"message": "Light GPU Job submitted", "queued": GPU_LQ}

        new_job = copy.deepcopy(job)
        meta = new_job["metadata"]
        meta["name"] = meta["name"].replace("-gpu", "-cpu")
        meta.setdefault("annotations", {})["kueue.x-k8s.io/queue-name"] = CPU_LQ

        for c in new_job["spec"]["template"]["spec"]["containers"]:
            c["resources"]["requests"].pop("nvidia.com/gpu", None)
            c["resources"]["limits"].pop("nvidia.com/gpu", None)

            for env in c.get("env", []):
                if env["name"] == "RUN_ENV":
                    env["value"] = "cpu"

        batch_api.create_namespaced_job(JOB_NAMESPACE, new_job)
        return { "message": "Light GPU Job submitted", "queued": CPU_LQ}
            
    batch_api.create_namespaced_job(JOB_NAMESPACE, job)
    return {"message": "Light GPU Job submitted", "queued": GPU_LQ}

# 별도의 조건 없이 GPU Job을 제출
@app.post("/job-submit-no-eval")
async def job_submit(job_file: UploadFile = File(...)):
    job = yaml.safe_load(await job_file.read())
    labels = job.setdefault("metadata", {}).setdefault("labels", {})

    # GPU Job or Light GPU Job
    workload_type = labels.get("workload-type", "gpu")

    if workload_type == "gpu":
        batch_api.create_namespaced_job(JOB_NAMESPACE, job)
        return {"message": "GPU Job submitted", "queued": GPU_LQ}
    
            
    batch_api.create_namespaced_job(JOB_NAMESPACE, job)
    return {"message": "Light GPU Job submitted", "queued": GPU_LQ}
