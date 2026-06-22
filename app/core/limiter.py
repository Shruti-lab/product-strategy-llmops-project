"""Rate limiting configuration for the application.

This module configures rate limiting using slowapi, with default limits
defined in the application settings. Rate limits are applied based on
remote IP addresses.

When Valkey is configured, uses it as a distributed storage backend
so rate limits work correctly across multiple app instances.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.logging import logger

# Build storage URI for Valkey if configured
_storage_uri = None
if settings.VALKEY_HOST:
    _password_part = f":{settings.VALKEY_PASSWORD}@" if settings.VALKEY_PASSWORD else ""
    _storage_uri = f"redis://{_password_part}{settings.VALKEY_HOST}:{settings.VALKEY_PORT}/{settings.VALKEY_DB}"
    logger.info("rate_limiter_using_valkey", host=settings.VALKEY_HOST, port=settings.VALKEY_PORT)

# Initialize rate limiter (uses in-memory storage if no Valkey)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=settings.RATE_LIMIT_DEFAULT,  # pyright: ignore[reportArgumentType]
    storage_uri=_storage_uri,
)


"""
Because of this line:

```python
limiter = Limiter(
    key_func=get_remote_address,
    ...
)
```

The key is understanding what `key_func` does.

In SlowAPI, `key_func` is the function used to generate the **identifier ("bucket key")** for rate limiting. Every request gets mapped to a key, and the rate limit counter is tracked against that key.

Here the code passes:

```python
from slowapi.util import get_remote_address
```

and then:

```python
key_func=get_remote_address
```

`get_remote_address(request)` returns the client's remote IP address from the incoming request.

Conceptually:

```python
def get_remote_address(request):
    return request.client.host
```

(The actual implementation may vary slightly, but that's the idea.)

So when requests arrive:

| Request                  | Generated Key    |
| ------------------------ | ---------------- |
| User A from 203.0.113.10 | `"203.0.113.10"` |
| User B from 198.51.100.5 | `"198.51.100.5"` |

SlowAPI stores counters like:

```text
203.0.113.10 -> 57 requests
198.51.100.5 -> 12 requests
```

That's why the docstring says:

> "Rate limits are applied based on remote IP addresses."

The implementation directly supports that statement.

---

If the application wanted to rate-limit by something else, it would use a different `key_func`.

For example:

### Per authenticated user

```python
def user_id_key(request):
    return str(request.user.id)

limiter = Limiter(
    key_func=user_id_key
)
```

Now:

```text
user:123 -> 50 requests
user:456 -> 12 requests
```

---

### Per API key

```python
def api_key_key(request):
    return request.headers["X-API-Key"]
```

---

### Per tenant

```python
def tenant_key(request):
    return request.headers["X-Tenant-ID"]
```

---

So the evidence is not the comment or docstring; it's the actual configuration:

```python
key_func=get_remote_address
```

which tells SlowAPI, "use the client's remote IP address as the rate-limit key."

"""