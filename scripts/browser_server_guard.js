const net = require("node:net");

function parseBrowserPort(raw, label) {
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`invalid ${label} port: ${raw}`);
  }
  return port;
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function assertPortAvailable(port, label) {
  await new Promise((resolve, reject) => {
    const probe = net.createServer();
    const finish = (error) => {
      probe.close(() => {
        if (error) reject(error);
        else resolve();
      });
    };
    probe.once("error", (error) => {
      if (error.code === "EADDRINUSE") {
        finish(new Error(
          `${label} port ${port} is already in use; `
          + "choose a free port instead of attaching to an existing service",
        ));
        return;
      }
      finish(error);
    });
    probe.listen({ host: "127.0.0.1", port }, () => finish());
  });
}

async function waitForSpawnedHealth({ server, baseURL, label, attempts = 120 }) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (server && server.exitCode !== null) {
      throw new Error(
        `${label} API exited before becoming ready (code=${server.exitCode})`,
      );
    }
    try {
      const response = await fetch(`${baseURL}/api/v1/health`);
      if (response.ok) return;
    } catch (_error) {}
    await sleep(500);
  }
  throw new Error(`${label} API did not become ready`);
}

module.exports = { assertPortAvailable, parseBrowserPort, waitForSpawnedHealth };
