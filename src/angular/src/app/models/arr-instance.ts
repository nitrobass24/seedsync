export type ArrKind = 'sonarr' | 'radarr';

export const ARR_KINDS: ArrKind[] = ['sonarr', 'radarr'];

export interface ArrInstance {
  id: string;
  name: string;
  kind: ArrKind;
  url: string;
  api_key: string;
  enabled: boolean;
}

export interface ArrInstanceCreate {
  name: string;
  kind: ArrKind;
  url: string;
  api_key: string;
  enabled: boolean;
}

export type ArrInstanceUpdate = Partial<ArrInstanceCreate>;
