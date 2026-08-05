import type { TreeNode } from "primereact/treenode";

function nodeIdentity(node: TreeNode): string {
  const data = (node.data || {}) as Record<string, unknown>;
  const pn = String(data.pn || "").trim();
  const rev = String(data.rev || "").trim();
  if (pn) return `${pn}::${rev}`;
  return String(node.key || "unknown");
}

/**
 * PrimeReact tree keys identify occurrences, not parts. The same PN/revision
 * can legitimately appear below multiple branches, so a part identity alone
 * is not a safe key for expansion or immutable tree updates.
 */
export function withBomOccurrenceKeys(nodes: TreeNode[], parentPath = "bom"): TreeNode[] {
  return (nodes || []).map((node, index) => {
    const sourceKey = String(node.key || nodeIdentity(node));
    const segment = `${index + 1}:${encodeURIComponent(nodeIdentity(node))}`;
    const occurrenceKey = `${parentPath}/${segment}`;
    const children = Array.isArray(node.children)
      ? withBomOccurrenceKeys(node.children as TreeNode[], occurrenceKey)
      : node.children;
    return {
      ...node,
      key: occurrenceKey,
      data: { ...(node.data || {}), _bom_part_key: sourceKey },
      children,
    };
  });
}

/** Replace one node's children, leaving the rest of the tree untouched. */
export function setNodeChildren(tree: TreeNode[], key: string, children: TreeNode[]): TreeNode[] {
  return (tree || []).map((node) => {
    if (String(node.key) === String(key)) return { ...node, children };
    if (node.children?.length) {
      return { ...node, children: setNodeChildren(node.children as TreeNode[], key, children) };
    }
    return node;
  });
}

/** Depth-first lookup by occurrence key. */
export function findNode(tree: TreeNode[], key: string): TreeNode | undefined {
  for (const node of tree || []) {
    if (String(node.key) === String(key)) return node;
    const hit = node.children?.length ? findNode(node.children as TreeNode[], key) : undefined;
    if (hit) return hit;
  }
  return undefined;
}
