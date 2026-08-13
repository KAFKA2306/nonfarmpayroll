import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.mjs";
const ready = loadPyodide();
self.onmessage = async ({data}) => {
  try {
    const pyodide = await ready;
    const [m, d, p] = await Promise.all([
      fetch("../api/v1/manifest.json").then(r => r.arrayBuffer()),
      fetch("../api/v1/total-nonfarm.json").then(r => r.arrayBuffer()),
      fetch("./level_explorer.py").then(r => r.text()),
    ]);
    pyodide.runPython(p);
    pyodide.globals.set("manifest_bytes", new Uint8Array(m));
    pyodide.globals.set("data_bytes", new Uint8Array(d));
    pyodide.globals.set("start_value", data.start);
    pyodide.globals.set("end_value", data.end);
    pyodide.globals.set("mode_value", data.mode);
    const result = pyodide.runPython("explore(bytes(manifest_bytes), bytes(data_bytes), start_value, end_value, mode_value)");
    self.postMessage({ok:true, result: JSON.parse(result)});
  } catch (error) {
    self.postMessage({ok:false, error:String(error?.message || error)});
  }
};
