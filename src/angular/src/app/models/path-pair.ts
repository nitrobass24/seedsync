export interface PathPair {
  id: string;
  name: string;
  remote_path: string;
  local_path: string;
  enabled: boolean;
  auto_queue: boolean;
  arr_target_ids: string[];
}
