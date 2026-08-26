export const Localization = {
  Error: {
    SERVER_DISCONNECTED: 'Lost connection to the SeedSync service.',
  },
  Notification: {
    CONFIG_RESTART: 'Restart the app to apply new settings.',
    AUTOQUEUE_PATTERN_EMPTY: 'Cannot add an empty autoqueue pattern.',
    STATUS_CONNECTION_WAITING: 'Waiting for SeedSync service to respond...',
    STATUS_REMOTE_SCAN_WAITING: 'Waiting for remote server to respond...',
    STATUS_REMOTE_SERVER_ERROR: (error: string) =>
      `Lost connection to remote server. Retrying automatically. ${error ? '<br />' + error : ''}`,
    STATUS_NO_ENABLED_PAIRS: 'All path pairs are disabled. Enable a pair in Settings to start syncing.',
    NEW_VERSION_AVAILABLE: (url: string) =>
      `A new version of SeedSync is available! Click <a href="${url}" target="blank">here</a> to grab the latest version.`,
  },
} as const;
