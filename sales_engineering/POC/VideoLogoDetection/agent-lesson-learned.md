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
