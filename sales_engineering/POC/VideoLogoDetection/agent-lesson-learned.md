# Agent Lesson Learned: SQLAlchemy Reserved Attribute Names

**Date:** January 7, 2026  
**Component:** Video Model (Flask-SQLAlchemy)  
**Severity:** Critical (Application Startup Blocker)

---

## Problem Summary

The Flask application failed to start with the following error:

```python
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.
```

And subsequently:

```python
AttributeError: 'property' object has no attribute 'tables'
```

---

## Root Cause

SQLAlchemy's Declarative API **reserves the `metadata` attribute name** on all model classes. This attribute is used internally by SQLAlchemy to store the `MetaData` object that contains information about all tables.

When we defined a column or property named `metadata` in our `Video` model, it conflicted with SQLAlchemy's internal machinery, causing the mapper configuration to fail.

---

## Attempted Solutions (Failed)

### Attempt 1: Rename column with alias
```python
metadata_json = db.Column("metadata", JSONB(), ...)
```
**Result:** Still failed because the Python attribute name `metadata_json` doesn't fix the internal conflict when SQLAlchemy tries to access `cls.metadata.tables`.

### Attempt 2: Use property accessor after column rename
```python
extra_metadata = db.Column("metadata", JSONB(), ...)

@property
def metadata(self):
    return self.extra_metadata or {}
```
**Result:** Failed because defining a `@property` named `metadata` still overrides the reserved `metadata` class attribute that SQLAlchemy needs.

### Attempt 3: Move property after relationships
```python
# Moved @property definition after __table_args__
```
**Result:** Failed because the order doesn't matter—the property is still evaluated during class construction and conflicts with SQLAlchemy's internal `metadata` attribute.

---

## Working Solution

Use a **completely different attribute name** for the column, and **access it directly** throughout the codebase without using a property accessor.

```python
class Video(db.Model):
    __tablename__ = "videos"
    __mapper_args__ = {"eager_defaults": True}
    
    # ... other columns ...
    
    # Column stored as "metadata" in database, but accessed as video_metadata in Python
    video_metadata = db.Column(
        "metadata",  # DB column name can remain "metadata"
        JSONB().with_variant(db.JSON, "sqlite"),
        default=dict,
        nullable=False
    )
    
    # ... relationships ...
    
    # NO @property accessor - use video_metadata directly everywhere
```

**Key insights:**
1. The database column name can remain `"metadata"` using `db.Column("metadata", ...)`
2. The Python attribute MUST NOT be named `metadata` - use `video_metadata` or another non-reserved name
3. **DO NOT** create a `@property` accessor named `metadata` - it still conflicts with SQLAlchemy's internal use
4. Update all code to reference `video.video_metadata` instead of `video.metadata`

---

## Code Updates Required

When renaming from `metadata` to `video_metadata`, update:

1. **Model definition** ([app/models/video.py](app/models/video.py)):
   - Column: `video_metadata = db.Column("metadata", ...)`
   - Remove any `@property` accessors named `metadata`

2. **Service layer** ([app/services/video_service.py](app/services/video_service.py)):
   - Change all `video.data` or `video.metadata` to `video.video_metadata`
   - Lines updated: 33, 45, 77, 182
   
3. **API layer** ([app/api/videos.py](app/api/videos.py)):
   - Change response dictionaries to use `"video_metadata": video.video_metadata`
   - Lines updated: 77, 141, 161
   
4. **Schemas** ([app/api/schemas.py](app/api/schemas.py)):
   - Change field: `video_metadata = fields.Dict(attribute="video_metadata")`
   - Line updated: 40
   
5. **Frontend** ([static/js/dashboard.js](static/js/dashboard.js)):
   - Change all `video.metadata` to `video.video_metadata`
   - Lines updated: 65, 463

6. **Database schema** ([create-schema.sql](create-schema.sql)):
   - Column name can remain `metadata` - SQLAlchemy will map it correctly

7. **File cleanup** (Critical!):
   - Remove all `*** End of File` markers that may have been added during editing
   - Files cleaned: schemas.py, inference_models.py, billing_service.py, metrics_service.py
   - These markers cause SyntaxError and prevent app startup

---

## Best Practice: Avoid Reserved Names

### SQLAlchemy Reserved Attributes (Declarative API)
Never use these names as column attributes or properties in SQLAlchemy models:
- `metadata` ⚠️ (MetaData instance)
- `__table__` (Table instance)
- `__mapper__` (Mapper instance)
- `__tablename__`
- `__table_args__`
- `__mapper_args__`
- `query` (when using Flask-SQLAlchemy)
- `registry`

### Recommended Naming Alternatives
Instead of `metadata`, use:
- `meta_data`
- `meta_info`
- `extra_data`
- `video_metadata`
- `record_metadata`
- `custom_metadata`

---

## Impact on Codebase

All code referencing `video.metadata` needed to be updated to use `video.video_metadata` OR the property accessor had to be removed entirely.

### Files Affected
- `app/models/video.py` - Model definition
- `app/services/video_service.py` - Video processing logic
- `app/api/videos.py` - API endpoints
- `app/services/inference_service.py` - Inference logic (if applicable)

---

## Prevention Strategy

1. **Check SQLAlchemy documentation** for reserved names before naming model attributes
2. **Use linting rules** or static analysis to catch reserved attribute names early
3. **Test model imports in isolation** before integrating with the full application:
   ```python
   from app.models.video import Video
   print("Model loads OK")
   ```
4. **Prefer domain-specific prefixes** for metadata columns (e.g., `video_metadata`, `project_settings`)

---

## Additional Notes

- This issue manifests differently in different SQLAlchemy versions
- Flask-SQLAlchemy adds its own reserved attributes (e.g., `query`)
- Using `__mapper_args__` with `eager_defaults` can help with other edge cases
- Always test model loading before deploying schema changes

---

## References

- [SQLAlchemy Declarative API Documentation](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html)
- [Flask-SQLAlchemy Reserved Names](https://flask-sqlalchemy.palletsprojects.com/en/3.0.x/)
- [SQLAlchemy FAQ - Reserved Names](https://docs.sqlalchemy.org/en/20/faq/ormconfiguration.html)

---

**Resolution:** Changed column attribute from `metadata` to `video_metadata` and updated all references in the services layer.

---

# Agent Lesson Learned: Missing Database Import in API Blueprint

**Date:** January 7, 2026  
**Component:** Videos API Blueprint (Flask)  
**Severity:** High (Runtime Error on DELETE requests)

---

## Problem Summary

The DELETE endpoint for videos returned a 500 Internal Server Error with the following traceback:

```python
NameError: name 'db' is not defined
  File "app/api/videos.py", line 258, in delete_video
    db.session.delete(video)
NameError: name 'db' is not defined
```

---

## Root Cause

When adding the DELETE endpoint to `app/api/videos.py`, the code used `db.session.delete()` and `db.session.rollback()` without importing the `db` object from `app.extensions`.

The blueprint module had `socketio` imported but was missing the `db` import:

```python
# Before (incomplete)
from app.extensions import socketio
```

---

## Solution

Add `db` to the imports from `app.extensions`:

```python
# After (complete)
from app.extensions import db, socketio
```

---

## Lessons Learned

1. **Always verify imports** when adding new functionality that uses database operations
2. **Check import statements** in blueprint files - they may not have all necessary extensions
3. **Test endpoint immediately** after implementation to catch import errors early
4. **Use IDE autocomplete warnings** - missing imports often show as unresolved references
5. **Database operations require explicit db import** - it's not globally available in Flask blueprints

---

## Prevention Strategy

1. Always add database imports at the top of blueprint files that perform CRUD operations
2. Run the endpoint immediately after implementation to verify it works
3. Use linters (pylint, flake8) to catch undefined names before runtime
4. Create a checklist for new endpoints: imports, route decorator, error handling, database commit/rollback

---

**Resolution:** Added `db` to the import statement: `from app.extensions import db, socketio`

---

# Agent Lesson Learned: Media File Serving with Relative Paths

**Date:** January 7, 2026  
**Component:** Flask Media Serving Route  
**Severity:** Medium (404 errors on video playback)

---

## Problem Summary

The video player on the preprocessing page failed to load videos, and the media serving route returned 404 errors:

```
INFO:werkzeug:127.0.0.1 - - [07/Jan/2026 22:25:32] "HEAD /media/1/6/video_6_vlc-record-2025-11-20-11h12m15s-I04_R_3c.MP4-.mp4 HTTP/1.1" 404 -
```

Despite the video file existing at `media/project_1/video_6/video_6_vlc-record-2025-11-20-11h12m15s-I04_R_3c.MP4-.mp4`.

---

## Root Cause

Flask's `send_from_directory()` function requires an **absolute path** for the directory argument, but the code was passing a relative `Path` object:

```python
# Before (incorrect - relative path)
media_root = Path(app.config.get("PROJECT_MEDIA_ROOT", "media"))
video_dir = media_root / f"project_{project_id}" / f"video_{video_id}"
return send_from_directory(video_dir, filename)
```

When `send_from_directory()` received a relative path, it couldn't find the files and returned 404.

---

## Solution

Convert relative paths to absolute paths before passing to `send_from_directory()`:

```python
# After (correct - absolute path)
media_root = Path(app.config.get("PROJECT_MEDIA_ROOT", "media"))
if not media_root.is_absolute():
    media_root = Path(app.root_path).parent / media_root
video_dir = media_root / f"project_{project_id}" / f"video_{video_id}"
return send_from_directory(video_dir, filename)
```

---

## Lessons Learned

1. **`send_from_directory()` requires absolute paths** - relative paths will fail silently with 404
2. **Configuration values** like `PROJECT_MEDIA_ROOT` may be relative - always check and convert
3. **Use `app.root_path`** as the base for converting relative config paths to absolute
4. **Test file serving routes** with actual file requests, not just endpoint registration
5. **Check file existence** vs **route functionality** - files existing doesn't mean routes serve them correctly

---

## Testing Verification

After fix, the media route returned proper responses:

```
HTTP/1.1 200 OK
Content-Type: video/mp4
Content-Length: 95582034
```

---

## Prevention Strategy

1. Always use absolute paths for `send_from_directory()`
2. Add path resolution logic for config values that may be relative
3. Test file serving routes with `curl` or browser before marking as complete
4. Document in code comments that paths must be absolute for file serving
5. Consider adding validation in config loading to convert relative paths early

---

**Resolution:** Added absolute path resolution logic using `app.root_path` when media_root is relative.

---

# Agent Lesson Learned: Model Dropdowns Need Config-Driven Options

**Date:** January 8, 2026  
**Component:** Frontend Dashboard (Model Comparison)  
**Severity:** Medium (Feature Incomplete)

---

## Problem Summary

The Model A / Model B dropdowns on the comparison pane remained empty and stayed disabled even though the Clarifai config file (`config/models.yaml`) listed multiple presets. The console log confirmed: "Loaded 2 models from config" and "Model dropdowns populated", but the `<select>` elements still showed their placeholder and `disabled` attribute.

## Root Cause

We were constructing `<select>` options as plain strings (model ids) and relying on `setSelectOptions()` to accept them. However, the actual configuration entries were objects with `model_id`, `name`, and `params`. When we assigned these objects directly to the selects, the `value` attributes were `[object Object]`, and the `<select>` remained disabled because the helper detected "no values". Furthermore, `setSelectOptions()` disabled the selects whenever the normalized item list appeared empty.

## Working Solution

1. Normalize the config models when loading:
   - Map `model_id` → `id`, keep `name`, and include metadata fields for consistent rendering.
   - Decorations now record `model_type`, description, and version metadata so they behave like API models.
2. Improve `setSelectOptions()` to accept arrays of objects (with explicit `id`/`name`) and to compute option labels/values safely.
3. Update `populateComparisonDropdowns()` to pass normalized objects into `setSelectOptions()` and to seed the selects with the first two models so they become enabled immediately.
4. Log population progress for easier debugging.

## Lessons Learned

1. UI helpers must accept the same shape of data returned by the backend (configs vs strings).
2. Always normalize the data before using helper utilities that expect primitive values.
3. Logging the normalized payload and element references helps diagnose silent failures (e.g., disabled selects).
4. Drilling the source of `disabled` attributes requires verifying both the data and the enabling logic.

## Prevention Strategy

1. Keep a single source of truth for models (e.g., `config/models.yaml`) and document its format so downstream code doesn’t treat it as plain strings.
2. Use helper functions (like `normalizeModelEntry`) when reading config files so the rest of the UI always receives the expected structure.
3. Add frontend tests or manual checks to ensure dropdowns render options once data is loaded.
4. Avoid embedding `disabled` logic solely inside generic helpers—make sure callers override it when they know valid options exist.
