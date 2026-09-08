export function summarizeBatchProgress(items: { status: string }[]) {
  const total = items.filter(item => item.status !== "error").length;
  const done = items.filter(item => item.status === "done").length;
  const failed = items.filter(item => item.status === "failed").length;
  const building = items.filter(item => item.status === "building").length;
  const finished = done + failed;
  return { total, done, failed, finished, building, allFinished: total > 0 && finished === total };
}
