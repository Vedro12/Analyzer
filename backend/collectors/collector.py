import aiohttp
import asyncio
from backend.storage import save_data
from backend import config

# ---------- Базовые асинхронные запросы ----------
async def async_request(url: str, params: dict = None, timeout: int = 30):
    headers = {"Authorization": f"Bearer {config.iam_token}"}
    params = params or {}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"error": f"HTTP {resp.status}", "status": "not_configured"}
        except asyncio.TimeoutError:
            return {"error": "timeout", "status": "not_configured"}
        except Exception as e:
            return {"error": str(e), "status": "not_configured"}

async def async_request_with_pagination(url: str, item_key: str, params: dict = None):
    """Асинхронный запрос с пагинацией"""
    params = params or {}
    all_items = []
    page_token = None
    
    while True:
        if page_token:
            params["pageToken"] = page_token
        
        data = await async_request(url, params)
        if "error" in data:
            break
        
        items = data.get(item_key, [])
        all_items.extend(items)
        
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    
    return all_items

# ---------- Асинхронные вызовы для Compute ----------
async def yc_get_compute_info(resource_type: str, endpoint: str = "", params: dict = None):
    base_url = f"https://compute.api.cloud.yandex.net/compute/v1/{resource_type}"
    url = f"{base_url}{endpoint}"
    params = params or {}
    return await async_request(url, params)

async def get_resource_with_bindings(resource_type: str, item_id_key: str, resource_id: str, status: str = None):
    """Получает ресурс и его привязки параллельно"""
    details_task = yc_get_compute_info(resource_type, params={"folderId": config.folder_id})
    bindings_task = yc_get_compute_info(resource_type, endpoint=f"/{resource_id}:listAccessBindings")
    
    details, bindings = await asyncio.gather(details_task, bindings_task)
    
    resource_data = {
        item_id_key: resource_id,
        "details": details,
        "bindings": bindings
    }
    
    # Только для ВМ собираем вывод серийного порта (если ВМ включена)
    if resource_type == "instances" and status == "RUNNING":
        serial_task = yc_get_compute_info(resource_type, endpoint=f"/{resource_id}:serialPortOutput")
        serial_resp = await serial_task
        resource_data["serial"] = serial_resp.get("contents", "") if isinstance(serial_resp, dict) else ""
    elif resource_type == "instances":
        resource_data["serial"] = "VM не запущена, вывод серийного порта отсутствует"
    
    return resource_data

async def collect_all_compute_data():
    """Параллельный сбор всех ресурсов Compute"""
    # Получаем списки ресурсов
    instances_list = await async_request_with_pagination(
        f"https://compute.api.cloud.yandex.net/compute/v1/instances",
        "instances",
        {"folderId": config.folder_id}
    )
    disks_list = await async_request_with_pagination(
        f"https://compute.api.cloud.yandex.net/compute/v1/disks",
        "disks",
        {"folderId": config.folder_id}
    )
    images_list = await async_request_with_pagination(
        f"https://compute.api.cloud.yandex.net/compute/v1/images",
        "images",
        {"folderId": config.folder_id}
    )
    snapshots_list = await async_request_with_pagination(
        f"https://compute.api.cloud.yandex.net/compute/v1/snapshots",
        "snapshots",
        {"folderId": config.folder_id}
    )
    
    # Параллельно собираем детали 
    instances_tasks = [
        get_resource_with_bindings("instances", "instance_id", vm.get("id"), vm.get("status"))
        for vm in instances_list if vm.get("id")
    ]
    disks_tasks = [
        get_resource_with_bindings("disks", "disk_id", disk.get("id"))
        for disk in disks_list if disk.get("id")
    ]
    images_tasks = [
        get_resource_with_bindings("images", "image_id", img.get("id"))
        for img in images_list if img.get("id")
    ]
    snapshots_tasks = [
        get_resource_with_bindings("snapshots", "snapshot_id", snap.get("id"))
        for snap in snapshots_list if snap.get("id")
    ]
    
    all_instances, all_disks, all_images, all_snapshots = await asyncio.gather(
        asyncio.gather(*instances_tasks) if instances_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*disks_tasks) if disks_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*images_tasks) if images_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*snapshots_tasks) if snapshots_tasks else asyncio.sleep(0, result=[])
    )
    
    result = {
        "instances": all_instances,
        "disks": all_disks,
        "images": all_images,
        "snapshots": all_snapshots
    }
    
    save_data(result, "backend/data/compute.json")
    return result

# ---------- Асинхронный сбор S3 ----------
async def yc_get_s3_info(endpoint: str = "", params: dict = None, use_folder: bool = True):
    base_url = "https://storage.api.cloud.yandex.net/storage/v1/buckets"
    url = f"{base_url}{endpoint}"
    params = params or {}
    if use_folder:
        params["folderId"] = config.folder_id
    return await async_request(url, params)

async def collect_all_s3_data():
    """Параллельный сбор всех данных S3"""
    # Получаем список бакетов
    buckets_resp = await yc_get_s3_info()
    buckets = buckets_resp.get("buckets", []) if isinstance(buckets_resp, dict) else []
    
    # Параллельно собираем данные по каждому бакету
    async def process_bucket(bucket):
        name = bucket.get("name")
        stats, https, bindings, inventory = await asyncio.gather(
            yc_get_s3_info(endpoint=f"/{name}:getStats", use_folder=False),
            yc_get_s3_info(endpoint=f"/{name}:getHttpsConfig", use_folder=False),
            yc_get_s3_info(endpoint=f"/{name}:listAccessBindings", use_folder=False),
            yc_get_s3_info(endpoint=f"/{name}:listInventoryConfiguration", use_folder=False)
        )
        return {
            "bucket": bucket,
            "stats": stats,
            "https": https,
            "bindings": bindings,
            "inventory": inventory
        }
    
    tasks = [process_bucket(bucket) for bucket in buckets]
    result_s3 = await asyncio.gather(*tasks) if tasks else []
    
    save_data(result_s3, "backend/data/s3.json")
    return result_s3

# ---------- Асинхронный сбор VPC ----------
async def yc_get_vpc_info(endpoint: str = "", params: dict = None, use_folder: bool = True):
    base_url = "https://vpc.api.cloud.yandex.net/vpc/v1/"
    url = f"{base_url}{endpoint}"
    params = params or {}
    if use_folder:
        params["folderId"] = config.folder_id
    return await async_request(url, params)

async def collect_all_vpc_data():
    """Параллельный сбор всех VPC ресурсов"""
    endpoints = ["addresses", "gateways", "networks", "routeTables", "securityGroups", "subnets"]
    
    tasks = [yc_get_vpc_info(endpoint) for endpoint in endpoints]
    results = await asyncio.gather(*tasks)
    
    vpc_data = {
        "addresses": results[0],
        "gateways": results[1],
        "networks": results[2],
        "routeTables": results[3],
        "securityGroups": results[4],
        "subnets": results[5]
    }
    
    save_data(vpc_data, "backend/data/vpc.json")
    return vpc_data