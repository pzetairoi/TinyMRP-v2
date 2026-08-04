import { describe, expect, it } from 'vitest'
import type { TreeNode } from 'primereact/treenode'
import { withBomOccurrenceKeys } from './bomTree'

/**
 * QA-FE-01. The invariant here is easy to break and hard to notice: a BOM key
 * identifies an OCCURRENCE, not a part. The same PN/revision legitimately
 * appears under several parents, so keying by part identity would make two
 * distinct rows share a key - collapsing one when the other expands, and
 * corrupting immutable tree updates.
 */

function node(pn: string, rev = 'A', children?: TreeNode[]): TreeNode {
  return { data: { pn, rev }, children } as TreeNode
}

function collectKeys(nodes: TreeNode[]): string[] {
  return nodes.flatMap((n) => [
    String(n.key),
    ...(Array.isArray(n.children) ? collectKeys(n.children as TreeNode[]) : []),
  ])
}

describe('withBomOccurrenceKeys', () => {
  it('gives every node a key rooted at the default path', () => {
    expect(String(withBomOccurrenceKeys([node('PN-1')])[0].key)).toMatch(/^bom\/1:/)
  })

  it('keeps repeated parts distinct, under different parents and the same one', () => {
    // The defect this guards: a shared bolt appearing under two assemblies,
    // and twice under one, must not collapse onto a single key.
    const tree = [
      node('ASSY-1', 'A', [node('BOLT-1'), node('BOLT-1')]),
      node('ASSY-2', 'A', [node('BOLT-1')]),
    ]
    const keys = collectKeys(withBomOccurrenceKeys(tree))
    expect(keys).toHaveLength(5)
    expect(new Set(keys).size).toBe(5)
  })

  it('keeps the original part identity available as _bom_part_key', () => {
    // Occurrence keys are for the tree widget; callers still need to know
    // which PART a row is, e.g. to fetch its detail.
    const result = withBomOccurrenceKeys([node('PN-1', 'B')])
    expect((result[0].data as Record<string, unknown>)._bom_part_key).toBe('PN-1::B')
  })

  it('nests child keys under their parent key', () => {
    const result = withBomOccurrenceKeys([node('ASSY-1', 'A', [node('BOLT-1')])])
    const parentKey = String(result[0].key)
    const childKey = String((result[0].children as TreeNode[])[0].key)
    expect(childKey.startsWith(`${parentKey}/`)).toBe(true)
  })

  it('does not mutate the input nodes', () => {
    // The tree is React state; mutating it in place would skip re-renders.
    const original = node('PN-1')
    const before = JSON.stringify(original)
    withBomOccurrenceKeys([original])
    expect(JSON.stringify(original)).toBe(before)
  })

  it('preserves other node properties', () => {
    const input = { data: { pn: 'PN-1', rev: 'A', qty: 4 }, selectable: false } as TreeNode
    const [out] = withBomOccurrenceKeys([input])
    expect((out.data as Record<string, unknown>).qty).toBe(4)
    expect(out.selectable).toBe(false)
  })

  it('encodes identities so separators in a part number cannot forge a key', () => {
    // A PN containing "/" must not be able to look like a nested path.
    const result = withBomOccurrenceKeys([node('PN/WITH/SLASH')])
    const key = String(result[0].key)
    expect(key.split('/').length).toBe(2)
  })

  it('falls back to the node key when there is no part number', () => {
    const orphan = { key: 'legacy-7', data: {} } as TreeNode
    const [out] = withBomOccurrenceKeys([orphan])
    expect((out.data as Record<string, unknown>)._bom_part_key).toBe('legacy-7')
  })

  it('handles empty and missing input without throwing', () => {
    expect(withBomOccurrenceKeys([])).toEqual([])
    expect(withBomOccurrenceKeys(undefined as unknown as TreeNode[])).toEqual([])
  })

  it('handles deep nesting', () => {
    const deep = [node('L1', 'A', [node('L2', 'A', [node('L3', 'A', [node('L4')])])])]
    const keys = collectKeys(withBomOccurrenceKeys(deep))
    expect(keys).toHaveLength(4)
    expect(new Set(keys).size).toBe(4)
  })
})
