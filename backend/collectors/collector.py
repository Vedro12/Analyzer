# backend/collectors/collector.py

from backend.storage import save_data
from backend import config
import requests

def yc_get_compute_info(resource_type: str, endpoint: str = "", params: dict = None):

    base_url = f"https://compute.api.cloud.yandex.net/compute/v1/{resource_type}"
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {config.iam_token}"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def yc_get_s3_info(endpoint: str = "", params: dict = None, use_folder: bool = True):

    base_url = "https://storage.api.cloud.yandex.net/storage/v1/buckets"
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {config.iam_token}"}
    if params is None:
        params = {}
    if use_folder:
        params["folderId"] = config.folder_id
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    
def yc_get_vpc_info(endpoint: str = "", params: dict = None, use_folder: bool = True):

    base_url = f"https://vpc.api.cloud.yandex.net/vpc/v1/"
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {config.iam_token}"}
    if params is None:
        params = {}
    if use_folder:
        params["folderId"] = config.folder_id
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    
def call_compute(resource_type, item_id_key, output_filename=None):
    if output_filename is None:
        output_filename = "backend/data/compute.json"
    
    resp = call_api_safely(
        yc_get_compute_info,
        resource_type,
        params={"folderId": config.folder_id}
    )
    
    resources = resp.get(resource_type, []) if isinstance(resp, dict) else []
    result_resources = []
    
    for resource in resources:
        resource_id = resource.get("id")
        
        bindings = call_api_safely(
            yc_get_compute_info,
            resource_type,
            endpoint=f"/{resource_id}:listAccessBindings"
        )
        
        resource_data = {
            item_id_key: resource_id,
            "details": resource,
            "bindings": bindings
        }
        
        if resource_type == "instances" and resource.get("status") == "RUNNING":
            serial_resp = call_api_safely(
                yc_get_compute_info,
                resource_type,
                endpoint=f"/{resource_id}:serialPortOutput"
            )
            resource_data["serial"] = serial_resp.get("contents", "") if isinstance(serial_resp, dict) else ""
        elif resource_type == "instances":
            resource_data["serial"] = "VM не запущена, вывод серийного порта отсутствует"
        
        result_resources.append(resource_data)
    
    save_data(result_resources, output_filename)
    return result_resources

def call_api_safely(call_func, *args, error_message="not_configured", **kwargs):
    try:
        return call_func(*args, **kwargs)
    except requests.exceptions.RequestException as e:
        print("API ERROR:", e)
        return {"error": error_message}