#!/usr/bin/env node
import serve from 'serve';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const port = process.env.PORT || 8080;
const host = '0.0.0.0';

serve(path.join(__dirname, 'dist'), {
  port: parseInt(port),
  host: host,
  single: true,
  cors: true,
});

console.log(`🚀 Server running on http://${host}:${port}`);
