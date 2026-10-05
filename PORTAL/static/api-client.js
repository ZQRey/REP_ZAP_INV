(function () {
    'use strict';

    const nativeFetch = window.fetch.bind(window);

    class ApiError extends Error {
        constructor(status, message, body) {
            super(message || ('HTTP ' + status));
            this.name = 'ApiError';
            this.status = status;
            this.body = body;
        }
    }

    function token() {
        return sessionStorage.getItem('token') || '';
    }

    function logout() {
        sessionStorage.removeItem('token');
        window.dispatchEvent(new CustomEvent('api:unauthorized'));
    }

    async function request(url, options) {
        const config = Object.assign({}, options || {});
        const headers = new Headers(config.headers || {});
        const currentToken = token();
        if (currentToken && !headers.has('Authorization')) {
            headers.set('Authorization', 'Bearer ' + currentToken);
        }
        if (config.body && !(config.body instanceof FormData) && !headers.has('Content-Type')) {
            headers.set('Content-Type', 'application/json');
        }
        config.headers = headers;

        const response = await nativeFetch(url, config);
        if (response.status === 401) {
            logout();
        }
        if (response.status === 403 && window.location.pathname !== '/') {
            const body = await response.clone().json().catch(() => null);
            if (body?.detail === 'password_change_required') window.location.replace('/');
        }
        return response;
    }

    async function parseError(response) {
        let body = null;
        try { body = await response.clone().json(); } catch (_) {}
        const detail = body && (body.detail || body.message);
        const defaults = {
            401: 'Сессия истекла. Войдите в систему снова.',
            403: 'Недостаточно прав для выполнения операции.',
            404: 'Запрошенный объект не найден.',
            409: 'Операция конфликтует с текущим состоянием объекта.',
            422: 'Проверьте корректность введённых данных.',
            429: 'Слишком много запросов. Повторите попытку позже.',
            500: 'Внутренняя ошибка сервера.'
        };
        return new ApiError(response.status, detail || defaults[response.status] || ('Ошибка HTTP ' + response.status), body);
    }

    async function json(url, options) {
        const response = await request(url, options);
        if (!response.ok) throw await parseError(response);
        if (response.status === 204) return null;
        return response.json();
    }

    window.ApiClient = {
        ApiError,
        request,
        json,
        get: (url, options) => json(url, Object.assign({}, options || {}, {method: 'GET'})),
        post: (url, body, options) => json(url, Object.assign({}, options || {}, {method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body)})),
        put: (url, body, options) => json(url, Object.assign({}, options || {}, {method: 'PUT', body: body instanceof FormData ? body : JSON.stringify(body)})),
        patch: (url, body, options) => json(url, Object.assign({}, options || {}, {method: 'PATCH', body: body instanceof FormData ? body : JSON.stringify(body)})),
        delete: (url, options) => json(url, Object.assign({}, options || {}, {method: 'DELETE'})),
        token,
        logout
    };
})();
