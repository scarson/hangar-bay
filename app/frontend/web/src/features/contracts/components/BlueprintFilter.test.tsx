// ABOUTME: Every blueprint bound control maps to its own search key, driven through the UI.
// ABOUTME: Five of the six were never exercised, so a swapped key in FAMILIES shipped green.
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { BlueprintFilter } from './BlueprintFilter'
import { parseContractSearch } from '../filters'

/**
 * The six controls and the key each one owns, written as LITERALS rather than read
 * back out of the FAMILIES table the component maps over. Deriving the expectation
 * from the same table the implementation uses would agree with any table, including
 * one whose `min` and `max` are transposed — which is precisely the regression the
 * register flagged: only one of the six pairs was ever exercised, so a swapped key
 * shipped green.
 */
const CONTROLS = [
  { label: 'Minimum runs', key: 'min_runs' },
  { label: 'Maximum runs', key: 'max_runs' },
  { label: 'Minimum material efficiency', key: 'min_me' },
  { label: 'Maximum material efficiency', key: 'max_me' },
  { label: 'Minimum time efficiency', key: 'min_te' },
  { label: 'Maximum time efficiency', key: 'max_te' },
] as const

function renderFilter() {
  const onUpdate = vi.fn()
  render(<BlueprintFilter search={parseContractSearch({})} onUpdate={onUpdate} />)
  return onUpdate
}

describe('BlueprintFilter', () => {
  it('offers exactly the six bounds, no more and no fewer', () => {
    // Guards the table below against silent shrinkage, and catches a family added to
    // the component without a case here.
    renderFilter()
    const spinners = screen.getAllByRole('spinbutton')
    expect(spinners).toHaveLength(CONTROLS.length)
  })

  it.each(CONTROLS)('$label updates $key and nothing else', ({ label, key }) => {
    const onUpdate = renderFilter()

    fireEvent.change(screen.getByLabelText(label), { target: { value: '7' } })

    expect(onUpdate).toHaveBeenCalledTimes(1)
    const [patch, options] = onUpdate.mock.calls[0]
    // The whole patch, not just the key of interest: asserting `patch[key] === 7`
    // alone would still pass if the control also wrote a second, wrong key.
    expect(patch).toEqual({ [key]: 7 })
    // Typed bounds fire per keystroke, so they must replace rather than push — one
    // history entry per character is a back button that cannot escape the field.
    expect(options).toEqual({ replace: true })
  })

  it.each(CONTROLS)('$label clears to undefined rather than to zero', ({ label, key }) => {
    // An emptied box is the ABSENCE of a bound. Coercing it to 0 would turn "no
    // filter" into `min_me=0`, which matches every blueprint that has any ME at all
    // — a filter, silently applied, that the reader did not ask for.
    // Rendered from a search with no bounds set, so the box starts empty and setting
    // it to '' again fires no change at all. It has to be populated first — which is
    // also the real sequence: a reader types a bound, then clears it.
    const onUpdate = vi.fn()
    const { rerender } = render(
      <BlueprintFilter search={parseContractSearch({})} onUpdate={onUpdate} />,
    )
    rerender(
      <BlueprintFilter search={parseContractSearch({ [key]: 7 })} onUpdate={onUpdate} />,
    )
    expect(screen.getByLabelText(label)).toHaveValue(7)

    fireEvent.change(screen.getByLabelText(label), { target: { value: '' } })

    expect(onUpdate).toHaveBeenCalledTimes(1)
    expect(onUpdate.mock.calls[0][0]).toEqual({ [key]: undefined })
  })
})
