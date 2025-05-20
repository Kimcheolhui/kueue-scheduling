from flask import Flask, jsonify, request
import os
import json
import subprocess

app = Flask(__name__)


def get_cq_json(cq_name: str) -> dict:
    raw = subprocess.check_output(
        ["kubectl", "get", "clusterqueue", cq_name, "-o", "json"], text=True
    )
    return json.loads(raw)


def query_clusterqueue(cq_name:str, flavor:str, resource:str):

    # raw
    data = get_cq_json(cq_name)

    print(data)

    # clusterqueue quota
    # spec.nominalQuota
    quota = int(next(
        res for rg in data["spec"]["resourceGroups"]
        for fl in rg["flavors"] if fl["name"] == flavor
        for res in fl["resources"] if res["name"] == resource
    )["nominalQuota"])

    # clusterqueue reservation
    # status.flavorsReservation[*].total
    reserved = int(next(
        res for fr in data["status"]["flavorsReservation"]
        if fr["name"] == flavor
        for res in fr["resources"] if res["name"] == resource
    )["total"])

    # clusterqueue usage
    # status.flavorsUsage[*].total
    used = int(next(
        res for fl in data["status"]["flavorsUsage"]
        if fl["name"] == flavor
        for res in fl["resources"] if res["name"] == resource
    )["total"])

    return {"available": quota - reserved,
            "quota": quota,
            "reserved": reserved,
            "used": used,
            "resource": resource,
            "clusterqueue": cq_name,
            "flavor": flavor}

def query_pending(cq_name: str):

    data = get_cq_json(cq_name)

    pending = int(data["status"].get("pendingWorkloads", 0))
    reserving = int(data["status"].get("reservingWorkloads", 0))

    return {
        "clusterqueue": cq_name,
        "pendingWorkloads": pending,
        "reservingWorkloads": reserving,
    }


@app.route("/quota")
def get_quota():
    # 쿼리 파라미터
    cq = request.args.get("clusterqueue", "gpu-cluster-queue")
    flavor = request.args.get("flavor", "gpu-flavor")
    res = request.args.get("resource", "gpu")

    if res == "gpu":
        res = "nvidia.com/gpu"

    try:
        return jsonify(query_clusterqueue(cq, flavor, res))
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/pending")
def get_pending():
    cq = request.args.get("clusterqueue", "gpu-cluster-queue")
    try:
        return jsonify(query_pending(cq))
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)