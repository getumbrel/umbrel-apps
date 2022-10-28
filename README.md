# Umbrel App Framework

If you can code in any language, you already know how to develop an app for Umbrel. There is no restriction on the kind of programming languages, frameworks or databases that you can use. Apps run inside isolated Docker containers, and the only requirement (for now) is that they should have a web-based UI.

> Some server apps might not have a UI at all. In that case, the app should serve a simple web page listing the connection details, QR codes, setup instructions, and anything else needed for the user to connect. The user is never expected to have CLI access on Umbrel.

To keep this document short and easy, we won't go into the app development itself, and will instead focus on packaging an existing app.

Let's straightaway jump into action by packaging [BTC RPC Explorer](https://github.com/janoside/btc-rpc-explorer), a Node.js based blockchain explorer, for Umbrel.

There are 4 steps:

1. [🛳 Containerizing the app using Docker](#1-containerizing-the-app-using-docker)
1. [☂️ Packaging the app for Umbrel](#2-%EF%B8%8Fpackaging-the-app-for-umbrel)
1. [🛠 Testing the app on Umbrel](#3-testing-the-app-on-umbrel)
    1. [Testing on Umbrel development environment (Linux or macOS)](#31-testing-the-app-on-umbrel-development-environment)
    1. [Testing on Umbrel OS (Raspberry Pi 4)](#32-testing-on-umbrel-os-raspberry-pi-4)
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

- [x] Uses `debian:buster-slim` (or its derivatives, like `node:12-buster-slim`) as the base image — resulting in less storage consumption and faster app installs as the base image is already cached on the user's Umbrel.
- [x] Uses [multi-stage builds](https://docs.docker.com/develop/develop-images/multistage-build/) for smaller image size.
- [x] Ensures development files are not included in the final image.
- [x] Has only one service per container.
- [x] Doesn't run the service as root.
- [x] Uses remote assets that are verified against a checksum.
- [x] Results in deterministic image builds.

3\. We're now ready to build the Docker image of BTC RPC Explorer. Umbrel supports both 64-bit ARM and x86 architectures, so we'll use `docker buildx` to build, tag, and push multi-architecture Docker images of our app to Docker Hub.

```sh
docker buildx build --platform linux/arm64,linux/amd64 --tag getumbrel/btc-rpc-explorer:v2.0.2 --output "type=registry" .
```

> You need to enable ["experimental features"](https://docs.docker.com/engine/reference/commandline/cli/#experimental-features) in Docker to use `docker buildx`.

___

## 2. ☂️&nbsp;&nbsp;Packaging the app for Umbrel

1\. Let's fork the [getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps) repo on GitHub, clone our fork locally, create a new branch for our app, and then switch to it:

```sh
git clone https://github.com/<username>/umbrel-apps.git
cd umbrel-apps
```

2\. It's now time to decide an ID for our app. An app ID should only contain lowercase alphabetical characters and dashes, and should be humanly recognizable. For this app we'll go with `btc-rpc-explorer`.

We need to create a new subdirectory in the apps directory with same name as our app ID and move into it:

```sh
mkdir btc-rpc-explorer
cd btc-rpc-explorer
```

3\. Within the app's directory, we'll now create the skeleton for our app will consist of:

- `docker-compose.yml` - Used to start and stop your app's Docker containers
- `umbrel-app.yml` - A app manifest file so that Umbrel knows the name and version of the app
- `exports.sh` - A shell script to export environment variables used within `docker-compose.yml` and shared with other installed apps

We'll now create a `docker-compose.yml` file in this directory to define our application.

> New to Docker Compose? It's a simple tool for defining and running Docker applications that can have multiple containers. Follow along the tutorial, we promise it's not hard if you already understand the basics of Docker.

Let's copy-paste the following template `docker-compose.yml` file in a text editor and edit it according to our app.

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
    image: <docker-image>:<tag>
    restart: on-failure
    stop_grace_period: 1m
    ports:
      # Replace <port> with the port that your app's web server
      # is listening inside the Docker container. If you need to
      # expose more ports, add them below.
      - <port>:<port>
    volumes:
      # Uncomment to mount your data directories inside
      # the Docker container for storing persistent data
      # - ${APP_DATA_DIR}/foo:/foo
      # - ${APP_DATA_DIR}/bar:/bar

      # Uncomment to mount LND's data directory as read-only
      # inside the Docker container at path /lnd
      # - ${APP_LIGHTNING_NODE_DATA_DIR}:/lnd:ro

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
  #   image: <docker-image>:<tag>
  #   ...

```

Our app manifest YAML file tells Umbrel details about our app such as name, description, dependencies, port number to access the app, etc.

```yml
manifestVersion: 1
id: btc-rpc-explorer
category: Explorers
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
```

The `dependencies` section within the app manifest gives Umbrel a list of app IDs that must be already installed in order for the user to install BTC RPC Explorer and also function.

The `exports.sh` shell script is a simple script to export environmental variables that your `docker-compose.yml` can read. These env. vars. are also accessible when other apps start through their `docker-compose.yml` files. Most applications will not require this feature.

If we (for example) wanted to share BTC RPC Explorer's Address API with other apps; that would look like this:
```sh
export APP_BTC_RPC_EXPLORER_ADDRESS_API="electrumx"
```

4\. For our app, we'll update `<docker-image>` with `getumbrel/btc-rpc-explorer`, `<tag>` with `v2.0.2`, and `<port>` with `3002`. Since BTC RPC Explorer doesn't need to store any persistent data and doesn't require access to Bitcoin Core's or LND's data directories, we can remove the entire `volumes` block.

BTC RPC Explorer is an application with a single Docker container, so we don't need to define any other additional services (like a database service, etc) in the compose file.

> If BTC RPC Explorer needed to persist some data we would have created a new `data` directory next to the `docker-compose.yml` file. We'd then mount the volume `- ${APP_DATA_DIR}/data:/data` in  `docker-compose.yml` to make the directory available at `/data` inside the container.

Updated `docker-compose.yml` file:

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

## 3. 🛠&nbsp;&nbsp;Testing the app on Umbrel

### 3.1 Test using a low-cost cloud virtual machine (VM)

Using a Ubuntu/Debian based VM from your favourite cloud vendor, we can SSH into the server (e.g. `ssh root@123.123.123.123`).

1\. Install Umbrel with one command: `curl -L https://umbrel.sh | bash`.

Once Umbrel has started, the Web UI will be accessible at the IP address of the VM (e.g. `http://123.123.123.123`)

2\. We need to use our forked remote app repo:

```sh
cd umbrel
sudo ./scripts/repo checkout https://github.com/<username>/umbrel-apps.git
```

3\. And finally, it's time to install our app:

```sh
sudo ./scripts/app install btc-rpc-explorer
```

That's it! Our BTC RPC Explorer app should now be accessible at http://umbrel-dev.local:3002

4\. To make changes:

Let's commit and push our changes to our forked Umbrel app repo then run:

```sh
sudo ./scripts/repo checkout https://github.com/<username>/umbrel-apps.git
sudo ./scripts/app update btc-rpc-explorer
```

### 3.1 Testing the app on Umbrel development environment

Umbrel development environment ([`umbrel-dev`](https://github.com/getumbrel/umbrel-dev)) is a lightweight regtest instance of Umbrel that runs inside a virtual machine on your system. It's currently only compatible with Linux or macOS, so if you're on Windows, you may skip this section and directly test your app on a Raspberry Pi 4 running [Umbrel OS](https://github.com/getumbrel/umbrel-os).

1\. First, we'll install the `umbrel-dev` CLI and it's dependencies [Virtual Box](https://www.virtualbox.org) and [Vagrant](https://vagrantup.com) on our system. If you use [Homebrew](https://brew.sh) you can do that with just:

```sh
brew install lukechilds/tap/umbrel-dev gnu-sed
brew install --cask virtualbox vagrant
```

2\. Now let's initialize our development environment and boot the VM:

```sh
mkdir umbrel-dev
cd umbrel-dev
umbrel-dev init
umbrel-dev boot
```

> The first `umbrel-dev` boot usually takes a while due to the initial setup and configuration of the VM. Subsequent boots are much faster.

After the VM has booted, we can verify if the Umbrel dashboard is accessible at http://umbrel-dev.local in our browser to make sure everything is running fine.

3\. We need to use our forked remote app repo:

```sh
cd getumbrel/umbrel
sudo ./scripts/repo checkout https://github.com/<username>/umbrel-apps.git
```

4\. And finally, it's time to install our app:

```sh
sudo ./scripts/app install btc-rpc-explorer
```

That's it! Our BTC RPC Explorer app should now be accessible at http://umbrel-dev.local:3002

5\. To make changes:

Let's commit and push our changes to our forked Umbrel app repo then run:

```sh
sudo ./scripts/repo checkout https://github.com/<username>/umbrel-apps.git
sudo ./scripts/app update btc-rpc-explorer
```

>Don't forget to shutdown the `umbrel-dev` virtual machine after testing with `umbrel-dev shutdown`!

### 3.2 Testing on Umbrel OS (Raspberry Pi 4)

1\. We'll first install and run Umbrel OS on a Raspberry Pi 4. [Full instructions can be found here](https://getumbrel.com/#start). After installation, we'll set it up on http://umbrel.local, and then SSH into the Pi:

```sh
ssh umbrel@umbrel.local
```

(SSH password is the same as your Umbrel's dashboard password)

2\. Next, we'll switch to the forked remote app repo:

```sh
sudo ./scripts/repo checkout https://github.com/<username>/umbrel-apps.git
```

3\. Once the repo has updated, it's time to test our app:

```sh
sudo ./scripts/app install btc-rpc-explorer
```

The app should now be accessible at http://umbrel.local:3002

4\. To uninstall:

```sh
sudo ./scripts/app uninstall btc-rpc-explorer
```

> When testing your app, make sure to verify that any application state that needs to be persisted is in-fact being persisted in volumes.
>
> A good way to test this is to restart the app with `scripts/app stop <app-id> && scripts/app start <app-id>`. If any state is lost, it means that state should be mapped to a persistent volume.
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

...

### Gallery images
_(Upload 3 to 5 high-quality gallery images (1440x900px) of your app in PNG format, or just upload 3 to 5 screenshots of your app and we'll help you design the gallery images.)_

...


### I have tested my app on:
- [ ] [Umbrel dev environment](https://github.com/getumbrel/umbrel-dev)
- [ ] [Umbrel OS on a Raspberry Pi 4](https://github.com/getumbrel/umbrel-os)
- [ ] [Custom Umbrel install on Linux](https://github.com/getumbrel/umbrel#-installation)
```

This is where the above information is used when the app goes live in the Umbrel App Store:

![Umbrel App Store Labels](https://i.imgur.com/0CorPRK.png)

> After you've submitted your app, we'll review your pull request, make some adjustments in the `docker-compose.yml` file, such as removing any port conflicts with other apps, pinning Docker images to their sha256 digests, assigning unique IP addresses to the containers, etc before merging.

🎉 Congratulations! That's all you need to do to package, test and submit your app to Umbrel. We can't wait to have you onboard!

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

Another example could be that the root of the web application (`/`) should be publically accessible but the admin section by protected by Umbrel. This can be achieved by adding these env. vars. to the `app_proxy` Docker Compose service:
```
PROXY_AUTH_WHITELIST: "*"
PROXY_AUTH_BLACKLIST: "/admin/*"
```

---

## FAQs

1. **How to push app updates?**

    Every time you release a new version of your app, you should build, tag and push the new Docker images to Docker Hub. Then open a new PR on our main app repo (getumbrel/umbrel-apps) with your up-to-date docker image, and updated `version` and `releaseNotes` in your app's `umbrel-app.yml` file.

1. **I need help with something else?**

    You can open an [issue](https://github.com/getumbrel/umbrel-apps/issues) on GitHub or get in touch with [@mayankchhabra](https://t.me/mayankchhabra) or [@lukechilds](https://t.me/lukechilds) on Telegram.
