// Keep ORIGIN for the PHP API's canonical share URLs. The upstream launcher
// forces that origin onto browser requests, which rejects HTTPS form actions
// when ORIGIN uses HTTP. Start the adapter directly so it uses the trusted
// Umbrel proxy's protocol and the request's Host, with CSRF checks intact.
await import('./index.js');
