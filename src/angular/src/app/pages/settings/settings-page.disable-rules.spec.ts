import '@angular/compiler';
import { describe, it, expect } from 'vitest';
import { SettingsPageComponent } from './settings-page.component';
import { IOptionsContext } from './options-list';

// buildValidateContext is a private static reached the same way the existing
// settings-page spec reaches buildServerContext/buildAutoqueueContext. This
// focused spec covers the validate ('validateDisabled') branch of the generic
// applyDisableRules transform, which the existing spec does not exercise.
interface ValidateStatics {
  buildValidateContext(validateEnabled: boolean): IOptionsContext;
}
const statics = SettingsPageComponent as unknown as ValidateStatics;
const buildValidateContext = (enabled: boolean): IOptionsContext => statics.buildValidateContext(enabled);

describe('SettingsPageComponent.buildValidateContext', () => {
  it('disables auto_validate and algorithm when validation is disabled', () => {
    const ctx = buildValidateContext(false);
    const autoValidate = ctx.options.find((o) => o.valuePath[1] === 'auto_validate')!;
    const algorithm = ctx.options.find((o) => o.valuePath[1] === 'algorithm')!;

    expect(autoValidate.disabled).toBe(true);
    expect(algorithm.disabled).toBe(true);
  });

  it('keeps the original description on disabled validate options (no override note)', () => {
    const ctx = buildValidateContext(false);
    const autoValidate = ctx.options.find((o) => o.valuePath[1] === 'auto_validate')!;

    // validateDisabled options carry no overrideNote, so the description is unchanged.
    expect(autoValidate.description).toBe(
      'Automatically validate files when download completes. Requires post-download validation above.',
    );
  });

  it('does not disable auto_validate and algorithm when validation is enabled', () => {
    const ctx = buildValidateContext(true);
    const autoValidate = ctx.options.find((o) => o.valuePath[1] === 'auto_validate')!;
    const algorithm = ctx.options.find((o) => o.valuePath[1] === 'algorithm')!;

    expect(autoValidate.disabled).toBeFalsy();
    expect(algorithm.disabled).toBeFalsy();
  });

  it('never disables the other validate options', () => {
    const ctx = buildValidateContext(false);
    const others = ctx.options.filter(
      (o) => o.valuePath[1] !== 'auto_validate' && o.valuePath[1] !== 'algorithm',
    );

    for (const option of others) {
      expect(option.disabled).toBeFalsy();
    }
  });
});
