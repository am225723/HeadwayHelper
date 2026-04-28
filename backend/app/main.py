--- a/main.py
+++ b/main.py
@@ -82,12 +82,15 @@ async def api_get_patient_detail(folder_id: str, session: AsyncSession = Depends
     outs = [
         {
             "id": out.id,
             "file_id": out.output_drive_file_id,
             "file_name": out.output_file_name,
             "output_type": out.output_type,
             "created_at": out.created_at,
+            "content": getattr(out, "content", None),
+            "is_draft": not bool(out.output_drive_file_id),
         }
         for out in pat_obj.outputs
     ]
     return {
         "folder": {
@@ -183,17 +186,44 @@ async def api_get_output_file(output_id: int, session: AsyncSession = Depends(ge
     out_obj = await session.get(Output, output_id)
     if not out_obj:
         raise HTTPException(status_code=404, detail="Output not found")
+    if not out_obj.output_drive_file_id:
+        raise HTTPException(
+            status_code=409,
+            detail="This output is a draft and does not have a PDF file yet. Use /outputs/{output_id}/preview to view it.",
+        )
     # Download the file from Drive
     from .drive_service import download_file
     file_bytes = download_file(out_obj.output_drive_file_id)
     # Return streaming response
     return StreamingResponse(
         iter([file_bytes]),
         media_type="application/pdf",
         headers={
             "Content-Disposition": f"attachment; filename={out_obj.output_file_name}"
         },
     )
+
+
+@app.get("/outputs/{output_id}/preview")
+async def api_preview_output(output_id: int, session: AsyncSession = Depends(get_session)) -> dict:
+    """Return a generated output for in-app preview, including drafts.
+
+    Drafts may not have been uploaded to Drive yet, so the normal
+    /outputs/{output_id} PDF download endpoint cannot access them.
+    This endpoint returns the stored database content when present.
+    """
+    out_obj = await session.get(Output, output_id)
+    if not out_obj:
+        raise HTTPException(status_code=404, detail="Output not found")
+
+    content = getattr(out_obj, "content", None)
+    if content is None:
+        content = getattr(out_obj, "html_content", None)
+    if content is None:
+        content = getattr(out_obj, "text_content", None)
+
+    return {
+        "id": out_obj.id,
+        "file_id": out_obj.output_drive_file_id,
+        "file_name": out_obj.output_file_name,
+        "output_type": out_obj.output_type,
+        "created_at": out_obj.created_at,
+        "is_draft": not bool(out_obj.output_drive_file_id),
+        "content": content,
+    }
