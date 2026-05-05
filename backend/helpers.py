# backend/helpers.py
import aiohttp

def validate_token_request(token: str, folder_id: str, session_id: str):
    if not session_id:
        return "Не найден ID сессии"

    if not token or not folder_id:
        return "Не заполнены поля с OAuth-токеном и идентификатором каталога. Без их указания рекомендации будут общими, без учёта ваших ресурсов"

    if len(token) < 50 or " " in token:
        return "Некорректная длина OAuth-токена"

    if not folder_id.isalnum() or not folder_id.islower():
        return "Идентификатор каталога должен содержать только строчные латинские буквы и цифры"

    if not (20 <= len(folder_id) <= 25):
        return "Некорректная длина идентификатора каталога"

    return None

async def get_iam_token(oauth_token: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"yandexPassportOauthToken": oauth_token},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as response:

            if response.status != 200:
                return None

            data = await response.json()
            return data.get("iamToken")
        
async def check_folder_exists(iam_token: str, folder_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders/{folder_id}",
            headers={"Authorization": f"Bearer {iam_token}"},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as response:

            return response.status == 200