#!/usr/bin/env bash

start_resource_sampler() {
  local stage="$1"
  python3 scripts/resource_sampler.py \
    --stage "$stage" \
    --metrics-file "${METRICS_FILE:-/tmp/build_metrics.json}" \
    --path . \
    --interval 1 &
  RESOURCE_SAMPLER_PID=$!
}

stop_resource_sampler() {
  if [ -n "${RESOURCE_SAMPLER_PID:-}" ]; then
    kill -TERM "$RESOURCE_SAMPLER_PID" 2>/dev/null || true
    wait "$RESOURCE_SAMPLER_PID" 2>/dev/null || true
    unset RESOURCE_SAMPLER_PID
  fi
}
