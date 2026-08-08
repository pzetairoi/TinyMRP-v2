/// <reference types="vite/client" />

// This file used to contain a stale copy of vite.config.ts - an older,
// slightly different one, sitting where the ambient type declarations belong.
// Because of that, TypeScript had no declaration for `import './App.css'` or
// any other asset import, and every CSS import in the app reported
// "Cannot find module". Nothing caught it: Vite's build strips types without
// checking them, and the typecheck was never wired into CI.
//
// The reference above is what the file is for. It brings in Vite's ambient
// declarations for CSS, images and the rest of the asset imports.
