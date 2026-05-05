# Understanding the `app_proxy` Service in Umbrel Apps

## What is `app_proxy`?

The `app_proxy` service is a **special Umbrel infrastructure service** that provides:

1. **Reverse proxy** - Routes external requests to your app's web container
2. **Authentication** - Automatically requires Umbrel password (configurable)
3. **Path-based routing** - Can whitelist/blacklist specific paths
4. **Network isolation** - Apps run in isolated Docker networks

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    User's Browser                        │
│              (http://umbrel.local:3002)                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              umbrelOS app_proxy Service                  │
│  (Provided by umbrelOS, NOT defined in your compose)    │
│  - Handles authentication                               │
│  - Routes to correct app container                      │
│  - Manages network isolation                            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Your App's Web Container                    │
│         (e.g., caddy-https-app_web_1:8080)              │
└─────────────────────────────────────────────────────────┘
```

## Why Define `app_proxy` in docker-compose.yml?

Even though umbrelOS provides the actual `app_proxy` service at runtime, you **MUST** define it in your `docker-compose.yml` for these reasons:

### 1. **Configuration**
The `app_proxy` service definition tells umbrelOS:
- Which container to route traffic to (`APP_HOST`)
- Which port to use (`APP_PORT`)
- Authentication settings (`PROXY_AUTH_ADD`)
- Path whitelisting/blacklisting (`PROXY_AUTH_WHITELIST`)

### 2. **Umbrel App Framework Requirement**
The Umbrel App Framework expects every app to define an `app_proxy` service. It's part of the [official specification](https://github.com/getumbrel/umbrel-apps/blob/master/README.md).

### 3. **Local Development vs. Production**
- **In umbrelOS**: The `app_proxy` service is **injected** by the OS at runtime
- **Locally**: When running `docker compose` outside Umbrel, you'll see errors because the service has no image - **this is expected and normal**

## Example Configuration

```yaml
version: "3.7"

services:
  app_proxy:
    environment:
      # Format: <app-id>_<container-name>_1
      APP_HOST: caddy-https-app_web_1
      APP_PORT: 8080
      
      # Disable authentication (optional)
      PROXY_AUTH_ADD: "false"
      
      # Whitelist API paths (optional)
      PROXY_AUTH_WHITELIST: "/api/*"

  web:
    image: node:24-alpine@sha256:...
    # No need to expose ports - app_proxy handles routing
    volumes:
      - ${APP_DATA_DIR}/web:/app
```

## Common `app_proxy` Settings

### Basic Setup
```yaml
app_proxy:
  environment:
    APP_HOST: <app-id>_<container-name>_1
    APP_PORT: <port>
```

### Disable Authentication
```yaml
app_proxy:
  environment:
    PROXY_AUTH_ADD: "false"
```

### Path Whitelisting
```yaml
app_proxy:
  environment:
    PROXY_AUTH_WHITELIST: "/api/*"
```

### Path Blacklisting
```yaml
app_proxy:
  environment:
    PROXY_AUTH_WHITELIST: "*"
    PROXY_AUTH_BLACKLIST: "/admin/*"
```

## Testing Locally

When testing your app locally (outside umbrelOS), you'll see errors like:

```
service "app_proxy" has neither an image nor a build context specified
```

**This is normal!** The `app_proxy` service is only meant to run inside umbrelOS.

### Workaround for Local Testing

To test locally, you can:

1. **Comment out `app_proxy`** temporarily:
   ```yaml
   # app_proxy:
   #   environment:
   #     APP_HOST: caddy-https-app_web_1
   #     APP_PORT: 8080
   ```

2. **Expose ports directly** on your web container:
   ```yaml
   web:
     image: node:24-alpine
     ports:
       - "8080:8080"
   ```

3. **Use environment variables**:
   ```bash
   export APP_DATA_DIR=/tmp/test
   docker compose up
   ```

## Official Documentation

- [Umbrel App Framework](https://github.com/getumbrel/umbrel-apps/blob/master/README.md) - See the `app_proxy` example
- [Umbrel App Submission Guide](https://github.com/getumbrel/umbrel-apps#4-submitting-the-app)

## Key Takeaways

✅ **Always define `app_proxy`** in your docker-compose.yml  
✅ **Don't worry about local errors** - they're expected  
✅ **Test on umbrelOS** for final validation  
✅ **Follow the naming convention**: `<app-id>_<container-name>_1`  
✅ **No need to expose ports** - `app_proxy` handles routing  

---

**Note**: The `app_proxy` service is part of Umbrel's internal infrastructure. It's automatically managed by umbrelOS and should not be modified or replaced by app developers.
