import { describe, it, expect } from 'vitest';

import { ModelFileState } from '../../models/model-file';
import { ViewFileStatus } from '../../models/view-file';
import {
  mapState,
  deriveCapabilities,
  QUEUEABLE_STATUSES,
  STOPPABLE_STATUSES,
  LOCAL_ACTION_STATUSES,
  REMOTELY_DELETABLE_STATUSES,
  VALIDATABLE_STATUSES,
  VALIDATE_UNAVAILABLE_TOOLTIP,
} from './view-file-capabilities';

describe('view-file-capabilities', () => {
  describe('mapState', () => {
    // Every 1:1 state -> status mapping (sizes irrelevant for these).
    const directCases: [ModelFileState, ViewFileStatus][] = [
      [ModelFileState.QUEUED, ViewFileStatus.QUEUED],
      [ModelFileState.DOWNLOADING, ViewFileStatus.DOWNLOADING],
      [ModelFileState.DOWNLOADED, ViewFileStatus.DOWNLOADED],
      [ModelFileState.DELETED, ViewFileStatus.DELETED],
      [ModelFileState.EXTRACTING, ViewFileStatus.EXTRACTING],
      [ModelFileState.EXTRACTED, ViewFileStatus.EXTRACTED],
      [ModelFileState.EXTRACT_FAILED, ViewFileStatus.EXTRACT_FAILED],
      [ModelFileState.VALIDATING, ViewFileStatus.VALIDATING],
      [ModelFileState.VALIDATED, ViewFileStatus.VALIDATED],
      [ModelFileState.CORRUPT, ViewFileStatus.CORRUPT],
    ];

    for (const [state, expected] of directCases) {
      it(`maps ${state} -> ${expected}`, () => {
        expect(mapState(state, 0, 0)).toBe(expected);
        expect(mapState(state, 100, 200)).toBe(expected);
      });
    }

    it('maps DEFAULT with both sizes > 0 to STOPPED', () => {
      expect(mapState(ModelFileState.DEFAULT, 50, 200)).toBe(ViewFileStatus.STOPPED);
    });

    it('maps DEFAULT with local_size = 0 to DEFAULT', () => {
      expect(mapState(ModelFileState.DEFAULT, 0, 200)).toBe(ViewFileStatus.DEFAULT);
    });

    it('maps DEFAULT with remote_size = 0 to DEFAULT', () => {
      expect(mapState(ModelFileState.DEFAULT, 50, 0)).toBe(ViewFileStatus.DEFAULT);
    });

    it('maps DEFAULT with both sizes = 0 to DEFAULT', () => {
      expect(mapState(ModelFileState.DEFAULT, 0, 0)).toBe(ViewFileStatus.DEFAULT);
    });

    it('falls through to DEFAULT for an unknown state', () => {
      expect(mapState('something-unexpected' as ModelFileState, 100, 200)).toBe(ViewFileStatus.DEFAULT);
    });
  });

  describe('deriveCapabilities', () => {
    // isQueueable: in QUEUEABLE_STATUSES with remoteSize > 0, OR CORRUPT.
    it('marks queueable statuses queueable only when remoteSize > 0', () => {
      for (const status of QUEUEABLE_STATUSES) {
        expect(deriveCapabilities(status, 0, 100, 0, 100).isQueueable).toBe(true);
        expect(deriveCapabilities(status, 0, 0, 0, 0).isQueueable).toBe(false);
      }
    });

    it('marks CORRUPT queueable even when remoteSize is 0', () => {
      expect(deriveCapabilities(ViewFileStatus.CORRUPT, 0, 0, 0, 0).isQueueable).toBe(true);
    });

    it('does not mark a non-queueable status queueable', () => {
      expect(deriveCapabilities(ViewFileStatus.DOWNLOADING, 0, 100, 0, 100).isQueueable).toBe(false);
    });

    it('marks stoppable statuses stoppable', () => {
      for (const status of STOPPABLE_STATUSES) {
        expect(deriveCapabilities(status, 0, 0, 0, 0).isStoppable).toBe(true);
      }
      expect(deriveCapabilities(ViewFileStatus.DEFAULT, 0, 0, 0, 0).isStoppable).toBe(false);
    });

    it('marks isExtractable / isLocallyDeletable for local-action statuses only when localSize > 0', () => {
      for (const status of LOCAL_ACTION_STATUSES) {
        const onWithLocal = deriveCapabilities(status, 100, 0, 100, 0);
        expect(onWithLocal.isExtractable).toBe(true);
        expect(onWithLocal.isLocallyDeletable).toBe(true);

        const offNoLocal = deriveCapabilities(status, 0, 100, 0, 100);
        expect(offNoLocal.isExtractable).toBe(false);
        expect(offNoLocal.isLocallyDeletable).toBe(false);
      }
    });

    it('does not mark non-local-action statuses extractable / locally-deletable', () => {
      const caps = deriveCapabilities(ViewFileStatus.QUEUED, 100, 100, 100, 100);
      expect(caps.isExtractable).toBe(false);
      expect(caps.isLocallyDeletable).toBe(false);
    });

    it('keeps isExtractable and isLocallyDeletable in lockstep (shared allow-list)', () => {
      for (const status of Object.values(ViewFileStatus)) {
        const caps = deriveCapabilities(status, 100, 100, 100, 100);
        expect(caps.isExtractable).toBe(caps.isLocallyDeletable);
      }
    });

    it('marks isRemotelyDeletable for remote-deletable statuses only when remoteSize > 0', () => {
      for (const status of REMOTELY_DELETABLE_STATUSES) {
        expect(deriveCapabilities(status, 0, 100, 0, 100).isRemotelyDeletable).toBe(true);
        expect(deriveCapabilities(status, 0, 0, 0, 0).isRemotelyDeletable).toBe(false);
      }
    });

    it('marks DELETED remotely-deletable with remoteSize > 0 (delete-from-remote after local delete)', () => {
      expect(deriveCapabilities(ViewFileStatus.DELETED, 0, 100, 0, 100).isRemotelyDeletable).toBe(true);
    });

    it('marks isValidatable only when status allows AND both raw sizes are non-null', () => {
      for (const status of VALIDATABLE_STATUSES) {
        expect(deriveCapabilities(status, 100, 100, 100, 100).isValidatable).toBe(true);
        // raw null on either side disables validation
        expect(deriveCapabilities(status, 100, 0, 100, null).isValidatable).toBe(false);
        expect(deriveCapabilities(status, 0, 100, null, 100).isValidatable).toBe(false);
        expect(deriveCapabilities(status, 0, 0, null, null).isValidatable).toBe(false);
      }
    });

    it('does not mark a non-validatable status validatable even with both sizes present', () => {
      const caps = deriveCapabilities(ViewFileStatus.DEFAULT, 100, 100, 100, 100);
      expect(caps.isValidatable).toBe(false);
      expect(caps.validateTooltip).toBeNull();
    });

    it('keys isValidatable off RAW null-ness, not coalesced sizes', () => {
      // Coalesced sizes are both > 0, but raw remote is null -> not validatable.
      const caps = deriveCapabilities(ViewFileStatus.DOWNLOADED, 100, 0, 100, null);
      expect(caps.isValidatable).toBe(false);
    });

    it('shows the unavailable tooltip when validatable-status but raw remote_size is null', () => {
      const caps = deriveCapabilities(ViewFileStatus.DOWNLOADED, 100, 0, 100, null);
      expect(caps.validateTooltip).toBe(VALIDATE_UNAVAILABLE_TOOLTIP);
    });

    it('shows the unavailable tooltip when both raw sizes are null', () => {
      const caps = deriveCapabilities(ViewFileStatus.DOWNLOADED, 0, 0, null, null);
      expect(caps.validateTooltip).toBe(VALIDATE_UNAVAILABLE_TOOLTIP);
    });

    it('does not show a tooltip when only the raw local_size is null (remote present)', () => {
      const caps = deriveCapabilities(ViewFileStatus.DOWNLOADED, 0, 100, null, 100);
      expect(caps.isValidatable).toBe(false);
      expect(caps.validateTooltip).toBeNull();
    });

    it('does not show a tooltip when the file is validatable', () => {
      const caps = deriveCapabilities(ViewFileStatus.DOWNLOADED, 100, 100, 100, 100);
      expect(caps.isValidatable).toBe(true);
      expect(caps.validateTooltip).toBeNull();
    });

    it('does not show a tooltip for a non-validatable status with null remote', () => {
      const caps = deriveCapabilities(ViewFileStatus.QUEUED, 100, 0, 100, null);
      expect(caps.validateTooltip).toBeNull();
    });
  });

  describe('allow-list constants are the single source of truth', () => {
    it('shares the verbatim LOCAL_ACTION_STATUSES list for extraction and local deletion', () => {
      // isExtractable and isLocallyDeletable both gate on this list; assert the
      // exact membership so a divergence would fail here rather than silently.
      expect([...LOCAL_ACTION_STATUSES]).toEqual([
        ViewFileStatus.DEFAULT,
        ViewFileStatus.STOPPED,
        ViewFileStatus.DOWNLOADED,
        ViewFileStatus.EXTRACTED,
        ViewFileStatus.EXTRACT_FAILED,
        ViewFileStatus.VALIDATED,
        ViewFileStatus.CORRUPT,
      ]);
    });

    it('REMOTELY_DELETABLE_STATUSES is LOCAL_ACTION_STATUSES plus DELETED', () => {
      expect([...REMOTELY_DELETABLE_STATUSES]).toEqual([...LOCAL_ACTION_STATUSES, ViewFileStatus.DELETED]);
    });
  });
});
