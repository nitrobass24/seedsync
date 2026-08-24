/**
 * Backend config.
 * Note: Naming convention matches that used in the JSON.
 */

/** The value any single config field may hold. */
export type ConfigValue = string | number | boolean | null;

/**
 * A config section read as a string-keyed bag of ConfigValues. Sections do NOT
 * `extends` this (that would collapse `keyof Section` to `string` and defeat the
 * typo-catching ConfigValuePath in options-list.ts); it is only used as an
 * explicit, localized cast target at the few dynamic section/option access sites.
 */
export type ConfigSection = Record<string, ConfigValue>;

export interface General {
  log_level: string | null;
  verbose: boolean | null;
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
  remote_python_path: string | null;
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
  protocol: string | null;
  remote_ftp_port: number | null;
  ftp_ssl_verify_certificate: boolean | null;
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
  notify_on_download_start: boolean | null;
  notify_on_download_complete: boolean | null;
  notify_on_extraction_complete: boolean | null;
  notify_on_extraction_failed: boolean | null;
  notify_on_delete_complete: boolean | null;
  discord_webhook_url: string | null;
  telegram_bot_token: string | null;
  telegram_chat_id: string | null;
}

export interface Validate {
  enabled: boolean | null;
  algorithm: string | null;
  auto_validate: boolean | null;
  xfer_verify: boolean | null;
}

/** Sentinel value the backend uses to mask sensitive fields in API responses. */
export const REDACTED_SENTINEL = '********';

export interface Config {
  general: General;
  lftp: Lftp;
  controller: Controller;
  web: Web;
  autoqueue: AutoQueue;
  logging: Logging;
  notifications: Notifications;
  validate: Validate;
}

export const DEFAULT_CONFIG: Config = {
  general: {
    log_level: null,
    verbose: null,
    exclude_patterns: null,
  },
  lftp: {
    remote_address: null,
    remote_username: null,
    remote_password: null,
    remote_port: null,
    remote_path: null,
    local_path: null,
    remote_path_to_scan_script: null,
    remote_python_path: null,
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
    protocol: 'sftp',
    remote_ftp_port: 21,
    ftp_ssl_verify_certificate: false,
  },
  controller: {
    interval_ms_remote_scan: null,
    interval_ms_local_scan: null,
    interval_ms_downloading_scan: null,
    extract_path: null,
    use_local_path_as_extract_path: null,
    staging_path: null,
    use_staging: null,
  },
  web: {
    port: null,
    api_key: null,
  },
  autoqueue: {
    enabled: null,
    patterns_only: null,
    auto_extract: null,
    auto_delete_remote: null,
  },
  logging: {
    log_format: null,
  },
  notifications: {
    webhook_url: null,
    notify_on_download_start: null,
    notify_on_download_complete: null,
    notify_on_extraction_complete: null,
    notify_on_extraction_failed: null,
    notify_on_delete_complete: null,
    discord_webhook_url: null,
    telegram_bot_token: null,
    telegram_chat_id: null,
  },
  validate: {
    enabled: null,
    algorithm: null,
    auto_validate: null,
    xfer_verify: true,
  },
};
