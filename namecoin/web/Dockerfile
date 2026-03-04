# Simple web interface showing Namecoin Core connection info
# Build and push to Docker Hub as: namecoin/namecoin-core-umbrel-web:30.2

FROM node:20-slim

WORKDIR /app

COPY package.json .
RUN npm install --production

COPY server.js .
COPY public/ public/

EXPOSE 18080

CMD ["node", "server.js"]
