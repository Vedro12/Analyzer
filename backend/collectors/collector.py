# backend/collectors/collector.py
import aiohttp
import asyncio
from urllib.parse import quote
from backend.helpers import check_api_field, give_empty_resource_message, unwrap_api_response, get_response_data_or_empty_list

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
                    data = await resp.json()

                    return {
                        "status": "ok",
                        "data": data
                    }

                response_text = await resp.text()

                return {
                    "status": "api_error",
                    "message": "Ошибка при обращении к API",
                    "http_status": resp.status,
                    "url": url,
                    "params": params,
                    "details": response_text
                }

        except asyncio.TimeoutError:
            return {
                "status": "api_timeout",
                "message": "Таймаут при обращении к API",
                "url": url,
                "params": params
            }

        except Exception as e:
            return {
                "status": "api_error",
                "message": "Ошибка при обращении к API",
                "url": url,
                "params": params,
                "details": str(e)
            }


async def async_request_with_pagination(
    iam_token: str,
    url: str,
    item_key: str,
    params: dict = None,
    resource_name: str = None
):
    params = params.copy() if params else {}
    all_items = []
    page_token = None

    while True:
        if page_token:
            params["pageToken"] = page_token

        response = await async_request(iam_token, url, params)

        if response.get("status") != "ok":
            return response

        data = response.get("data", {})

        if check_api_field(data, item_key):
            return give_empty_resource_message(resource_name or item_key)

        items = data.get(item_key, [])
        all_items.extend(items)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return {
        "status": "ok",
        "data": all_items
    }


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

    details_resp, bindings_resp = await asyncio.gather(
        details_task,
        bindings_task
    )

    resource_data = {
        item_id_key: resource_id,
        "details": unwrap_api_response(details_resp),
        "bindings": unwrap_api_response(bindings_resp)
    }

    if resource_type == "instances" and status == "RUNNING":
        serial_resp = await yc_get_compute_info(
            iam_token,
            resource_type,
            endpoint=f"/{resource_id}:serialPortOutput"
        )

        serial_data = unwrap_api_response(serial_resp)

        resource_data["serial"] = (
            serial_data.get("contents", "")
            if isinstance(serial_data, dict)
            else serial_data
        )

    elif resource_type == "instances":
        resource_data["serial"] = "VM не запущена, вывод серийного порта отсутствует"

    return resource_data


async def collect_all_compute_data(iam_token: str, folder_id: str):
    instances_resp = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/instances",
        "instances",
        {"folderId": folder_id},
        "виртуальных машинах"
    )

    disks_resp = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/disks",
        "disks",
        {"folderId": folder_id},
        "дисках"
    )

    images_resp = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/images",
        "images",
        {"folderId": folder_id},
        "образах"
    )

    snapshots_resp = await async_request_with_pagination(
        iam_token,
        "https://compute.api.cloud.yandex.net/compute/v1/snapshots",
        "snapshots",
        {"folderId": folder_id},
        "снимках"
    )

    instances_list = get_response_data_or_empty_list(instances_resp)
    disks_list = get_response_data_or_empty_list(disks_resp)
    images_list = get_response_data_or_empty_list(images_resp)
    snapshots_list = get_response_data_or_empty_list(snapshots_resp)

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
        if isinstance(vm, dict) and vm.get("id")
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
        if isinstance(disk, dict) and disk.get("id")
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
        if isinstance(img, dict) and img.get("id")
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
        if isinstance(snap, dict) and snap.get("id")
    ]

    all_instances, all_disks, all_images, all_snapshots = await asyncio.gather(
        asyncio.gather(*instances_tasks) if instances_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*disks_tasks) if disks_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*images_tasks) if images_tasks else asyncio.sleep(0, result=[]),
        asyncio.gather(*snapshots_tasks) if snapshots_tasks else asyncio.sleep(0, result=[])
    )

    return {
        "instances": all_instances if instances_resp.get("status") == "ok" else instances_resp,
        "disks": all_disks if disks_resp.get("status") == "ok" else disks_resp,
        "images": all_images if images_resp.get("status") == "ok" else images_resp,
        "snapshots": all_snapshots if snapshots_resp.get("status") == "ok" else snapshots_resp
    }


# ---------- S3 ----------
async def yc_get_s3_buckets(
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


async def yc_get_s3_bucket_info(
    iam_token: str,
    bucket_name: str,
    action: str,
    params: dict = None
):
    safe_bucket_name = quote(bucket_name, safe="")
    url = f"https://storage.api.cloud.yandex.net/storage/v1/buckets/{safe_bucket_name}:{action}"
    return await async_request(iam_token, url, params)


async def collect_all_s3_data(iam_token: str, folder_id: str):
    buckets_resp = await yc_get_s3_buckets(iam_token, folder_id)

    if not isinstance(buckets_resp, dict):
        return {
            "status": "api_error",
            "message": "Ошибка при обращении к API",
            "details": "Некорректный формат ответа при получении списка S3-бакетов"
        }

    if buckets_resp.get("status") != "ok":
        return buckets_resp

    buckets_data = buckets_resp.get("data", {})

    if check_api_field(buckets_data, "buckets"):
        return give_empty_resource_message("S3-бакетах")

    buckets = buckets_data.get("buckets", [])

    async def process_bucket(bucket):
        name = bucket.get("name")

        if not name:
            return {
                "status": "no_data",
                "message": "Не найдено имя S3-бакета"
            }

        stats, https, bindings, inventory = await asyncio.gather(
            yc_get_s3_buckets(
                iam_token,
                folder_id,
                endpoint=f"/{name}:getStats",
                use_folder=False
            ),
            yc_get_s3_buckets(
                iam_token,
                folder_id,
                endpoint=f"/{name}:getHttpsConfig",
                use_folder=False
            ),
            yc_get_s3_bucket_info(
                iam_token,
                name,
                "listAccessBindings"
            ),
            yc_get_s3_buckets(
                iam_token,
                folder_id,
                endpoint=f"/{name}:listInventoryConfigurations",
                use_folder=False
            )
        )

        return {
            "bucket": bucket,
            "stats": unwrap_api_response(stats),
            "https": unwrap_api_response(https),
            "bindings": unwrap_api_response(bindings),
            "inventory": unwrap_api_response(inventory)
        }

    tasks = [
        process_bucket(bucket)
        for bucket in buckets
        if isinstance(bucket, dict)
    ]

    return await asyncio.gather(*tasks) if tasks else give_empty_resource_message("S3-бакетах")

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

    data = {}

    for endpoint, result in zip(endpoints, results):
        if not isinstance(result, dict):
            data[endpoint] = {
                "status": "api_error",
                "message": "Ошибка при обращении к API",
                "details": "Некорректный формат ответа"
            }
            continue

        if result.get("status") != "ok":
            data[endpoint] = result
            continue

        endpoint_data = result.get("data", {})

        if check_api_field(endpoint_data, endpoint):
            data[endpoint] = give_empty_resource_message(endpoint)
        else:
            data[endpoint] = endpoint_data

    return data