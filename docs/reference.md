# ✧ Tool reference

[← README](../README.md) · [Setup](setup.md)

The client launches `refero_mcp_server.py` and exchanges JSON-RPC messages over stdio. The server reads Refero API/style/CDN endpoints or the local mirror in `data/`. Multi-image stitching requires Pillow; other server operations use the Python standard library.

## Tool Reference (14 Tools)

| Tool | Parameters | Description |
|---|---|---|
| `refero_search_styles` | `query`, `limit` | Searches curated design systems from `styles.refero.design` (e.g. Apple, Cursor, Minimal). |
| `refero_get_style` | `style_id` / `style_ids`, `response_format` (`md`/`json`) | Fetches complete `DESIGN.md` spec (colors, fonts, layout rules, component guidelines). |
| `refero_search_screens` | `query`, `platform` (`web`/`ios`), `order` (`trending`/`latest`/`oldest`), `page`, `per_page` | Searches real UI screens. Automatically enriches all records with direct CDN URLs and embeds. |
| `refero_get_screen` | `screen_id` / `screen_ids` (numeric ID or UUID) | Retrieves full metadata, dimensions, font tokens, RGB palettes, and high-res image URLs. |
| `refero_get_similar_screens` | `screen_id`, `limit`, `platform` | Uses remote similarity results; offline fallback returns screens from the same domain, or other cached screens. |
| `refero_get_screen_image` | `screen_id`, `image_size` (`full`/`thumbnail`) | Returns source image URLs, cached-file paths, previews, and embeds. |
| `refero_download_screen` | `screen_id` / `screen_ids`, `output_dir`, `all_slices`, `stitch` (bool) | Downloads full-resolution JPG(s) to local disk. Supports multi-slice screens. |
| `refero_get_image_instructions` | `topic` (`all`/`cdn`/`browser_bypass`/`console_scripts`/`downloads`) | Returns complete instructions, DevTools scripts, and CDN patterns. |
| `refero_get_screen_content` | `screen_id` | Analyzes screen layout, typography list, color palette, design patterns, and page elements. |
| `refero_search_flows` | `query`, `platform`, `page` | Searches multi-step user journey flows (onboarding, checkout, signup, settings). |
| `refero_get_flow` | `flow_id` / `flow_ids` | Retrieves the entire multi-step screen sequence with transitions and image links. |
| `refero_search_site` | `query`, `page`, `per_page` | Searches web services, domains, and design collections. |
| `refero_search_app` | `query`, `page`, `per_page` | Searches iOS mobile apps and App Store design collections. |
| `refero_get_catalog` | `catalog_type` (`sites`/`apps`), `search`, `limit` | Reads a local or remote sites/apps catalog; coverage depends on the available data. |

---

## Downloads
```python
# Single screenshot download
refero_download_screen(screen_id="184751")

# Batch download multiple screens
refero_download_screen(screen_ids=["184751", "184752", "184753"])

# Download all vertical slices of a long scrollable screen
refero_download_screen(screen_id="184751", all_slices=True)

# Download all slices AND stitch vertically into a single image (requires Pillow)
refero_download_screen(screen_id="184751", stitch=True)
```

---

## CDN paths

Source image records can contain these paths:

```text
https://images.refero.design/screenshots/{domain}/desktop/{uuid}/{slice_index}.jpg
https://images.refero.design/app_screenshots/{app_id}/{uuid}/{slice_index}.jpg
```

Dimensions and access depend on the source. Browser-specific instructions are available through `refero_get_image_instructions`; frontend class names and behavior can change.
