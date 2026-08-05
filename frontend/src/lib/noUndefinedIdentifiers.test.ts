import { execFileSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'

/**
 * QA-FE-01 regression guard.
 *
 * `vite build` transpiles without type-checking, so a call to a function that
 * is used but never imported compiles cleanly and only fails in the browser
 * with "X is not defined". That is exactly what shipped on 2026-08-06 after
 * helpers were extracted out of PartDetailPage and its imports were lost:
 * groupFiles, formatBytes, hasDisplayValue, processTokens and six more were
 * all referenced with no import, and the page crashed on load.
 *
 * `tsc --noEmit` catches it. This runs the compiler and fails on the two error
 * codes that mean "this identifier does not exist" - deliberately NOT on the
 * whole type-check, which still has a pre-existing backlog (missing CSS module
 * declarations, PrimeReact generics) that would make the gate useless.
 */

const UNDEFINED_IDENTIFIER_CODES = /error TS(2304|2552):/

describe('no undefined identifiers', () => {
  it('type-checks without any missing-name errors', () => {
    let output = ''
    try {
      execFileSync('npx', ['tsc', '--noEmit', '-p', 'tsconfig.app.json'], {
        encoding: 'utf8',
        shell: process.platform === 'win32',
      })
    } catch (err) {
      output = String((err as { stdout?: string }).stdout ?? '')
    }

    const broken = output
      .split('\n')
      .filter((line) => UNDEFINED_IDENTIFIER_CODES.test(line))

    expect(broken, `Unimported or misspelled identifiers:\n${broken.join('\n')}`).toEqual([])
  }, 120_000)
})
