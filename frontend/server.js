#!/usr/bin/env node
import serve from 'serve';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const port = parseInt(process.env.PORT || 8080);
const host = '0.0.0.0';

const server = serve(path.join(__dirname, 'dist'), {
  port: port,
  host: host,
  single: true,
  cors: true,
  listen: true,
});

server.then((server) => {
  console.log(`🚀 Server running on http://${host}:${port}`);
  console.log(`📁 Serving files from: ${path.join(__dirname, 'dist')}`);
}).catch((err) => {
  console.error('❌ Server failed to start:', err);
  process.exit(1);
});
