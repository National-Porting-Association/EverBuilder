#!/usr/bin/env python3
"""
Build an offline HTML file by embedding resources listed in files.txt.
"""

import os
import re
import json
import base64
# optional brotli support (best-effort)
try:
    import brotli
except Exception:
    brotli = None
import mimetypes
from pathlib import Path
import sys
import tempfile
import threading
import time
import webbrowser
import queue
import shutil
import subprocess

# ---------- Config ----------
FILES_LIST = "files.txt"
OUTPUT_FILE = "offline.html"
VARIABLES = {
}
# Runtime flags (controlled by the server when running builds)
GLOBAL_VERBOSE = False
GLOBAL_EMIT_PROGRESS = False
# Binary extensions that are needed for WASM
BINARY_EXTS = {'.wasm', '.data', '.mem', '.symbols', '.bundle'}
# --------------------------------

def read_files_list(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]

def file_bytes_map(files):
    """Read all files into a map path -> bytes.

    `files` is expected to be an iterable of path strings (relative or
    absolute). This function reads each file in binary mode and returns a
    dictionary mapping the forward-slash normalized path -> bytes.
    """
    m = {}
    for p in files:
        try:
            # read file relative to current working directory
            with open(p, 'rb') as fh:
                bs = fh.read()
            # normalize key to always use forward slashes
            key = str(p).replace('\\', '/')
            m[key] = bs
        except Exception as e:
            print(f"[WARN] Could not read file '{p}': {e}")
    return m

def try_decode_utf8(bs, path):
    try:
        return bs.decode("utf-8")
    except UnicodeDecodeError:
        return None

def to_b64(bs):
    return base64.b64encode(bs).decode("ascii")

def replace_variables_in_text(text, variables):
    for k, v in variables.items():
        text = text.replace(f"{{{{ {k} }}}}", v)
    return text

def make_data_uri(path, bs, mime=None):
    mt = mime or mimetypes.guess_type(path)[0] or "application/octet-stream"
    return f"data:{mt};base64,{to_b64(bs)}"

def inject_fetch_patch_into_head(html_text, embedded_files_map, loader_html=None):
    """Insert fetch/WASM monkeypatch into the <head> element of html_text."""
    embedded_json = json.dumps(embedded_files_map)

    # the injected fetch patch understands two kinds of embedded values:
    #  - legacy: a base64 string containing the file bytes
    #  - compressed: an object { b64: <base64>, encoding: 'br', mime: '...'}
    # The client will try to decompress using DecompressionStream when available,
    # otherwise it will return a Response with Content-Encoding set (best-effort).
    fetch_patch = f"""
<script>
/* EMBEDDED FILES MAP */
const EMBEDDED_FILES = {embedded_json};

/* Helpers */
function base64ToResponse(b64, mime) {{
    const raw = atob(b64);
    const u8 = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) u8[i] = raw.charCodeAt(i);
    const blob = new Blob([u8.buffer], {{ type: mime || 'application/octet-stream' }});
    return new Response(blob);
}}

function entryToResponse(entry) {{
    // entry can be a string (base64) or an object with b64/encoding/mime
    try {{
        if (!entry) return null;
        if (typeof entry === 'string') return base64ToResponse(entry);
        if (entry.b64) {{
            const raw = atob(entry.b64);
            const u8 = new Uint8Array(raw.length);
            for (let i = 0; i < raw.length; i++) u8[i] = raw.charCodeAt(i);
            const mime = entry.mime || 'application/octet-stream';
            const blob = new Blob([u8.buffer], {{ type: mime }});
            if (entry.encoding && typeof DecompressionStream === 'function') {{
                try {{
                    const ds = new DecompressionStream(entry.encoding);
                    const stream = blob.stream().pipeThrough(ds);
                    return new Response(stream, {{ headers: {{ 'Content-Type': mime }} }});
                }} catch(e) {{
                    // DecompressionStream may not support the encoding or fail; fall through
                }}
            }}
            // fallback: return compressed blob and set encoding header (may not auto-decompress)
            const headers = {{ 'Content-Type': mime }};
            if (entry.encoding) headers['Content-Encoding'] = entry.encoding;
            return new Response(blob, {{ headers: headers }});
        }}
    }} catch (e) {{
        console.warn('entryToResponse error', e);
    }}
    return null;
}}

/* Normalize a URL-ish string: strip query/hash, convert backslashes, return lower-case for matching convenience */
function normalizeUrlForMatch(url) {{
    if (!url) return url;
    // If resource is a Request or Response or URL object, try to extract its URL
    try {{
        if (typeof url === 'object' && url.url) url = url.url;
    }} catch(e){{}}
    // strip query and fragment
    let s = String(url).split('?')[0].split('#')[0];
    s = s.replace(/\\\\/g, '/'); // backslashes -> forward slashes
    return s;
}}

/* Return basename of a path */
function basename(p) {{
    if (!p) return p;
    p = p.replace(/\\\\/g, '/');
    const parts = p.split('/');
    return parts[parts.length - 1];
}}

/* Monkeypatch fetch to intercept requests whose normalized URL matches an embedded key.
   Matching rules (in order):
     1) exact match of normalized URL === key
     2) normalized URL endsWith key
     3) normalized URL endsWith '/' + key
     4) basename(normalized URL) === basename(key)
*/
(function() {{
    const origFetch = window.fetch.bind(window);
    window.fetch = function(resource, init) {{
        try {{
            let rawUrl = (typeof resource === 'string') ? resource : (resource && resource.url) || '';
            const urlNorm = normalizeUrlForMatch(rawUrl);
            if (urlNorm) {{
                // try to match embedded keys
                for (const key in EMBEDDED_FILES) {{
                    if (!Object.prototype.hasOwnProperty.call(EMBEDDED_FILES, key)) continue;
                    const keyNorm = normalizeUrlForMatch(key);
                    if (!keyNorm) continue;
                    // direct and endsWith matches
                    if (urlNorm === keyNorm || urlNorm.endsWith(keyNorm) || urlNorm.endsWith('/' + keyNorm) || basename(urlNorm) === basename(keyNorm)) {{
                        // determine mime heuristically
                        let mime = 'application/octet-stream';
                        if (keyNorm.endsWith('.wasm')) mime = 'application/wasm';
                        else if (keyNorm.endsWith('.js')) mime = 'application/javascript';
                        else if (keyNorm.endsWith('.css')) mime = 'text/css';
                        else if (keyNorm.endsWith('.json')) mime = 'application/json';
                        console.debug('[EMBEDDED FILE SERVED]', rawUrl, '->', key);
                        const resp = entryToResponse(EMBEDDED_FILES[key]);
                        if (resp) return Promise.resolve(resp);
                    }}
                }}
            }}
        }} catch (e) {{
            console.warn('fetch patch error', e);
        }}
        return origFetch(resource, init);
    }};
}})();

/* Patch WebAssembly.instantiateStreaming to convert Response -> arrayBuffer and instantiate.
   This helps when we return a Blob/Response for a .wasm file.
*/
(function() {{
    if (typeof WebAssembly !== 'undefined') {{
        const orig = WebAssembly.instantiateStreaming;
        WebAssembly.instantiateStreaming = async function(resp, importObj) {{
            try {{
                if (resp && typeof resp.arrayBuffer === 'function') {{
                    const buf = await resp.arrayBuffer();
                    return await WebAssembly.instantiate(buf, importObj);
                }}
                if (orig) return orig(resp, importObj);
            }} catch (e) {{
                const r = await Promise.resolve(resp);
                const buf = await r.arrayBuffer();
                return await WebAssembly.instantiate(buf, importObj);
            }}
        }};
    }}
}})();
</script>
"""
    # If a loader HTML fragment was provided, try to extract its <head> and <body>
    loader_head = None
    loader_body = None
    if loader_html:
        try:
            lh = re.search(r'<head[^>]*>(.*?)</head>', loader_html, flags=re.IGNORECASE | re.DOTALL)
            if lh:
                loader_head = lh.group(1)
        except Exception:
            loader_head = None
        try:
            lb = re.search(r'<body[^>]*>(.*?)</body>', loader_html, flags=re.IGNORECASE | re.DOTALL)
            if lb:
                loader_body = lb.group(1)
        except Exception:
            loader_body = None

    # Simplified, robust strategy when loader is present:
    # Prepend a small prefix containing loader_head (if any), then the fetch_patch,
    # then loader_body (wrapped) so the loader DOM and its styles/scripts are
    # available to the browser before the large EMBEDDED_FILES payload.
    new_html = html_text

    if loader_html:
        prefix_parts = []
        # Add a clear marker so verification can find injected loader
        prefix_parts.append('<!-- EVERBUILDER LOADER PREFIX START -->')


        if loader_head:
            # loader_head may contain <style> and <script> fragments
            prefix_parts.append(loader_head)
        else:
            # If no loader_head but full loader_html present, try to extract any head-like content
            lh_try = re.search(r'<head[^>]*>(.*?)</head>', loader_html, flags=re.IGNORECASE | re.DOTALL)
            if lh_try:
                prefix_parts.append(lh_try.group(1))

        # Add loader body wrapped in a container so it is at the very top of the document
        if loader_body:
            prefix_parts.append('<!-- EVERBUILDER LOADER BODY START -->')
            prefix_parts.append(f"<div id=\"everbuilder-loader-wrapper\">{loader_body}</div>")
            prefix_parts.append('<!-- EVERBUILDER LOADER BODY END -->')
        else:
            # if loader_body missing, append the raw loader_html as fallback
            prefix_parts.append('<!-- EVERBUILDER LOADER RAW START -->')
            prefix_parts.append(loader_html)
            prefix_parts.append('<!-- EVERBUILDER LOADER RAW END -->')

        # Insert the fetch patch after the loader body so EMBEDDED_FILES appears after the loader
        prefix_parts.append(fetch_patch)

        prefix_parts.append('<!-- EVERBUILDER LOADER PREFIX END -->')

        prefix = '\n'.join(prefix_parts)

        # Prepend the prefix to the document to guarantee it appears before the embedded JSON
        new_html = prefix + '\n' + new_html
        return new_html

    # No loader requested: behave as before (insert fetch_patch into head or top)
    m = re.search(r'(<head[^>]*>)', new_html, flags=re.IGNORECASE)
    if m:
        insert_at = m.end()
        new_html = new_html[:insert_at] + fetch_patch + new_html[insert_at:]
    else:
        new_html = fetch_patch + new_html

    return new_html

def try_replace_script_srcs(html_text, files_map, variables):
    """Replace <script src="..."></script> occurrences with inline script or data: URL when possible."""
    s = html_text
    pattern = re.compile(r'<script\b([^>]*)\bsrc=(["\'])([^"\']+)\2([^>]*)>\s*</script>', flags=re.IGNORECASE)
    out = []
    last = 0
    for m in pattern.finditer(s):
        out.append(s[last:m.start()])
        attrs_before = m.group(1)
        quote = m.group(2)
        path = m.group(3)
        attrs_after = m.group(4)
        full_tag = m.group(0)
        replaced = full_tag
        if path in files_map:
            bs = files_map[path]
            decoded = try_decode_utf8(bs, path)
            if decoded is not None:
                decoded = replace_variables_in_text(decoded, variables)
                replaced = f"<script>\n{decoded}\n</script>"
            else:
                data = make_data_uri(path, bs, mime='application/javascript')
                replaced = f"<script src=\"{data}\"></script>"
        # else leave as-is
        out.append(replaced)
        last = m.end()
    out.append(s[last:])
    return ''.join(out)

def try_replace_links(html_text, files_map, variables, embed_css_direct=False):
    """Replace <link rel="stylesheet" href="..."> with inline <style> when the href file exists.

    If `embed_css_direct` is True, the function will embed the CSS directly and preserve the
    original link's `id` attribute if present. If no `id` is present, a safe id is generated
    from the href so consumers can target the style block.
    """
    s = html_text
    pattern = re.compile(r"<link\b([^>]*\brel=(['\"])stylesheet\2[^>]*)>", flags=re.IGNORECASE)
    out = []
    last = 0
    for m in pattern.finditer(s):
        out.append(s[last:m.start()])
        tag = m.group(0)
        attrs = m.group(1)
        href_m = re.search(r"href=(['\"])([^'\"]+)\1", attrs, flags=re.IGNORECASE)
        id_m = re.search(r"id=(['\"])([^'\"]+)\1", attrs, flags=re.IGNORECASE)
        if href_m:
            raw_path = href_m.group(2)
            # normalize requested path for matching
            path_norm = raw_path.replace('\\', '/').lstrip('./')
            # find best match in files_map: prefer exact normalized match, then endswith, then basename
            best_key = None
            best_score = 0
            target_basename = Path(path_norm).name
            for key in files_map.keys():
                key_norm = key.replace('\\', '/')
                score = 0
                if key_norm == path_norm:
                    score = 40
                elif key_norm.endswith('/' + path_norm) or key_norm.endswith(path_norm):
                    score = 30
                elif Path(key_norm).name == target_basename:
                    score = 10
                # prefer matches inside TemplateData or Build when ambiguous if both have same basename
                if score and ('TemplateData/' in key_norm or key_norm.startswith('TemplateData/')):
                    score += 5
                if score > best_score:
                    best_score = score
                    best_key = key

            if best_key and Path(best_key).suffix.lower() == '.css':
                bs = files_map[best_key]
                decoded = try_decode_utf8(bs, best_key)
                if decoded is None:
                    decoded = bs.decode('utf-8', errors='replace')
                    print(f"[WARN] CSS {best_key} had non-utf8; decoded with replacement")
                decoded = replace_variables_in_text(decoded, variables)
                if embed_css_direct:
                    # preserve id if present, else generate one from the path
                    style_id = None
                    if id_m:
                        style_id = id_m.group(2)
                    else:
                        # generate a safe id by sanitizing the path
                        style_id = re.sub(r'[^a-zA-Z0-9_-]', '_', path_norm)
                        # ensure it doesn't start with a digit
                        if re.match(r'^\d', style_id):
                            style_id = 'css_' + style_id
                    replacement = f'<style id="{style_id}">\n{decoded}\n</style>'
                else:
                    replacement = f"<style>\n{decoded}\n</style>"
            else:
                replacement = tag
        else:
            replacement = tag
        out.append(replacement)
        last = m.end()
    out.append(s[last:])
    return ''.join(out)

def try_replace_media_srcs(html_text, files_map):
    """Replace media srcs (img, source, video, audio) with data URIs when present."""
    s = html_text
    pattern = re.compile(r'(<(?:img|source|video|audio|image)\b[^>]*\bsrc=(["\'])([^"\']+)\2[^>]*>)', flags=re.IGNORECASE)
    out = []
    last = 0
    for m in pattern.finditer(s):
        out.append(s[last:m.start()])
        full_tag = m.group(1)
        path = m.group(3)
        replaced = full_tag
        if path in files_map:
            ext = Path(path).suffix.lower()
            bs = files_map[path]
            if ext in ['.png','.jpg','.jpeg','.gif','.ico','.webp','.svg']:
                data = make_data_uri(path, bs)
                replaced = re.sub(r'src=(["\'])[^"\']+\1', f'src="{data}"', full_tag)
        out.append(replaced)
        last = m.end()
    out.append(s[last:])
    return ''.join(out)

def rewrite_index_html(index_html_text, files_map, embedded_map, variables):
    """
    Rewrite index.html content:
    - inline/link/script/img references for files present in files_map when appropriate
    - fill embedded_map for all files (base64)
    """
    text = index_html_text
    text = replace_variables_in_text(text, variables)

    text = replace_dynamic_resource_assignments(text, files_map)


    text = try_replace_script_srcs(text, files_map, variables)

    # By default do not embed CSS directly; callers may choose to pass True
    text = try_replace_links(text, files_map, variables, embed_css_direct=variables.get('__embed_css_direct__', False) if isinstance(variables, dict) else False)

    text = try_replace_media_srcs(text, files_map)

    # NOTE: embedded_map population is performed by build() so it can
    # optionally apply compression. rewrite_index_html only rewrites the
    # index content (inlining scripts/links/media) but does not emit the
    # embedded base64 map itself.

    return text


def replace_dynamic_resource_assignments(html_text, files_map):
    """Replace occurrences of expressions like `buildUrl + "/<basename>"` with
    a data: URI built from the corresponding file in files_map.

    This handles dynamic loader/script creation in Unity's template where the
    loader URL and config.url entries are built at runtime from `buildUrl`.
    Converting them to data: URIs prevents the browser from attempting to
    resolve them relative to the offline HTML file location (e.g. total/Build/...).
    """
    text = html_text
    basename_map = {}
    for p in files_map.keys():
        b = Path(p).name
        if b not in basename_map:
            basename_map[b] = p
        else:
            cur = basename_map[b]
            if ('Build' in p.split(os.sep) or p.startswith('Build/')) and not ('Build' in cur.split(os.sep) or cur.startswith('Build/')):
                basename_map[b] = p

    def replace_match(m):
        match_text = m.group(0)
        basename = m.group('name')
        full = basename_map.get(basename)
        if not full:
            return match_text
        try:
            bs = files_map[full]
            data_uri = make_data_uri(full, bs)
            return '"' + data_uri + '"'
        except Exception:
            return match_text

    pattern = re.compile(r'buildUrl\s*\+\s*["\']/?(?P<name>[^"\'/]+)["\']')
    text = pattern.sub(replace_match, text)

    return text

def build(files_list, variables, outpath, inject_loader=True, selected_loader=None, embed_css_direct=False, compress=False):
    files_map = file_bytes_map(files_list)

    index_keys = [k for k in files_map.keys() if Path(k).name.lower() == 'index.html']
    if not index_keys:
        print("[ERROR] index.html not found in files.txt. Aborting.")
        return
    index_path = index_keys[0]
    index_bytes = files_map[index_path]
    decoded_index = try_decode_utf8(index_bytes, index_path)
    if decoded_index is None:
        decoded_index = index_bytes.decode('utf-8', errors='replace')
        print(f"[WARN] index.html not strict-utf8; decoded with replacement chars.")

    # Detect loader HTML (under loaders/.../index.html or src/loaders/...) and extract it
    loader_html = None
    loader_keys = [k for k in files_map.keys() if re.match(r'(^|/|\\)loaders/[^/\\]+/index\.html$', k, flags=re.IGNORECASE) or re.match(r'(^|/|\\)src/loaders/[^/\\]+/index\.html$', k, flags=re.IGNORECASE)]
    if inject_loader and loader_keys:
        # prefer first
        lk = loader_keys[0]
        try:
            decoded_loader = try_decode_utf8(files_map[lk], lk)
            if decoded_loader is None:
                decoded_loader = files_map[lk].decode('utf-8', errors='replace')
            loader_html = decoded_loader
            # remove loader from files_map so it doesn't get embedded into the large JSON
            del files_map[lk]
            print(f"[INFO] Using loader from uploaded file: {lk}")
        except Exception:
            loader_html = None
    else:
        # try repository-local fallback paths relative to this script's location
        repo_root = Path(__file__).parent.resolve()
        candidate_used = None
        # If a specific loader name was requested, prefer that
        candidates = []
        if selected_loader:
            candidates.append(f'src/loaders/{selected_loader}/index.html')
            candidates.append(f'loaders/{selected_loader}/index.html')
        # fallback: try the list file or default basic
        candidates.extend(['src/loaders/basic/index.html', 'loaders/basic/index.html'])
        for candidate in candidates:
            try:
                cand_path = repo_root / candidate
                if cand_path.exists():
                    with open(cand_path, 'r', encoding='utf-8') as fh:
                        loader_html = fh.read()
                    candidate_used = str(cand_path)
                    break
            except Exception:
                continue

    if loader_html:
        if 'lk' in locals():
            print(f"[INFO] Using loader from uploaded file: {lk}")
        elif 'candidate_used' in locals() and candidate_used:
            print(f"[INFO] Using loader from repo path: {candidate_used}")
        else:
            print("[INFO] Using loader_html from fallback")

    embedded_map = {}
    # allow callers to request direct css embedding by setting a special variable
    # so rewrite_index_html can pick it up when deciding how to replace <link> tags
    if isinstance(variables, dict) and '__embed_css_direct__' in variables:
        embed_css_direct = bool(variables.get('__embed_css_direct__'))
    else:
        embed_css_direct = False

    rewritten_index = rewrite_index_html(decoded_index, files_map, embedded_map, variables)

    # If compression requested but brotli missing, warn and disable
    if compress and not brotli:
        print('[WARN] Compression requested but brotli module not available. Install brotli to enable compression. Falling back to uncompressed embedding.')
        compress = False

    # Populate embedded_map now so we can optionally compress certain assets.
    total_files = len(files_map)
    if total_files == 0:
        total_files = 1
    for idx, (path, bs) in enumerate(files_map.items()):
        try:
            ext = Path(path).suffix.lower()
            # Skip compression for html and css (they are typically text and may be inlined)
            if compress and brotli and ext not in ['.html', '.css']:
                try:
                    if GLOBAL_VERBOSE:
                        print(f"[INFO] Compressing {path} (brotli)")
                    comp = brotli.compress(bs)
                    embedded_map[path] = {
                        'b64': to_b64(comp),
                        'encoding': 'br',
                        'mime': mimetypes.guess_type(path)[0] or 'application/octet-stream'
                    }
                except Exception:
                    # fallback to raw base64 if compression fails
                    embedded_map[path] = to_b64(bs)
            else:
                embedded_map[path] = to_b64(bs)
        except Exception:
            embedded_map[path] = to_b64(bs)

        # emit progress mapped to 50-99% during embedding/compression
        try:
            if GLOBAL_EMIT_PROGRESS:
                pct = 50 + int(((idx + 1) / total_files) * 49)
                if GLOBAL_VERBOSE:
                    print(f"[{pct}%] embedded {path}")
                else:
                    print(f"[{pct}%]")
        except Exception:
            pass

    # Emit progress: embedding phase
    try:
        if GLOBAL_EMIT_PROGRESS:
            if GLOBAL_VERBOSE:
                print(f"[50%] Starting embedding {len(files_map)} resources")
            else:
                print('[50%]')
    except Exception:
        pass

    final_html = inject_fetch_patch_into_head(rewritten_index, embedded_map, loader_html=loader_html)

    # emit incremental progress while we report embedded keys (map size growth)
    try:
        if GLOBAL_EMIT_PROGRESS and embedded_map:
            total_keys = len(embedded_map)
            shown = 0
            for idx, k in enumerate(list(embedded_map.keys())):
                # map embedding progress to 50-99%
                pct = 50 + int(((idx + 1) / total_keys) * 49)
                if GLOBAL_VERBOSE:
                    print(f"[{pct}%] embedded {k}")
                else:
                    print(f"[{pct}%]")
                shown += 1
    except Exception:
        pass

    with open(outpath, "w", encoding="utf-8") as fh:
        fh.write(final_html)

    # Post-write verification: if loader was requested/injected, check it appears before the EMBEDDED_FILES
    if inject_loader and loader_html:
        try:
            with open(outpath, 'r', encoding='utf-8', errors='replace') as fh:
                head = fh.read(2000000)
            # Prefer explicit prefix marker; fall back to known loader ids
            loader_prefix_marker = '<!-- EVERBUILDER LOADER PREFIX START -->'
            loader_pos = head.find(loader_prefix_marker)
            if loader_pos == -1:
                # try other markers
                for marker in ['everbuilder-loader', 'basicFill', 'Basic loader', 'Preparing assets']:
                    p = head.find(marker)
                    if p != -1:
                        loader_pos = p
                        break
            emb_pos = head.find('EMBEDDED FILES')
            if loader_pos == -1:
                # no loader present in the output: treat as failure
                raise RuntimeError('Loader was requested but loader markers not found in output file')
            else:
                if emb_pos != -1 and loader_pos > emb_pos:
                    raise RuntimeError('Loader appears after embedded files in output; expected before')
                else:
                    print('[OK] Loader appears before the embedded files in output')
        except Exception as e:
            # For CLI builds we want to surface failures; raise so callers can detect/exit non-zero.
            print('[ERROR] Loader verification failed:', e)
            raise

    # Quick check: ensure no loader files were accidentally left in embedded_map
    try:
        leftover_loaders = [k for k in embedded_map.keys() if '/loaders/' in k.replace('\\','/') or k.lower().startswith('loaders/')]
        if leftover_loaders:
            print('[WARN] Found loader paths still embedded (should have been removed):')
            for lked in leftover_loaders[:10]:
                print('  embedded loader key:', lked)
    except Exception:
        pass

    # Finalize at 100%
    print(f"[100%] Wrote {outpath}. Embedded keys: {len(embedded_map)}")
    if GLOBAL_VERBOSE and embedded_map:
        for k in list(embedded_map.keys())[:20]:
            print("  embedded:", k)

if __name__ == "__main__":
    # If called with --cli run the original CLI behavior, otherwise start the web UI
    def cli_build():
        try:
            files = read_files_list(FILES_LIST)
            total = len(files)
            print(f"[0%] Found {total} files listed.")
            # enable progress in CLI by default
            try:
                global GLOBAL_VERBOSE, GLOBAL_EMIT_PROGRESS
                GLOBAL_EMIT_PROGRESS = True
                # if user passed --verbose, enable verbose
                if '--verbose' in sys.argv:
                    GLOBAL_VERBOSE = True
                # if user passed --no-loader, disable loader injection
                no_loader_flag = '--no-loader' in sys.argv
            except Exception:
                pass
            inject_loader_flag = not ('--no-loader' in sys.argv)
            # support --loader NAME for CLI
            selected_loader = None
            if '--loader' in sys.argv:
                try:
                    idx = sys.argv.index('--loader')
                    selected_loader = sys.argv[idx+1]
                except Exception:
                    selected_loader = None
            # support --embed-css flag to embed css directly preserving ids
            embed_css_flag = '--embed-css' in sys.argv

            # prepare variables dict for build
            vars_for_build = dict(VARIABLES) if isinstance(VARIABLES, dict) else {}
            if embed_css_flag:
                vars_for_build['__embed_css_direct__'] = True
            compress_flag = '--compress' in sys.argv
            build(files, vars_for_build, OUTPUT_FILE, inject_loader=inject_loader_flag, selected_loader=selected_loader, compress=compress_flag)
            # Post-check: if loader injection was enabled, verify offline.html contains loader before EMBEDDED_FILES
            try:
                if '--no-loader' not in sys.argv:
                    with open(OUTPUT_FILE, 'r', encoding='utf-8', errors='replace') as fh:
                        outtext = fh.read(2000000)  # read head portion
                    # check for known loader fragment id or basicFill then ensure it occurs before EMBEDDED_FILES
                    loader_pos = None
                    for marker in ['everbuilder-loader', 'basicFill', 'Basic loader', 'Preparing assets']:
                        p = outtext.find(marker)
                        if p != -1:
                            loader_pos = p
                            break
                    emb_pos = outtext.find('EMBEDDED FILES')
                    if loader_pos is None:
                        print('[WARN] Loader injection enabled but loader markers not found in output.')
                    else:
                        if emb_pos != -1 and loader_pos > emb_pos:
                            print('[ERROR] Loader appears after embedded files; it must be above. Build failed verification.')
                            raise RuntimeError('Loader injection ordering verification failed')
                        else:
                            print('[OK] Loader appears before the embedded files block')
            except Exception as e:
                print('ERROR during post-build verification:', e, file=sys.stderr)
        except Exception as e:
            print("ERROR:", e, file=sys.stderr)
            raise

    def serve_ui(port=5000):
        try:
            from flask import Flask, send_from_directory, request, Response, jsonify, send_file, stream_with_context
        except Exception:
            print("Flask is required for the web UI. Install with: python -m pip install Flask", file=sys.stderr)
            sys.exit(1)

        # serve the UI under a namespaced path to avoid collisions with other index.html files
        app = Flask(__name__, static_folder='src', static_url_path='/everbuilder_static')

        LAST_BUILD = {'log': None, 'artifact': None, 'artifact_name': None, 'tempdir': None}

        @app.route('/everbuilder')
        def index():
            return send_from_directory(app.static_folder, 'index.html')

        @app.route('/everbuilder_static/<path:filename>')
        def static_files(filename):
            return send_from_directory(app.static_folder, filename)

        def make_files_list_for_builder(saved_paths, tempdir):
            # return relative paths (forward-slash) as the builder expects
            rels = []
            for p in saved_paths:
                r = os.path.relpath(p, start=tempdir).replace('\\', '/')
                rels.append(r)
            return rels

        @app.route('/build', methods=['POST'])
        def build_route():
            tempdir = tempfile.mkdtemp(prefix='hazmob-build-')
            LAST_BUILD['tempdir'] = tempdir

            # parse settings if provided
            settings = {}
            if 'settings' in request.form:
                try:
                    settings = json.loads(request.form['settings'])
                except Exception:
                    settings = {}
            LAST_BUILD['settings'] = settings

            files = request.files.getlist('files')
            saved_paths = []
            for f in files:
                filename = f.filename.lstrip('/\\')
                dest_path = os.path.join(tempdir, *Path(filename).parts)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                f.save(dest_path)
                saved_paths.append(dest_path)

            q = queue.Queue()
            LAST_BUILD['queue'] = q
            log_lines = []

            # set global flags based on settings
            try:
                global GLOBAL_VERBOSE, GLOBAL_EMIT_PROGRESS
                GLOBAL_VERBOSE = bool(settings.get('verbose'))
                GLOBAL_EMIT_PROGRESS = bool(settings.get('emit_progress', True))
            except Exception:
                pass

            class QueueWriter:
                def write(self, s):
                    if s is None:
                        return
                    text = str(s)
                    # normalize line endings and split into lines so each queued item is a logical line
                    parts = text.replace('\r\n','\n').replace('\r','\n').split('\n')
                    for part in parts:
                        if part == '':
                            continue
                        log_lines.append(part)
                        q.put(part)
                def flush(self):
                    pass

            def run_build():
                orig_cwd = os.getcwd()
                orig_stdout = sys.stdout
                try:
                    os.chdir(tempdir)
                    sys.stdout = QueueWriter()

                    files_list = make_files_list_for_builder(saved_paths, tempdir)
                    with open('files.txt', 'w', encoding='utf-8') as fh:
                        fh.write('\n'.join(files_list) + '\n')

                    q.put(f"[0%] Found {len(files_list)} files listed.")
                    try:
                        # call the existing build() defined above in this module
                        inject_loader_flag = bool(settings.get('inject_loader', True))
                        selected_loader_name = settings.get('selected_loader')
                        # construct variables dict and include embed_css setting
                        vars_for_build = dict(VARIABLES) if isinstance(VARIABLES, dict) else {}
                        if settings.get('embed_css'):
                            vars_for_build['__embed_css_direct__'] = True
                        compress_flag = bool(settings.get('compress'))
                        build(files_list, vars_for_build, 'offline.html', inject_loader=inject_loader_flag, selected_loader=selected_loader_name, compress=compress_flag)
                        q.put('[100%] Build finished')
                    except Exception as e:
                        q.put('[ERROR] ' + str(e))

                    # save written stdout lines into a log file (use collected log_lines)
                    log_path = os.path.join(tempdir, 'build.log')
                    try:
                        with open(log_path, 'w', encoding='utf-8') as fh:
                            # write settings at top
                            try:
                                fh.write('Settings: ' + json.dumps(settings) + '\n')
                            except Exception:
                                fh.write('Settings: (invalid)\n')
                            fh.write('\n'.join(log_lines))
                        LAST_BUILD['log'] = log_path
                    except Exception:
                        LAST_BUILD['log'] = None

                    offline_path = os.path.join(tempdir, 'offline.html')
                    if os.path.exists(offline_path):
                        LAST_BUILD['artifact'] = offline_path
                        LAST_BUILD['artifact_name'] = 'offline.html'
                        # Auto-open artifact if requested and supported
                        try:
                            sa = settings.get('auto_open')
                            if sa and supports_auto_open():
                                try:
                                    if os.name == 'nt':
                                        os.startfile(offline_path)
                                    else:
                                        # macOS or Linux
                                        if shutil.which('open'):
                                            subprocess.Popen(['open', offline_path])
                                        elif shutil.which('xdg-open'):
                                            subprocess.Popen(['xdg-open', offline_path])
                                        else:
                                            # fallback to webbrowser
                                            webbrowser.open('file://' + offline_path)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    else:
                        LAST_BUILD['artifact'] = None
                finally:
                    sys.stdout = orig_stdout
                    os.chdir(orig_cwd)
                    q.put('@@BUILD_DONE@@')

            # optionally start a cleanup thread if requested
            def maybe_cleanup():
                s = settings or {}
                if s.get('clean_temp'):
                    # wait a bit and then remove tempdir
                    time.sleep(10)
                    try:
                        shutil.rmtree(tempdir)
                    except Exception:
                        pass

            if settings.get('clean_temp'):
                ct = threading.Thread(target=maybe_cleanup, daemon=True)
                ct.start()

            t = threading.Thread(target=run_build, daemon=True)
            t.start()

            # Return a small JSON acknowledgement. Clients should connect to
            # GET /build/stream to receive the live logs for the started build.
            return jsonify({'status': 'started'})

        @app.route('/build/stream')
        def build_stream():
            # allow clients to connect to the current build's queue to receive live logs
            q2 = LAST_BUILD.get('queue')
            if not q2:
                return 'No active build', 404

            def stream2():
                try:
                    while True:
                        s = q2.get()
                        if s == '@@BUILD_DONE@@':
                            yield 'READY\n'
                            break
                        yield str(s) + '\n'
                except Exception as e:
                    print('stream2 exception:', e, file=sys.stderr)
                    raise

            resp2 = Response(stream_with_context(stream2()), mimetype='text/plain')
            resp2.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return resp2

        @app.route('/build/result')
        def build_result():
            if LAST_BUILD['log'] is None and LAST_BUILD['artifact'] is None:
                return jsonify({}), 404
            return jsonify({
                'log_url': '/build/log',
                'build_url': '/build/artifact',
                'build_name': LAST_BUILD.get('artifact_name')
            })

        @app.route('/build/log')
        def build_log():
            if not LAST_BUILD.get('log') or not os.path.exists(LAST_BUILD['log']):
                return 'No log', 404
            return send_file(LAST_BUILD['log'], mimetype='text/plain', as_attachment=True, download_name='build.log')

        @app.route('/build/artifact')
        def build_artifact():
            if not LAST_BUILD.get('artifact') or not os.path.exists(LAST_BUILD['artifact']):
                return 'No artifact', 404
            return send_file(LAST_BUILD['artifact'], as_attachment=True, download_name=LAST_BUILD.get('artifact_name'))

        def supports_auto_open():
            # check whether we can open files programmatically on this OS
            try:
                if os.name == 'nt':
                    return True
                if shutil.which('open') or shutil.which('xdg-open'):
                    return True
                return True if webbrowser else False
            except Exception:
                return False

        @app.route('/features')
        def features():
            return jsonify({
                'auto_open': supports_auto_open()
            })

        @app.route('/everbuilder/_debug')
        def _everbuilder_debug():
            # expose some internal state for local debugging
            q = LAST_BUILD.get('queue')
            return jsonify({
                'has_queue': bool(q),
                'tempdir': LAST_BUILD.get('tempdir'),
                'artifact': bool(LAST_BUILD.get('artifact')),
                'log': bool(LAST_BUILD.get('log'))
            })

        url = f'http://127.0.0.1:{port}/everbuilder'
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        app.run(port=port, debug=False, threaded=True)

# decide mode
if len(sys.argv) > 1 and sys.argv[1] == '--cli':
    cli_build()
else:
    serve_ui()
