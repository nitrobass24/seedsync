/**
 * Backend config.
 * Note: Naming convention matches that used in the JSON.
 */

export interface General {
  debug: boolean | null;
  exclude_patterns: string | null;
}

export interface Lftp {
  remote_address: string | null;
  remote_username: string | null;
  remote_password: string | null;
  remote_port: number | null;
  remote_path: string | null;
  local_path: string | null;
  remote_path_to_scan_script: string | null;
  use_ssh_key: boolean | null;
  num_max_parallel_downloads: number | null;
  num_max_parallel_files_per_download: number | null;
  num_max_connections_per_root_file: number | null;
  num_max_connections_per_dir_file: number | null;
  num_max_total_connections: number | null;
  use_temp_file: boolean | null;
  net_limit_rate: string | null;
  net_socket_buffer: string | null;
  pget_min_chunk_size: string | null;
  mirror_parallel_directories: boolean | null;
  net_timeout: number | null;
  net_max_retries: number | null;
  net_reconnect_interval_base: number | null;
  net_reconnect_interval_multiplier: number | null;
}

export interface Controller {
  interval_ms_remote_scan: number | null;
  interval_ms_local_scan: number | null;
  interval_ms_downloading_scan: number | null;
  extract_path: string | null;
  use_local_path_as_extract_path: boolean | null;
  staging_path: string | null;
  use_staging: boolean | null;
}

export interface Web {
  port: number | null;
  api_key: string | null;
}

export interface AutoQueue {
  enabled: boolean | null;
  patterns_only: boolean | null;
  auto_extract: boolean | null;
  auto_delete_remote: boolean | null;
}

export interface Logging {
  log_format: string | null;
}

export interface Notifications {
    webhook_url: string | null;
    notify_on_download_complete: boolean | null;
    notify_on_extraction_complete: boolean | null;
    notify_on_extraction_failed: boolean | null;
    notify_on_delete_complete: boolean | null;
}

export interface Config {
  general: General;
  lftp: Lftp;
  controller: Controller;
  web: Web;
  autoqueue: AutoQueue;
  logging: Logging;
  notifications: Notifications;
}

export const DEFAULT_GENERAL: General = {
  debug: null,
  exclude_patterns: null,
};

export const DEFAULT_LFTP: Lftp = {
  remote_address: null,
  remote_username: null,
  remote_password: null,
  remote_port: null,
  remote_path: null,
  local_path: null,
  remote_path_to_scan_script: null,
  use_ssh_key: null,
  num_max_parallel_downloads: null,
  num_max_parallel_files_per_download: null,
  num_max_connections_per_root_file: null,
  num_max_connections_per_dir_file: null,
  num_max_total_connections: null,
  use_temp_file: null,
  net_limit_rate: null,
  net_socket_buffer: null,
  pget_min_chunk_size: null,
  mirror_parallel_directories: null,
  net_timeout: null,
  net_max_retries: null,
  net_reconnect_interval_base: null,
  net_reconnect_interval_multiplier: null,
};

export const DEFAULT_CONTROLLER: Controller = {
  interval_ms_remote_scan: null,
  interval_ms_local_scan: null,
  interval_ms_downloading_scan: null,
  extract_path: null,
  use_local_path_as_extract_path: null,
  staging_path: null,
  use_staging: null,
};

export const DEFAULT_WEB: Web = {
  port: null,
  api_key: null,
};

export const DEFAULT_AUTOQUEUE: AutoQueue = {
  enabled: null,
  patterns_only: null,
  auto_extract: null,
  auto_delete_remote: null,
};

export const DEFAULT_LOGGING: Logging = {
  log_format: null,
};

export const DEFAULT_NOTIFICATIONS: Notifications = {
    webhook_url: null,
    notify_on_download_complete: null,
    notify_on_extraction_complete: null,
    notify_on_extraction_failed: null,
    notify_on_delete_complete: null,
};

export const DEFAULT_CONFIG: Config = {
  general: { ...DEFAULT_GENERAL },
  lftp: { ...DEFAULT_LFTP },
  controller: { ...DEFAULT_CONTROLLER },
  web: { ...DEFAULT_WEB },
  autoqueue: { ...DEFAULT_AUTOQUEUE },
  logging: { ...DEFAULT_LOGGING },
  notifications: { ...DEFAULT_NOTIFICATIONS },
};
