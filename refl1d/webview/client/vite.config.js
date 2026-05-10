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
    // By default, Vite doesn't include shims for NodeJS.
    // Plotly fails to load without this shim.
    global: {},
  },
  optimizeDeps: {
    include: ["plotly.js/lib/core", "plotly.js/lib/heatmap", "plotly.js/lib/bar", "json-difference"],
  },
});
