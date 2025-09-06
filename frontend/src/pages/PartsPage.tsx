/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useEffect, useState } from "react";
import { TreeTable } from "primereact/treetable";
import { Column } from "primereact/column";
import type { TreeNode } from "primereact/treenode";
import { FilterMatchMode } from "primereact/api";
import { Link } from "react-router-dom";
import "./partdetail.css";

// ---------- Types ----------
type TTFilters = Record<string, { value: any; matchMode: string }>;

// ---------- Helpers ----------
const makeInitFilters = (): TTFilters => ({
  pn: { value: null, matchMode: FilterMatchMode.CUSTOM },
  desc: { value: null, matchMode: FilterMatchMode.CUSTOM },
  process: { value: null, matchMode: FilterMatchMode.CUSTOM },
  rev: { value: null, matchMode: FilterMatchMode.CUSTOM },
  material: { value: null, matchMode: FilterMatchMode.CUSTOM },
  finish: { value: null, matchMode: FilterMatchMode.CUSTOM },
});

function normalizeFilters(next: TTFilters): TTFilters {
  const out: TTFilters = { ...makeInitFilters() };
  for (const k of Object.keys(next || {})) {
    const v = next[k]?.value;
    if (v !== "" && v !== null && v !== undefined) out[k] = next[k];
  }
  return out;
}

// Multi-term (space-separated) CONTAINS-ALL, case-insensitive
const containsAllTerms = (value: any, filter: any) => {
  if (filter == null || filter === "") return true;
  const hay = String(value ?? "").toLowerCase();
  const terms = String(filter)
    .toLowerCase()
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!terms.length) return true;
  return terms.every((t) => hay.includes(t));
};

// ---------- Component ----------
export default function PartsPage() {
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [ttFilters, setTtFilters] = useState<TTFilters>(makeInitFilters());
  const [search, setSearch] = useState("");

  // Load all part roots once
  useEffect(() => {
    let canceled = false;
    (async () => {
      try {
        setLoading(true);
        const r = await fetch("/api/parts_lazy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ first: 0, rows: 1000 }),
        });
        const j = await r.json();
        const pns: string[] = (j.data || []).map((p: any) => p.part_number);
        const roots: TreeNode[] = [];
        for (const pn of pns) {
          const rr = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}`);
          const arr = await rr.json();
          if (Array.isArray(arr) && arr.length) roots.push(arr[0]);
        }
        if (!canceled) setNodes(roots);
      } finally {
        if (!canceled) setLoading(false);
      }
    })();
    return () => {
      canceled = true;
    };
  }, []);

  function onTTFilter(e: any) {
    setTtFilters(normalizeFilters(e.filters || {}));
  }

  const onExpandNode = async (e: any) => {
    const node = e.node;
    if (node && (!node.children || node.children.length === 0)) {
      const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(node.key)}`);
      const kids = await r.json();
      node.children = kids;
      setNodes([...nodes]);
    }
  };

  const pnBody = (n: any) => {
    const pn = n?.data?.pn || "";
    return (
      <Link className="tt-pnlink" to={`/ui/part/${encodeURIComponent(pn)}`}>
        {pn}
      </Link>
    );
  };

  const linksBody = (n: any) => {
    const pn = n?.data?.pn || "";
    return (
      <a href={`/ui/part/${encodeURIComponent(pn)}`} target="_blank" rel="noreferrer">
        View
      </a>
    );
  };

  const onSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setSearch(v);
    setTtFilters((f) =>
      normalizeFilters({
        ...f,
        pn: { value: v, matchMode: FilterMatchMode.CUSTOM },
        desc: { value: v, matchMode: FilterMatchMode.CUSTOM },
      })
    );
  };

  return (
    <div className="p-3">
      <div className="p-inputgroup mb-3">
        <span className="p-inputgroup-addon">Search</span>
        <input
          type="text"
          className="p-inputtext p-component"
          placeholder="Partnumber or description"
          value={search}
          onChange={onSearchChange}
        />
      </div>
      <TreeTable
        value={nodes}
        loading={loading}
        expandedKeys={expanded}
        onToggle={(e) => setExpanded(e.value)}
        onExpand={onExpandNode}
        filters={ttFilters}
        onFilter={onTTFilter}
        filterDisplay="row"
        showGridlines
        scrollable
        scrollHeight="70vh"
      >
        <Column
          field="pn"
          header="Partnumber"
          body={pnBody}
          sortable
          filter
          filterMatchMode="custom"
          filterFunction={(value, flt) => containsAllTerms(value, flt)}
          showFilterMenu={false}
          filterPlaceholder="Filter PN"
        />
        <Column
          field="desc"
          header="Description"
          sortable
          filter
          filterMatchMode="custom"
          filterFunction={(value, flt) => containsAllTerms(value, flt)}
          showFilterMenu={false}
          filterPlaceholder="Filter description"
        />
        <Column
          field="process"
          header="Processes"
          sortable
          filter
          filterMatchMode="custom"
          filterFunction={(value, flt) => containsAllTerms(value, flt)}
          showFilterMenu={false}
          filterPlaceholder="Filter process"
        />
        <Column
          field="rev"
          header="Revision"
          sortable
          filter
          filterMatchMode="custom"
          filterFunction={(value, flt) => containsAllTerms(value, flt)}
          showFilterMenu={false}
          filterPlaceholder="Rev"
          style={{ width: 120 }}
        />
        <Column
          field="material"
          header="Material"
          sortable
          filter
          filterMatchMode="custom"
          filterFunction={(value, flt) => containsAllTerms(value, flt)}
          showFilterMenu={false}
          filterPlaceholder="Filter material"
        />
        <Column
          field="finish"
          header="Finish"
          sortable
          filter
          filterMatchMode="custom"
          filterFunction={(value, flt) => containsAllTerms(value, flt)}
          showFilterMenu={false}
          filterPlaceholder="Filter finish"
        />
        <Column header="Links" body={linksBody} style={{ width: 120 }} />
      </TreeTable>
    </div>
  );
}
