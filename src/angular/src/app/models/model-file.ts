/**
 * Model file received from the backend.
 * Note: Naming convention matches that used in the JSON.
 */
export interface ModelFile {
  name: string;
  is_dir: boolean;
  local_size: number;
  remote_size: number;
  state: ModelFileState;
  downloading_speed: number;
  eta: number;
  full_path: string;
  is_extractable: boolean;
  local_created_timestamp: Date | null;
  local_modified_timestamp: Date | null;
  remote_created_timestamp: Date | null;
  remote_modified_timestamp: Date | null;
  children: ModelFile[];
}

export enum ModelFileState {
  DEFAULT      = 'default',
  QUEUED       = 'queued',
  DOWNLOADING  = 'downloading',
  DOWNLOADED   = 'downloaded',
  DELETED      = 'deleted',
  EXTRACTING   = 'extracting',
  EXTRACTED    = 'extracted',
}

const STATE_LOOKUP: Record<string, ModelFileState> = {
  DEFAULT:     ModelFileState.DEFAULT,
  QUEUED:      ModelFileState.QUEUED,
  DOWNLOADING: ModelFileState.DOWNLOADING,
  DOWNLOADED:  ModelFileState.DOWNLOADED,
  DELETED:     ModelFileState.DELETED,
  EXTRACTING:  ModelFileState.EXTRACTING,
  EXTRACTED:   ModelFileState.EXTRACTED,
};

export function modelFileFromJson(json: any): ModelFile {
  const children: ModelFile[] = [];
  for (const child of json.children) {
    children.push(modelFileFromJson(child));
  }

  return {
    name: json.name,
    is_dir: json.is_dir,
    local_size: json.local_size,
    remote_size: json.remote_size,
    state: STATE_LOOKUP[json.state.toUpperCase()] ?? ModelFileState.DEFAULT,
    downloading_speed: json.downloading_speed,
    eta: json.eta,
    full_path: json.full_path,
    is_extractable: json.is_extractable,
    local_created_timestamp:
      json.local_created_timestamp != null ? new Date(1000 * +json.local_created_timestamp) : null,
    local_modified_timestamp:
      json.local_modified_timestamp != null ? new Date(1000 * +json.local_modified_timestamp) : null,
    remote_created_timestamp:
      json.remote_created_timestamp != null ? new Date(1000 * +json.remote_created_timestamp) : null,
    remote_modified_timestamp:
      json.remote_modified_timestamp != null ? new Date(1000 * +json.remote_modified_timestamp) : null,
    children,
  };
}
