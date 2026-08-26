import useSWR from "swr";
import { getJob, listBackgrounds, listJobs } from "./api";
import type { Job } from "./types";

export function useJobs() {
  return useSWR("jobs", listJobs, { refreshInterval: 5000 });
}

const ACTIVE_STATUSES: Job["status"][] = ["pending", "processing"];

export function useJob(id: string | undefined) {
  return useSWR(id ? ["job", id] : null, () => getJob(id as string), {
    refreshInterval: (data) => (!data || ACTIVE_STATUSES.includes(data.status) ? 2000 : 0),
  });
}

export function useBackgrounds() {
  return useSWR("backgrounds", listBackgrounds);
}
