import hmac
import httpx
from fastapi import HTTPException, Request


async def current_user(request: Request) -> dict:
    settings = request.app.state.settings
    try:
        response = await request.app.state.http.get(
            f'{settings.auth_url}/api/v1/auth/me',
            headers={'Cookie': request.headers.get('cookie', '')}, timeout=5)
    except httpx.RequestError:
        raise HTTPException(503, 'Сервис авторизации недоступен') from None
    if response.status_code == 401:
        raise HTTPException(401, 'Войдите в аккаунт')
    if response.status_code != 200:
        raise HTTPException(503, 'Не удалось проверить сессию')
    try:
        session = response.json()
        user = session['user']
        if not isinstance(user['id'], str) or not user['id']:
            raise ValueError('Invalid user identity')
        csrf = session['csrf_token']
    except (ValueError, TypeError, KeyError):
        raise HTTPException(503, 'Некорректный ответ сервиса авторизации') from None
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        provided = request.headers.get('x-csrf-token', '')
        if not provided or not hmac.compare_digest(provided.encode(), str(csrf).encode()):
            raise HTTPException(403, 'Не удалось проверить запрос. Обновите страницу')
    return user
