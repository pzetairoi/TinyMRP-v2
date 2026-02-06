using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Globalization;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class TinyMrpPublisher
    {
        // Flip these to true when diagnosing hide-features issues.
        private static readonly bool EnableHideDebugLog = false;
        private static readonly bool EnableHideStatusLog = false;
        // Writes additional structured entries into the export run log (errorLog) to help diagnose batch issues.
        // Keep these entries terse and prefixed so they can be filtered easily.
        private static readonly bool EnableExportDebugLog = true;
        private sealed class ModelEntry
        {
            public ModelDoc2 Model;
            public string ConfigurationName;
        }

        private sealed class BatchEntry
        {
            public string ModelPath;
            public string ModelTitle;
            public string ConfigurationName;
            public bool IsRoot;
        }

        private sealed class FlatBomEntry
        {
            public string ModelPath;
            public string ModelTitle;
            public string ConfigurationName;
            public string PartNumber;
            public string Revision;
            public string Process;
            public string Process2;
            public string Process3;
        }

        private sealed class DeliverablePlan
        {
            public string ModelPath;
            public string ModelTitle;
            public string ConfigurationName;
            public string FileString;
            public string PartNumber;
            public bool ExportPngModel;
            public bool ExportStep;
            public bool ExportEdrawing;
            public bool Export3mf;
            public bool ExportPly;
            public bool ExportStl;
            public bool ExportPdf;
            public bool ExportPngDrawing;
            public bool ExportEdrawingDrawing;
            public bool DrawingExists;

            public bool HasModelExports()
            {
                return ExportPngModel || ExportStep || ExportEdrawing || Export3mf || ExportPly || ExportStl;
            }

            public bool HasDrawingExports()
            {
                return DrawingExists && (ExportPdf || ExportPngDrawing || ExportEdrawingDrawing);
            }
        }

        private sealed class DeliverableGroup
        {
            public string ModelPath;
            public string ModelTitle;
            public bool IsRoot;
            public List<DeliverablePlan> Plans = new List<DeliverablePlan>();
        }

        private sealed class BatchGroup
        {
            public BatchEntry OpenEntry;
            public List<BatchEntry> Entries = new List<BatchEntry>();
        }

        private sealed class ExportRunLog
        {
            private readonly object _lock = new object();

            public ExportRunLog(string path)
            {
                Path = path;
            }

            public string Path { get; private set; }
            public bool HasEntries { get; private set; }

            public void Write(string message)
            {
                if (string.IsNullOrWhiteSpace(message) || string.IsNullOrWhiteSpace(Path))
                {
                    return;
                }

                try
                {
                    string dir = System.IO.Path.GetDirectoryName(Path);
                    if (!string.IsNullOrWhiteSpace(dir))
                    {
                        Directory.CreateDirectory(dir);
                    }

                    string line = DateTime.UtcNow.ToString("s") + " " + message + System.Environment.NewLine;
                    lock (_lock)
                    {
                        File.AppendAllText(Path, line);
                        HasEntries = true;
                    }
                }
                catch
                {
                    // ignore logging errors
                }
            }
        }

        private sealed class UserPreferenceToggleScope : IDisposable
        {
            private readonly ISldWorks _swApp;
            private readonly int _toggle;
            private readonly bool _original;
            private readonly bool _restore;
            private readonly bool _changed;

            public UserPreferenceToggleScope(ISldWorks swApp, swUserPreferenceToggle_e toggle, bool value)
            {
                _swApp = swApp;
                _toggle = (int)toggle;

                try
                {
                    _original = _swApp.GetUserPreferenceToggle(_toggle);
                    _restore = true;
                }
                catch
                {
                    _original = false;
                    _restore = false;
                }

                if (_restore)
                {
                    try
                    {
                        _swApp.SetUserPreferenceToggle(_toggle, value);
                        _changed = true;
                    }
                    catch
                    {
                        _changed = false;
                        // ignore preference set errors
                    }
                }
                else
                {
                    _changed = false;
                }
            }

            public void Dispose()
            {
                if (!_restore || !_changed || _swApp == null)
                {
                    return;
                }

                try
                {
                    _swApp.SetUserPreferenceToggle(_toggle, _original);
                }
                catch
                {
                    // ignore restore errors
                }
            }
        }

        private sealed class ExternalReferenceBatchOpenScope : IDisposable
        {
            private readonly UserPreferenceToggleScope _openReadOnly;
            private readonly UserPreferenceToggleScope _noPromptOrSave;

            public ExternalReferenceBatchOpenScope(ISldWorks swApp)
            {
                _openReadOnly = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swExtRefOpenReadOnly, true);
                _noPromptOrSave = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swExtRefNoPromptOrSave, true);
            }

            public void Dispose()
            {
                if (_noPromptOrSave != null)
                {
                    _noPromptOrSave.Dispose();
                }
                if (_openReadOnly != null)
                {
                    _openReadOnly.Dispose();
                }
            }
        }

        private sealed class ExportDialogSuppressionScope : IDisposable
        {
            private readonly ISldWorks _swApp;
            private readonly bool _prevCommand;
            private readonly bool _prevUserControl;
            private readonly bool _prevUserControlBackground;
            private readonly UserPreferenceToggleScope _stlInfoOnSave;
            private readonly UserPreferenceToggleScope _threeMfInfoOnSave;
            private readonly UserPreferenceToggleScope _pdfViewOnSave;
            private readonly UserPreferenceToggleScope _edrawSnlNotify;
            private readonly UserPreferenceToggleScope _warnSaveUpdateErrors;
            private readonly UserPreferenceToggleScope _warnSavingReferencedDoc;
            private readonly UserPreferenceToggleScope _drawingShowSheetFormatDialog;
            private readonly UserPreferenceToggleScope _autoDismissOpenMessages;

            public ExportDialogSuppressionScope(ISldWorks swApp)
            {
                _swApp = swApp;

                try
                {
                    _prevCommand = _swApp.CommandInProgress;
                    _prevUserControl = _swApp.UserControl;
                    _prevUserControlBackground = _swApp.UserControlBackground;
                }
                catch
                {
                    _prevCommand = false;
                    _prevUserControl = true;
                    _prevUserControlBackground = true;
                }

                try
                {
                    _swApp.CommandInProgress = true;
                }
                catch
                {
                    // ignore
                }
                try
                {
                    _swApp.UserControl = false;
                }
                catch
                {
                    // ignore
                }
                try
                {
                    _swApp.UserControlBackground = true;
                }
                catch
                {
                    // ignore
                }

                // Disable common "info on save" / viewer prompts that can break unattended batch export.
                _stlInfoOnSave = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swSTLShowInfoOnSave, false);
                _threeMfInfoOnSave = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.sw3MFShowInfoOnSave, false);
                _pdfViewOnSave = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swPDFViewOnSave, false);
                _edrawSnlNotify = new UserPreferenceToggleScope(swApp,
                    swUserPreferenceToggle_e.swNotifySNLNotObtainedForEDrawingsSave, false);
                _warnSaveUpdateErrors = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swWarnSaveUpdateErrors, false);
                _warnSavingReferencedDoc = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swWarnSavingReferencedDoc, false);
                _drawingShowSheetFormatDialog = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swDrawingShowSheetFormatDialog, false);
                _autoDismissOpenMessages = new UserPreferenceToggleScope(swApp, swUserPreferenceToggle_e.swWhileOpeningAssembliesAutoDismissMessages, true);
            }

            public void Dispose()
            {
                if (_autoDismissOpenMessages != null)
                {
                    _autoDismissOpenMessages.Dispose();
                }
                if (_drawingShowSheetFormatDialog != null)
                {
                    _drawingShowSheetFormatDialog.Dispose();
                }
                if (_warnSavingReferencedDoc != null)
                {
                    _warnSavingReferencedDoc.Dispose();
                }
                if (_warnSaveUpdateErrors != null)
                {
                    _warnSaveUpdateErrors.Dispose();
                }
                if (_edrawSnlNotify != null)
                {
                    _edrawSnlNotify.Dispose();
                }
                if (_pdfViewOnSave != null)
                {
                    _pdfViewOnSave.Dispose();
                }
                if (_threeMfInfoOnSave != null)
                {
                    _threeMfInfoOnSave.Dispose();
                }
                if (_stlInfoOnSave != null)
                {
                    _stlInfoOnSave.Dispose();
                }

                if (_swApp == null)
                {
                    return;
                }

                try
                {
                    _swApp.CommandInProgress = _prevCommand;
                }
                catch
                {
                    // ignore
                }
                try
                {
                    _swApp.UserControl = _prevUserControl;
                }
                catch
                {
                    // ignore
                }
                try
                {
                    _swApp.UserControlBackground = _prevUserControlBackground;
                }
                catch
                {
                    // ignore
                }
            }
        }

        private struct DrawingReference
        {
            public ModelDoc2 Model;
            public Configuration Configuration;
        }

        private static readonly Regex SanitizeRegex = new Regex("[^\\x28-\\x7F\\x20\\x21]+", RegexOptions.Compiled);

        private readonly ISldWorks _swApp;
        private readonly TinyMrpConfig _config;
        private volatile bool _cancelRequested;
        private readonly HashSet<string> _closeWarningOnce = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly HashSet<string> _debugOnce = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        public TinyMrpPublisher(ISldWorks swApp, TinyMrpConfig config)
        {
            _swApp = swApp;
            _config = config;
        }

        public void ProcessFiles(PublishOptions options, Action<string> log, Action<int, int> progress)
        {
            PublishOptions effective = NormalizeOptions(options);
            if (effective == null)
            {
                return;
            }

            ExportRunLog runLog = CreateExportRunLog();
            Action<string> errorLog = runLog != null ? new Action<string>(runLog.Write) : null;

            try
            {
                ResetCancel();
                _closeWarningOnce.Clear();
                _debugOnce.Clear();
                HashSet<string> uploadPackBases;
                List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras;
                string flatFile = TraverseModel(true, string.Empty, effective, log, null, progress, errorLog,
                    out uploadPackBases, out uploadPackExtras);
                if (effective.CreateUploadPack)
                {
                    try
                    {
                        CreateUploadPack(flatFile, uploadPackBases, uploadPackExtras, effective, log, errorLog);
                    }
                    catch (Exception ex)
                    {
                        if (ex is OperationCanceledException)
                        {
                            throw;
                        }
                        if (IsBaselineAbortException(ex))
                        {
                            throw;
                        }
                        Log(log, "Upload pack failed: " + ex.Message);
                        LogExportFailure(log, errorLog, "Upload pack failed: " + ex.Message);
                    }
                }
                string message = BuildRunLogMessage("File creation finished.", runLog);
                System.Windows.Forms.MessageBox.Show(message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK,
                    runLog != null && runLog.HasEntries
                        ? System.Windows.Forms.MessageBoxIcon.Warning
                        : System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                LogExportFailure(log, errorLog, "File creation failed: " + ex.Message);
                string message = BuildRunLogMessage("File creation failed: " + ex.Message, runLog);
                System.Windows.Forms.MessageBox.Show(message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
        }

        public void ProcessBom(PublishOptions options, Action<string> log, Action<int, int> progress)
        {
            PublishOptions effective = NormalizeOptions(options);
            if (effective == null)
            {
                return;
            }

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                System.Windows.Forms.MessageBox.Show("No active document.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            string startTitle = swModel.GetTitle();
            // Baseline of documents the user actually has open (visible). Hidden docs are often opened by SW as
            // references and should not be treated as "keep open forever" for batch export.
            HashSet<string> initialDocs = GetOpenVisibleDocumentIds();
            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            int modelType = swModel.GetType();

            if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(swDraw, out reference) && reference.Model != null &&
                    reference.Configuration != null)
                {
                    swModel = reference.Model;
                    swConf = reference.Configuration;
                    modelType = swModel.GetType();
                    _swApp.ActivateDoc(swModel.GetTitle());
                }
                else
                {
                    System.Windows.Forms.MessageBox.Show("No reference model found in the drawing.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }
            }

            if (swConf == null)
            {
                System.Windows.Forms.MessageBox.Show("No active configuration.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
            }

            ModelDoc2 rootModel = swModel;
            string rootTitle = swModel.GetTitle();

            ResetCancel();
            try
            {
                string pubFolder = EnsureTrailingSlash(effective.BomFolder);
                if (string.IsNullOrWhiteSpace(pubFolder))
                {
                    System.Windows.Forms.MessageBox.Show("BOM output folder is empty.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }

                Directory.CreateDirectory(pubFolder);
                string bomFolder = Path.Combine(pubFolder, "bom");
                Directory.CreateDirectory(bomFolder);

                string exportTag = Path.Combine(bomFolder, GetFileString(swModel, swConf.Name) + "_" +
                    DateTime.Now.ToString("yyyy_MM_dd_HH_mm_ss"));
                string flatFile = TraverseModel(false, exportTag, effective, log, progress, null);
                string bomFile = exportTag + "_TREEBOM.txt";

                string modelPath = swModel.GetPathName();
                if (string.IsNullOrWhiteSpace(modelPath))
                {
                    System.Windows.Forms.MessageBox.Show("Active document must be saved before exporting BOM.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }

                ThrowIfCancelled();

                HashSet<string> baseline = SnapshotOpenDocIds();

                string template = _swApp.GetUserPreferenceStringValue(
                    (int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly);
                ModelDoc2 assyDoc = _swApp.NewDocument(template, 0, 0, 0) as ModelDoc2;
                AssemblyDoc swAssembly = assyDoc as AssemblyDoc;
                if (assyDoc == null || swAssembly == null)
                {
                    System.Windows.Forms.MessageBox.Show("Failed to create temporary assembly.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
                    return;
                }

                try
                {
                    _swApp.ActivateDoc(assyDoc.GetTitle());
                    swAssembly.AddComponent5(modelPath, 0, string.Empty, false, string.Empty, 0, 0, 0);
                    ModelDoc2 assyModel = _swApp.ActiveDoc as ModelDoc2;
                    if (assyModel == null)
                    {
                        System.Windows.Forms.MessageBox.Show("Failed to activate temporary assembly.", "TinyMRP",
                            System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
                        return;
                    }

                    Configuration assyConfig = assyModel.GetActiveConfiguration() as Configuration;
                    if (assyConfig == null)
                    {
                        System.Windows.Forms.MessageBox.Show("Failed to read assembly configuration.", "TinyMRP",
                            System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
                        return;
                    }

                    SetUnitPreferences(swModel);
                    ThrowIfCancelled();

                    int bomX = 69;
                    int bomY = 69;
                    BomTableAnnotation bomTable = assyModel.Extension.InsertBomTable3(
                        _config.BomTemplatePath,
                        bomX,
                        bomY,
                        (int)swBomType_e.swBomType_Indented,
                        assyConfig.Name,
                        true,
                        (int)swNumberingType_e.swNumberingType_Detailed,
                        true);

                    if (bomTable != null)
                    {
                        ITableAnnotation tableAnn = (ITableAnnotation)bomTable;
                        tableAnn.SaveAsText(bomFile, "\t");
                        TextFileHelper.StripUtf8Bom(bomFile);
                    }
                    else
                    {
                        Log(log, "Failed to create BOM table.");
                    }

                    string zipPath = exportTag + ".zip";
                    string zipFolderName = Path.GetFileName(exportTag);
                    string zipRoot = Path.Combine(
                        Path.GetDirectoryName(exportTag) ?? pubFolder,
                        zipFolderName + "_zip");
                    string innerFolder = Path.Combine(zipRoot, zipFolderName);
                    string bomInZip = Path.Combine(innerFolder, Path.GetFileName(bomFile));
                    string flatInZip = Path.Combine(innerFolder, Path.GetFileName(flatFile));

                    TryDeleteDirectory(zipRoot);
                    Directory.CreateDirectory(innerFolder);
                    MoveFileIfExists(bomFile, bomInZip);
                    MoveFileIfExists(flatFile, flatInZip);

                    if (File.Exists(zipPath))
                    {
                        File.Delete(zipPath);
                    }

                    CreateZipWithFolder(zipPath, zipFolderName, bomInZip, flatInZip);
                    TryDeleteDirectory(zipRoot);
                }
                finally
                {
                    if (assyDoc != null)
                    {
                        ForceCloseDocNoSave(assyDoc, null, "BOM temp assembly close");
                    }
                    EnsureDocBaseline(baseline, log, null, "post BOM temp assembly cleanup");
                }

                System.Windows.Forms.MessageBox.Show("BOM file generation finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("BOM export failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
            }
        }

        public void ProcessUploadPack(PublishOptions options, Action<string> log)
        {
            PublishOptions effective = NormalizeOptions(options);
            if (effective == null)
            {
                return;
            }

            try
            {
                ResetCancel();
                HashSet<string> uploadPackBases;
                List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras;
                string flatFile = TraverseModel(false, string.Empty, effective, log, null, null, null,
                    out uploadPackBases, out uploadPackExtras);
                CreateUploadPack(flatFile, uploadPackBases, uploadPackExtras, effective, log, null);
                System.Windows.Forms.MessageBox.Show("Upload pack created.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("Upload pack failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
        }

        public void NormalizeUnits(Action<string> log)
        {
            NormalizeUnits(log, null);
        }

        public void NormalizeUnits(Action<string> log, Action<int, int> progress)
        {
            ModelDoc2 rootModel = null;
            string rootTitle = string.Empty;
            HashSet<string> initialDocs = null;
            string startTitle = string.Empty;

            try
            {
                ResetCancel();
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs, out startTitle);
                UpdateProgress(progress, 0, entries.Count);

                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();
                    SetUnitPreferences(entry.Model);
                    if (!string.IsNullOrWhiteSpace(entry.Model.GetPathName()))
                    {
                        entry.Model.Save2(true);
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                    CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                }

                Log(log, "Units normalized.");
                System.Windows.Forms.MessageBox.Show("Units normalized.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("Failed to normalize units: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
            }
        }

        public void HideFeatures(HideFeaturesOptions options, Action<string> log, Action<int, int> progress)
        {
            if (options == null || options.FeatureMask == HideFeatureTypeFlags.None)
            {
                System.Windows.Forms.MessageBox.Show("No feature types selected.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                return;
            }

            ModelDoc2 rootModel = null;
            string rootTitle = string.Empty;
            string startTitle = string.Empty;
            HashSet<string> initialDocs = null;
            string rootConfigName = string.Empty;
            string debugLogPath = EnableHideDebugLog
                ? Path.Combine(Path.GetTempPath(), "TinyMRP_hide_features.log")
                : string.Empty;

            try
            {
                ResetCancel();
                LogHideDebug(debugLogPath, "Start hide features.");
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs, out startTitle);
                if (entries.Count == 0)
                {
                    System.Windows.Forms.MessageBox.Show("No model entries to process.", "TinyMRP",
                        System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Warning);
                    return;
                }

                Configuration rootConfig = rootModel.GetActiveConfiguration() as Configuration;
                if (rootConfig != null)
                {
                    rootConfigName = rootConfig.Name;
                }

                int total = CalculateHideTotal(entries, options.AllConfigurations);
                UpdateProgress(progress, 0, total);

                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();

                    if (entry == null || entry.Model == null)
                    {
                        continue;
                    }

                    int docType = entry.Model.GetType();
                    if (docType != (int)swDocumentTypes_e.swDocPART &&
                        docType != (int)swDocumentTypes_e.swDocASSEMBLY)
                    {
                        continue;
                    }

                    string modelLabel = OnlyFile(entry.Model.GetPathName());
                    if (string.IsNullOrWhiteSpace(modelLabel))
                    {
                        modelLabel = entry.Model.GetTitle();
                    }

                    string[] configs = BuildConfigList(entry.Model, options.AllConfigurations, entry.ConfigurationName);
                    foreach (string configName in configs)
                    {
                        ThrowIfCancelled();
                        System.Windows.Forms.Application.DoEvents();

                        _swApp.ActivateDoc(entry.Model.GetTitle());
                        if (!string.IsNullOrWhiteSpace(configName))
                        {
                            entry.Model.ShowConfiguration2(configName);
                        }

                        LogHideDebug(debugLogPath, "Processing " + modelLabel + " [" + configName + "]");
                        if (EnableHideStatusLog)
                        {
                            Log(log, "Hide features: " + modelLabel + " [" + configName + "]");
                        }
                        try
                        {
                            HideFeaturesInModel(entry.Model, options.FeatureMask, debugLogPath);
                            if (options.HideEnvelopes && docType == (int)swDocumentTypes_e.swDocASSEMBLY)
                            {
                                HideEnvelopeComponents(entry.Model, debugLogPath);
                            }
                        }
                        catch (Exception ex)
                        {
                            LogHideDebug(debugLogPath, "Failed " + modelLabel + ": " + ex.Message);
                            if (EnableHideStatusLog)
                            {
                                Log(log, "Hide features failed: " + modelLabel + " (" + ex.Message + ")");
                            }
                        }

                        processed++;
                        UpdateProgress(progress, processed, total);
                    }

                    CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                }

                if (!string.IsNullOrWhiteSpace(rootConfigName))
                {
                    rootModel.ShowConfiguration2(rootConfigName);
                }

                LogHideDebug(debugLogPath, "Hide features finished.");
                System.Windows.Forms.MessageBox.Show("Hide features finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                LogHideDebug(debugLogPath, "Hide features cancelled.");
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                LogHideDebug(debugLogPath, "Hide features error: " + ex.Message);
                System.Windows.Forms.MessageBox.Show("Hide features failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
            }
        }

        public void FreezeDesign(bool freeze, Action<string> log)
        {
            FreezeDesign(freeze, log, null);
        }

        public void FreezeDesign(bool freeze, Action<string> log, Action<int, int> progress)
        {
            ModelDoc2 rootModel = null;
            string rootTitle = string.Empty;
            HashSet<string> initialDocs = null;
            string startTitle = string.Empty;

            try
            {
                ResetCancel();
                var entries = GetEntriesForActiveDoc(true, out rootModel, out rootTitle, out initialDocs, out startTitle);
                UpdateProgress(progress, 0, entries.Count);

                int processed = 0;
                foreach (ModelEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();

                    int docType = entry.Model.GetType();
                    if (docType == (int)swDocumentTypes_e.swDocPART)
                    {
                        bool closeAfter = !ReferenceEquals(entry.Model, rootModel);
                        FreezePart(entry.Model, freeze, closeAfter);
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                    CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                }

                System.Windows.Forms.MessageBox.Show(freeze ? "Freeze finished." : "Unfreeze finished.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (OperationCanceledException)
            {
                System.Windows.Forms.MessageBox.Show("Operation cancelled.", "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                System.Windows.Forms.MessageBox.Show("Freeze failed: " + ex.Message, "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK, System.Windows.Forms.MessageBoxIcon.Error);
            }
            finally
            {
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
            }
        }

        private void FreezeDesignInternal(ModelDoc2 swModel, bool freeze)
        {
            ModelView view = swModel.ActiveView as ModelView;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            if (swModel.FeatureManager != null)
            {
                swModel.FeatureManager.EnableFeatureTree = false;
            }

            int docType = swModel.GetType();
            if (docType == (int)swDocumentTypes_e.swDocPART)
            {
                FreezePart(swModel, freeze);
            }
            else if (docType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                AssemblyDoc assy = swModel as AssemblyDoc;
                if (assy != null)
                {
                    assy.ResolveAllLightWeightComponents(true);
                }
                FreezeTraverseModel(swModel, freeze);
            }
            else if (docType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                if (swDraw != null)
                {
                    View firstView = swDraw.GetFirstView() as View;
                    View modelView = firstView != null ? firstView.GetNextView() as View : null;
                    ModelDoc2 refModel = modelView != null ? modelView.ReferencedDocument : null;
                    if (refModel != null)
                    {
                        FreezeDesignInternal(refModel, freeze);
                    }
                }
            }

            if (swModel.FeatureManager != null)
            {
                swModel.FeatureManager.EnableFeatureTree = true;
            }

            if (view != null)
            {
                view.EnableGraphicsUpdate = true;
            }
        }

        private void FreezePart(ModelDoc2 model, bool freeze)
        {
            FreezePart(model, freeze, true);
        }

        private void FreezePart(ModelDoc2 model, bool freeze, bool closeAfter)
        {
            PartDoc part = model as PartDoc;
            if (part == null)
            {
                return;
            }

            _swApp.ActivateDoc(model.GetTitle());

            ModelView view = model.ActiveView as ModelView;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = false;
            }

            if (HasCutList(model))
            {
                model.Extension.SetUserPreferenceToggle(
                    (int)swUserPreferenceToggle_e.swWeldmentEnableAutomaticUpdate, 0, !freeze);
            }

            FeatureManager featMgr = model.FeatureManager;
            if (featMgr != null)
            {
                if (freeze)
                {
                    featMgr.EditFreeze2((int)swMoveFreezeBarTo_e.swMoveFreezeBarToEnd, string.Empty, true, true);
                }
                else
                {
                    featMgr.EditFreeze2((int)swMoveFreezeBarTo_e.swMoveFreezeBarToTop, string.Empty, true, true);
                    model.ForceRebuild3(true);
                }
            }

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = true;
            }

            if (view != null)
            {
                view.EnableGraphicsUpdate = true;
            }

            model.Save2(true);
            if (closeAfter)
            {
                ForceCloseDocNoSave(model, null, "FreezePart close");
            }
        }

        private void FreezeTraverseModel(ModelDoc2 assemblyModel, bool freeze)
        {
            Configuration config = assemblyModel.GetActiveConfiguration() as Configuration;
            if (config == null)
            {
                return;
            }

            Component2 root = config.GetRootComponent() as Component2;
            if (root == null)
            {
                return;
            }

            object[] comps = root.GetChildren() as object[];
            if (comps == null)
            {
                return;
            }

            foreach (object obj in comps)
            {
                Component2 comp = obj as Component2;
                if (comp == null || comp.IsSuppressed())
                {
                    continue;
                }

                ModelDoc2 compModel = comp.GetModelDoc2() as ModelDoc2;
                if (compModel == null)
                {
                    continue;
                }

                FreezePart(compModel, freeze);
                FreezeTraverseModel(compModel, freeze);
            }
        }

        private bool HasCutList(ModelDoc2 model)
        {
            Feature feat = model.FirstFeature() as Feature;
            while (feat != null)
            {
                if (string.Equals(feat.GetTypeName(), "CutListFolder", StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }

                feat = feat.GetNextFeature() as Feature;
            }

            return false;
        }

        private bool TryGetActiveModel(out ModelDoc2 model, out Configuration config, out string startTitle)
        {
            model = _swApp.ActiveDoc as ModelDoc2;
            config = null;
            startTitle = string.Empty;
            if (model == null)
            {
                return false;
            }

            startTitle = model.GetTitle();
            config = model.GetActiveConfiguration() as Configuration;

            if (model.GetType() == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc draw = model as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(draw, out reference) && reference.Model != null)
                {
                    model = reference.Model;
                    config = reference.Configuration;
                    _swApp.ActivateDoc(model.GetTitle());
                }
            }

            return config != null;
        }

        private string[] BuildConfigList(ModelDoc2 model, bool allConfigs, string fallback)
        {
            if (model == null)
            {
                return new[] { fallback ?? string.Empty };
            }

            if (allConfigs)
            {
                string[] configs = ToStringArray(model.GetConfigurationNames());
                if (configs != null && configs.Length > 0)
                {
                    return configs;
                }
            }

            if (!string.IsNullOrWhiteSpace(fallback))
            {
                return new[] { fallback };
            }

            Configuration activeConfig = model.GetActiveConfiguration() as Configuration;
            if (activeConfig != null && !string.IsNullOrWhiteSpace(activeConfig.Name))
            {
                return new[] { activeConfig.Name };
            }

            return new[] { string.Empty };
        }

        private int CalculateHideTotal(List<ModelEntry> entries, bool allConfigs)
        {
            if (entries == null || entries.Count == 0)
            {
                return 1;
            }

            int total = 0;
            foreach (ModelEntry entry in entries)
            {
                if (entry == null || entry.Model == null)
                {
                    continue;
                }

                int docType = entry.Model.GetType();
                if (docType != (int)swDocumentTypes_e.swDocPART &&
                    docType != (int)swDocumentTypes_e.swDocASSEMBLY)
                {
                    continue;
                }

                string[] configs = BuildConfigList(entry.Model, allConfigs, entry.ConfigurationName);
                total += configs.Length > 0 ? configs.Length : 1;
            }

            return total > 0 ? total : 1;
        }

        private void HideFeaturesInModel(ModelDoc2 model, HideFeatureTypeFlags mask, string debugPath)
        {
            if (model == null)
            {
                return;
            }

            LogHideDebug(debugPath, "Collect features in " + model.GetTitle());

            ModelView view = model.ActiveView as ModelView;
            bool prevGraphics = view != null && view.EnableGraphicsUpdate;
            if (view != null)
            {
                view.EnableGraphicsUpdate = false;
            }

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = false;
            }

            var features = new List<Feature>();
            Feature first = model.FirstFeature() as Feature;
            CollectFeatures(first, mask, features, debugPath);
            LogHideDebug(debugPath, "Collected " + features.Count + " features in " + model.GetTitle());
            BlankFeatures(model, features, debugPath);

            if (model.FeatureManager != null)
            {
                model.FeatureManager.EnableFeatureTree = true;
            }

            if (view != null)
            {
                view.EnableGraphicsUpdate = prevGraphics;
            }

            if (!string.IsNullOrWhiteSpace(model.GetPathName()))
            {
                model.Save2(true);
            }
        }

        private void HideEnvelopeComponents(ModelDoc2 model, string debugPath)
        {
            if (model == null || model.GetType() != (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                return;
            }

            Configuration conf = model.GetActiveConfiguration() as Configuration;
            Component2 root = conf != null ? conf.GetRootComponent() as Component2 : null;
            if (root == null)
            {
                return;
            }

            HideEnvelopeComponentsRecursive(root, debugPath);
        }

        private void HideEnvelopeComponentsRecursive(Component2 parent, string debugPath)
        {
            if (parent == null)
            {
                return;
            }

            object[] children = parent.GetChildren() as object[];
            if (children == null)
            {
                return;
            }

            foreach (object obj in children)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                Component2 child = obj as Component2;
                if (child == null || child.IsSuppressed())
                {
                    continue;
                }

                bool isEnvelope = IsEnvelopeComponent(child);
                if (isEnvelope)
                {
                    bool hidden = TryHideComponent(child);
                    LogHideDebug(debugPath, "Hide envelope " + child.Name2 + " -> " + hidden);
                }

                HideEnvelopeComponentsRecursive(child, debugPath);
            }
        }

        private bool IsEnvelopeComponent(Component2 comp)
        {
            if (comp == null)
            {
                return false;
            }

            object target = comp;
            Type type = target.GetType();

            object result = TryInvokeMember(type, target, "IsEnvelope", BindingFlags.GetProperty | BindingFlags.InvokeMethod);
            if (result is bool)
            {
                return (bool)result;
            }

            if (result is int)
            {
                return (int)result != 0;
            }

            return false;
        }

        private bool TryHideComponent(Component2 comp)
        {
            if (comp == null)
            {
                return false;
            }

            object target = comp;
            Type type = target.GetType();

            if (TrySetMember(type, target, "Visible", false) ||
                TrySetMember(type, target, "Visible", 0))
            {
                return true;
            }

            if (TryInvokeVoidMember(type, target, "SetVisible", false) ||
                TryInvokeVoidMember(type, target, "SetVisible", 0))
            {
                return true;
            }

            if (TryInvokeVoidMember(type, target, "SetVisibility", 0))
            {
                return true;
            }

            return false;
        }

        private object TryInvokeMember(Type type, object target, string name, BindingFlags flags, params object[] args)
        {
            try
            {
                return type.InvokeMember(name, flags | BindingFlags.Instance | BindingFlags.Public, null, target, args);
            }
            catch
            {
                return null;
            }
        }

        private bool TryInvokeVoidMember(Type type, object target, string name, params object[] args)
        {
            try
            {
                type.InvokeMember(name, BindingFlags.InvokeMethod | BindingFlags.Instance | BindingFlags.Public,
                    null, target, args);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private bool TrySetMember(Type type, object target, string name, object value)
        {
            try
            {
                type.InvokeMember(name, BindingFlags.SetProperty | BindingFlags.Instance | BindingFlags.Public,
                    null, target, new[] { value });
                return true;
            }
            catch
            {
                return false;
            }
        }

        private void CollectFeatures(Feature feature, HideFeatureTypeFlags mask, List<Feature> result, string debugPath)
        {
            Feature current = feature;
            while (current != null)
            {
                try
                {
                    if (ShouldHideFeature(current, mask))
                    {
                        LogHideDebug(debugPath, "Queue feature " + SafeFeatureLabel(current));
                        result.Add(current);
                    }
                }
                catch (Exception ex)
                {
                    LogHideDebug(debugPath, "Feature check failed: " + ex.Message);
                }

                Feature next = null;
                try
                {
                    next = current.GetNextFeature() as Feature;
                }
                catch (Exception ex)
                {
                    LogHideDebug(debugPath, "GetNextFeature failed: " + ex.Message);
                    next = null;
                }

                current = next;
            }
        }

        private bool ShouldHideFeature(Feature feature, HideFeatureTypeFlags mask)
        {
            if (feature == null)
            {
                return false;
            }

            int visible = feature.Visible;
            if (visible != (int)swVisibilityState_e.swVisibilityStateShown &&
                visible != (int)swVisibilityState_e.swVisibilityStateUnknown)
            {
                return false;
            }

            string typeName = feature.GetTypeName();
            HideFeatureTypeFlags typeFlag = MapFeatureType(typeName);
            return typeFlag != HideFeatureTypeFlags.None && (mask & typeFlag) == typeFlag;
        }

        private HideFeatureTypeFlags MapFeatureType(string typeName)
        {
            switch (typeName)
            {
                case "OriginProfileFeature":
                    return HideFeatureTypeFlags.Origin;
                case "RefPlane":
                    return HideFeatureTypeFlags.RefPlane;
                case "RefAxis":
                    return HideFeatureTypeFlags.RefAxis;
                case "RefPoint":
                    return HideFeatureTypeFlags.RefPoint;
                case "CoordSys":
                    return HideFeatureTypeFlags.CoordSys;
                case "ProfileFeature":
                    return HideFeatureTypeFlags.Sketch2D;
                case "3DProfileFeature":
                    return HideFeatureTypeFlags.Sketch3D;
                case "3DSplineCurve":
                    return HideFeatureTypeFlags.Spline3D;
                case "CompositeCurve":
                    return HideFeatureTypeFlags.CompositeCurve;
                case "Helix":
                    return HideFeatureTypeFlags.Helix;
                default:
                    return HideFeatureTypeFlags.None;
            }
        }

        private void BlankFeatures(ModelDoc2 model, List<Feature> features, string debugPath)
        {
            if (model == null || features == null || features.Count == 0)
            {
                return;
            }

            int count = 0;
            bool append = false;

            foreach (Feature feat in features)
            {
                if (feat == null)
                {
                    continue;
                }

                LogHideDebug(debugPath, "Select feature " + SafeFeatureLabel(feat));
                bool selected = false;
                try
                {
                    selected = feat.Select2(append, 0);
                }
                catch
                {
                    selected = false;
                }

                if (!selected)
                {
                    append = false;
                    continue;
                }

                count++;
                append = true;

                if (count % 25 == 0)
                {
                    LogHideDebug(debugPath, "Blank batch at " + count);
                    try
                    {
                        model.BlankRefGeom();
                        model.BlankSketch();
                    }
                    catch (Exception ex)
                    {
                        LogHideDebug(debugPath, "Blank batch failed: " + ex.Message);
                    }
                    append = false;
                }
            }

            LogHideDebug(debugPath, "Blank final at " + count);
            try
            {
                model.BlankRefGeom();
                model.BlankSketch();
            }
            catch (Exception ex)
            {
                LogHideDebug(debugPath, "Blank final failed: " + ex.Message);
            }

            if (features.Count > 0)
            {
                Feature first = features[0];
                try
                {
                    first.Select2(false, 0);
                    first.DeSelect();
                }
                catch (Exception ex)
                {
                    LogHideDebug(debugPath, "Deselect failed: " + ex.Message);
                }
            }
        }

        private string SafeFeatureLabel(Feature feature)
        {
            if (feature == null)
            {
                return "<null>";
            }

            string name = string.Empty;
            try
            {
                name = feature.Name;
            }
            catch
            {
                name = string.Empty;
            }

            string type = string.Empty;
            try
            {
                type = feature.GetTypeName();
            }
            catch
            {
                type = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(name))
            {
                name = "<unnamed>";
            }

            if (string.IsNullOrWhiteSpace(type))
            {
                type = "<unknown>";
            }

            return name + " [" + type + "]";
        }

        private string TraverseModel(bool createFiles, string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress, Action<int, int> deliverablesProgress)
        {
            HashSet<string> ignored;
            List<UploadPackBuilder.AssociatedFilesBundle> ignoredExtras;
            return TraverseModel(createFiles, exportTag, options, log, flatBomProgress, deliverablesProgress, null,
                out ignored, out ignoredExtras);
        }

        private string TraverseModel(bool createFiles, string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress, Action<int, int> deliverablesProgress, Action<string> errorLog,
            out HashSet<string> uploadPackBases, out List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras)
        {
            uploadPackBases = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            uploadPackExtras = null;
            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            string startTitle = swModel.GetTitle();
            // Keep only user-visible docs as the baseline; hidden reference docs are aggressively closed by leak-guard.
            HashSet<string> initialDocs = GetOpenVisibleDocumentIds();

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            int modelType = swModel.GetType();
            if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(swDraw, out reference))
                {
                    swModel = reference.Model;
                    swConf = reference.Configuration;
                    modelType = swModel.GetType();
                    _swApp.ActivateDoc(swModel.GetTitle());
                }
            }

            if (swConf == null)
            {
                throw new InvalidOperationException("No active configuration.");
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
            }

            string pubFolder = EnsureTrailingSlash(options.BomFolder);
            if (string.IsNullOrWhiteSpace(pubFolder))
            {
                throw new InvalidOperationException("BOM folder is empty.");
            }

            string bomFolder = Path.Combine(pubFolder, "bom");
            Directory.CreateDirectory(bomFolder);

            string deliverablesFolder = EnsureTrailingSlash(options.DeliverablesFolder);
            if (string.IsNullOrWhiteSpace(deliverablesFolder))
            {
                throw new InvalidOperationException("Deliverables folder is empty.");
            }

            Directory.CreateDirectory(deliverablesFolder);
            EnsureMediaFolders(deliverablesFolder);

            ModelView view = swModel.ActiveView as ModelView;
            bool prevGraphics = view != null && view.EnableGraphicsUpdate;
            int prevBgAppearance = _swApp.GetUserPreferenceIntegerValue(
                (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance);
            int prevColorScheme = _swApp.GetUserPreferenceIntegerValue(
                (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme);
            int prevViewport = _swApp.GetUserPreferenceIntegerValue(
                (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground);

            ModelDoc2 rootModel = swModel;
            string rootTitle = swModel.GetTitle();

            DebugExport(errorLog,
                "TraverseModel start createFiles=" + createFiles +
                " startTitle=" + (startTitle ?? string.Empty) +
                " rootTitle=" + (rootTitle ?? string.Empty) +
                " rootPath=" + (rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty) +
                " initialVisibleDocs=" + (initialDocs != null ? initialDocs.Count : 0) +
                " openDocs=" + SnapshotOpenDocIds().Count);

            try
            {
                if (view != null)
                {
                    view.EnableGraphicsUpdate = false;
                }

                if (swModel.FeatureManager != null)
                {
                    swModel.FeatureManager.EnableFeatureTree = false;
                }

                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance, 0);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme,
                    (int)swSystemColorsCurrentColorScheme_e.swSystemColorsCurrentColorSchemeBlueHighlight);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground, 16777215);

                // Proactively unload references from any kept assemblies (esp. root) so leak-guard can close
                // hidden reference docs quickly instead of fighting "resolved" state re-opening children.
                var keepAtStart = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                if (initialDocs != null)
                {
                    keepAtStart.UnionWith(initialDocs);
                }
                AddDocToKeepSet(keepAtStart, rootModel, rootTitle);
                TryLightweightAssembliesInKeepSet(keepAtStart, log, errorLog, "traverse start", allowCancel: true);

                var entries = BuildBatchEntries(swModel, swConf, modelType, options.TopLevelOnly);

                string outputFile;
                if (string.IsNullOrWhiteSpace(exportTag))
                {
                    outputFile = Path.Combine(bomFolder,
                        GetFileString(swModel, swConf.Name) + "_" +
                        DateTime.Now.ToString("yyyy_MM_dd_HH_mm_ss") + "_FLATBOM.txt");
                }
                else
                {
                    outputFile = exportTag + "_FLATBOM.txt";
                }

                if (options != null && options.CreateUploadPack && options.UploadPackIncludeExtras)
                {
                    uploadPackExtras = new List<UploadPackBuilder.AssociatedFilesBundle>();
                }

                UpdateProgress(flatBomProgress, 0, entries.Count);
                WriteFlatBom(outputFile, entries, log, flatBomProgress, initialDocs, rootModel, rootTitle,
                    uploadPackBases, uploadPackExtras, errorLog);
                ThrowIfCancelled();

                if (createFiles)
                {
                    if (!AnyDeliverablesSelected(options))
                    {
                        UpdateProgress(deliverablesProgress, 0, 0);
                    }
                    else
                    {
                        List<FlatBomEntry> flatEntries = ReadFlatBomEntries(outputFile, log, errorLog);
                        List<DeliverablePlan> plans = BuildDeliverablePlans(flatEntries, deliverablesFolder, options, log, errorLog);
                        DebugExport(errorLog,
                            "Deliverables planning: flatEntries=" + (flatEntries != null ? flatEntries.Count : 0) +
                            " plans=" + (plans != null ? plans.Count : 0));

                        if ((flatEntries == null || flatEntries.Count == 0) && entries.Count > 0)
                        {
                            LogExportFailure(log, errorLog,
                                "Deliverables planning skipped: flat BOM parse empty; using direct traversal.");
                            ProcessDeliverablesLegacy(entries, deliverablesFolder, options, log, errorLog,
                                initialDocs, rootModel, rootTitle, deliverablesProgress);
                        }
                        else if (plans == null || plans.Count == 0)
                        {
                            Log(log, "No deliverables to export (all selected files already exist).");
                            UpdateProgress(deliverablesProgress, 0, 0);
                        }
                        else
                        {
                            ProcessDeliverablePlans(plans ?? new List<DeliverablePlan>(), deliverablesFolder, options, log,
                                errorLog, initialDocs, rootModel, rootTitle, deliverablesProgress);
                        }
                    }
                }

                return outputFile;
            }
            finally
            {
                if (swModel.FeatureManager != null)
                {
                    swModel.FeatureManager.EnableFeatureTree = true;
                }

                if (view != null)
                {
                    view.EnableGraphicsUpdate = prevGraphics;
                }

                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance, prevBgAppearance);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme, prevColorScheme);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground, prevViewport);

                Exception baselineError = null;
                try
                {
                    var keep = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                    if (initialDocs != null)
                    {
                        keep.UnionWith(initialDocs);
                    }
                    AddDocToKeepSet(keep, rootModel, rootTitle);
                    EnsureDocBaseline(keep, log, errorLog, "final cleanup");
                }
                catch (Exception ex)
                {
                    baselineError = ex;
                }

                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);

                DebugExport(errorLog,
                    "TraverseModel end startTitle=" + (startTitle ?? string.Empty) +
                    " openDocs=" + SnapshotOpenDocIds().Count);

                if (baselineError != null)
                {
                    throw baselineError;
                }
            }
        }

        private void CreateUploadPack(
            string flatBomPath,
            HashSet<string> uploadPackBases,
            List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras,
            PublishOptions options,
            Action<string> log,
            Action<string> errorLog)
        {
            if (string.IsNullOrWhiteSpace(flatBomPath))
            {
                Log(log, "Upload pack skipped: missing flat BOM path.");
                return;
            }

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                Log(log, "Upload pack skipped: no active model.");
                return;
            }

            Configuration config = swModel.GetActiveConfiguration() as Configuration;
            if (config == null)
            {
                Log(log, "Upload pack skipped: no active configuration.");
                return;
            }

            string treeBomPath = BuildTreeBomPath(flatBomPath);
            TryBuildTreeBom(swModel, treeBomPath, log, errorLog);

            string deliverablesRoot = EnsureTrailingSlash(options.DeliverablesFolder);
            if (string.IsNullOrWhiteSpace(deliverablesRoot))
            {
                Log(log, "Upload pack skipped: deliverables folder missing.");
                return;
            }
            deliverablesRoot = deliverablesRoot.TrimEnd('\\', '/');

            string bomFolder = Path.GetDirectoryName(flatBomPath) ?? string.Empty;
            if (string.IsNullOrWhiteSpace(bomFolder))
            {
                bomFolder = EnsureTrailingSlash(options.BomFolder);
                if (!string.IsNullOrWhiteSpace(bomFolder))
                {
                    bomFolder = bomFolder.TrimEnd('\\', '/');
                }
            }
            if (string.IsNullOrWhiteSpace(bomFolder))
            {
                bomFolder = deliverablesRoot;
            }
            try
            {
                if (!string.IsNullOrWhiteSpace(bomFolder))
                {
                    Directory.CreateDirectory(bomFolder);
                }
            }
            catch
            {
                // ignore folder creation errors
            }

            string zipName = GetFileString(swModel, config.Name) + "_UPLOADPACK_" +
                DateTime.Now.ToString("yyyy_MM_dd_HH_mm_ss") + ".zip";
            string zipPath = Path.Combine(bomFolder, zipName);

            HashSet<string> allowedGroups = BuildUploadPackGroups(options);
            IEnumerable<UploadPackBuilder.AssociatedFilesBundle> extras = options.UploadPackIncludeExtras
                ? uploadPackExtras
                : null;

            bool built = false;
            try
            {
                UploadPackBuilder.Build(
                    zipPath,
                    deliverablesRoot,
                    flatBomPath,
                    treeBomPath,
                    extras,
                    log,
                    uploadPackBases,
                    allowedGroups);
                built = true;

                Log(log, "Upload pack created: " + zipPath);
            }
            finally
            {
                if (built)
                {
                    TryDeleteFile(flatBomPath);
                    TryDeleteFile(treeBomPath);
                }
            }
        }

        private AssociatedFilesPayload ReadAssociatedFiles(ModelDoc2 model, string configName)
        {
            if (model == null)
            {
                return new AssociatedFilesPayload();
            }

            string raw = GetRawProperty(model, configName, AssociatedFilesPayload.PropertyName);
            if (string.IsNullOrWhiteSpace(raw))
            {
                raw = GetRawProperty(model, string.Empty, AssociatedFilesPayload.PropertyName);
            }
            AssociatedFilesPayload payload = AssociatedFilesPayload.FromJson(raw);
            if (payload.Files == null)
            {
                payload.Files = new List<AssociatedFileEntry>();
            }
            return payload;
        }

        private string BuildTreeBomPath(string flatBomPath)
        {
            if (string.IsNullOrWhiteSpace(flatBomPath))
            {
                return string.Empty;
            }

            const string suffix = "_FLATBOM.txt";
            if (flatBomPath.EndsWith(suffix, StringComparison.OrdinalIgnoreCase))
            {
                return flatBomPath.Substring(0, flatBomPath.Length - suffix.Length) + "_TREEBOM.txt";
            }
            return flatBomPath + "_TREEBOM.txt";
        }

        private HashSet<string> BuildUploadPackGroups(PublishOptions options)
        {
            var groups = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (options == null)
            {
                return groups;
            }

            if (!options.UploadPackIncludeDeliverables)
            {
                return groups;
            }

            if (options.ExportPngModel || options.ExportPngDrawing)
            {
                groups.Add("png");
            }
            if (options.ExportPdf)
            {
                groups.Add("pdf");
            }
            if (options.ExportStep)
            {
                groups.Add("step");
            }
            if (options.ExportEdrawing || options.ExportEdrawingDrawing)
            {
                groups.Add("edr");
            }
            if (options.Export3mf)
            {
                groups.Add("3mf");
            }
            if (options.ExportPly)
            {
                groups.Add("ply");
            }
            if (options.ExportStl)
            {
                groups.Add("stl");
            }

            return groups;
        }

        private bool TryBuildTreeBom(ModelDoc2 rootModel, string treeBomPath, Action<string> log, Action<string> errorLog)
        {
            if (rootModel == null || string.IsNullOrWhiteSpace(treeBomPath))
            {
                return false;
            }

            string modelPath = rootModel.GetPathName();
            if (string.IsNullOrWhiteSpace(modelPath))
            {
                Log(log, "Upload pack: active document must be saved to build TREEBOM.");
                return false;
            }

            HashSet<string> baseline = SnapshotOpenDocIds();

            string template = _swApp.GetUserPreferenceStringValue(
                (int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly);
            ModelDoc2 assyDoc = _swApp.NewDocument(template, 0, 0, 0) as ModelDoc2;
            AssemblyDoc swAssembly = assyDoc as AssemblyDoc;
            if (assyDoc == null || swAssembly == null)
            {
                Log(log, "Upload pack: failed to create temp assembly for TREEBOM.");
                return false;
            }

            try
            {
                _swApp.ActivateDoc(assyDoc.GetTitle());
                swAssembly.AddComponent5(modelPath, 0, string.Empty, false, string.Empty, 0, 0, 0);
                ModelDoc2 assyModel = _swApp.ActiveDoc as ModelDoc2;
                if (assyModel == null)
                {
                    Log(log, "Upload pack: failed to activate temp assembly.");
                    return false;
                }

                Configuration assyConfig = assyModel.GetActiveConfiguration() as Configuration;
                if (assyConfig == null)
                {
                    Log(log, "Upload pack: failed to read assembly configuration.");
                    return false;
                }

                SetUnitPreferences(assyModel);

                string treeDir = Path.GetDirectoryName(treeBomPath);
                if (!string.IsNullOrWhiteSpace(treeDir))
                {
                    Directory.CreateDirectory(treeDir);
                }
                int bomX = 69;
                int bomY = 69;
                BomTableAnnotation bomTable = assyModel.Extension.InsertBomTable3(
                    _config.BomTemplatePath,
                    bomX,
                    bomY,
                    (int)swBomType_e.swBomType_Indented,
                    assyConfig.Name,
                    true,
                    (int)swNumberingType_e.swNumberingType_Detailed,
                    true);

                if (bomTable != null)
                {
                    ITableAnnotation tableAnn = (ITableAnnotation)bomTable;
                    tableAnn.SaveAsText(treeBomPath, "\t");
                    TextFileHelper.StripUtf8Bom(treeBomPath);
                    return true;
                }

                Log(log, "Upload pack: failed to create BOM table.");
                return false;
            }
            finally
            {
                ForceCloseDocNoSave(assyDoc, errorLog, "TREEBOM temp assembly close");
                EnsureDocBaseline(baseline, log, errorLog, "post TREEBOM temp assembly cleanup");
            }
        }

        private List<ModelEntry> GetEntriesForActiveDoc(bool includeChildren, out ModelDoc2 rootModel,
            out string rootTitle, out HashSet<string> initialDocs, out string startTitle)
        {
            ThrowIfCancelled();

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            startTitle = swModel.GetTitle();
            // Keep only user-visible docs as the baseline; hidden reference docs are aggressively closed by leak-guard.
            initialDocs = GetOpenVisibleDocumentIds();

            Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
            int modelType = swModel.GetType();
            if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                DrawingDoc swDraw = swModel as DrawingDoc;
                DrawingReference reference;
                if (TryGetDrawingReference(swDraw, out reference) && reference.Model != null)
                {
                    swModel = reference.Model;
                    swConf = reference.Configuration;
                    modelType = swModel.GetType();
                    _swApp.ActivateDoc(swModel.GetTitle());
                }
            }

            if (swConf == null)
            {
                throw new InvalidOperationException("No active configuration.");
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
            }

            rootModel = swModel;
            rootTitle = swModel.GetTitle();

            var entries = new List<ModelEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            AddModelEntry(swModel, swConf.Name, entries, seen, false);

            if (includeChildren && modelType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                AssemblyDoc assy = swModel as AssemblyDoc;
                if (assy != null)
                {
                    assy.ResolveAllLightWeightComponents(true);
                }

                Component2 root = swConf.GetRootComponent() as Component2;
                TraverseComponents(root, entries, seen);
            }

            return entries;
        }

        private void AddModelEntry(ModelDoc2 model, string configName, List<ModelEntry> entries, HashSet<string> seen, bool prepend)
        {
            ThrowIfCancelled();
            string path = model.GetPathName();
            if (string.IsNullOrWhiteSpace(path))
            {
                path = model.GetTitle();
            }

            string key = path + configName + GetEvalProperty(model, configName, "revision");
            if (!seen.Add(key))
            {
                return;
            }

            var entry = new ModelEntry
            {
                Model = model,
                ConfigurationName = configName
            };

            if (prepend)
            {
                entries.Insert(0, entry);
            }
            else
            {
                entries.Add(entry);
            }
        }

        private void TraverseComponents(Component2 parent, List<ModelEntry> entries, HashSet<string> seen)
        {
            if (parent == null)
            {
                return;
            }

            object[] children = parent.GetChildren() as object[];
            if (children == null)
            {
                return;
            }

            foreach (object obj in children)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();
                Component2 child = obj as Component2;
                if (child == null)
                {
                    continue;
                }

                if (child.IsSuppressed() || child.ExcludeFromBOM)
                {
                    continue;
                }

                ModelDoc2 childModel = child.GetModelDoc2() as ModelDoc2;
                if (childModel == null)
                {
                    continue;
                }

                string confName = child.ReferencedConfiguration;
                AddModelEntry(childModel, confName, entries, seen, true);
                TraverseComponents(child, entries, seen);
            }
        }

        private List<BatchEntry> BuildBatchEntries(ModelDoc2 rootModel, Configuration rootConfig, int modelType, bool topLevelOnly)
        {
            var entries = new List<BatchEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            string rootConfigName = rootConfig != null ? rootConfig.Name : string.Empty;
            AddBatchEntry(rootModel.GetPathName(), rootModel.GetTitle(), rootConfigName, true, entries, seen, false);

            if (modelType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                if (!topLevelOnly && rootConfig != null)
                {
                    Component2 root = rootConfig.GetRootComponent() as Component2;
                    TraverseComponentRefs(root, entries, seen);
                }
            }

            return entries;
        }

        private void AddBatchEntry(string path, string title, string configName, bool isRoot,
            List<BatchEntry> entries, HashSet<string> seen, bool prepend)
        {
            ThrowIfCancelled();
            string keyPath = !string.IsNullOrWhiteSpace(path) ? path : (title ?? string.Empty);
            string key = keyPath + "|" + (configName ?? string.Empty);
            if (!seen.Add(key))
            {
                return;
            }

            var entry = new BatchEntry
            {
                ModelPath = path ?? string.Empty,
                ModelTitle = title ?? string.Empty,
                ConfigurationName = configName ?? string.Empty,
                IsRoot = isRoot
            };

            if (prepend)
            {
                entries.Insert(0, entry);
            }
            else
            {
                entries.Add(entry);
            }
        }

        private void TraverseComponentRefs(Component2 parent, List<BatchEntry> entries, HashSet<string> seen)
        {
            if (parent == null)
            {
                return;
            }

            object[] children = parent.GetChildren() as object[];
            if (children == null)
            {
                return;
            }

            foreach (object obj in children)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();
                Component2 child = obj as Component2;
                if (child == null)
                {
                    continue;
                }

                if (child.IsSuppressed() || child.ExcludeFromBOM)
                {
                    continue;
                }

                string confName = child.ReferencedConfiguration;
                string path = string.Empty;
                string title = string.Empty;
                try
                {
                    path = child.GetPathName();
                }
                catch
                {
                    path = string.Empty;
                }

                if (string.IsNullOrWhiteSpace(path))
                {
                    ModelDoc2 childModel = child.GetModelDoc2() as ModelDoc2;
                    if (childModel != null)
                    {
                        try
                        {
                            path = childModel.GetPathName();
                            title = childModel.GetTitle();
                        }
                        catch
                        {
                            path = string.Empty;
                        }
                    }
                }

                AddBatchEntry(path, title, confName, false, entries, seen, true);
                TraverseComponentRefs(child, entries, seen);
            }
        }

        private ModelDoc2 ResolveBatchModel(BatchEntry entry, ModelDoc2 rootModel, out bool openedHere)
        {
            return ResolveBatchModel(entry, rootModel, null, out openedHere);
        }

        private ModelDoc2 ResolveBatchModel(BatchEntry entry, ModelDoc2 rootModel, Action<string> errorLog, out bool openedHere)
        {
            openedHere = false;
            if (entry == null)
            {
                return null;
            }
            if (entry.IsRoot && rootModel != null)
            {
                DebugExport(errorLog, "ResolveBatchModel: using root model: " + DescribeModel(rootModel.GetPathName(), rootModel.GetTitle()));
                TryShowConfiguration(rootModel, entry.ConfigurationName);
                return rootModel;
            }

            ModelDoc2 openDoc = FindOpenDocument(entry.ModelPath, entry.ModelTitle);
            if (openDoc != null)
            {
                string reuseKey = !string.IsNullOrWhiteSpace(entry.ModelPath)
                    ? entry.ModelPath
                    : (entry.ModelTitle ?? string.Empty);
                DebugExportOnce(errorLog, "ResolveBatchModel: reuse|" + reuseKey,
                    "ResolveBatchModel: reusing already-open model: " + DescribeModel(entry.ModelPath, entry.ModelTitle));
                TryShowConfiguration(openDoc, entry.ConfigurationName);
                return openDoc;
            }

            if (!string.IsNullOrWhiteSpace(entry.ModelPath) && File.Exists(entry.ModelPath))
            {
                int errors = 0;
                int warnings = 0;
                int docType = DocumentTypeFromPath(entry.ModelPath);
                int openOptions = (int)swOpenDocOptions_e.swOpenDocOptions_Silent |
                                  (int)swOpenDocOptions_e.swOpenDocOptions_ReadOnly;
                ModelDoc2 opened = null;
                DebugExport(errorLog, "ResolveBatchModel: opening " + entry.ModelPath + " type=" + docType +
                                     " options=" + openOptions);
                using (new ExportDialogSuppressionScope(_swApp))
                using (new ExternalReferenceBatchOpenScope(_swApp))
                {
                    opened = _swApp.OpenDoc6(entry.ModelPath, docType,
                        openOptions, string.Empty, ref errors, ref warnings) as ModelDoc2;
                }
                if (opened != null)
                {
                    openedHere = true;
                    DebugExport(errorLog, "ResolveBatchModel: opened OK title=" + opened.GetTitle());
                    TryShowConfiguration(opened, entry.ConfigurationName);
                }
                else
                {
                    DebugExport(errorLog, "ResolveBatchModel: open FAILED " + entry.ModelPath +
                                         " errors=" + errors + " warnings=" + warnings);
                }
                return opened;
            }

            return null;
        }

        private ModelDoc2 FindOpenDocument(string path, string title)
        {
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                try
                {
                    string docPath = doc.GetPathName();
                    if (!string.IsNullOrWhiteSpace(path) &&
                        !string.IsNullOrWhiteSpace(docPath) &&
                        string.Equals(docPath, path, StringComparison.OrdinalIgnoreCase))
                    {
                        return doc;
                    }

                    if (string.IsNullOrWhiteSpace(path) && !string.IsNullOrWhiteSpace(title))
                    {
                        string docTitle = doc.GetTitle();
                        string docTitleNorm = NormalizeDocTitleForClose(docTitle);
                        string titleNorm = NormalizeDocTitleForClose(title);
                        if (!string.IsNullOrWhiteSpace(docTitleNorm) &&
                            string.Equals(docTitleNorm, titleNorm, StringComparison.OrdinalIgnoreCase))
                        {
                            return doc;
                        }
                    }
                }
                catch
                {
                    // ignore lookup errors
                }
            }

            return null;
        }

        private void CloseBatchModel(ModelDoc2 model, BatchEntry entry, HashSet<string> initialDocs,
            ModelDoc2 rootModel, string rootTitle, bool openedHere)
        {
            if (model == null || entry == null)
            {
                return;
            }

            if (entry.IsRoot || ReferenceEquals(model, rootModel))
            {
                return;
            }

            string id = GetDocumentId(model);
            if (!string.IsNullOrWhiteSpace(id) && initialDocs != null && initialDocs.Contains(id))
            {
                return;
            }

            string title = string.Empty;
            try
            {
                title = model.GetTitle();
            }
            catch
            {
                title = string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(rootTitle) &&
                string.Equals(title, rootTitle, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            if (!openedHere && !string.IsNullOrWhiteSpace(id) && initialDocs != null && initialDocs.Contains(id))
            {
                return;
            }

            ForceCloseDocNoSave(model);
        }

        private int DocumentTypeFromPath(string path)
        {
            string ext = Path.GetExtension(path ?? string.Empty).ToLowerInvariant();
            if (ext == ".sldasm")
            {
                return (int)swDocumentTypes_e.swDocASSEMBLY;
            }
            if (ext == ".slddrw")
            {
                return (int)swDocumentTypes_e.swDocDRAWING;
            }
            return (int)swDocumentTypes_e.swDocPART;
        }

        private void TryShowConfiguration(ModelDoc2 model, string configName)
        {
            if (model == null || string.IsNullOrWhiteSpace(configName))
            {
                return;
            }

            try
            {
                model.ShowConfiguration2(configName);
            }
            catch
            {
                // ignore config switch errors
            }
        }

        private void WriteFlatBom(string outputFile, List<BatchEntry> entries, Action<string> log,
            Action<int, int> progress, HashSet<string> initialDocs, ModelDoc2 rootModel, string rootTitle,
            HashSet<string> uploadPackBases, List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras,
            Action<string> errorLog)
        {
            // Capture a stable root identity up-front. Never call methods on rootModel after we start aggressively
            // closing documents; if the root is closed/disconnected, those COM calls can throw RPC_E_DISCONNECTED.
            string rootPathSnapshot = string.Empty;
            string rootTitleSnapshot = rootTitle ?? string.Empty;
            try
            {
                if (rootModel != null)
                {
                    try
                    {
                        rootPathSnapshot = rootModel.GetPathName() ?? string.Empty;
                    }
                    catch
                    {
                        rootPathSnapshot = string.Empty;
                    }

                    try
                    {
                        string t = rootModel.GetTitle();
                        if (!string.IsNullOrWhiteSpace(t))
                        {
                            rootTitleSnapshot = t;
                        }
                    }
                    catch
                    {
                        // ignore title snapshot errors
                    }
                }
            }
            catch
            {
                rootPathSnapshot = string.Empty;
                rootTitleSnapshot = rootTitle ?? string.Empty;
            }

            using (var writer = TextFileHelper.CreateUtf8NoBomWriter(outputFile))
            {
                var keepBase = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                if (initialDocs != null)
                {
                    keepBase.UnionWith(initialDocs);
                }
                // Ensure the keep set contains stable root identifiers even if rootModel later disconnects.
                if (!string.IsNullOrWhiteSpace(rootPathSnapshot))
                {
                    keepBase.Add(rootPathSnapshot);
                }
                if (!string.IsNullOrWhiteSpace(rootTitleSnapshot))
                {
                    keepBase.Add(rootTitleSnapshot);
                    string norm = NormalizeDocTitleForClose(rootTitleSnapshot);
                    if (!string.IsNullOrWhiteSpace(norm))
                    {
                        keepBase.Add(norm);
                    }
                }
                if (!string.IsNullOrWhiteSpace(rootTitle))
                {
                    keepBase.Add(rootTitle);
                    string norm = NormalizeDocTitleForClose(rootTitle);
                    if (!string.IsNullOrWhiteSpace(norm))
                    {
                        keepBase.Add(norm);
                    }
                }

                AddDocToKeepSet(keepBase, rootModel, rootTitle);
                EnsureDocBaseline(keepBase, log, errorLog, "pre-flatbom", allowCancel: true);
                // If the root/start document gets closed, any cached ModelDoc2 references become disconnected and
                // SolidWorks automation becomes unstable. Fail fast with a clear message.
                try
                {
                    if (!IsDocOpenByIdOrTitle(rootPathSnapshot, rootTitleSnapshot))
                    {
                        // Extra diagnostics on the failure path only (kept out of the normal log).
                        try
                        {
                            string activeTitle = string.Empty;
                            string activePath = string.Empty;
                            try
                            {
                                ModelDoc2 active = _swApp.ActiveDoc as ModelDoc2;
                                if (active != null)
                                {
                                    activeTitle = active.GetTitle();
                                    activePath = active.GetPathName();
                                }
                            }
                            catch
                            {
                                activeTitle = string.Empty;
                                activePath = string.Empty;
                            }

                            DebugExport(errorLog,
                                "Root check failed after baseline cleanup. " +
                                "rootPathSnapshot=" + (rootPathSnapshot ?? string.Empty) +
                                " rootTitleSnapshot=" + (rootTitleSnapshot ?? string.Empty) +
                                " activeTitle=" + (activeTitle ?? string.Empty) +
                                " activePath=" + (activePath ?? string.Empty) +
                                " openDocs=" + SnapshotOpenDocIds().Count +
                                " keepCount=" + (keepBase != null ? keepBase.Count : 0));
                        }
                        catch
                        {
                            // ignore debug errors
                        }

                        throw new InvalidOperationException("Root document was closed unexpectedly during baseline cleanup.");
                    }
                }
                catch (Exception ex)
                {
                    if (IsBaselineAbortException(ex))
                    {
                        throw;
                    }
                    LogExportFailure(log, errorLog,
                        "Root document disconnected/closed during baseline cleanup; aborting to prevent SolidWorks COM disconnect.");
                    throw;
                }
                DebugExport(errorLog,
                    "FlatBOM start entries=" + (entries != null ? entries.Count : 0) +
                    " openDocs=" + SnapshotOpenDocIds().Count);

                int processed = 0;
                foreach (BatchEntry entry in entries)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();

                    // Enforce baseline before opening the next model so we never accumulate open docs.
                    EnsureDocBaseline(keepBase, log, errorLog, "pre-open flatbom entry", allowCancel: true);
                    ThrowIfCancelled();

                    bool openedHere = false;
                    ModelDoc2 model = null;
                    try
                    {
                        model = ResolveBatchModel(entry, rootModel, errorLog, out openedHere);
                        if (model != null)
                        {
                            try
                            {
                                writer.WriteLine(GetDocDict(model, entry.ConfigurationName));
                                if (uploadPackBases != null)
                                {
                                    string fileKey = GetFileString(model, entry.ConfigurationName);
                                    if (!string.IsNullOrWhiteSpace(fileKey))
                                    {
                                        uploadPackBases.Add(fileKey);
                                    }
                                }
                            }
                            catch (Exception ex)
                            {
                                Log(log, "Error building properties for model: " + ex.Message);
                                try
                                {
                                    Configuration entryConf = model.GetConfigurationByName(entry.ConfigurationName) as Configuration;
                                    string fallback = "{'partnumber':'" +
                                                      SanitizeString(BomPartNumber(entryConf, model)) + "'}";
                                    writer.WriteLine(fallback);
                                }
                                catch
                                {
                                    writer.WriteLine("{'partnumber':''}");
                                }
                            }

                            if (uploadPackExtras != null)
                            {
                                AddAssociatedFiles(uploadPackExtras, model, entry.ConfigurationName, log);
                            }
                        }
                        else
                        {
                            LogExportFailure(log, errorLog,
                                "Flat BOM entry skipped: unable to open model " +
                                DescribeModel(entry != null ? entry.ModelPath : string.Empty,
                                    entry != null ? entry.ModelTitle : string.Empty));
                        }
                    }
                    finally
                    {
                        if (openedHere && model != null)
                        {
                            ForceCloseDocNoSave(model, errorLog, "flatbom entry close");
                        }
                        EnsureDocBaseline(keepBase, log, errorLog, "post-close flatbom entry", allowCancel: true);
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                }

                DebugExport(errorLog, "FlatBOM end openDocs=" + SnapshotOpenDocIds().Count);
            }
        }

        private void AddAssociatedFiles(
            List<UploadPackBuilder.AssociatedFilesBundle> bundles,
            ModelDoc2 model,
            string configName,
            Action<string> log)
        {
            if (bundles == null || model == null)
            {
                return;
            }

            AssociatedFilesPayload payload = ReadAssociatedFiles(model, configName);
            if (payload == null || payload.Files == null || payload.Files.Count == 0)
            {
                return;
            }

            Configuration conf = model.GetConfigurationByName(configName) as Configuration;
            string pn = BomPartNumber(conf, model);
            if (string.IsNullOrWhiteSpace(pn))
            {
                string partProp = _config != null ? _config.PartNumberProperty : "PartNumber";
                if (string.IsNullOrWhiteSpace(partProp))
                {
                    partProp = "PartNumber";
                }
                pn = GetEvalProperty(model, configName, partProp);
                if (string.IsNullOrWhiteSpace(pn))
                {
                    pn = GetEvalProperty(model, string.Empty, partProp);
                }
            }

            if (string.IsNullOrWhiteSpace(pn))
            {
                Log(log, "Associated files skipped: part number not found.");
                return;
            }

            string revProp = _config != null ? _config.RevisionProperty : "Revision";
            if (string.IsNullOrWhiteSpace(revProp))
            {
                revProp = "Revision";
            }
            string rev = GetEvalProperty(model, configName, revProp);
            if (string.IsNullOrWhiteSpace(rev) && !string.Equals(revProp, "revision", StringComparison.OrdinalIgnoreCase))
            {
                rev = GetEvalProperty(model, configName, "revision");
            }
            if (string.IsNullOrWhiteSpace(rev))
            {
                rev = GetEvalProperty(model, string.Empty, revProp);
            }
            if (string.IsNullOrWhiteSpace(rev) && !string.Equals(revProp, "revision", StringComparison.OrdinalIgnoreCase))
            {
                rev = GetEvalProperty(model, string.Empty, "revision");
            }
            rev = rev ?? string.Empty;

            UploadPackBuilder.AssociatedFilesBundle existing = null;
            foreach (UploadPackBuilder.AssociatedFilesBundle bundle in bundles)
            {
                if (bundle == null)
                {
                    continue;
                }
                if (string.Equals(bundle.PartNumber, pn, StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(bundle.Revision ?? string.Empty, rev, StringComparison.OrdinalIgnoreCase))
                {
                    existing = bundle;
                    break;
                }
            }

            if (existing == null)
            {
                existing = new UploadPackBuilder.AssociatedFilesBundle
                {
                    PartNumber = pn,
                    Revision = rev,
                    Files = new List<AssociatedFileEntry>()
                };
                bundles.Add(existing);
            }

            foreach (AssociatedFileEntry entry in payload.Files)
            {
                if (entry == null || string.IsNullOrWhiteSpace(entry.Path))
                {
                    continue;
                }

                bool already = false;
                foreach (AssociatedFileEntry seen in existing.Files)
                {
                    if (seen == null)
                    {
                        continue;
                    }
                    if (string.Equals(seen.Path, entry.Path, StringComparison.OrdinalIgnoreCase))
                    {
                        already = true;
                        break;
                    }
                }
                if (!already)
                {
                    existing.Files.Add(entry);
                }
            }
        }

        private bool AnyDeliverablesSelected(PublishOptions options)
        {
            if (options == null)
            {
                return false;
            }

            return options.ExportPngModel ||
                   options.ExportStep ||
                   options.ExportEdrawing ||
                   options.Export3mf ||
                   options.ExportPly ||
                   options.ExportStl ||
                   options.ExportPngDrawing ||
                   options.ExportPdf ||
                   options.ExportEdrawingDrawing;
        }

        private List<FlatBomEntry> ReadFlatBomEntries(string flatBomPath, Action<string> log, Action<string> errorLog)
        {
            var entries = new List<FlatBomEntry>();
            if (string.IsNullOrWhiteSpace(flatBomPath) || !File.Exists(flatBomPath))
            {
                LogExportFailure(log, errorLog, "Flat BOM not found: " + (flatBomPath ?? string.Empty));
                return entries;
            }

            try
            {
                foreach (string line in File.ReadLines(flatBomPath))
                {
                    if (string.IsNullOrWhiteSpace(line))
                    {
                        continue;
                    }

                    if (line.IndexOf("'partnumber':'", StringComparison.OrdinalIgnoreCase) < 0)
                    {
                        continue;
                    }

                    var entry = new FlatBomEntry
                    {
                        PartNumber = ExtractBomValue(line, "partnumber"),
                        Revision = ExtractBomValue(line, "revision"),
                        ConfigurationName = ExtractBomValue(line, "sw_configuration"),
                        Process = ExtractBomValue(line, "process"),
                        Process2 = ExtractBomValue(line, "process2"),
                        Process3 = ExtractBomValue(line, "process3")
                    };

                    string rawPath = ExtractBomValue(line, "path");
                    entry.ModelPath = NormalizeBomPath(rawPath);

                    string file = ExtractBomValue(line, "file");
                    if (!string.IsNullOrWhiteSpace(entry.ModelPath))
                    {
                        entry.ModelTitle = Path.GetFileName(entry.ModelPath);
                    }
                    else
                    {
                        entry.ModelTitle = file ?? string.Empty;
                    }

                    entries.Add(entry);
                }
            }
            catch (Exception ex)
            {
                LogExportFailure(log, errorLog, "Failed to read flat BOM: " + ex.Message);
            }

            return entries;
        }

        private string ExtractBomValue(string line, string key)
        {
            if (string.IsNullOrWhiteSpace(line) || string.IsNullOrWhiteSpace(key))
            {
                return string.Empty;
            }

            string token = "'" + key + "':'";
            int start = line.IndexOf(token, StringComparison.OrdinalIgnoreCase);
            if (start < 0)
            {
                return string.Empty;
            }

            start += token.Length;
            int end = line.IndexOf("'", start);
            if (end < 0)
            {
                return string.Empty;
            }

            return line.Substring(start, end - start);
        }

        private string NormalizeBomPath(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            return path.Replace("/", "\\");
        }

        private string BuildFileString(string partNumber, string revision)
        {
            if (string.IsNullOrWhiteSpace(partNumber))
            {
                return string.Empty;
            }

            string rev = revision ?? string.Empty;
            string fileString = partNumber + "_REV_" + rev;
            return fileString.ToUpperInvariant();
        }

        private string GetEdrawingExtension(string modelPath, string modelTitle)
        {
            string ext = Path.GetExtension(!string.IsNullOrWhiteSpace(modelPath) ? modelPath : (modelTitle ?? string.Empty))
                .ToLowerInvariant();
            return ext == ".sldasm" ? ".easm" : ".eprt";
        }

        private bool HasProcess(FlatBomEntry entry, string process)
        {
            if (entry == null || string.IsNullOrWhiteSpace(process))
            {
                return false;
            }

            return ContainsIgnoreCase(entry.Process, process) ||
                   ContainsIgnoreCase(entry.Process2, process) ||
                   ContainsIgnoreCase(entry.Process3, process);
        }

        private DeliverablePlan BuildDeliverablePlanFromBomEntry(FlatBomEntry entry, string deliverablesFolder, PublishOptions options)
        {
            if (entry == null || options == null)
            {
                return null;
            }

            string fileString = BuildFileString(entry.PartNumber, entry.Revision);
            if (string.IsNullOrWhiteSpace(fileString))
            {
                return null;
            }

            bool drawingExists = false;
            if (!string.IsNullOrWhiteSpace(entry.ModelPath) && !string.IsNullOrWhiteSpace(entry.PartNumber))
            {
                string drawingPath = OnlyFolder(entry.ModelPath) + entry.PartNumber + ".SLDDRW";
                drawingExists = File.Exists(drawingPath);
            }

            bool createPng = options.ExportPngModel &&
                             ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + ".png"),
                                 options.OverwriteFiles);

            bool createStep = (options.ExportStep ||
                               HasProcess(entry, "FOLDING") ||
                               HasProcess(entry, "MACHINE") ||
                               HasProcess(entry, "3D Laser")) &&
                              ShouldExport(Path.Combine(deliverablesFolder, "step", fileString + ".step"),
                                  options.OverwriteFiles);

            bool create3mf = options.Export3mf &&
                             ShouldExport(Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf"),
                                 options.OverwriteFiles);

            bool createPly = options.ExportPly &&
                             ShouldExport(Path.Combine(deliverablesFolder, "ply", fileString + ".ply"),
                                 options.OverwriteFiles);

            bool createStl = options.ExportStl &&
                             ShouldExport(Path.Combine(deliverablesFolder, "stl", fileString + ".stl"),
                                 options.OverwriteFiles);

            bool createEdr = options.ExportEdrawing &&
                             ShouldExport(Path.Combine(deliverablesFolder, "edr",
                                 fileString + GetEdrawingExtension(entry.ModelPath, entry.ModelTitle)),
                                 options.OverwriteFiles);

            bool createPdf = drawingExists && options.ExportPdf &&
                             ShouldExport(Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf"),
                                 options.OverwriteFiles);

            bool createPngD = drawingExists && options.ExportPngDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png"),
                                  options.OverwriteFiles);

            bool createEdrD = drawingExists && options.ExportEdrawingDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString + ".edrw"),
                                  options.OverwriteFiles);

            if (!createPng && !createStep && !create3mf && !createPly && !createStl && !createEdr &&
                !createPdf && !createPngD && !createEdrD)
            {
                return null;
            }

            return new DeliverablePlan
            {
                ModelPath = entry.ModelPath ?? string.Empty,
                ModelTitle = entry.ModelTitle ?? string.Empty,
                ConfigurationName = entry.ConfigurationName ?? string.Empty,
                FileString = fileString,
                PartNumber = entry.PartNumber ?? string.Empty,
                DrawingExists = drawingExists,
                ExportPngModel = createPng,
                ExportStep = createStep,
                Export3mf = create3mf,
                ExportPly = createPly,
                ExportStl = createStl,
                ExportEdrawing = createEdr,
                ExportPdf = createPdf,
                ExportPngDrawing = createPngD,
                ExportEdrawingDrawing = createEdrD
            };
        }

        private DeliverablePlan BuildDeliverablePlanFromModel(ModelDoc2 model, string confName, string deliverablesFolder,
            PublishOptions options)
        {
            if (model == null || options == null)
            {
                return null;
            }

            string fileString = GetFileString(model, confName);
            if (string.IsNullOrWhiteSpace(fileString))
            {
                return null;
            }

            string modelPath = model.GetPathName() ?? string.Empty;
            string modelTitle = model.GetTitle() ?? string.Empty;
            bool drawingExists = false;
            string partNumber = string.Empty;

            if (!string.IsNullOrWhiteSpace(modelPath))
            {
                Configuration modelConf = model.GetConfigurationByName(confName) as Configuration;
                partNumber = BomPartNumber(modelConf, model);
                if (!string.IsNullOrWhiteSpace(partNumber))
                {
                    string drawingPath = OnlyFolder(modelPath) + partNumber + ".SLDDRW";
                    drawingExists = File.Exists(drawingPath);
                }
            }

            bool createPng = options.ExportPngModel &&
                             ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + ".png"),
                                 options.OverwriteFiles);

            bool createStep = (options.ExportStep ||
                               HasProcess(model, confName, "FOLDING") ||
                               HasProcess(model, confName, "MACHINE") ||
                               HasProcess(model, confName, "3D Laser")) &&
                              ShouldExport(Path.Combine(deliverablesFolder, "step", fileString + ".step"),
                                  options.OverwriteFiles);

            bool create3mf = options.Export3mf &&
                             ShouldExport(Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf"),
                                 options.OverwriteFiles);

            bool createPly = options.ExportPly &&
                             ShouldExport(Path.Combine(deliverablesFolder, "ply", fileString + ".ply"),
                                 options.OverwriteFiles);

            bool createStl = options.ExportStl &&
                             ShouldExport(Path.Combine(deliverablesFolder, "stl", fileString + ".stl"),
                                 options.OverwriteFiles);

            string edrExt = model.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt";
            bool createEdr = options.ExportEdrawing &&
                             ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString + edrExt),
                                 options.OverwriteFiles);

            bool createPdf = drawingExists && options.ExportPdf &&
                             ShouldExport(Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf"),
                                 options.OverwriteFiles);

            bool createPngD = drawingExists && options.ExportPngDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png"),
                                  options.OverwriteFiles);

            bool createEdrD = drawingExists && options.ExportEdrawingDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString + ".edrw"),
                                  options.OverwriteFiles);

            if (!createPng && !createStep && !create3mf && !createPly && !createStl && !createEdr &&
                !createPdf && !createPngD && !createEdrD)
            {
                return null;
            }

            return new DeliverablePlan
            {
                ModelPath = modelPath,
                ModelTitle = modelTitle,
                ConfigurationName = confName ?? string.Empty,
                FileString = fileString,
                PartNumber = partNumber ?? string.Empty,
                DrawingExists = drawingExists,
                ExportPngModel = createPng,
                ExportStep = createStep,
                Export3mf = create3mf,
                ExportPly = createPly,
                ExportStl = createStl,
                ExportEdrawing = createEdr,
                ExportPdf = createPdf,
                ExportPngDrawing = createPngD,
                ExportEdrawingDrawing = createEdrD
            };
        }

        private List<DeliverablePlan> BuildDeliverablePlans(List<FlatBomEntry> entries, string deliverablesFolder,
            PublishOptions options, Action<string> log, Action<string> errorLog)
        {
            var plans = new List<DeliverablePlan>();
            if (entries == null || entries.Count == 0 || options == null)
            {
                return plans;
            }

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (FlatBomEntry entry in entries)
            {
                if (entry == null)
                {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(entry.PartNumber))
                {
                    LogExportFailure(log, errorLog, "Flat BOM entry skipped: missing part number.");
                    continue;
                }

                DeliverablePlan plan = BuildDeliverablePlanFromBomEntry(entry, deliverablesFolder, options);
                if (plan == null)
                {
                    continue;
                }

                if (!seen.Add(plan.FileString ?? string.Empty))
                {
                    continue;
                }

                plans.Add(plan);
            }

            return plans;
        }

        private List<DeliverableGroup> BuildDeliverableGroups(List<DeliverablePlan> plans, ModelDoc2 rootModel, string rootTitle)
        {
            var groups = new List<DeliverableGroup>();
            if (plans == null || plans.Count == 0)
            {
                return groups;
            }

            string rootPath = rootModel != null ? rootModel.GetPathName() : string.Empty;
            string rootDocTitle = rootModel != null ? rootModel.GetTitle() : rootTitle ?? string.Empty;

            var lookup = new Dictionary<string, DeliverableGroup>(StringComparer.OrdinalIgnoreCase);
            foreach (DeliverablePlan plan in plans)
            {
                if (plan == null)
                {
                    continue;
                }

                string key = !string.IsNullOrWhiteSpace(plan.ModelPath)
                    ? plan.ModelPath
                    : (plan.ModelTitle ?? string.Empty);
                if (string.IsNullOrWhiteSpace(key))
                {
                    if (!string.IsNullOrWhiteSpace(rootPath))
                    {
                        key = rootPath;
                    }
                    else if (!string.IsNullOrWhiteSpace(rootDocTitle))
                    {
                        key = rootDocTitle;
                    }
                }
                if (string.IsNullOrWhiteSpace(key))
                {
                    continue;
                }

                DeliverableGroup group;
                if (!lookup.TryGetValue(key, out group))
                {
                    group = new DeliverableGroup
                    {
                        ModelPath = !string.IsNullOrWhiteSpace(plan.ModelPath) ? plan.ModelPath : (rootPath ?? string.Empty),
                        ModelTitle = !string.IsNullOrWhiteSpace(plan.ModelTitle) ? plan.ModelTitle : (rootDocTitle ?? string.Empty),
                        IsRoot = false
                    };
                    lookup[key] = group;
                    groups.Add(group);
                }

                group.Plans.Add(plan);

                if (!group.IsRoot)
                {
                    bool matchPath = !string.IsNullOrWhiteSpace(rootPath) &&
                                     !string.IsNullOrWhiteSpace(plan.ModelPath) &&
                                     string.Equals(rootPath, plan.ModelPath, StringComparison.OrdinalIgnoreCase);
                    bool matchTitle = !string.IsNullOrWhiteSpace(rootDocTitle) &&
                                      !string.IsNullOrWhiteSpace(plan.ModelTitle) &&
                                      string.Equals(rootDocTitle, plan.ModelTitle, StringComparison.OrdinalIgnoreCase);
                    bool matchKey = (!string.IsNullOrWhiteSpace(rootPath) &&
                                     string.Equals(rootPath, key, StringComparison.OrdinalIgnoreCase)) ||
                                    (!string.IsNullOrWhiteSpace(rootDocTitle) &&
                                     string.Equals(rootDocTitle, key, StringComparison.OrdinalIgnoreCase));
                    group.IsRoot = matchPath || matchTitle || matchKey;
                }
            }

            return groups;
        }

        private List<BatchGroup> BuildBatchGroups(List<BatchEntry> entries)
        {
            var groups = new List<BatchGroup>();
            if (entries == null || entries.Count == 0)
            {
                return groups;
            }

            var lookup = new Dictionary<string, BatchGroup>(StringComparer.OrdinalIgnoreCase);
            foreach (BatchEntry entry in entries)
            {
                if (entry == null)
                {
                    continue;
                }

                string key = !string.IsNullOrWhiteSpace(entry.ModelPath)
                    ? entry.ModelPath
                    : (entry.ModelTitle ?? string.Empty);
                if (string.IsNullOrWhiteSpace(key))
                {
                    continue;
                }

                BatchGroup group;
                if (!lookup.TryGetValue(key, out group))
                {
                    group = new BatchGroup
                    {
                        OpenEntry = entry
                    };
                    lookup[key] = group;
                    groups.Add(group);
                }

                if (entry.IsRoot)
                {
                    group.OpenEntry = entry;
                }

                group.Entries.Add(entry);
            }

            return groups;
        }

        private BatchEntry BuildOpenEntry(DeliverableGroup group)
        {
            if (group == null)
            {
                return null;
            }

            string configName = string.Empty;
            if (group.Plans != null && group.Plans.Count > 0 && group.Plans[0] != null)
            {
                configName = group.Plans[0].ConfigurationName;
            }

            return new BatchEntry
            {
                ModelPath = group.ModelPath ?? string.Empty,
                ModelTitle = group.ModelTitle ?? string.Empty,
                ConfigurationName = configName ?? string.Empty,
                IsRoot = group.IsRoot
            };
        }

        private string DescribeModel(string modelPath, string modelTitle)
        {
            if (!string.IsNullOrWhiteSpace(modelPath))
            {
                return modelPath;
            }

            if (!string.IsNullOrWhiteSpace(modelTitle))
            {
                return modelTitle;
            }

            return "<unknown>";
        }

        private void ProcessDeliverablePlans(List<DeliverablePlan> plans, string deliverablesFolder, PublishOptions options,
            Action<string> log, Action<string> errorLog, HashSet<string> initialDocs, ModelDoc2 rootModel, string rootTitle,
            Action<int, int> progress)
        {
            int total = plans != null ? plans.Count : 0;
            UpdateProgress(progress, 0, total);

            if (plans == null || plans.Count == 0)
            {
                return;
            }

            List<DeliverableGroup> groups = BuildDeliverableGroups(plans, rootModel, rootTitle);
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            int processed = 0;

            var keepBase = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (initialDocs != null)
            {
                keepBase.UnionWith(initialDocs);
            }
            AddDocToKeepSet(keepBase, rootModel, rootTitle);

            foreach (DeliverableGroup group in groups)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                EnsureDocBaseline(keepBase, log, errorLog, "pre-open deliverable group", allowCancel: true);
                ThrowIfCancelled();

                BatchEntry openEntry = BuildOpenEntry(group);
                string modelDesc = DescribeModel(group != null ? group.ModelPath : string.Empty,
                    group != null ? group.ModelTitle : string.Empty);
                Log(log, "Opening model for deliverables: " + modelDesc);
                Log(log, "Open docs now: " + SnapshotOpenDocIds().Count);
                DebugExport(errorLog,
                    "DeliverablesGroup start model=" + modelDesc +
                    " plans=" + (group != null && group.Plans != null ? group.Plans.Count : 0) +
                    " openDocs=" + SnapshotOpenDocIds().Count);

                bool openedHere = false;
                ModelDoc2 model = null;
                try
                {
                    model = ResolveBatchModel(openEntry, rootModel, errorLog, out openedHere);
                    if (model == null)
                    {
                        LogExportFailure(log, errorLog,
                            "Deliverables skipped: unable to open model " + modelDesc);
                        processed += group != null && group.Plans != null ? group.Plans.Count : 0;
                        UpdateProgress(progress, processed, total);
                        continue;
                    }

                    DebugExport(errorLog,
                        "DeliverablesGroup openedHere=" + openedHere +
                        " title=" + (model != null ? model.GetTitle() : string.Empty) +
                        " path=" + (model != null ? model.GetPathName() : string.Empty));

                    foreach (DeliverablePlan plan in group.Plans)
                    {
                        ThrowIfCancelled();
                        System.Windows.Forms.Application.DoEvents();

                        bool shouldExecute = plan != null && seen.Add(plan.FileString ?? string.Empty);
                        if (shouldExecute)
                        {
                            DebugExport(errorLog,
                                "DeliverablesPlan file=" + (plan.FileString ?? string.Empty) +
                                " conf=" + (plan.ConfigurationName ?? string.Empty) +
                                " exports=" + DescribePlanExports(plan));
                            ExecuteDeliverablePlan(model, plan, deliverablesFolder,
                                options != null && options.OverwriteFiles, log, errorLog);
                        }
                        processed++;
                        UpdateProgress(progress, processed, total);
                    }
                }
                finally
                {
                    if (openedHere && model != null && openEntry != null && !openEntry.IsRoot &&
                        (rootModel == null || !ReferenceEquals(model, rootModel)))
                    {
                        ForceCloseDocNoSave(model, errorLog, "deliverable group close");
                    }

                    EnsureDocBaseline(keepBase, log, errorLog, "post-close deliverable group", allowCancel: true);
                    Log(log, "Open docs now: " + SnapshotOpenDocIds().Count);
                    DebugExport(errorLog, "DeliverablesGroup end model=" + modelDesc +
                                         " openDocs=" + SnapshotOpenDocIds().Count);
                }
            }
        }

        private void ProcessDeliverablesLegacy(List<BatchEntry> entries, string deliverablesFolder, PublishOptions options,
            Action<string> log, Action<string> errorLog, HashSet<string> initialDocs, ModelDoc2 rootModel, string rootTitle,
            Action<int, int> progress)
        {
            int total = entries != null ? entries.Count : 0;
            UpdateProgress(progress, 0, total);

            if (entries == null || entries.Count == 0)
            {
                return;
            }

            var groups = BuildBatchGroups(entries);
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            int processed = 0;

            var keepBase = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (initialDocs != null)
            {
                keepBase.UnionWith(initialDocs);
            }
            AddDocToKeepSet(keepBase, rootModel, rootTitle);

            foreach (BatchGroup group in groups)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                EnsureDocBaseline(keepBase, log, errorLog, "pre-open legacy deliverable group", allowCancel: true);
                ThrowIfCancelled();

                BatchEntry openEntry = group.OpenEntry;
                string modelDesc = DescribeModel(openEntry != null ? openEntry.ModelPath : string.Empty,
                    openEntry != null ? openEntry.ModelTitle : string.Empty);
                Log(log, "Opening model for deliverables (legacy): " + modelDesc);
                Log(log, "Open docs now: " + SnapshotOpenDocIds().Count);
                DebugExport(errorLog,
                    "LegacyGroup start model=" + modelDesc +
                    " entries=" + (group != null && group.Entries != null ? group.Entries.Count : 0) +
                    " openDocs=" + SnapshotOpenDocIds().Count);

                bool openedHere = false;
                ModelDoc2 model = null;
                try
                {
                    model = ResolveBatchModel(openEntry, rootModel, errorLog, out openedHere);
                    if (model == null)
                    {
                        LogExportFailure(log, errorLog, "Deliverables skipped: unable to open model " + modelDesc);
                        processed += group != null && group.Entries != null ? group.Entries.Count : 0;
                        UpdateProgress(progress, processed, total);
                        continue;
                    }

                    DebugExport(errorLog,
                        "LegacyGroup openedHere=" + openedHere +
                        " title=" + (model != null ? model.GetTitle() : string.Empty) +
                        " path=" + (model != null ? model.GetPathName() : string.Empty));

                    foreach (BatchEntry entry in group.Entries)
                    {
                        ThrowIfCancelled();
                        System.Windows.Forms.Application.DoEvents();

                        DeliverablePlan plan = BuildDeliverablePlanFromModel(model, entry.ConfigurationName, deliverablesFolder, options);
                        if (plan != null)
                        {
                            if (!seen.Add(plan.FileString ?? string.Empty))
                            {
                                plan = null;
                            }
                        }

                        if (plan != null)
                        {
                            DebugExport(errorLog,
                                "LegacyPlan file=" + (plan.FileString ?? string.Empty) +
                                " conf=" + (plan.ConfigurationName ?? string.Empty) +
                                " exports=" + DescribePlanExports(plan));
                            ExecuteDeliverablePlan(model, plan, deliverablesFolder,
                                options != null && options.OverwriteFiles, log, errorLog);
                        }

                        processed++;
                        UpdateProgress(progress, processed, total);
                    }
                }
                finally
                {
                    if (openedHere && model != null && openEntry != null && !openEntry.IsRoot &&
                        (rootModel == null || !ReferenceEquals(model, rootModel)))
                    {
                        ForceCloseDocNoSave(model, errorLog, "legacy deliverable group close");
                    }

                    EnsureDocBaseline(keepBase, log, errorLog, "post-close legacy deliverable group", allowCancel: true);
                    Log(log, "Open docs now: " + SnapshotOpenDocIds().Count);
                    DebugExport(errorLog, "LegacyGroup end model=" + modelDesc +
                                         " openDocs=" + SnapshotOpenDocIds().Count);
                }
            }
        }

        private void ExecuteDeliverablePlan(ModelDoc2 model, DeliverablePlan plan, string deliverablesFolder, bool overwriteFiles,
            Action<string> log, Action<string> errorLog)
        {
            if (model == null || plan == null)
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(plan.ConfigurationName))
            {
                TryShowConfiguration(model, plan.ConfigurationName);
            }

            if (plan.HasModelExports())
            {
                try
                {
                    ModelPublish(model, plan.ConfigurationName, plan.FileString, deliverablesFolder,
                        plan.ExportPngModel, plan.ExportStep, plan.ExportEdrawing, plan.Export3mf,
                        plan.ExportPly, plan.ExportStl, log, errorLog);
                }
                catch (Exception ex)
                {
                    if (ex is OperationCanceledException)
                    {
                        throw;
                    }
                    if (IsBaselineAbortException(ex))
                    {
                        throw;
                    }
                    LogExportFailure(log, errorLog, "Model export failed for " + plan.FileString + ": " + ex.Message);
                }
            }

            if (plan.HasDrawingExports())
            {
                try
                {
                    DwgPublish(model, plan.FileString, deliverablesFolder,
                        overwriteFiles, plan.ExportPdf, plan.ExportPngDrawing, plan.ExportEdrawingDrawing, log, errorLog,
                        plan.PartNumber);
                }
                catch (Exception ex)
                {
                    if (ex is OperationCanceledException)
                    {
                        throw;
                    }
                    if (IsBaselineAbortException(ex))
                    {
                        throw;
                    }
                    LogExportFailure(log, errorLog, "Drawing export failed for " + plan.FileString + ": " + ex.Message);
                }
            }
        }

        private string DescribePlanExports(DeliverablePlan plan)
        {
            if (plan == null)
            {
                return string.Empty;
            }

            var parts = new List<string>();
            if (plan.ExportPngModel) parts.Add("png");
            if (plan.ExportStep) parts.Add("step");
            if (plan.ExportEdrawing) parts.Add("edr");
            if (plan.Export3mf) parts.Add("3mf");
            if (plan.ExportPly) parts.Add("ply");
            if (plan.ExportStl) parts.Add("stl");
            if (plan.ExportPdf) parts.Add("pdf");
            if (plan.ExportPngDrawing) parts.Add("pngDwg");
            if (plan.ExportEdrawingDrawing) parts.Add("edrw");
            return string.Join(",", parts.ToArray());
        }

        private void EnsureMediaFolders(string deliverablesFolder)
        {
            string[] folders =
            {
                "png",
                "step",
                "pdf",
                "dxf",
                "edr",
                "3mf",
                "ply",
                "stl",
                "bom",
                Path.Combine("temp", "upload")
            };

            foreach (string folder in folders)
            {
                Directory.CreateDirectory(Path.Combine(deliverablesFolder, folder));
            }
        }

        private bool ShouldExport(string path, bool overwrite)
        {
            return overwrite || !File.Exists(path);
        }

        private void ModelPublish(ModelDoc2 model, string confName, string fileString, string deliverablesFolder,
            bool png, bool step, bool edr, bool threeMf, bool ply, bool stl, Action<string> log, Action<string> errorLog)
        {
            using (new ExportDialogSuppressionScope(_swApp))
            {
                string modelTitle = string.Empty;
                try
                {
                    modelTitle = model.GetTitle();
                }
                catch
                {
                    modelTitle = string.Empty;
                }

                string activateTitle = NormalizeDocTitleForClose(modelTitle);
                if (!string.IsNullOrWhiteSpace(activateTitle))
                {
                    _swApp.ActivateDoc(activateTitle);
                }
                else if (!string.IsNullOrWhiteSpace(modelTitle))
                {
                    _swApp.ActivateDoc(modelTitle);
                }
                model.ShowConfiguration(confName);
                ThrowIfCancelled();

                ModelView view = model.GetFirstModelView() as ModelView;
                bool prevGraphicsUpdate = true;
                if (view != null)
                {
                    prevGraphicsUpdate = view.EnableGraphicsUpdate;
                    view.EnableGraphicsUpdate = false;
                }

                // Avoid mutating document-level options or forcing rebuilds. These operations can dirty documents
                // and trigger modal "Save?" prompts when closing during unattended batch export.
                try
                {
                    ThrowIfCancelled();

                    int errors = 0;
                    int warnings = 0;

                    if (threeMf)
                    {
                        string path = Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf");
                        bool ok = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (!ok || !File.Exists(path))
                        {
                            LogExportFailure(log, errorLog, "3MF export failed: " + path);
                        }
                    }
                    ThrowIfCancelled();

                    bool stlExported = false;
                    string stlPath = Path.Combine(deliverablesFolder, "stl", fileString + ".stl");
                    if (stl)
                    {
                        stlExported = model.Extension.SaveAs(stlPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        stlExported = stlExported && File.Exists(stlPath);
                        if (!stlExported)
                        {
                            LogExportFailure(log, errorLog, "STL export failed: " + stlPath);
                        }
                    }
                    ThrowIfCancelled();

                    if (ply)
                    {
                        string plyPath = Path.Combine(deliverablesFolder, "ply", fileString + ".ply");
                        bool plyExported = model.Extension.SaveAs(plyPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        plyExported = plyExported && File.Exists(plyPath);

                        if (!plyExported)
                        {
                            ThrowIfCancelled();

                            string sourceStl = stlExported ? stlPath : string.Empty;
                            string tempStl = string.Empty;

                            if (string.IsNullOrWhiteSpace(sourceStl))
                            {
                                tempStl = Path.Combine(Path.GetTempPath(),
                                    fileString + "_" + Guid.NewGuid().ToString("N") + ".stl");
                                bool tempOk = model.Extension.SaveAs(tempStl, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                                if (tempOk && File.Exists(tempStl))
                                {
                                    sourceStl = tempStl;
                                }
                            }

                            ThrowIfCancelled();

                            if (!string.IsNullOrWhiteSpace(sourceStl) && File.Exists(sourceStl))
                            {
                                if (!TryConvertStlToPly(sourceStl, plyPath))
                                {
                                    LogExportFailure(log, errorLog, "PLY export failed: STL conversion failed.");
                                }
                            }
                            else
                            {
                                LogExportFailure(log, errorLog, "PLY export failed: STL source unavailable.");
                            }

                            if (!string.IsNullOrWhiteSpace(tempStl))
                            {
                                try
                                {
                                    File.Delete(tempStl);
                                }
                                catch
                                {
                                    // ignore cleanup errors
                                }
                            }
                        }

                        if (!File.Exists(plyPath))
                        {
                            LogExportFailure(log, errorLog, "PLY export failed: " + plyPath);
                        }
                    }
                    ThrowIfCancelled();

                    if (step)
                    {
                        string path = Path.Combine(deliverablesFolder, "step", fileString + ".step");
                        bool ok = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (!ok || !File.Exists(path))
                        {
                            LogExportFailure(log, errorLog, "STEP export failed: " + path);
                        }
                    }
                    ThrowIfCancelled();

                    if (edr)
                    {
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                            (int)swEdrawingSaveAsOption_e.swEdrawingSaveActive);

                        string ext = model.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt";
                        string path = Path.Combine(deliverablesFolder, "edr", fileString + ext);
                        bool ok = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (!ok || !File.Exists(path))
                        {
                            LogExportFailure(log, errorLog, "eDrawing export failed: " + path);
                        }
                    }
                    ThrowIfCancelled();

                    if (png)
                    {
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swTiffScreenOrPrintCapture, 1);
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swTiffPrintDPI, 150);
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swTiffPrintPaperSize,
                            (int)swDwgPaperSizes_e.swDwgPapersUserDefined);
                        _swApp.SetUserPreferenceDoubleValue(
                            (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperWidth, 0.297);
                        _swApp.SetUserPreferenceDoubleValue(
                            (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperHeight, 0.21);

                        model.ShowNamedView2("Isometric", 7);
                        model.ViewZoomtofit2();

                        if (view != null)
                        {
                            view.EnableGraphicsUpdate = true;
                        }

                        string path = Path.Combine(deliverablesFolder, "png", fileString + ".png");
                        bool ok = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (!ok || !File.Exists(path))
                        {
                            LogExportFailure(log, errorLog, "PNG export failed: " + path);
                        }
                    }
                }
                finally
                {
                    if (view != null)
                    {
                        try
                        {
                            view.EnableGraphicsUpdate = prevGraphicsUpdate;
                        }
                        catch
                        {
                            // ignore restore errors
                        }
                    }
                }
            }
        }

        private bool TryConvertStlToPly(string stlPath, string plyPath)
        {
            try
            {
                List<float> vertices;
                if (!TryReadBinaryStlVertices(stlPath, out vertices) &&
                    !TryReadAsciiStlVertices(stlPath, out vertices))
                {
                    return false;
                }

                int vertexCount = vertices.Count / 3;
                int faceCount = vertexCount / 3;
                if (faceCount <= 0)
                {
                    return false;
                }

                vertexCount = faceCount * 3;
                int floatCount = vertexCount * 3;

                using (var stream = new FileStream(plyPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var writer = new BinaryWriter(stream))
                {
                    string header = BuildPlyHeader(vertexCount, faceCount);
                    writer.Write(Encoding.ASCII.GetBytes(header));

                    for (int i = 0; i < floatCount; i++)
                    {
                        writer.Write(vertices[i]);
                    }

                    for (int i = 0; i < faceCount; i++)
                    {
                        writer.Write((byte)3);
                        writer.Write(i * 3);
                        writer.Write(i * 3 + 1);
                        writer.Write(i * 3 + 2);
                    }
                }

                return File.Exists(plyPath);
            }
            catch
            {
                return false;
            }
        }

        private bool TryReadBinaryStlVertices(string path, out List<float> vertices)
        {
            vertices = null;
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (var reader = new BinaryReader(stream))
            {
                if (stream.Length < 84)
                {
                    return false;
                }

                reader.ReadBytes(80);
                uint triCount = reader.ReadUInt32();
                long expectedSize = 84L + (50L * triCount);
                if (expectedSize != stream.Length)
                {
                    return false;
                }

                vertices = new List<float>(checked((int)triCount * 9));
                for (uint i = 0; i < triCount; i++)
                {
                    reader.ReadSingle();
                    reader.ReadSingle();
                    reader.ReadSingle();

                    for (int v = 0; v < 3; v++)
                    {
                        vertices.Add(reader.ReadSingle());
                        vertices.Add(reader.ReadSingle());
                        vertices.Add(reader.ReadSingle());
                    }

                    reader.ReadUInt16();
                }
            }

            return vertices.Count >= 9;
        }

        private bool TryReadAsciiStlVertices(string path, out List<float> vertices)
        {
            vertices = new List<float>();
            foreach (string raw in File.ReadLines(path))
            {
                string line = raw.Trim();
                if (!line.StartsWith("vertex", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length < 4)
                {
                    continue;
                }

                float x;
                float y;
                float z;
                if (float.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out x) &&
                    float.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out y) &&
                    float.TryParse(parts[3], NumberStyles.Float, CultureInfo.InvariantCulture, out z))
                {
                    vertices.Add(x);
                    vertices.Add(y);
                    vertices.Add(z);
                }
            }

            return vertices.Count >= 9;
        }

        private string BuildPlyHeader(int vertexCount, int faceCount)
        {
            var sb = new StringBuilder();
            sb.Append("ply\n");
            sb.Append("format binary_little_endian 1.0\n");
            sb.Append("element vertex ").Append(vertexCount).Append("\n");
            sb.Append("property float x\n");
            sb.Append("property float y\n");
            sb.Append("property float z\n");
            sb.Append("element face ").Append(faceCount).Append("\n");
            sb.Append("property list uchar int vertex_indices\n");
            sb.Append("end_header\n");
            return sb.ToString();
        }

        private void DwgPublish(ModelDoc2 model, string fileString, string deliverablesFolder,
            bool overwriteFiles, bool pdf, bool png, bool edr, Action<string> log, Action<string> errorLog, string partNumberOverride)
        {
            using (new ExportDialogSuppressionScope(_swApp))
            {
                Configuration conf = model.GetActiveConfiguration() as Configuration;
                if (conf == null)
                {
                    return;
                }

                string modelPath = model.GetPathName();
                if (string.IsNullOrWhiteSpace(modelPath))
                {
                    return;
                }

                string pn = !string.IsNullOrWhiteSpace(partNumberOverride)
                    ? partNumberOverride
                    : BomPartNumber(conf, model);
                string drawingPath = OnlyFolder(modelPath) + pn + ".SLDDRW";
                if (!File.Exists(drawingPath))
                {
                    return;
                }

                string pdfPath = Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf");
                string dxfPath = Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf");
                string pngPath = Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png");
                string edrPath = Path.Combine(deliverablesFolder, "edr", fileString + ".edrw");
                bool dxfRequested = ShouldExport(dxfPath, overwriteFiles);

                HashSet<string> baseline = SnapshotOpenDocIds();
                DocumentSpecification spec = _swApp.GetOpenDocSpec(drawingPath) as DocumentSpecification;
                if (spec == null)
                {
                    EnsureDocBaseline(baseline, log, errorLog, "drawing open spec failed");
                    return;
                }
                spec.DocumentType = (int)swDocumentTypes_e.swDocDRAWING;
                spec.ReadOnly = true;
                spec.Silent = true;

                ModelDoc2 drawDoc = null;
                using (new ExternalReferenceBatchOpenScope(_swApp))
                {
                    ThrowIfCancelled();
                    drawDoc = _swApp.OpenDoc7(spec) as ModelDoc2;
                }
                if (drawDoc == null)
                {
                    EnsureDocBaseline(baseline, log, errorLog, "drawing open failed");
                    return;
                }

                try
                {
                    string drawTitle = string.Empty;
                    try
                    {
                        drawTitle = drawDoc.GetTitle();
                    }
                    catch
                    {
                        drawTitle = string.Empty;
                    }

                    string activateTitle = NormalizeDocTitleForClose(drawTitle);
                    if (!string.IsNullOrWhiteSpace(activateTitle))
                    {
                        _swApp.ActivateDoc(activateTitle);
                    }
                    else if (!string.IsNullOrWhiteSpace(drawTitle))
                    {
                        _swApp.ActivateDoc(drawTitle);
                    }
                    ThrowIfCancelled();

                    DrawingDoc drawing = drawDoc as DrawingDoc;
                    if (drawing == null)
                    {
                        return;
                    }

                    object sheetNamesObj = drawing.GetSheetNames();
                    string[] sheetNames = ToStringArray(sheetNamesObj);
                    if (sheetNames == null || sheetNames.Length == 0)
                    {
                        return;
                    }

                    string dxfSheetName = string.Empty;
                    if (dxfRequested)
                    {
                        for (int i = 0; i < sheetNames.Length; i++)
                        {
                            ThrowIfCancelled();
                            string lower = (sheetNames[i] ?? string.Empty).Trim().ToLowerInvariant();
                            if (lower == "flatpattern" || lower == "dxf" || lower == "dxf sheet")
                            {
                                dxfSheetName = sheetNames[i];
                                break;
                            }
                        }
                    }

                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swDxfMultiSheetOption,
                        (int)swDxfMultisheet_e.swDxfActiveSheetOnly);
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swDxfOutputNoScale, 1);

                    int errors = 0;
                    int warnings = 0;

                    if (pdf)
                    {
                        ThrowIfCancelled();
                        ExportPdfData exportData = _swApp.GetExportFileData(
                            (int)swExportDataFileType_e.swExportPdfData) as ExportPdfData;
                        if (exportData != null)
                        {
                            exportData.SetSheets((int)swExportDataSheetsToExport_e.swExportData_ExportSpecifiedSheets,
                                sheetNames);
                            bool ok = drawDoc.Extension.SaveAs(pdfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, exportData, ref errors, ref warnings);
                            if (!ok || !File.Exists(pdfPath))
                            {
                                LogExportFailure(log, errorLog, "PDF export failed: " + pdfPath);
                            }
                        }
                        else
                        {
                            LogExportFailure(log, errorLog, "PDF export failed: export data unavailable.");
                        }
                    }

                    if (edr)
                    {
                        ThrowIfCancelled();
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                            (int)swEdrawingSaveAsOption_e.swEdrawingSaveAll);
                        bool ok = drawDoc.Extension.SaveAs(edrPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (!ok || !File.Exists(edrPath))
                        {
                            LogExportFailure(log, errorLog, "eDrawing export failed: " + edrPath);
                        }
                    }

                    if (png)
                    {
                        ThrowIfCancelled();
                        drawing.ActivateSheet(sheetNames[0]);
                        drawing.ViewFullPage();

                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swTiffScreenOrPrintCapture, 1);
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swTiffPrintDPI, 150);
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swTiffPrintPaperSize,
                            (int)swDwgPaperSizes_e.swDwgPapersUserDefined);
                        _swApp.SetUserPreferenceDoubleValue(
                            (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperWidth, 0.297);
                        _swApp.SetUserPreferenceDoubleValue(
                            (int)swUserPreferenceDoubleValue_e.swTiffPrintDrawingPaperHeight, 0.21);

                        bool ok = drawDoc.Extension.SaveAs(pngPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        if (!ok || !File.Exists(pngPath))
                        {
                            LogExportFailure(log, errorLog, "Drawing PNG export failed: " + pngPath);
                        }
                    }

                    if (dxfRequested)
                    {
                        ThrowIfCancelled();
                        bool exported = false;

                        // If the drawing has a dedicated DXF/flat pattern sheet, export it directly without
                        // mutating the sheet format (mutations can dirty the doc and trigger save prompts).
                        if (!string.IsNullOrWhiteSpace(dxfSheetName))
                        {
                            try
                            {
                                drawing.ActivateSheet(dxfSheetName);
                                bool ok = drawDoc.SaveAs4(dxfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref errors, ref warnings);
                                exported = ok && File.Exists(dxfPath);
                            }
                            catch
                            {
                                exported = false;
                            }
                        }

                        // Fallback: find a FLATPATTERN view and export it via a temporary doc.
                        if (!exported)
                        {
                            View flatView = drawing.GetFirstView() as View;
                            View flatPatternView = null;
                            while (flatView != null)
                            {
                                ThrowIfCancelled();
                                if (string.Equals(flatView.GetName2(), "FLATPATTERN", StringComparison.OrdinalIgnoreCase))
                                {
                                    flatPatternView = flatView;
                                    break;
                                }

                                flatView = flatView.GetNextView() as View;
                            }

                            if (flatPatternView != null)
                            {
                                ExportFlatPatternView(drawDoc, flatPatternView, dxfPath);
                                exported = File.Exists(dxfPath);
                            }
                        }

                        if (!exported)
                        {
                            LogExportFailure(log, errorLog, "DXF export failed: " + dxfPath);
                        }
                    }
                }
                finally
                {
                    ForceCloseDocNoSave(drawDoc, errorLog, "DwgPublish close");
                    EnsureDocBaseline(baseline, log, errorLog, "post-close drawing publish");
                }
            }
        }

        private void ReplaceSheetFormat(DrawingDoc draw, Sheet sheet, string targetSheetFormatFile)
        {
            object propsObj = sheet.GetProperties();
            object[] props = propsObj as object[];
            if (props == null || props.Length < 7)
            {
                return;
            }

            int paperSize = Convert.ToInt32(props[0]);
            int templateType = Convert.ToInt32(props[1]);
            double scale1 = Convert.ToDouble(props[2]);
            double scale2 = Convert.ToDouble(props[3]);
            bool firstAngle = Convert.ToBoolean(props[4]);
            double width = Convert.ToDouble(props[5]);
            double height = Convert.ToDouble(props[6]);
            string customView = sheet.CustomPropertyView;

            bool result = draw.SetupSheet5(sheet.GetName(), paperSize, templateType, scale1, scale2, firstAngle,
                targetSheetFormatFile, width, height, customView, _config.RemoveModifiedNotes);

            if (!result)
            {
                throw new InvalidOperationException("Failed to set sheet format.");
            }
        }

        private void ExportFlatPatternView(ModelDoc2 model, View view, string dxfFilePath)
        {
            object[] views = { view };
            int selected = model.Extension.MultiSelect2(views, false, null);
            if (selected == 1)
            {
                model.EditCopy();
                ModelDoc2 viewModel = PasteViewInNewDocument();
                int errors = 0;
                int warnings = 0;
                bool result = viewModel.Extension.SaveAs(dxfFilePath,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                ForceCloseDocNoSave(viewModel);

                if (!result)
                {
                    throw new InvalidOperationException("Failed to export " + view.Name);
                }
            }
            else
            {
                throw new InvalidOperationException("Failed to select " + view.Name);
            }
        }

        private ModelDoc2 PasteViewInNewDocument()
        {
            ModelDoc2 drawDoc = _swApp.NewDocument(_config.BlankTemplatePath,
                (int)swDwgPaperSizes_e.swDwgPapersUserDefined, 0.1, 0.1) as ModelDoc2;

            if (drawDoc == null)
            {
                throw new InvalidOperationException("Failed to create new drawing document.");
            }

            drawDoc.Paste();

            DrawingDoc drawing = drawDoc as DrawingDoc;
            if (drawing == null)
            {
                return drawDoc;
            }

            Sheet sheet = drawing.GetCurrentSheet() as Sheet;
            if (sheet == null)
            {
                return drawDoc;
            }
            object[] viewsObj = sheet.GetViews() as object[];
            View view = viewsObj != null && viewsObj.Length > 0 ? viewsObj[0] as View : null;
            if (view == null)
            {
                return drawDoc;
            }

            double[] ratio = { 1.0, 1.0 };
            view.ScaleRatio = ratio;
            sheet.SetScale(1, 1, false, false);

            drawDoc.ForceRebuild3(true);
            RemoveDimensions(drawDoc, view);
            RemoveTables(drawDoc, view);
            FitSheetToView(sheet, view);

            return drawDoc;
        }

        private void RemoveDimensions(ModelDoc2 model, View view)
        {
            object annotationsObj = view.GetAnnotations();
            object[] annotations = annotationsObj as object[];
            if (annotations == null || annotations.Length == 0)
            {
                return;
            }

            var toDelete = new List<Annotation>();
            foreach (object obj in annotations)
            {
                Annotation ann = obj as Annotation;
                if (ann != null)
                {
                    toDelete.Add(ann);
                }
            }

            if (toDelete.Count == 0)
            {
                return;
            }

            int selected = model.Extension.MultiSelect2(toDelete.ToArray(), false, null);
            if (selected == toDelete.Count)
            {
                model.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
            }
        }

        private void RemoveTables(ModelDoc2 model, View view)
        {
            DrawingDoc drawing = model as DrawingDoc;
            if (drawing == null)
            {
                return;
            }

            object sheetsObj = drawing.GetViews();
            object[] sheets = sheetsObj as object[];
            if (sheets == null || sheets.Length == 0)
            {
                return;
            }

            object[] firstSheetViews = sheets[0] as object[];
            if (firstSheetViews == null || firstSheetViews.Length == 0)
            {
                return;
            }

            View sheetView = firstSheetViews[0] as View;
            if (sheetView == null)
            {
                return;
            }

            object tablesObj = sheetView.GetTableAnnotations();
            object[] tables = tablesObj as object[];
            if (tables == null || tables.Length == 0)
            {
                return;
            }

            int selected = model.Extension.MultiSelect2(tables, false, null);
            if (selected == tables.Length)
            {
                model.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
            }
        }

        private void FitSheetToView(Sheet sheet, View view)
        {
            double[] outline = view.GetOutline() as double[];
            if (outline == null || outline.Length < 4)
            {
                return;
            }

            double width = outline[2] - outline[0];
            double height = outline[3] - outline[1];
            sheet.SetSize((int)swDwgPaperSizes_e.swDwgPapersUserDefined, width, height);

            double[] position = view.Position as double[];
            if (position == null || position.Length < 2)
            {
                return;
            }

            position[0] = position[0] - outline[0];
            position[1] = position[1] - outline[1];
            view.Position = position;
        }

        private bool TryGetDrawingReference(DrawingDoc draw, out DrawingReference reference)
        {
            reference = new DrawingReference();
            if (draw == null)
            {
                return false;
            }

            string[] sheetNames = ToStringArray(draw.GetSheetNames());
            if (sheetNames == null || sheetNames.Length == 0)
            {
                return false;
            }

            Sheet sheet = draw.get_Sheet(sheetNames[0]);
            if (sheet == null)
            {
                return false;
            }

            draw.ActivateSheet(sheetNames[0]);

            string viewName = sheet.CustomPropertyView;
            View[] views = GetSheetViews(draw, sheet);
            if (views == null || views.Length == 0)
            {
                return false;
            }

            if (string.Equals(viewName, "Default", StringComparison.OrdinalIgnoreCase))
            {
                viewName = views[0].Name;
            }

            foreach (View view in views)
            {
                if (string.Equals(view.Name, viewName, StringComparison.OrdinalIgnoreCase))
                {
                    ModelDoc2 model = view.ReferencedDocument;
                    string confName = view.ReferencedConfiguration;
                    if (model == null)
                    {
                        return false;
                    }

                    model.ShowConfiguration(confName);
                    Configuration conf = model.GetConfigurationByName(confName) as Configuration;
                    reference = new DrawingReference { Model = model, Configuration = conf };
                    return true;
                }
            }

            return false;
        }

        private View[] GetSheetViews(DrawingDoc draw, Sheet sheet)
        {
            object viewsObj = draw.GetViews();
            object[] sheets = viewsObj as object[];
            if (sheets == null)
            {
                return new View[0];
            }

            foreach (object sheetViewsObj in sheets)
            {
                object[] views = sheetViewsObj as object[];
                if (views == null || views.Length == 0)
                {
                    continue;
                }

                View sheetView = views[0] as View;
                if (sheetView != null &&
                    string.Equals(sheetView.Name, sheet.GetName(), StringComparison.OrdinalIgnoreCase))
                {
                    if (views.Length <= 1)
                    {
                        return new View[0];
                    }

                    var result = new View[views.Length - 1];
                    for (int i = 1; i < views.Length; i++)
                    {
                        result[i - 1] = views[i] as View;
                    }

                    return result;
                }
            }

            return new View[0];
        }

        private string GetFileString(ModelDoc2 model, string configName)
        {
            string tempRev = (GetEvalProperty(model, configName, "revision") ?? string.Empty).Trim();
            Configuration config = model.GetConfigurationByName(configName) as Configuration;
            string fileString = BomPartNumber(config, model) + "_REV_" + tempRev;
            return fileString.ToUpperInvariant();
        }

        private string BomPartNumber(Configuration config, ModelDoc2 document)
        {
            if (config == null)
            {
                return string.Empty;
            }

            string partNumber = string.Empty;
            switch ((swBOMPartNumberSource_e)config.BOMPartNoSource)
            {
                case swBOMPartNumberSource_e.swBOMPartNumber_ConfigurationName:
                    partNumber = config.Name;
                    break;
                case swBOMPartNumberSource_e.swBOMPartNumber_DocumentName:
                    string title = document.GetTitle();
                    partNumber = Path.GetFileNameWithoutExtension(title);
                    break;
                case swBOMPartNumberSource_e.swBOMPartNumber_UserSpecified:
                    partNumber = config.AlternateName;
                    break;
                case swBOMPartNumberSource_e.swBOMPartNumber_ParentName:
                    Configuration parent = config.GetParent() as Configuration;
                    if (parent != null && parent.BOMPartNoSource == (int)swBOMPartNumberSource_e.swBOMPartNumber_ParentName)
                    {
                        partNumber = BomPartNumber(parent, document);
                    }
                    else if (parent != null)
                    {
                        partNumber = parent.Name;
                    }
                    break;
            }

            if (string.Equals(partNumber, "allocate", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(partNumber, "default", StringComparison.OrdinalIgnoreCase))
            {
                // Never mutate the document/config during batch export. Some models (toolbox, vendor parts,
                // or "default"/"allocate" configs) can yield unusable BOM part numbers; generate a stable
                // fallback purely for naming purposes.
                string baseName = string.Empty;
                try
                {
                    baseName = Path.GetFileNameWithoutExtension(document.GetPathName());
                }
                catch
                {
                    baseName = string.Empty;
                }
                if (string.IsNullOrWhiteSpace(baseName))
                {
                    baseName = Path.GetFileNameWithoutExtension(document.GetTitle());
                }

                string derived = SanitizeFileName("FIX_" + baseName + "_" + config.Name);
                derived = ReplaceNonAlphaNumeric(derived);
                partNumber = derived;
            }

            return partNumber;
        }

        private string ReplaceNonAlphaNumeric(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return string.Empty;
            }

            var result = new StringBuilder(input.Length);
            foreach (char c in input)
            {
                if (char.IsLetterOrDigit(c))
                {
                    result.Append(c);
                }
                else
                {
                    result.Append('_');
                }
            }

            return result.ToString();
        }

        private string SanitizeFileName(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return string.Empty;
            }

            string invalid = ",\\/:*?\"<>| ";
            foreach (char c in invalid)
            {
                string replacement = c == ' ' ? "_" : string.Empty;
                input = input.Replace(c.ToString(), replacement);
            }

            return input;
        }

        private string GetDocDict(ModelDoc2 model, string confName)
        {
            Configuration modelConf = model.GetConfigurationByName(confName) as Configuration;
            string[] minProperties =
            {
                "approved", "author", "checkedby", "category", "oem_data_sheet", "item_no", "description",
                "drawndate", "finish", "oem_internet", "mass", "material", "oem_supplier", "process", "process2",
                "process3", "revision", "spare_part", "distributor", "oem_part_number", "spare_part", "supplier",
                "supplier_partnumber", "asset", "thickness", "treatment", "colour", "design_notes", "comments",
                "classified", "secondprocess", "thirdprocess", "datasheet"
            };

            var json = new StringBuilder();
            json.Append("{");
            json.Append("'partnumber':'")
                .Append(SanitizeString(BomPartNumber(modelConf, model)))
                .Append("',");
            json.Append("'sw_configuration':'")
                .Append(SanitizeString(confName))
                .Append("',");

            for (int i = 0; i < minProperties.Length; i++)
            {
                string prop = minProperties[i];
                string value = GetEvalProperty(model, confName, prop);
                if (string.IsNullOrEmpty(value) &&
                    !string.Equals(prop, "partnumber", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(prop, "revision", StringComparison.OrdinalIgnoreCase))
                {
                    value = GetEvalProperty(model, string.Empty, prop);
                }

                json.Append("'").Append(prop).Append("':'")
                    .Append(SanitizeString((value ?? string.Empty).Replace("\\", "/")))
                    .Append("',");
            }

            json.Append("'path':'")
                .Append((model.GetPathName() ?? string.Empty).Replace("\\", "/"))
                .Append("',");
            json.Append("'file':'")
                .Append(OnlyFile(model.GetPathName()))
                .Append("',");
            json.Append("'folder':'")
                .Append(OnlyFolder(model.GetPathName()).Replace("\\", "/"))
                .Append("'");

            string[] configProps = GetCustomPropertyNames(model, confName);
            foreach (string prop in configProps)
            {
                if (string.IsNullOrWhiteSpace(prop))
                {
                    continue;
                }

                if (ContainsProperty(json, prop) ||
                    string.Equals(prop, "partnumber", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string value = GetEvalProperty(model, confName, prop);
                json.Append(",'").Append(prop).Append("':'")
                    .Append(SanitizeString((value ?? string.Empty).Replace("\\", "/")))
                    .Append("'");
            }

            string[] partProps = GetCustomPropertyNames(model, string.Empty);
            foreach (string prop in partProps)
            {
                if (string.IsNullOrWhiteSpace(prop))
                {
                    continue;
                }

                if (ContainsProperty(json, prop) ||
                    string.Equals(prop, "partnumber", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string value = GetEvalProperty(model, string.Empty, prop);
                json.Append(",'").Append(prop).Append("':'")
                    .Append(SanitizeString((value ?? string.Empty).Replace("\\", "/")))
                    .Append("'");
            }

            json.Append("}");
            return json.ToString();
        }

        private string[] GetCustomPropertyNames(ModelDoc2 model, string confName)
        {
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[confName];
            object namesObj = cpm.GetNames();
            return ToStringArray(namesObj) ?? new string[0];
        }

        private static string[] ToStringArray(object values)
        {
            string[] strings = values as string[];
            if (strings != null)
            {
                return strings;
            }

            object[] objs = values as object[];
            if (objs == null)
            {
                return null;
            }

            var result = new string[objs.Length];
            for (int i = 0; i < objs.Length; i++)
            {
                result[i] = objs[i] != null ? objs[i].ToString() : string.Empty;
            }

            return result;
        }

        private bool ContainsProperty(StringBuilder json, string prop)
        {
            if (string.IsNullOrWhiteSpace(prop))
            {
                return false;
            }

            return json.ToString().IndexOf("'" + prop + "':", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private bool HasCustomProperty(ModelDoc2 model, string confName, string property)
        {
            if (model == null || string.IsNullOrWhiteSpace(property))
            {
                return false;
            }

            string[] names = GetCustomPropertyNames(model, confName);
            if (names == null || names.Length == 0)
            {
                return false;
            }

            foreach (string name in names)
            {
                if (string.Equals(name, property, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        private string GetEvalProperty(ModelDoc2 model, string confName, string property)
        {
            if (model == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrEmpty(confName))
            {
                model.ShowConfiguration(confName);
            }

            string valOut;
            string resolved;
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[confName];
            cpm.Get2(property, out valOut, out resolved);

            bool hasConfigProperty = !string.IsNullOrEmpty(confName) &&
                HasCustomProperty(model, confName, property);

            if (string.Equals(property, "revision", StringComparison.OrdinalIgnoreCase) &&
                string.IsNullOrEmpty(resolved) &&
                !string.IsNullOrEmpty(confName) &&
                !hasConfigProperty)
            {
                cpm = model.Extension.CustomPropertyManager[string.Empty];
                cpm.Get2(property, out valOut, out resolved);
            }

            return resolved ?? string.Empty;
        }

        private string GetRawProperty(ModelDoc2 model, string confName, string property)
        {
            if (model == null || string.IsNullOrWhiteSpace(property))
            {
                return string.Empty;
            }

            string conf = confName ?? string.Empty;
            if (!string.IsNullOrEmpty(conf))
            {
                model.ShowConfiguration(conf);
            }

            string valOut;
            string resolved;
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[conf];
            cpm.Get2(property, out valOut, out resolved);
            if (!string.IsNullOrWhiteSpace(resolved))
            {
                return resolved;
            }
            return valOut ?? string.Empty;
        }

        private bool HasProcess(ModelDoc2 model, string confName, string process)
        {
            if (string.IsNullOrWhiteSpace(process))
            {
                return false;
            }

            return ContainsIgnoreCase(GetEvalProperty(model, confName, "process"), process) ||
                   ContainsIgnoreCase(GetEvalProperty(model, confName, "process2"), process) ||
                   ContainsIgnoreCase(GetEvalProperty(model, confName, "process3"), process);
        }

        private bool ContainsIgnoreCase(string source, string value)
        {
            if (string.IsNullOrEmpty(source) || string.IsNullOrEmpty(value))
            {
                return false;
            }

            return source.IndexOf(value, StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private string SanitizeString(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return string.Empty;
            }

            return SanitizeRegex.Replace(input, string.Empty);
        }

        private string OnlyFile(string path)
        {
            return string.IsNullOrWhiteSpace(path) ? string.Empty : Path.GetFileName(path);
        }

        private string OnlyFolder(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            string folder = Path.GetDirectoryName(path);
            if (string.IsNullOrWhiteSpace(folder))
            {
                return string.Empty;
            }

            return EnsureTrailingSlash(folder);
        }

        private string EnsureTrailingSlash(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            if (path.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal))
            {
                return path;
            }

            return path + Path.DirectorySeparatorChar;
        }

        private void SetUnitPreferences(ModelDoc2 model)
        {
            ModelDocExtension ext = model.Extension;
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsLinear, 0,
                (int)swLengthUnit_e.swMM);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsLinearDecimalPlaces, 0, 1);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsDualLinear, 0,
                (int)swLengthUnit_e.swMM);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsDualLinearDecimalPlaces, 0, 4);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsAngular, 0,
                (int)swAngleUnit_e.swDEGREES);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsAngularDecimalPlaces, 0, 1);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropLength, 0,
                (int)swLengthUnit_e.swMM);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropDecimalPlaces, 0, 1);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropMass, 0,
                (int)swUnitsMassPropMass_e.swUnitsMassPropMass_Kilograms);
            ext.SetUserPreferenceInteger((int)swUserPreferenceIntegerValue_e.swUnitsMassPropVolume, 0,
                (int)swUnitsMassPropVolume_e.swUnitsMassPropVolume_Liters);
        }

        private PublishOptions NormalizeOptions(PublishOptions options)
        {
            if (options == null)
            {
                options = new PublishOptions();
            }

            if (string.IsNullOrWhiteSpace(options.DeliverablesFolder))
            {
                options.DeliverablesFolder = _config.DeliverablesFolder;
            }

            if (string.IsNullOrWhiteSpace(options.BomFolder))
            {
                options.BomFolder = _config.BomFolder;
            }

            return options;
        }

        private void Log(Action<string> log, string message)
        {
            if (log != null)
            {
                log(message);
            }
        }

        private void LogExportFailure(Action<string> log, Action<string> errorLog, string message)
        {
            if (string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            Log(log, message);
            if (errorLog != null)
            {
                errorLog(message);
            }
        }

        private void DebugExport(Action<string> errorLog, string message)
        {
            if (!EnableExportDebugLog || errorLog == null || string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            try
            {
                errorLog("DBG: " + message);
            }
            catch
            {
                // ignore logging errors
            }
        }

        private void DebugExportOnce(Action<string> errorLog, string key, string message)
        {
            if (!EnableExportDebugLog || errorLog == null || string.IsNullOrWhiteSpace(key) || string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            if (!_debugOnce.Add(key))
            {
                return;
            }

            DebugExport(errorLog, message);
        }

        private void LogCloseWarningOnce(Action<string> errorLog, string context, string title, string path)
        {
            if (errorLog == null)
            {
                return;
            }

            string id = !string.IsNullOrWhiteSpace(path) ? path : (title ?? string.Empty);
            string key = (context ?? string.Empty) + "|" + id;
            if (!_closeWarningOnce.Add(key))
            {
                return;
            }

            errorLog("Warning: unable to close document (context: " + (context ?? string.Empty) + "): " +
                     (string.IsNullOrWhiteSpace(title) ? "<no title>" : title) +
                     " | " + (string.IsNullOrWhiteSpace(path) ? "<no path>" : path));
        }

        private ExportRunLog CreateExportRunLog()
        {
            try
            {
                string dir = Path.Combine(Path.GetTempPath(), "TinyMRP", "export-logs");
                string name = "deliverables_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".log";
                string path = Path.Combine(dir, name);
                return new ExportRunLog(path);
            }
            catch
            {
                return null;
            }
        }

        private string BuildRunLogMessage(string baseMessage, ExportRunLog runLog)
        {
            if (runLog != null && runLog.HasEntries)
            {
                return baseMessage + " See log: " + runLog.Path;
            }

            return baseMessage;
        }

        private void LogHideDebug(string path, string message)
        {
            if (!EnableHideDebugLog || string.IsNullOrWhiteSpace(path))
            {
                return;
            }

            try
            {
                File.AppendAllText(path, DateTime.Now.ToString("s") + " " + message + System.Environment.NewLine);
            }
            catch
            {
                // ignore logging errors
            }
        }

        private void UpdateProgress(Action<int, int> progress, int current, int total)
        {
            if (progress != null)
            {
                progress(current, total);
            }
        }

        public void RequestCancel()
        {
            _cancelRequested = true;
        }

        private void ResetCancel()
        {
            _cancelRequested = false;
        }

        private void ThrowIfCancelled()
        {
            if (_cancelRequested)
            {
                throw new OperationCanceledException();
            }
        }

        private void CreateZipWithFolder(string zipPath, string folderName, params string[] filePaths)
        {
            string normalizedFolder = (folderName ?? string.Empty).Trim();
            normalizedFolder = normalizedFolder.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

            using (var stream = new FileStream(zipPath, FileMode.Create, FileAccess.Write, FileShare.None))
            using (var archive = new ZipArchive(stream, ZipArchiveMode.Create, false, Encoding.UTF8))
            {
                if (!string.IsNullOrWhiteSpace(normalizedFolder))
                {
                    archive.CreateEntry(normalizedFolder + "/");
                }

                foreach (string filePath in filePaths)
                {
                    if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
                    {
                        continue;
                    }

                    string entryName = string.IsNullOrWhiteSpace(normalizedFolder)
                        ? Path.GetFileName(filePath)
                        : normalizedFolder + "/" + Path.GetFileName(filePath);

                    archive.CreateEntryFromFile(filePath, entryName, CompressionLevel.Optimal);
                }
            }
        }

        private void MoveFileIfExists(string source, string dest)
        {
            if (string.IsNullOrWhiteSpace(source) || !File.Exists(source))
            {
                return;
            }

            if (File.Exists(dest))
            {
                File.Delete(dest);
            }

            File.Move(source, dest);
        }

        private void TryDeleteDirectory(string path)
        {
            try
            {
                if (Directory.Exists(path))
                {
                    Directory.Delete(path, true);
                }
            }
            catch
            {
                // ignore cleanup errors
            }
        }

        private void TryDeleteFile(string path)
        {
            try
            {
                if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch
            {
                // ignore cleanup errors
            }
        }

        private IEnumerable<ModelDoc2> EnumerateOpenDocuments()
        {
            object docsObj = null;
            try
            {
                docsObj = _swApp.GetDocuments();
            }
            catch
            {
                yield break;
            }

            if (docsObj == null)
            {
                yield break;
            }

            // SolidWorks may return a SAFEARRAY (Array) or, in some edge cases, a single COM object.
            Array docsArray = docsObj as Array;
            if (docsArray != null)
            {
                foreach (object obj in docsArray)
                {
                    ModelDoc2 doc = obj as ModelDoc2;
                    if (doc != null)
                    {
                        yield return doc;
                    }
                }

                yield break;
            }

            ModelDoc2 single = docsObj as ModelDoc2;
            if (single != null)
            {
                yield return single;
            }
        }

        // Snapshot of currently-open documents. Used to enforce "no doc leaks" during batch operations.
        private HashSet<string> SnapshotOpenDocIds()
        {
            return GetOpenDocumentIds();
        }

        private void AddDocToKeepSet(HashSet<string> keep, ModelDoc2 doc, string fallbackTitle)
        {
            if (keep == null)
            {
                return;
            }

            if (doc != null)
            {
                try
                {
                    string path = doc.GetPathName();
                    if (!string.IsNullOrWhiteSpace(path))
                    {
                        keep.Add(path);
                    }
                }
                catch
                {
                    // ignore keep-path errors
                }

                try
                {
                    string title = doc.GetTitle();
                    if (!string.IsNullOrWhiteSpace(title))
                    {
                        keep.Add(title);
                        string normalized = NormalizeDocTitleForClose(title);
                        if (!string.IsNullOrWhiteSpace(normalized))
                        {
                            keep.Add(normalized);
                        }
                    }
                }
                catch
                {
                    // ignore keep-title errors
                }
            }

            if (!string.IsNullOrWhiteSpace(fallbackTitle))
            {
                keep.Add(fallbackTitle);
                string normalized = NormalizeDocTitleForClose(fallbackTitle);
                if (!string.IsNullOrWhiteSpace(normalized))
                {
                    keep.Add(normalized);
                }
            }
        }

        private bool IsBaselineAbortException(Exception ex)
        {
            while (ex != null)
            {
                InvalidOperationException invalid = ex as InvalidOperationException;
                if (invalid != null &&
                    !string.IsNullOrWhiteSpace(invalid.Message) &&
                    invalid.Message.IndexOf("Unable to close leaked documents", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return true;
                }

                ex = ex.InnerException;
            }

            return false;
        }

        private bool IsDocOpenByIdOrTitle(string id, string title)
        {
            if (string.IsNullOrWhiteSpace(id) && string.IsNullOrWhiteSpace(title))
            {
                return false;
            }

            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                string docPath = string.Empty;
                string docTitle = string.Empty;
                try
                {
                    docPath = doc.GetPathName();
                    docTitle = doc.GetTitle();
                }
                catch
                {
                    docPath = string.Empty;
                    docTitle = string.Empty;
                }

                string docTitleNorm = NormalizeDocTitleForClose(docTitle);
                string idNorm = NormalizeDocTitleForClose(id);
                string titleNorm = NormalizeDocTitleForClose(title);

                if (!string.IsNullOrWhiteSpace(id))
                {
                    if ((!string.IsNullOrWhiteSpace(docPath) &&
                         string.Equals(docPath, id, StringComparison.OrdinalIgnoreCase)) ||
                        (!string.IsNullOrWhiteSpace(docTitleNorm) &&
                         string.Equals(docTitleNorm, idNorm, StringComparison.OrdinalIgnoreCase)))
                    {
                        return true;
                    }
                }

                if (!string.IsNullOrWhiteSpace(title))
                {
                    if ((!string.IsNullOrWhiteSpace(docPath) &&
                         string.Equals(docPath, title, StringComparison.OrdinalIgnoreCase)) ||
                        (!string.IsNullOrWhiteSpace(docTitleNorm) &&
                         string.Equals(docTitleNorm, titleNorm, StringComparison.OrdinalIgnoreCase)))
                    {
                        return true;
                    }
                }
            }

            return false;
        }

        private bool IsDocInKeepSet(ModelDoc2 doc, HashSet<string> keep)
        {
            if (doc == null)
            {
                return true;
            }
            if (keep == null || keep.Count == 0)
            {
                return false;
            }

            string path = string.Empty;
            string title = string.Empty;
            bool gotIdentity = false;
            try
            {
                path = doc.GetPathName();
                gotIdentity = !string.IsNullOrWhiteSpace(path);
            }
            catch
            {
                path = string.Empty;
            }
            try
            {
                title = doc.GetTitle();
                gotIdentity = gotIdentity || !string.IsNullOrWhiteSpace(title);
            }
            catch
            {
                title = string.Empty;
            }

            if (!gotIdentity)
            {
                // Defensive: if we cannot read a document's identity (path/title), do not attempt to close it.
                // Mis-identifying and closing the root/start document causes RPC_E_DISCONNECTED.
                return true;
            }

            if (!string.IsNullOrWhiteSpace(path) && keep.Contains(path))
            {
                return true;
            }
            if (!string.IsNullOrWhiteSpace(title) && keep.Contains(title))
            {
                return true;
            }
            if (!string.IsNullOrWhiteSpace(title))
            {
                string normalized = NormalizeDocTitleForClose(title);
                if (!string.IsNullOrWhiteSpace(normalized) && keep.Contains(normalized))
                {
                    return true;
                }
            }

            return false;
        }

        private List<ModelDoc2> GetOpenDocsNotInKeepSet(HashSet<string> keep)
        {
            var leaked = new List<ModelDoc2>();
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                if (!IsDocInKeepSet(doc, keep))
                {
                    leaked.Add(doc);
                }
            }

            return leaked;
        }

        private void EnsureDocBaseline(HashSet<string> keep, Action<string> log, Action<string> errorLog, string reason,
            bool allowCancel = false)
        {
            using (new ExportDialogSuppressionScope(_swApp))
            using (new ExternalReferenceBatchOpenScope(_swApp))
            {
                if (allowCancel)
                {
                    ThrowIfCancelled();
                }

                if (keep == null)
                {
                    keep = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                }

                // If we have documents to close, pre-emptively lightweight kept assemblies (esp. root) so they
                // don't immediately re-open resolved child documents while we are trying to close back to baseline.
                List<ModelDoc2> preClose = GetOpenDocsNotInKeepSet(keep);
                if (preClose.Count > 0)
                {
                    TryLightweightAssembliesInKeepSet(keep, log, errorLog, reason, allowCancel);
                }

                const int maxPasses = 3;
                CloseOpenDocsToBaseline(keep, log, errorLog, reason, maxPasses, allowCancel);

                List<ModelDoc2> remaining = GetOpenDocsNotInKeepSet(keep);
                if (remaining.Count > 0)
                {
                    // Some documents cannot be closed while referenced by an open assembly. Try again after
                    // switching any kept assemblies back to lightweight.
                    if (allowCancel)
                    {
                        ThrowIfCancelled();
                    }
                    TryLightweightAssembliesInKeepSet(keep, log, errorLog, reason, allowCancel);
                    CloseOpenDocsToBaseline(keep, log, errorLog, reason, maxPasses, allowCancel);
                    remaining = GetOpenDocsNotInKeepSet(keep);
                }

                if (remaining.Count > 0)
                {
                    bool hasVirtualComponents = false;
                    foreach (ModelDoc2 doc in remaining)
                    {
                        string path = string.Empty;
                        try
                        {
                            path = doc.GetPathName();
                        }
                        catch
                        {
                            path = string.Empty;
                        }

                        if (!string.IsNullOrWhiteSpace(path) &&
                            path.IndexOf("\\VC~~\\", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            hasVirtualComponents = true;
                            break;
                        }
                    }

                    if (hasVirtualComponents)
                    {
                        DebugExport(errorLog,
                            "Leak-guard: remaining leaks include VC~~ virtual component temp docs. These often cannot " +
                            "be closed while their owning assembly remains open/resolved.");
                    }

                    if (errorLog != null)
                    {
                        errorLog("Document leak detected after baseline enforcement (" + (reason ?? string.Empty) +
                                 "). Leaked documents:");
                        foreach (ModelDoc2 doc in remaining)
                        {
                            string title = string.Empty;
                            string path = string.Empty;
                            try
                            {
                                title = doc.GetTitle();
                                path = doc.GetPathName();
                            }
                            catch
                            {
                                title = string.Empty;
                                path = string.Empty;
                            }

                            errorLog(" - " + (string.IsNullOrWhiteSpace(title) ? "<no title>" : title) +
                                     " | " + (string.IsNullOrWhiteSpace(path) ? "<no path>" : path));
                        }
                    }

                    LogExportFailure(log, errorLog,
                        "Unable to close leaked documents; aborting to prevent SolidWorks crash.");
                    throw new InvalidOperationException(
                        "Unable to close leaked documents; aborting to prevent SolidWorks crash.");
                }
            }
        }

        private int GetDocCloseOrder(ModelDoc2 doc)
        {
            if (doc == null)
            {
                return int.MaxValue;
            }

            int docType = 0;
            try
            {
                docType = doc.GetType();
            }
            catch
            {
                docType = 0;
            }

            if (docType == (int)swDocumentTypes_e.swDocDRAWING)
            {
                return 0;
            }
            if (docType == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                return 1;
            }
            if (docType == (int)swDocumentTypes_e.swDocPART)
            {
                return 2;
            }

            return 3;
        }

        private void CloseOpenDocsToBaseline(HashSet<string> keep, Action<string> log, Action<string> errorLog,
            string reason, int maxPasses, bool allowCancel)
        {
            int passes = maxPasses > 0 ? maxPasses : 1;
            for (int pass = 0; pass < passes; pass++)
            {
                if (allowCancel)
                {
                    ThrowIfCancelled();
                }
                List<ModelDoc2> toClose = GetOpenDocsNotInKeepSet(keep);
                if (toClose.Count == 0)
                {
                    return;
                }

                DebugExport(errorLog,
                    "Baseline pass " + (pass + 1) + "/" + passes +
                    " reason=" + (reason ?? string.Empty) +
                    " closingDocs=" + toClose.Count);

                toClose.Sort((a, b) => GetDocCloseOrder(a).CompareTo(GetDocCloseOrder(b)));
                foreach (ModelDoc2 doc in toClose)
                {
                    if (allowCancel)
                    {
                        ThrowIfCancelled();
                    }
                    // Defensive: if the doc looks like it belongs to the keep set now (COM calls can be transient),
                    // never attempt to close it. Closing the root/start document disconnects COM clients.
                    if (IsDocInKeepSet(doc, keep))
                    {
                        DebugExportOnce(errorLog,
                            "Baseline: skipKeep|" + GetDocumentId(doc),
                            "Baseline: skip close because doc matched keep set reason=" + (reason ?? string.Empty));
                        continue;
                    }
                    ForceCloseDocNoSave(doc, errorLog, reason, allowCancel);
                }

                System.Windows.Forms.Application.DoEvents();
                // Give SolidWorks a brief moment to finish background operations (exports/rebuilds) before re-checking.
                try
                {
                    System.Threading.Thread.Sleep(75);
                }
                catch
                {
                    // ignore sleep errors
                }
            }
        }

        private void TryLightweightAssembliesInKeepSet(HashSet<string> keep, Action<string> log, Action<string> errorLog,
            string context, bool allowCancel)
        {
            if (allowCancel)
            {
                ThrowIfCancelled();
            }
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                if (allowCancel)
                {
                    ThrowIfCancelled();
                }

                if (!IsDocInKeepSet(doc, keep))
                {
                    continue;
                }

                int docType = 0;
                try
                {
                    docType = doc.GetType();
                }
                catch
                {
                    docType = 0;
                }

                if (docType != (int)swDocumentTypes_e.swDocASSEMBLY)
                {
                    continue;
                }

                string title = string.Empty;
                try
                {
                    title = doc.GetTitle();
                }
                catch
                {
                    title = string.Empty;
                }

                try
                {
                    string activateTitle = NormalizeDocTitleForClose(title);
                    if (!string.IsNullOrWhiteSpace(activateTitle))
                    {
                        _swApp.ActivateDoc(activateTitle);
                    }
                }
                catch
                {
                    // ignore activation errors
                }

                AssemblyDoc assy = doc as AssemblyDoc;
                if (assy == null)
                {
                    continue;
                }

                try
                {
                    try
                    {
                        // If anything is selected, SolidWorks applies LightweightAllResolved to the selection
                        // instead of the whole assembly. Clear selection so we unload everything we can.
                        doc.ClearSelection2(true);
                    }
                    catch
                    {
                        // ignore selection-clear errors
                    }

                    bool ok = false;
                    try
                    {
                        ok = assy.LightweightAllResolved();
                    }
                    catch
                    {
                        ok = false;
                    }
                    try
                    {
                        assy.MakeLightWeight();
                    }
                    catch
                    {
                        // ignore make-lightweight errors
                    }
                    DebugExport(errorLog,
                        "Leak-guard: lightweight kept assembly (" + (context ?? string.Empty) + "): " + title +
                        (ok ? "" : " (partial/failed)"));
                }
                catch (Exception ex)
                {
                    LogExportFailure(log, errorLog,
                        "Leak-guard: failed to lightweight assembly (" + title + "): " + ex.Message);
                }

                System.Windows.Forms.Application.DoEvents();
                try
                {
                    System.Threading.Thread.Sleep(100);
                }
                catch
                {
                    // ignore sleep errors
                }
            }
        }

        private string NormalizeDocTitleForClose(string title)
        {
            if (string.IsNullOrWhiteSpace(title))
            {
                return string.Empty;
            }

            string normalized = title.Trim();

            // SolidWorks shows dirty documents with a trailing "*" in the UI title, but API calls like CloseDoc/QuitDoc
            // typically expect the base document title.
            while (normalized.EndsWith("*", StringComparison.Ordinal))
            {
                normalized = normalized.Substring(0, normalized.Length - 1).TrimEnd();
            }

            return normalized;
        }

        private void ForceCloseDocNoSave(ModelDoc2 doc, Action<string> errorLog = null, string context = "", bool allowCancel = false)
        {
            if (doc == null)
            {
                return;
            }

            if (allowCancel)
            {
                ThrowIfCancelled();
            }

            string title = string.Empty;
            string path = string.Empty;
            try
            {
                title = doc.GetTitle();
                path = doc.GetPathName();
            }
            catch
            {
                title = string.Empty;
                path = string.Empty;
            }

            bool dirty = false;
            int docType = 0;
            try
            {
                dirty = doc.GetSaveFlag();
            }
            catch
            {
                dirty = false;
            }
            try
            {
                docType = doc.GetType();
            }
            catch
            {
                docType = 0;
            }

            string closeTitle = NormalizeDocTitleForClose(title);

            bool IsStillOpen()
            {
                if (IsDocOpenByIdOrTitle(path, title))
                {
                    return true;
                }

                if (!string.IsNullOrWhiteSpace(closeTitle) &&
                    !string.Equals(closeTitle, title, StringComparison.OrdinalIgnoreCase))
                {
                    return IsDocOpenByIdOrTitle(path, closeTitle);
                }

                return false;
            }

            bool prevCommand = false;
            bool prevUser = true;
            bool prevUserBackground = true;

            try
            {
                prevCommand = _swApp.CommandInProgress;
                prevUser = _swApp.UserControl;
                prevUserBackground = _swApp.UserControlBackground;
            }
            catch
            {
                // ignore state read errors
            }

            try
            {
                try
                {
                    _swApp.CommandInProgress = true;
                }
                catch
                {
                    // ignore state set errors
                }
                try
                {
                    _swApp.UserControl = false;
                }
                catch
                {
                    // ignore state set errors
                }
                try
                {
                    _swApp.UserControlBackground = true;
                }
                catch
                {
                    // ignore state set errors
                }

                if (dirty)
                {
                    DebugExport(errorLog,
                        "ForceClose: closing dirty doc context=" + (context ?? string.Empty) +
                        " type=" + docType +
                        " title=" + (title ?? string.Empty) +
                        " path=" + (path ?? string.Empty));
                }

                const int maxPasses = 3;
                for (int pass = 0; pass < maxPasses; pass++)
                {
                    if (allowCancel)
                    {
                        ThrowIfCancelled();
                    }
                    if (!IsStillOpen())
                    {
                        return;
                    }

                    // Assemblies can keep children open; try light-weighting before closing. This also reduces the
                    // chance that SOLIDWORKS keeps re-opening referenced docs while we're closing back to baseline.
                    try
                    {
                        if (doc.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY)
                        {
                            try
                            {
                                doc.ClearSelection2(true);
                            }
                            catch
                            {
                                // ignore selection errors
                            }

                            AssemblyDoc assy = doc as AssemblyDoc;
                            if (assy != null)
                            {
                                try
                                {
                                    assy.LightweightAllResolved();
                                }
                                catch
                                {
                                    // ignore lightweight errors
                                }
                                try
                                {
                                    assy.MakeLightWeight();
                                }
                                catch
                                {
                                    // ignore lightweight errors
                                }
                            }
                        }
                    }
                    catch
                    {
                        // ignore type/lightweight errors
                    }

                    // a) QuitDoc (discard changes, no UI)
                    try
                    {
                        if (!string.IsNullOrWhiteSpace(closeTitle))
                        {
                            _swApp.QuitDoc(closeTitle);
                        }
                        else if (!string.IsNullOrWhiteSpace(title))
                        {
                            _swApp.QuitDoc(title);
                        }

                        if (IsStillOpen() && !string.IsNullOrWhiteSpace(title) &&
                            !string.Equals(title, closeTitle, StringComparison.OrdinalIgnoreCase))
                        {
                            _swApp.QuitDoc(title);
                        }
                    }
                    catch
                    {
                        // ignore quit errors
                    }

                    System.Windows.Forms.Application.DoEvents();
                    try
                    {
                        System.Threading.Thread.Sleep(50);
                    }
                    catch
                    {
                        // ignore sleep errors
                    }
                    if (!IsStillOpen())
                    {
                        return;
                    }

                    if (allowCancel)
                    {
                        ThrowIfCancelled();
                    }
                    // b) CloseDoc (releases UI resources; may keep model data loaded if referenced)
                    try
                    {
                        if (!string.IsNullOrWhiteSpace(closeTitle))
                        {
                            _swApp.CloseDoc(closeTitle);
                        }
                        else if (!string.IsNullOrWhiteSpace(title))
                        {
                            _swApp.CloseDoc(title);
                        }

                        if (IsStillOpen() && !string.IsNullOrWhiteSpace(title) &&
                            !string.Equals(title, closeTitle, StringComparison.OrdinalIgnoreCase))
                        {
                            _swApp.CloseDoc(title);
                        }
                    }
                    catch
                    {
                        // ignore close errors
                    }

                    System.Windows.Forms.Application.DoEvents();
                    try
                    {
                        System.Threading.Thread.Sleep(50);
                    }
                    catch
                    {
                        // ignore sleep errors
                    }
                    if (!IsStillOpen())
                    {
                        return;
                    }

                    if (allowCancel)
                    {
                        ThrowIfCancelled();
                    }
                    // c) Close active doc after activation (some scenarios only close when active)
                    try
                    {
                        if (!string.IsNullOrWhiteSpace(closeTitle) || !string.IsNullOrWhiteSpace(title))
                        {
                            string desiredTitle = !string.IsNullOrWhiteSpace(closeTitle) ? closeTitle : title;
                            string desiredNorm = NormalizeDocTitleForClose(desiredTitle);
                            int errors = 0;
                            _swApp.ActivateDoc2(desiredTitle, false, ref errors);

                            // CloseDoc("") closes the active document. Only do that if we can verify the activation
                            // succeeded for the target doc; otherwise we risk closing the root/start doc and
                            // disconnecting COM clients (RPC_E_DISCONNECTED).
                            bool activeMatches = false;
                            try
                            {
                                ModelDoc2 active = _swApp.ActiveDoc as ModelDoc2;
                                if (active != null)
                                {
                                    string activePath = string.Empty;
                                    string activeTitle = string.Empty;
                                    try
                                    {
                                        activePath = active.GetPathName();
                                        activeTitle = active.GetTitle();
                                    }
                                    catch
                                    {
                                        activePath = string.Empty;
                                        activeTitle = string.Empty;
                                    }

                                    if (!string.IsNullOrWhiteSpace(path) &&
                                        !string.IsNullOrWhiteSpace(activePath) &&
                                        string.Equals(activePath, path, StringComparison.OrdinalIgnoreCase))
                                    {
                                        activeMatches = true;
                                    }
                                    else if (!string.IsNullOrWhiteSpace(desiredNorm))
                                    {
                                        string activeNorm = NormalizeDocTitleForClose(activeTitle);
                                        activeMatches = !string.IsNullOrWhiteSpace(activeNorm) &&
                                                        string.Equals(activeNorm, desiredNorm, StringComparison.OrdinalIgnoreCase);
                                    }
                                }
                            }
                            catch
                            {
                                activeMatches = false;
                            }

                            if (activeMatches)
                            {
                                _swApp.CloseDoc(string.Empty);
                            }
                            else
                            {
                                DebugExportOnce(errorLog,
                                    "ForceClose: skippedCloseActive|" + (!string.IsNullOrWhiteSpace(path) ? path : (title ?? string.Empty)),
                                    "ForceClose: skipped CloseDoc(\"\") because active doc didn't match target context=" +
                                    (context ?? string.Empty) + " title=" + (title ?? string.Empty) + " path=" + (path ?? string.Empty));
                            }

                            if (IsStillOpen() && !string.IsNullOrWhiteSpace(title) &&
                                !string.Equals(title, closeTitle, StringComparison.OrdinalIgnoreCase))
                            {
                                errors = 0;
                                _swApp.ActivateDoc2(title, false, ref errors);

                                bool activeMatches2 = false;
                                try
                                {
                                    ModelDoc2 active2 = _swApp.ActiveDoc as ModelDoc2;
                                    if (active2 != null)
                                    {
                                        string activePath2 = string.Empty;
                                        string activeTitle2 = string.Empty;
                                        try
                                        {
                                            activePath2 = active2.GetPathName();
                                            activeTitle2 = active2.GetTitle();
                                        }
                                        catch
                                        {
                                            activePath2 = string.Empty;
                                            activeTitle2 = string.Empty;
                                        }

                                        if (!string.IsNullOrWhiteSpace(path) &&
                                            !string.IsNullOrWhiteSpace(activePath2) &&
                                            string.Equals(activePath2, path, StringComparison.OrdinalIgnoreCase))
                                        {
                                            activeMatches2 = true;
                                        }
                                        else
                                        {
                                            string activeNorm2 = NormalizeDocTitleForClose(activeTitle2);
                                            string desiredNorm2 = NormalizeDocTitleForClose(title);
                                            activeMatches2 = !string.IsNullOrWhiteSpace(activeNorm2) &&
                                                             !string.IsNullOrWhiteSpace(desiredNorm2) &&
                                                             string.Equals(activeNorm2, desiredNorm2, StringComparison.OrdinalIgnoreCase);
                                        }
                                    }
                                }
                                catch
                                {
                                    activeMatches2 = false;
                                }

                                if (activeMatches2)
                                {
                                    _swApp.CloseDoc(string.Empty);
                                }
                                else
                                {
                                    DebugExportOnce(errorLog,
                                        "ForceClose: skippedCloseActive2|" + (!string.IsNullOrWhiteSpace(path) ? path : (title ?? string.Empty)),
                                        "ForceClose: skipped CloseDoc(\"\") (retry) because active doc didn't match target context=" +
                                        (context ?? string.Empty) + " title=" + (title ?? string.Empty) + " path=" + (path ?? string.Empty));
                                }
                            }
                        }
                    }
                    catch
                    {
                        // ignore close errors
                    }

                    System.Windows.Forms.Application.DoEvents();
                    try
                    {
                        System.Threading.Thread.Sleep(50);
                    }
                    catch
                    {
                        // ignore sleep errors
                    }
                    if (!IsStillOpen())
                    {
                        return;
                    }
                }
            }
            finally
            {
                try
                {
                    _swApp.CommandInProgress = prevCommand;
                }
                catch
                {
                    // ignore restore errors
                }
                try
                {
                    _swApp.UserControl = prevUser;
                }
                catch
                {
                    // ignore restore errors
                }
                try
                {
                    _swApp.UserControlBackground = prevUserBackground;
                }
                catch
                {
                    // ignore restore errors
                }
            }

            if (IsStillOpen() && errorLog != null)
            {
                LogCloseWarningOnce(errorLog, context, title, path);
            }
        }

        private void CloseNonRootDocs(HashSet<string> initialDocs, ModelDoc2 rootModel, string rootTitle)
        {
            if (rootModel == null)
            {
                return;
            }
            if (initialDocs == null)
            {
                return;
            }

            HashSet<string> keep = new HashSet<string>(initialDocs, StringComparer.OrdinalIgnoreCase);
            try
            {
                string rootPath = rootModel.GetPathName();
                if (!string.IsNullOrWhiteSpace(rootPath))
                {
                    keep.Add(rootPath);
                }
            }
            catch
            {
                // ignore root path errors
            }
            try
            {
                string title = rootModel.GetTitle();
                if (!string.IsNullOrWhiteSpace(title))
                {
                    keep.Add(title);
                }
            }
            catch
            {
                // ignore root title errors
            }

            const int maxPasses = 3;
            for (int pass = 0; pass < maxPasses; pass++)
            {
                List<ModelDoc2> toClose = GetOpenDocsNotInKeepSet(keep);
                if (toClose.Count == 0)
                {
                    return;
                }

                foreach (ModelDoc2 doc in toClose)
                {
                    ForceCloseDocNoSave(doc);
                }

                System.Windows.Forms.Application.DoEvents();
            }
        }

        private void RestoreStartDocument(string startTitle)
        {
            string activateTitle = NormalizeDocTitleForClose(startTitle);
            if (!string.IsNullOrWhiteSpace(activateTitle))
            {
                _swApp.ActivateDoc(activateTitle);
            }
            else if (!string.IsNullOrWhiteSpace(startTitle))
            {
                _swApp.ActivateDoc(startTitle);
            }
        }

        private void CloseModelIfNotInitiallyOpen(HashSet<string> initialDocs, ModelDoc2 model, string startTitle)
        {
            if (model == null || initialDocs == null)
            {
                return;
            }

            string id = GetDocumentId(model);
            if (!string.IsNullOrWhiteSpace(id) && initialDocs.Contains(id))
            {
                return;
            }

            string title = model.GetTitle();
            if (string.IsNullOrWhiteSpace(title))
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(startTitle) &&
                string.Equals(title, startTitle, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            try
            {
                ForceCloseDocNoSave(model);
            }
            catch
            {
                // ignore close errors
            }
        }

        private HashSet<string> GetOpenDocumentIds()
        {
            var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                string id = GetDocumentId(doc);
                if (!string.IsNullOrWhiteSpace(id))
                {
                    ids.Add(id);
                }
            }

            return ids;
        }

        private HashSet<string> GetOpenVisibleDocumentIds()
        {
            var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                bool visible = true;
                try
                {
                    visible = doc.Visible;
                }
                catch
                {
                    visible = true;
                }

                if (!visible)
                {
                    continue;
                }

                string id = GetDocumentId(doc);
                if (!string.IsNullOrWhiteSpace(id))
                {
                    ids.Add(id);
                }
            }

            return ids;
        }

        private string GetDocumentId(ModelDoc2 doc)
        {
            if (doc == null)
            {
                return string.Empty;
            }

            string path = string.Empty;
            try
            {
                path = doc.GetPathName();
            }
            catch
            {
                path = string.Empty;
            }
            if (!string.IsNullOrWhiteSpace(path))
            {
                return path;
            }

            string title = string.Empty;
            try
            {
                title = doc.GetTitle();
            }
            catch
            {
                title = string.Empty;
            }

            return NormalizeDocTitleForClose(title);
        }
    }
}
