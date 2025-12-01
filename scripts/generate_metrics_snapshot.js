#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { processRawData } = require('../metrics_engine');

function main() {
  const rawPath = path.join(__dirname, '..', 'data', 'raw_data.json');
  const snapshotPath = path.join(__dirname, '..', 'data', 'metrics_snapshot_baseline.json');

  if (!fs.existsSync(rawPath)) {
    console.error('❌ raw_data.json not found at', rawPath);
    process.exit(1);
  }

  const raw = JSON.parse(fs.readFileSync(rawPath, 'utf8'));
  const metrics = processRawData(raw);

  fs.writeFileSync(snapshotPath, JSON.stringify(metrics, null, 2));
  console.log('✅ Baseline metrics snapshot written to', snapshotPath);
}

main();
