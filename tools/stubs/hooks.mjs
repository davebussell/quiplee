// Module hook for local runs of the Netlify Functions: `import { register } from "node:module";
// register("./stubs/hooks.mjs", import.meta.url)` before importing a function, and @netlify/blobs resolves to the
// in-memory store in netlify-blobs.mjs (whether or not node_modules has the real package).
export async function resolve(specifier, context, next) {
  if (specifier === "@netlify/blobs") return { url: new URL("./netlify-blobs.mjs", import.meta.url).href, shortCircuit: true };
  return next(specifier, context);
}
