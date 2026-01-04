using System;
using System.IO;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class RenameOptions
    {
        public RenameMode Mode { get; set; } = RenameMode.Safe;
        public bool AppendRevision { get; set; }
        public bool KeepBackup { get; set; } = true;
        public bool RenameChildren { get; set; }
    }

    internal sealed class RenameResult
    {
        public bool Ok { get; set; }
        public string Message { get; set; }
        public string CurrentPath { get; set; }
        public string TargetPath { get; set; }
    }

    internal sealed class SolidWorksRenameService
    {
        public RenameResult PreviewRename(ModelDoc2 model, string partNumber, string revision, RenameOptions options)
        {
            var result = new RenameResult { Ok = false };
            if (model == null)
            {
                result.Message = "Active document not found.";
                return result;
            }

            string currentPath = model.GetPathName();
            string message;
            string targetPath;
            if (!PartNumberRenameHelper.TryBuildTargetPath(currentPath, partNumber, revision, options.AppendRevision, File.Exists, out targetPath, out message))
            {
                result.Message = message;
                return result;
            }

            result.Ok = true;
            result.CurrentPath = currentPath;
            result.TargetPath = targetPath;
            result.Message = string.Empty;
            return result;
        }

        public RenameResult TryRename(ModelDoc2 model, string partNumber, string revision, RenameOptions options)
        {
            var result = new RenameResult { Ok = false };
            if (model == null)
            {
                result.Message = "Active document not found.";
                return result;
            }

            string currentPath = model.GetPathName();
            bool isReferenced = HasExternalReferences(model, out string referenceNote);
            RenameDecision decision = PartNumberRenameHelper.EvaluateRenameDecision(currentPath, isReferenced, options.Mode);
            if (!decision.Allowed)
            {
                result.Message = decision.Reason + (string.IsNullOrWhiteSpace(referenceNote) ? string.Empty : " " + referenceNote);
                return result;
            }

            string targetPath;
            string message;
            if (!PartNumberRenameHelper.TryBuildTargetPath(currentPath, partNumber, revision, options.AppendRevision, File.Exists, out targetPath, out message))
            {
                result.Message = message;
                return result;
            }

            if (string.Equals(currentPath, targetPath, StringComparison.OrdinalIgnoreCase))
            {
                result.Message = "File name is already up to date.";
                result.CurrentPath = currentPath;
                result.TargetPath = targetPath;
                return result;
            }

            result.CurrentPath = currentPath;
            result.TargetPath = targetPath;

            AddinLogger.Write("Rename start: " + currentPath + " -> " + targetPath);

            int errors = 0;
            int warnings = 0;
            int version = (int)swSaveAsVersion_e.swSaveAsCurrentVersion;
            int updateOptions = (int)swSaveAsOptions_e.swSaveAsOptions_Silent |
                                TryGetSaveAsOption("swSaveAsOptions_UpdateReferences");

            bool ok = model.Extension.SaveAs(targetPath, version, updateOptions, null, ref errors, ref warnings);
            if (!ok)
            {
                AddinLogger.Write("Rename failed with update refs. Errors=" + errors + " Warnings=" + warnings);
                if (options.Mode == RenameMode.Safe)
                {
                    int copyOptions = (int)swSaveAsOptions_e.swSaveAsOptions_Silent |
                                      (int)swSaveAsOptions_e.swSaveAsOptions_Copy;
                    errors = 0;
                    warnings = 0;
                    ok = model.Extension.SaveAs(targetPath, version, copyOptions, null, ref errors, ref warnings);
                    if (!ok)
                    {
                        result.Message = "Rename failed. SaveAs copy also failed.";
                        AddinLogger.Write("Rename copy failed. Errors=" + errors + " Warnings=" + warnings);
                        return result;
                    }

                    result.Ok = true;
                    result.Message = "Saved copy. References were not updated.";
                    AddinLogger.Write("Rename safe mode saved copy: " + targetPath);
                    return result;
                }

                result.Message = "Rename failed. References could not be updated.";
                return result;
            }

            if (!options.KeepBackup && !string.IsNullOrWhiteSpace(currentPath))
            {
                TryDeleteBackup(currentPath);
            }

            result.Ok = true;
            result.Message = "Rename completed.";
            AddinLogger.Write("Rename completed: " + targetPath);
            return result;
        }

        private int TryGetSaveAsOption(string name)
        {
            try
            {
                Array values = Enum.GetValues(typeof(swSaveAsOptions_e));
                foreach (object val in values)
                {
                    if (string.Equals(Enum.GetName(typeof(swSaveAsOptions_e), val), name, StringComparison.Ordinal))
                    {
                        return (int)val;
                    }
                }
            }
            catch
            {
                // Ignore missing enum values for older SolidWorks versions.
            }
            return 0;
        }

        private bool HasExternalReferences(ModelDoc2 model, out string note)
        {
            note = string.Empty;
            try
            {
                ModelDocExtension ext = model.Extension;
                var method = ext.GetType().GetMethod("GetExternalReferences2");
                if (method == null)
                {
                    method = ext.GetType().GetMethod("GetExternalReferences");
                }

                if (method != null)
                {
                    object refsObj = method.Invoke(ext, null);
                    object[] refs = refsObj as object[];
                    if (refs != null && refs.Length > 0)
                    {
                        note = "(External references detected.)";
                        return true;
                    }
                }
                return false;
            }
            catch (Exception ex)
            {
                note = "(Reference check failed: " + ex.Message + ")";
                return true;
            }
        }

        private void TryDeleteBackup(string path)
        {
            try
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                    AddinLogger.Write("Deleted backup file: " + path);
                }
            }
            catch (Exception ex)
            {
                AddinLogger.Write("Failed to delete backup file: " + ex.Message);
            }
        }
    }
}
