import { describe, expect, it } from 'vitest'
import { processTokens } from './processTokens'

/**
 * QA-FE-01. Process lists come from CAD custom properties, so one part carries
 * "Milling, Turning", another "milling / turning", another an array. They must
 * normalise to the same tokens or process filtering silently misses parts -
 * a wrong answer that looks like a correct empty result.
 */

describe('processTokens', () => {
  it.each([',', ';', '/', '|', '&', '+', '\n', '\r'])(
    'splits on the %s separator',
    (separator) => {
      expect(processTokens(`Milling${separator}Turning`)).toEqual(['milling', 'turning'])
    },
  )

  it('lowercases and trims so spellings compare equal', () => {
    expect(processTokens('  Milling ,  TURNING ')).toEqual(['milling', 'turning'])
  })

  it('flattens arrays, including nested ones', () => {
    expect(processTokens(['Milling', ['Turning, Drilling']])).toEqual([
      'milling',
      'turning',
      'drilling',
    ])
  })

  it.each([null, undefined, '', '   ', ',,,'])('returns nothing for %s', (value) => {
    expect(processTokens(value)).toEqual([])
  })

  it('keeps a single unsplit value', () => {
    expect(processTokens('5-Axis Milling')).toEqual(['5-axis milling'])
  })

  it('coerces non-strings rather than throwing', () => {
    expect(processTokens(42)).toEqual(['42'])
  })
})
