/**
 * ServerStatus model.
 */
export interface ServerStatus {
  server: {
    up: boolean;
    errorMessage: string | null;
  };
  controller: {
    latestLocalScanTime: Date | null;
    latestRemoteScanTime: Date | null;
    latestRemoteScanFailed: boolean;
    latestRemoteScanError: string | null;
  };
}

/**
 * ServerStatus as serialized by the backend.
 * Note: naming convention matches that used in JSON.
 */
export interface ServerStatusJson {
  server: {
    up: boolean;
    error_msg: string;
  };
  controller: {
    latest_local_scan_time: string | null;
    latest_remote_scan_time: string | null;
    latest_remote_scan_failed: boolean;
    latest_remote_scan_error: string | null;
  };
}

export function serverStatusFromJson(json: ServerStatusJson): ServerStatus {
  let latestLocalScanTime: Date | null = null;
  if (json.controller.latest_local_scan_time != null) {
    latestLocalScanTime = new Date(1000 * +json.controller.latest_local_scan_time);
  }

  let latestRemoteScanTime: Date | null = null;
  if (json.controller.latest_remote_scan_time != null) {
    latestRemoteScanTime = new Date(1000 * +json.controller.latest_remote_scan_time);
  }

  return {
    server: {
      up: json.server.up,
      errorMessage: json.server.error_msg,
    },
    controller: {
      latestLocalScanTime,
      latestRemoteScanTime,
      latestRemoteScanFailed: json.controller.latest_remote_scan_failed,
      latestRemoteScanError: json.controller.latest_remote_scan_error,
    },
  };
}
