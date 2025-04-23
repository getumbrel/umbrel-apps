# Umbrel App Framework

🚨 This is the current workflow for developing and testing an app on umbrelOS 1.x. The app framework is under active development and this workflow will change in the future. For testing on umbrelOS 0.5.4, please refer to the [previous version of this document](https://github.com/getumbrel/umbrel-apps/blob/9eae789b8512ef2a213805524e17f33d2128e33e/README.md).

If you can code in any language, you already know how to develop an app for Umbrel. There is no restriction on the kinds of programming languages, frameworks, or databases that you can use. Apps run inside isolated [Docker](https://docs.docker.com/) containers, and the only requirement (for now) is that they should have a web-based UI.

> Some server apps might not have a UI at all. In that case, the app should serve a simple web page listing the connection details, QR codes, setup instructions, and anything else needed for the user to connect. The user is never expected to have CLI access on Umbrel.

To keep this document short and easy, we won't go into the app development itself, and will instead focus on packaging and testing an existing app.

Let's jump into action by packaging [BTC RPC Explorer](https://github.com/janoside/btc-rpc-explorer), a Node.js based blockchain explorer, for Umbrel.

There are 4 steps:

1. [🛳 Containerizing the app using Docker](#1-containerizing-the-app-using-docker)
1. [☂️ Packaging the app for umbrelOS](#2-%EF%B8%8Fpackaging-the-app-for-umbrelos)
1. [🛠 Testing the app on umbrelOS](#3-testing-the-app-on-umbrelos)
    1. [Test using an umbrelOS development environment on your local machine](#31-test-using-an-umbrelos-development-environment-on-your-local-machine)
    1. [Test using umbrelOS running on a physical device](#32-test-using-umbrelos-running-on-a-physical-device)
1. [🚀 Submitting the app](#4-submitting-the-app)
___

## 1. 🛳&nbsp;&nbsp;Containerizing the app using Docker

1\. Let's start by cloning BTC RPC Explorer on our system:

```sh
git clone --branch v2.0.2 https://github.com/janoside/btc-rpc-explorer.git
cd  btc-rpc-explorer
```

2\. Next, we'll create a `Dockerfile` in the app's directory:

```Dockerfile
FROM node:12-buster-slim AS builder

WORKDIR /build
COPY . .
RUN apt-get update
RUN apt-get install -y git python3 build-essential
RUN npm ci --production

FROM node:12-buster-slim

USER 1000
WORKDIR /build
COPY --from=builder /build .
EXPOSE 3002
CMD ["npm", "start"]
```

### A good Dockerfile:

- [x] Uses a lightweight base image - this results in less storage consumption and faster app installs.
- [x] Uses [multi-stage builds](https://docs.docker.com/develop/develop-images/multistage-build/) for smaller image size.
- [x] Excludes development files in the final image.
- [x] Has only one service per container.
- [x] Doesn't run the service as root.
- [x] Uses remote assets that are verified against a checksum.
- [x] Results in deterministic image builds.

3\. We're now ready to build the Docker image of BTC RPC Explorer. Umbrel supports both 64-bit ARM and x86 architectures, so we'll use `docker buildx` to build, tag, and push multi-architecture Docker images of our app to Docker Hub. This way, the same app can be installed on both ARM and x86 devices.

```sh
docker buildx build --platform linux/arm64,linux/amd64 --tag getumbrel/btc-rpc-explorer:v2.0.2 --output "type=registry" .
```

> You need to enable ["experimental features"](https://docs.docker.com/engine/reference/commandline/cli/#experimental-features) in Docker to use `docker buildx`.

___

## 2. ☂️&nbsp;&nbsp;Packaging the app for umbrelOS

1\. Let's fork the [getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps) repo on GitHub, clone our fork locally, create a new branch for our app, and then switch to it:

```sh
git clone https://github.com/<YOUR-GITHUB-USERNAME>/umbrel-apps.git
cd umbrel-apps
```

2\. It's now time to pick an ID for our app. An app ID should only contain lowercase alphabetical characters and dashes, and should be human readable and recognizable. For this app we'll go with `btc-rpc-explorer`.

We need to create a new subdirectory in the apps directory with the same name as our app ID and move into it:

```sh
mkdir btc-rpc-explorer
cd btc-rpc-explorer
```

3\. Within the app's directory, we'll now create the skeleton for our app with the following files:

- `docker-compose.yml` - Used to start and stop your app's Docker containers
- `umbrel-app.yml` - An app manifest file so that Umbrel knows the name and version of the app
- `exports.sh` - A shell script to export environment variables used within `docker-compose.yml` and share with other installed apps

We'll now create a `docker-compose.yml` file in this directory to define our application.

> New to Docker Compose? It's a simple tool for defining and running Docker applications that can have multiple containers. Follow along with the tutorial, we promise it's not hard if you already understand the basics of Docker.

Let's copy-paste the following `docker-compose.yml` template into a text editor and modify it according to our app.

```yml
version: "3.7"

services:
  app_proxy:
    environment:
      # <app-id>_<web-container-name>_1
      # e.g. 'btc-rpc-explorer_web_1'
      # Note that the '_1' at the end is needed
      APP_HOST: <web-container-dns-name>
      APP_PORT: <web-container-port-number>
  
  web:
    image: <docker-image>:<tag>@sha256:<digest>
    restart: on-failure
    stop_grace_period: 1m
    ports:
      # You do not need to expose the port that your app's web server is listening on if you're using the app_proxy service.
      # This is handled by the APP_HOST and APP_PORT environment variables in the service above.
      #
      # If you need to expose additional ports, you can do so like this, replacing <port> with the port number:
      - <port>:<port>
    volumes:
      # Uncomment to mount your data directories inside
      # the Docker container for storing persistent data
      # - ${APP_DATA_DIR}/foo:/foo
      # - ${APP_DATA_DIR}/bar:/bar
      #
      # Uncomment to mount LND's data directory as read-only
      # inside the Docker container at path /lnd
      # - ${APP_LIGHTNING_NODE_DATA_DIR}:/lnd:ro
      #
      # Uncomment to mount Bitcoin Core's data directory as
      # read-only inside the Docker container at path /bitcoin
      # - ${APP_BITCOIN_DATA_DIR}:/bitcoin:ro
    environment:
      # Pass any environment variables to your app for configuration in the form:
      # VARIABLE_NAME: value
      #
      # Here are all the Umbrel provided variables that you can pass through to
      # your app
      # System level environment variables
      # $DEVICE_HOSTNAME - Umbrel server device hostname (e.g. "umbrel")
      # $DEVICE_DOMAIN_NAME - A .local domain name for the Umbrel server (e.g. "umbrel.local")
      #
      # Tor proxy environment variables
      # $TOR_PROXY_IP - Local IP of Tor proxy
      # $TOR_PROXY_PORT - Port of Tor proxy
      #
      # App specific environment variables
      # $APP_HIDDEN_SERVICE - The address of the Tor hidden service your app will be exposed at
      # $APP_PASSWORD - Unique plain text password that can be used for authentication in your app, shown to the user in the Umbrel UI
      # $APP_SEED - Unique 256 bit long hex string (128 bits of entropy) deterministically derived from user's Umbrel seed and your app's ID
  # If your app has more services, like a database container, you can define those
  # services below:
  # db:
  #   image: <docker-image>:<tag>@sha256:<digest>
  #   ...

```

Our app manifest YAML file tells Umbrel details about our app such as the name, description, dependencies, port number to access the app, etc.

> There are currently two manifest versions: `1` and `1.1`. Version `1` is the basic version and is sufficient for most apps. However, if your app requires the use of hooks (scripts that are run at different stages of the app lifecycle), you need to use version `1.1`. Hooks allow you to perform custom actions at different stages of the app's lifecycle, such as before the app starts (pre-start), after the app installs (post-install), and more. If your app doesn't need to use hooks, you can stick with manifest version `1`.

```yml
manifestVersion: 1
id: btc-rpc-explorer
category: finance
name: BTC RPC Explorer
version: "3.3.0"
tagline: Simple, database-free blockchain explorer
description: >-
  BTC RPC Explorer is a full-featured, self-hosted explorer for the
  Bitcoin blockchain. With this explorer, you can explore not just the
  blockchain database, but also explore the functional capabilities of your
  Umbrel.

  It comes with a network summary dashboard, detailed view of blocks, transactions, addresses, along with analysis tools for viewing stats on miner activity, mempool summary, with fee, size, and age breakdowns. You can also search by transaction ID, block hash/height, and addresses.

  It's time to appreciate the "fullness" of your node.
releaseNotes: >-
  Dark mode is finally here! Easily switch between your preferred mode
  in one click.

  This version also includes lots of minor styling improvements, better
  error handling, and several bugfixes.
developer: Dan Janosik
website: https://explorer.btc21.org
dependencies:
  - bitcoin
  - electrs
repo: https://github.com/janoside/btc-rpc-explorer
support: https://github.com/janoside/btc-rpc-explorer/discussions
port: 3002
gallery:
  - 1.jpg
  - 2.jpg
  - 3.jpg
path: ""
defaultUsername: ""
defaultPassword: ""
submitter: Umbrel
submission: https://github.com/getumbrel/umbrel/pull/334
```

The `dependencies` section within the app manifest gives Umbrel a list of app IDs that must be already installed in order for the user to install BTC RPC Explorer and also function.

The `exports.sh` shell script is a simple script to export environmental variables that your `docker-compose.yml` can read. These environment variables are also accessible when other apps start through their `docker-compose.yml` files. Most applications will not require this feature.

If we (for example) wanted to share BTC RPC Explorer's Address API with other apps; that would look like this:
```sh
export APP_BTC_RPC_EXPLORER_ADDRESS_API="electrumx"
```

4\. For our app, we'll update `<docker-image>` with `getumbrel/btc-rpc-explorer`, `<tag>` with `v2.0.2`, `<digest>` with `f8ba8b97e550f65e5bc935d7516cce7172910e9009f3154a434c7baf55e82a2b`, and `<port>` with `3002`. Since BTC RPC Explorer doesn't need to store any persistent data and doesn't require access to Bitcoin Core's or LND's data directories, we can remove the entire `volumes` block.

> The digest is a unique, immutable identifier for the Docker image. This will supersede the tag in the `docker-compose.yml` file. The reason we want to pull an image by its digest, is that we are guaranteed to get the exact same image every time, and this image will be the same image that was tested and verified to work on umbrelOS. It is important to make sure that this digest is the multi-architecture digest, and not the digest for a specific architecture.

BTC RPC Explorer is an application with a single Docker container, so we don't need to define any other additional services (like a database service, etc) in the compose file.

> If BTC RPC Explorer needed to persist some data we would have created a new `data` directory next to the `docker-compose.yml` file. We'd then mount the volume `- ${APP_DATA_DIR}/data:/data` in the `docker-compose.yml` to make the directory available at `/data` inside the container.

Updated `docker-compose.yml` file:

```yml
version: "3.7"

services:
  app_proxy:
    environment:
      APP_HOST: btc-rpc-explorer_web_1
      APP_PORT: 8080

  web:
    image: getumbrel/btc-rpc-explorer:v2.0.2@sha256:f8ba8b97e550f65e5bc935d7516cce7172910e9009f3154a434c7baf55e82a2b
    restart: on-failure
    stop_grace_period: 1m
    environment:
      BTCEXP_PORT: 8080

```

5\. Next, let's set the environment variables required by our app to connect to Bitcoin Core, Electrum server, and for app-related configuration ([as required by the app](https://github.com/janoside/btc-rpc-explorer/blob/master/.env-sample)).

So the final version of `docker-compose.yml` would be:

```yml
version: "3.7"

services:
  app_proxy:
    environment:
      APP_HOST: btc-rpc-explorer_web_1
      APP_PORT: 8080
      
  web:
    image: getumbrel/btc-rpc-explorer:v2.0.2
    restart: on-failure
    stop_grace_period: 1m
    environment:
      PORT: 8080

      # Bitcoin Core connection details
      BTCEXP_BITCOIND_HOST: $APP_BITCOIN_NODE_IP
      BTCEXP_BITCOIND_PORT: $APP_BITCOIN_RPC_PORT
      BTCEXP_BITCOIND_USER: $APP_BITCOIN_RPC_USER
      BTCEXP_BITCOIND_PASS: $APP_BITCOIN_RPC_PASS

      # Electrum connection details
      BTCEXP_ELECTRUMX_SERVERS: "tcp://$APP_ELECTRS_NODE_IP:$APP_ELECTRS_NODE_PORT"

      # App Config
      BTCEXP_HOST: 0.0.0.0
      DEBUG: "btcexp:*,electrumClient"
      BTCEXP_ADDRESS_API: electrumx
      BTCEXP_SLOW_DEVICE_MODE: "true"
      BTCEXP_NO_INMEMORY_RPC_CACHE: "true"
      BTCEXP_PRIVACY_MODE: "true"
      BTCEXP_NO_RATES: "true"
      BTCEXP_RPC_ALLOWALL: "false"
      BTCEXP_BASIC_AUTH_PASSWORD: ""  

```

6\. We're pretty much done here. The next step is to commit the changes, push it to our fork's branch, and test out the app on Umbrel.

```sh
git add .
git commit -m "Add BTC RPC Explorer"
git push
```

___

## 3. 🛠&nbsp;&nbsp;Testing the app on umbrelOS

🚨 This is the current workflow for testing an app on umbrelOS 1.x. The app framework is under active development and this workflow will change in the future. For testing on umbrelOS 0.5.4, please refer to the [previous version of this document](https://github.com/getumbrel/umbrel-apps/blob/9eae789b8512ef2a213805524e17f33d2128e33e/README.md).

### 3.1 Test using an umbrelOS development environment on your local machine

The umbrelOS development environment (umbrel-dev) requires a Docker environment that exposes container IPs to the host. This is how Docker natively works on Linux and can be done with OrbStack on macOS and WSL 2 on Windows.

1\. Install [OrbStack](https://orbstack.dev/) on macOS or [WSL 2](https://learn.microsoft.com/en-us/windows/wsl/install) with Docker Desktop on Windows.

2\. Clone the [getumbrel/umbrel](https://github.com/getumbrel/umbrel) repo.

From the root of the cloned repo, run the following command to view the available umbrel-dev commands:

```sh
npm run dev help
```

To start the development environment, run the following command:

```sh
npm run dev
```

> [!NOTE]
> If this is your first time running the development environment, it may take a while to build the OS image locally on your machine.

Once initialized, umbrelOS will be accessible at http://umbrel-dev.local. 

3\. Copy the app's directory (with any .gitkeep files excluded) to the app-store directory on umbrel-dev.

To do this, we run the following command on our local machine:

```sh
rsync -av --exclude=".gitkeep" <path-to-your-forked-repo-on-local-machine>/btc-rpc-explorer umbrel@umbrel-dev.local:/home/umbrel/umbrel/app-stores/getumbrel-umbrel-apps-github-53f74447/
```

If you are asked for a password during the transfer, use the password that you set when you created your umbrelOS account.

4\. Install the app.

From the umbrelOS homescreen, go to the App Store and navigate to BTC RPC Explorer. Click on the "Install" button and wait for the app to install.

You can also install the app from the command line. umbrelOS provides a web terminal that can be accessed via Settings > Advanced Settings > Terminal > umbrelOS, or you can use the umbrel-dev scripts to install the app using the umbreld RPC server:

```sh
npm run dev client -- apps.install.mutate -- --appId btc-rpc-explorer
```

That's it! Our BTC RPC Explorer app should now be accessible at http://umbrel-dev.local:3002

To uninstall the app, you can right-click on the app's icon on your homescreen and click on the "Uninstall" button. You can also uninstall the app using the umbrel-dev scripts:

```sh
npm run dev client -- apps.uninstall.mutate -- --appId btc-rpc-explorer
```

> [!WARNING]
> When testing your app, make sure to verify that any application state that needs to be persisted is in-fact being persisted in volumes.
>
> A good way to test this is to restart the app (right-click on the app's icon on your homescreen and click on the "Restart" button). If any state is lost, it means that state should be mapped to a persistent volume.
>
> When stopping/starting the app, all data in volumes will be persisted and anything else will be discarded. When uninstalling/installing an app, even persistent data will be discarded.

### 3.2 Test using umbrelOS running on a physical device

You can get up and running with umbrelOS in a few different ways:
  
1. [Install umbrelOS on a Raspberry Pi 5](https://github.com/getumbrel/umbrel/wiki/Install-umbrelOS-on-a-Raspberry-Pi-5)
2. [Install umbrelOS on any x86 system](https://github.com/getumbrel/umbrel/wiki/Install-umbrelOS-on-x86-Systems)
3. [Install umbrelOS in a VM](https://github.com/getumbrel/umbrel/wiki/Install-umbrelOS-on-a-Linux-VM)
4. [Purchase an Umbrel Home device](https://umbrel.com/umbrel-home)

Regardless of the method you choose, once you have umbrelOS up and running and have visited http://umbrel.local and created an account, you can follow the steps below to test your app.

1\. Copy the app's directory (with any .gitkeep files excluded) to the app-store directory on your umbrelOS device.

To do this, we run the following command on our local machine:

```sh
rsync -av --exclude=".gitkeep" <path-to-your-forked-repo-on-local-machine>/btc-rpc-explorer umbrel@umbrel.local:/home/umbrel/umbrel/app-stores/getumbrel-umbrel-apps-github-53f74447/
```

If you are asked for a password during the transfer, use the password that you set for your umbrelOS device when you created your account.

2\. Install the app on your umbrelOS device:

From your umbrelOS homescreen, go to the App Store and navigate to BTC RPC Explorer. Click on the "Install" button and wait for the app to install.

You can also install the app from the command line. umbrelOS provides a web terminal that can be accessed via Settings > Advanced Settings > Terminal > umbrelOS, or you can SSH into the device from your local machine via `ssh umbrel@umbrel.local` and use the same password you set for your umbrelOS device when you created your account.

```sh
umbreld client apps.install.mutate --appId btc-rpc-explorer
```

That's it! The app should now be accessible at http://umbrel.local:3002

To uninstall the app, you can right-click on the app's icon on your homescreen and click on the "Uninstall" button. You can also uninstall the app from the command line with:

```sh
umbreld client apps.uninstall.mutate --appId btc-rpc-explorer
```

> [!WARNING]
> When testing your app, make sure to verify that any application state that needs to be persisted is in-fact being persisted in volumes.
>
> A good way to test this is to restart the app (right-click on the app's icon on your homescreen and click on the "Restart" button). If any state is lost, it means that state should be mapped to a persistent volume.
>
> When stopping/starting the app, all data in volumes will be persisted and anything else will be discarded. When uninstalling/installing an app, even persistent data will be discarded.

___

## 4. 🚀&nbsp;&nbsp;Submitting the app

We're now ready to open a pull request on the main [getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps) apps repo to submit our app. Let's copy-paste the following markdown for the pull request description, fill it up with the required details, and then open a pull request.

```
# App Submission

### App name
...

### 256x256 SVG icon
_(Submit an icon with no rounded corners as it will be dynamically rounded with CSS. GitHub doesn't allow uploading SVGs directly, so please upload your icon to an alternate service, like https://svgur.com, and paste the link below.)_
_We will help finalize this icon before the app goes live in the Umbrel App Store._

...

### Gallery images
_(Upload 3 to 5 high-quality gallery images (1440x900px) of your app in PNG format, or just upload 3 to 5 screenshots of your app and we'll help you design the gallery images.)_
_We will help finalize these images before the app goes live in the Umbrel App Store._
...


### I have tested my app on:
- [ ] umbrelOS on a Raspberry Pi
- [ ] umbrelOS on an Umbrel Home
- [ ] umbrelOS on Linux VM
```

This is where the above information is used when the app goes live in the Umbrel App Store:

<img width="877" alt="image" src="https://github.com/getumbrel/umbrel-apps/assets/85373263/2297030f-909a-4e33-afac-398e30fc79c4">

> After you've submitted your app, we'll review your pull request, make some adjustments in the `docker-compose.yml` file, such as removing any port conflicts with other apps, pinning Docker images to their sha256 digests, assigning unique IP addresses to the containers, etc before merging.

🎉 Congratulations! That's all you need to do to package, test, and submit your app to Umbrel. We can't wait to have you onboard!

---

## Advanced configuration

### App Proxy
The Umbrel App Proxy automatically protects an app by requiring the user to enter their Umbrel password (either when they login into the main Web UI or by visiting an app directly e.g. `http://umbrel.local:3002`)

##### Disable
There could be cases where you wish to disable this authentication. That can be done by adding this env. var. to the `app_proxy` Docker Compose service:
```
PROXY_AUTH_ADD: "false"
```

##### Whitelist/blacklist
Some apps host a user facing at the root of their web application and then an API at e.g. `/api`. And in this case we would like `/` to be protected by Umbrel and `/api` protected by the apps existing/inbuilt API token system. This can be achieved by adding this env. var. to the `app_proxy` Docker Compose service:
```
PROXY_AUTH_WHITELIST: "/api/*"
```

Another example could be that the root of the web application (`/`) should be publically accessible but the admin section be protected by Umbrel. This can be achieved by adding these env. vars. to the `app_proxy` Docker Compose service:
```
PROXY_AUTH_WHITELIST: "*"
PROXY_AUTH_BLACKLIST: "/admin/*"
```

---

## FAQs

1. **How do I push app updates?**

    Every time you release a new version of your app, you should build, tag, and push the new Docker images to Docker Hub. Then open a new PR on our main app repo (getumbrel/umbrel-apps) with your up-to-date docker image, and updated `version` and `releaseNotes` in your app's `umbrel-app.yml` file.

1. **I need help with something else**

    You can open an [issue](https://github.com/getumbrel/umbrel-apps/issues) on GitHub or get in touch with [@mayankchhabra](https://t.me/mayankchhabra), [@lukechilds](https://t.me/lukechilds), or [@nmfretz](https://t.me/nmfretz) on Telegram.
