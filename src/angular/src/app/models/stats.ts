export interface StatsSummary {
  total_count: number;
  success_count: number;
  failed_count: number;
  total_bytes: number;
  avg_speed_bps: number;
}

export interface TransferRecord {
  id: number;
  filename: string;
  pair_id: string | null;
  size_bytes: number | null;
  duration_seconds: number | null;
  completed_at: number;
  status: 'success' | 'failed';
}

export interface SpeedSample {
  bucket_epoch: number;
  bytes_per_sec: number;
}

export const EMPTY_SUMMARY: StatsSummary = {
  total_count: 0,
  success_count: 0,
  failed_count: 0,
  total_bytes: 0,
  avg_speed_bps: 0,
};
