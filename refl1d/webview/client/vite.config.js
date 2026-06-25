import { resolve } from "path";
import { defineConfig } from "vite";
import svgLoader from "vite-svg-loader";
import vue from "@vitejs/plugin-vue";

function overrideBumpsFileBrowser() {
  const localFileBrowser = resolve(__dirname, "src/components/FileBrowser.vue");
  return {
    name: "override-bumps-filebrowser",
    resolveId(source, importer) {
      if (source.endsWith("FileBrowser.vue") && importer?.includes("bumps-webview-client")) {
        return localFileBrowser;
      }
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), svgLoader(), overrideBumpsFileBrowser()],
  base: "",
  define: {
    // Plotly and its WebGL/regl dependencies reference the NodeJS `global`,
    // which doesn't exist in the browser. Map it to the real browser global
    // object (`window`).
    //
    // NOTE: this MUST be `"window"`, not `{}`. Vite's `define` does a literal
    // text substitution, so `global: {}` replaces every `global` with a *fresh*
    // empty object. Libraries that persist state on `global` then write to one
    // throwaway object and read back from another. In particular
    // `typedarray-pool` (pulled in by the WebGL reflectivity plot) does
    // `global.__TYPEDARRAY_POOL = {...}` then `var POOL = global.__TYPEDARRAY_POOL`
    // -> POOL is undefined -> `POOL.UINT8C` throws at startup:
    // "Cannot read properties of undefined (reading 'UINT8C')", which blanked
    // the whole app (white tab). A single shared `window` fixes it.
    global: "window",
  },
  optimizeDeps: {
    include: ["plotly.js/lib/core", "plotly.js/lib/heatmap", "plotly.js/lib/bar", "json-difference"],
  },
});
