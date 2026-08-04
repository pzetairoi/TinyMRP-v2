import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ThumbImg from './ThumbImg'

/**
 * QA-FE-01, first component test. Thumbnails come from storage scans, so a
 * missing or moved file is routine rather than exceptional. The cascade must
 * try each candidate and then settle on the branding logo; a bug here shows up
 * as a broken-image icon on every parts table.
 */

// Queried by tag, not by role: alt defaults to "", which makes the image
// role="presentation" and invisible to getByRole('img'). That is correct for a
// decorative thumbnail, and the alt-text case below covers the labelled one.
const img = () => document.querySelector('img') as HTMLImageElement

describe('ThumbImg', () => {
  it('falls back to the branding logo when no URLs are supplied', () => {
    render(<ThumbImg />)
    expect(img().getAttribute('src')).toBe('/branding/logo')
  })

  it('renders the first URL', () => {
    render(<ThumbImg urls={['/a.png', '/b.png']} />)
    expect(img().getAttribute('src')).toBe('/a.png')
  })

  it('advances through candidates as each one fails, then stops on the logo', () => {
    render(<ThumbImg urls={['/a.png', '/b.png']} />)
    fireEvent.error(img())
    expect(img().getAttribute('src')).toBe('/b.png')

    fireEvent.error(img())
    expect(img().getAttribute('src')).toBe('/branding/logo')

    // The logo failing too must not loop or blank the element.
    fireEvent.error(img())
    expect(img().getAttribute('src')).toBe('/branding/logo')
  })

  it('applies the requested dimensions', () => {
    render(<ThumbImg urls={['/a.png']} maxH={80} maxW={120} />)
    expect(img().style.maxHeight).toBe('80px')
    expect(img().style.maxWidth).toBe('120px')
  })

  it('exposes alt text for screen readers', () => {
    // Accessibility: a thumbnail with no accessible name is invisible to AT.
    render(<ThumbImg urls={['/a.png']} alt="Bracket PN-1" />)
    expect(screen.getByAltText('Bracket PN-1')).toBeInTheDocument()
  })
})
