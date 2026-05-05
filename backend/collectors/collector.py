# backend/collectors/collector.py
import aiohttp
import asyncio


# ---------- Базовые асинхронные запросы ----------
async def async_request(
    iam_token: str,
    url: str,
    params: dict = None,
    timeout: int = 30
):
    headers = {"Authorization": f"Bearer {iam_token}"}
    params = params or {}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout
            ) as resp:
                if resp.status == 200:
                    return await resp.json()

                return {
                    "error": f"HTTP {resp.status}",
                    "status": "not_configured"
                }

        except asyncio.TimeoutError:
            return {"error": "timeout", "status": "not_configured"}

        except Exception as e:
            return {"error": str(e), "status": "not_configured"}


async def async_request_with_pagination(
    iam_token: str,
    url: str,
    item_key: str,
    params: dict = None
):
    params = params.copy() if params else {}
    all_items = []
    page_token = None

    while True:
        if page_token:
            params["pageToken"] = page_token

        data = await async_request(iam_token, url, params)

        if "error" in data:
            break

        items = data.get(item_key, [])
        all_items.extend(items)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_items


# ---------- Compute ----------
async def yc_get_compute_info(
    iam_token: str,
    resource_type: str,
    endpoint: str = "",
    params: dict = None
):
    base_url = f"https://compute.api.cloud.yandex.net/compute/v1/{resource_type}"
    url = f"{base_url}{endpoint}"
    return await async_request(iam_token, url, params or {})


async def get_resource_with_bindings(
    iam_token: str,
    folder_id: str,
    resource_type: str,
    item_id_key: str,
    resource_id: str,
    status: str = None
):
    details_task = yc_get_compute_info(
        iam_token,
        resource_type,
        params={"folderId": folder_id}
    )

    bindings_task = yc_get_compute_info(
        iam_token,
        resource_type,
        endpoint=f"/{resource_id}:listAccessBindings"
    )

    details, bindings = await asyncio.gather(details_task, bindings_task)

    resource_data = {
        item_id_key: resource_id,
        "details": details,
        "bindings": bindings
    }

    if resource_type == "instances" and status == "RUNNING":
        serial_resp = await yc_get_compute_info(
            iam_token,
            resource_type,
            endpoint=f"/{resource_id}:serialPortOutput"
        )
        resource_data["serial"] = (
            serial_resp.get("contents", "")
            if isinstance(serial_resp, dict)
            else ""
        )

    elif resource_type == "instances":
        resource_data["serial"] = "VM не запущена, вывод серийного порта отсутствует"

    return resource_data


async def collect_all_compute_data(iam_token: str, folder_id: str):
    instances_list = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/instances",
        "instances",
        {"folderId": folder_id}
    )

    disks_list = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/disks",
        "disks",
        {"folderId": folder_id}
    )

    images_list = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/images",
        "images",
        {"folderId": folder_id}
    )

    snapshots_list = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/snapshots",
        "snapshots",
        {"folderId": folder_id}
    )

    instances_tasks = [
        get_resource_with_bindings(
            iam_token,
            folder_id,
            "instances",
            "instance_id",
            vm.get("id"),
            vm.get("status")
        )
        for vm in instances_list
        if vm.get("id")
    ]

    disks_tasks = [
        get_resource_with_bindings(
            iam_token,
            folder_id,
            "disks",
            "disk_id",
            disk.get("id")
        )
        for disk in disks_list
        if disk.get("id")
    ]

    images_tasks = [
        get_resource_with_bindings(
            iam_token,
            folder_id,
            "images",
            "image_id",
            img.get("id")
        )
        for img in images_list
        if img.get("id")
    ]

    snapshots_tasks = [
        get_resource_with_bindings(
            iam_token,
            folder_id,
            "snapshots",
            "snapshot_id",
            snap.get("id")
        )
        for snap in snapshots_list
        if snap.get("id")
    ]

    all_instances, all_disks, all_images, all_snapshots = await asyncio.gather(
        asyncio.gather(*instances_tasks) if instances_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*disks_tasks) if disks_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*images_tasks) if images_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*snapshots_tasks) if snapshots_tasks else asyncio.sleep(0, result=[])
    )

    return {
        "instances": all_instances,
        "disks": all_disks,
        "images": all_images,
        "snapshots": all_snapshots
    }


# ---------- S3 ----------
async def yc_get_s3_info(
    iam_token: str,
    folder_id: str,
    endpoint: str = "",
    params: dict = None,
    use_folder: bool = True
):
    base_url = "https://storage.api.cloud.yandex.net/storage/v1/buckets"
    url = f"{base_url}{endpoint}"
    params = params.copy() if params else {}

    if use_folder:
        params["folderId"] = folder_id

    return await async_request(iam_token, url, params)


async def collect_all_s3_data(iam_token: str, folder_id: str):
    buckets_resp = await yc_get_s3_info(iam_token, folder_id)
    buckets = buckets_resp.get("buckets", []) if isinstance(buckets_resp, dict) else []

    async def process_bucket(bucket):
        name = bucket.get("name")

        stats, https, bindings, inventory = await asyncio.gather(
            yc_get_s3_info(
                iam_token,
                folder_id,
                endpoint=f"/{name}:getStats",
                use_folder=False
            ),
            yc_get_s3_info(
                iam_token,
                folder_id,
                endpoint=f"/{name}:getHttpsConfig",
                use_folder=False
            ),
            yc_get_s3_info(
                iam_token,
                folder_id,
                endpoint=f"/{name}:listAccessBindings",
                use_folder=False
            ),
            yc_get_s3_info(
                iam_token,
                folder_id,
                endpoint=f"/{name}:listInventoryConfiguration",
                use_folder=False
            )
        )

        return {
            "bucket": bucket,
            "stats": stats,
            "https": https,
            "bindings": bindings,
            "inventory": inventory
        }

    tasks = [process_bucket(bucket) for bucket in buckets]
    return await asyncio.gather(*tasks) if tasks else []


# ---------- VPC ----------
async def yc_get_vpc_info(
    iam_token: str,
    folder_id: str,
    endpoint: str = "",
    params: dict = None,
    use_folder: bool = True
):
    base_url = "https://vpc.api.cloud.yandex.net/vpc/v1/"
    url = f"{base_url}{endpoint}"
    params = params.copy() if params else {}

    if use_folder:
        params["folderId"] = folder_id

    return await async_request(iam_token, url, params)


async def collect_all_vpc_data(iam_token: str, folder_id: str):
    endpoints = [
        "addresses",
        "gateways",
        "networks",
        "routeTables",
        "securityGroups",
        "subnets"
    ]

    tasks = [
        yc_get_vpc_info(iam_token, folder_id, endpoint)
        for endpoint in endpoints
    ]

    results = await asyncio.gather(*tasks)

    return {
        "addresses": results[0],
        "gateways": results[1],
        "networks": results[2],
        "routeTables": results[3],
        "securityGroups": results[4],
        "subnets": results[5]
    }