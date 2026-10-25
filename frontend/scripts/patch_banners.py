"""
Final patch: replace inline red-error banner JSX and add isWakingUp state
to the 5 remaining pages: users, policies, devices, enroll, incidents.
"""
import os, re

ROOT = r"c:\Users\ARUN\Desktop\dataghost\frontend"

# Each entry: (file_rel, load_fn_name, error_state_var, catch_fn_list)
PAGES = [
    (r"app\(app)\users\page.tsx",       "load",          "error", ["loadUsers", "load"]),
    (r"app\(app)\policies\page.tsx",    "load",          "error", ["load"]),
    (r"app\incidents\page.tsx",         "loadIncidents", "error", ["loadIncidents"]),
]

# Pages that are complex (devices, enroll) — only add isWakingUp + catch patch
# banner JSX replacement is done separately / already has enough inline handling
COMPLEX_PAGES = [
    (r"app\devices\page.tsx",           "loadDevices",   "error"),
    (r"app\enroll\page.tsx",            "loadData",      "error"),
]

# ── State injection ────────────────────────────────────────────────────────────

STATE_LINE = "  const [isWakingUp, setIsWakingUp] = useState(false);\n"

def inject_waking_state(txt, error_var="error"):
    if "isWakingUp" in txt:
        return txt, False
    # Find the error state line and add after it
    pattern = rf"(const \[{re.escape(error_var)}, set[A-Z]\w+\] = useState<[^>]+>\(null\);)"
    if re.search(pattern, txt):
        return re.sub(pattern, r"\1\n  const [isWakingUp, setIsWakingUp] = useState(false);", txt, count=1), True
    # Fallback: add after any useState(false) at same indentation
    pattern2 = r"(const \[loading, setLoading\] = useState\((?:true|false)\);)"
    if re.search(pattern2, txt):
        return re.sub(pattern2, r"\1\n  const [isWakingUp, setIsWakingUp] = useState(false);", txt, count=1), True
    return txt, False

# ── Catch-block patch ─────────────────────────────────────────────────────────

def patch_catch_block(txt):
    if "isBackendWakeUpError" in txt:
        return txt, False
    # Match:  setError(err instanceof Error ? err.message : "...");
    pattern = r"(setError\(\s*err instanceof Error \? err\.message\s*:\s*\"[^\"]+\"\s*\);)"
    replacement = (
        "if (isBackendWakeUpError(err)) {\n"
        "        setIsWakingUp(true);\n"
        "        setError(null);\n"
        "      } else {\n"
        "        setIsWakingUp(false);\n"
        "        \\1\n"
        "      }"
    )
    new_txt = re.sub(pattern, replacement, txt, count=1)
    changed = new_txt != txt
    return new_txt, changed

# ── Clear in try ──────────────────────────────────────────────────────────────

def patch_clear_in_try(txt, set_error="setError"):
    if "setIsWakingUp(false);" in txt:
        return txt
    return txt.replace(
        f"{set_error}(null);\n",
        f"{set_error}(null);\n    setIsWakingUp(false);\n",
        1
    )

# ── Banner JSX replacement ────────────────────────────────────────────────────

# Pattern: {error && ( <div...>...</div> )}  →  <WakeUpBanner> / <ErrorBanner>
# Works for the 3 simple pages with a known single error banner block

BANNER_PATTERN = re.compile(
    r"\{/\* Error banner \*/\}\s*\{error &&\s*\(\s*<div[^}]+style=\{\{[^}]*background: \"rgba\(255,59,59[^>]+>[\s\S]+?</div>\s*\)\s*\}\}?\s*\)\s*\}",
    re.MULTILINE
)

def replace_banner(txt, load_fn):
    replacement = (
        "{/* Wake-up banner */}\n"
        f"          {{isWakingUp && <WakeUpBanner onRetry={{{load_fn}}} />}}\n\n"
        "          {/* Error banner */}\n"
        f"          {{error && <ErrorBanner message={{error}} onRetry={{{load_fn}}} />}}"
    )
    new_txt = BANNER_PATTERN.sub(replacement, txt, count=1)
    return new_txt, new_txt != txt


# ── Process each page ─────────────────────────────────────────────────────────

for rel, load_fn, error_var, *_ in PAGES:
    fp = os.path.join(ROOT, rel)
    if not os.path.exists(fp):
        print(f"SKIP (not found): {rel}")
        continue
    txt = open(fp, encoding="utf-8").read()
    changed = False

    txt, c = inject_waking_state(txt, error_var)
    changed = changed or c
    txt, c = patch_catch_block(txt)
    changed = changed or c
    txt = patch_clear_in_try(txt)

    # Replace banner JSX
    new_txt, c = replace_banner(txt, load_fn)
    if c:
        txt = new_txt
        changed = True

    open(fp, "w", encoding="utf-8").write(txt)
    print(f"PATCHED: {rel} (state={not not c})")

# Complex pages: only state + catch (their banners are deep in JSX)
for rel, load_fn, error_var in COMPLEX_PAGES:
    fp = os.path.join(ROOT, rel)
    if not os.path.exists(fp):
        print(f"SKIP (not found): {rel}")
        continue
    txt = open(fp, encoding="utf-8").read()

    txt, _ = inject_waking_state(txt, error_var)
    txt, _ = patch_catch_block(txt)
    txt = patch_clear_in_try(txt)

    open(fp, "w", encoding="utf-8").write(txt)
    print(f"PATCHED state+catch only: {rel}")

print("Done.")
