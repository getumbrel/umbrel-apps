FROM node:20-slim

WORKDIR /app

COPY package.json .
RUN npm install --production

COPY server.js .
COPY public/ public/

RUN mkdir -p /data && chown -R 1000:1000 /data /app

EXPOSE 18081

USER 1000:1000

CMD ["node", "server.js"]
