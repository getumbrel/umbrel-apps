import http from 'node:http';

const request = http.get('http://127.0.0.1:8080/healthz', { timeout: 3000 }, (response) => {
  response.resume();
  process.exit(response.statusCode === 200 ? 0 : 1);
});
request.on('error', () => process.exit(1));
request.on('timeout', () => request.destroy(new Error('health check timeout')));
