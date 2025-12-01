#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { processRawData } = require('../metrics_engine');

function deepEqual(a, b, currentPath = '') {
  if (a === b) return true;

  if (typeof a !== typeof b) {
    console.error(`Type mismatch at ${currentPath}:`, typeof a, 'vs', typeof b);
    return false;
  }

  if (a === null || b === null) {
    console.error(`Null mismatch at ${currentPath}:`, a, 'vs', b);
    return false;
  }

  if (Array.isArray(a)) {
    if (!Array.isArray(b)) {
      console.error(`Array vs non-array at ${currentPath}`);
      return false;
    }
    if (a.length !== b.length) {
      console.error(`Length mismatch at ${currentPath}:`, a.length, 'vs', b.length);
      return false;
    }
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i], `${currentPath}[${i}]`)) return false;
    }
    return true;
  }

  if (typeof a === 'object') {
    const aKeys = Object.keys(a);
    const bKeys = Object.keys(b);
    aKeys.sort();
    bKeys.sort();
    if (aKeys.join(',') !== bKeys.join(',')) {
      console.error(`Key mismatch at ${currentPath}:`, aKeys, 'vs', bKeys);
      return false;
    }
    for (const key of aKeys) {
      if (!deepEqual(a[key], b[key], currentPath ? `${currentPath}.${key}` : key)) {
        return false;
      }
    }
    return true;
  }

  console.error(`Value mismatch at ${currentPath}:`, a, 'vs', b);
  return false;
}

function main() {
  const rawPath = path.join(__dirname, '..', 'data', 'raw_data.json');
  const snapshotPath = path.join(__dirname, '..', 'data', 'metrics_snapshot_baseline.json');

  if (!fs.existsSync(rawPath)) {
    console.error('❌ raw_data.json not found at', rawPath);
    process.exit(1);
  }
  if (!fs.existsSync(snapshotPath)) {
    console.error('❌ Baseline snapshot not found at', snapshotPath);
    console.error('   Run scripts/generate_metrics_snapshot.js first.');
    process.exit(1);
  }

  const raw = JSON.parse(fs.readFileSync(rawPath, 'utf8'));
  const baseline = JSON.parse(fs.readFileSync(snapshotPath, 'utf8'));
  const current = processRawData(raw);

  console.log('🔍 Comparing current metrics to baseline snapshot...');
  const ok = deepEqual(current, baseline, 'metrics');

  if (!ok) {
    console.error('❌ Metrics engine output differs from baseline.');
    process.exit(1);
  }

  console.log('✅ Metrics engine matches baseline snapshot.');
}

main();
