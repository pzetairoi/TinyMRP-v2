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
        // What changed (Create files / batch deliverables):
        // - Fixed SolidWorks COM SAFEARRAY handling (System.Array vs object[]) via ComInteropUtil.EnumerateCom/EnumerateComAs.
        // - Removed baseline GetDocuments()-driven cleanup (it was closing invisible in-memory docs and causing minute-long close loops/cancel lag).
        // - Create files no longer writes FlatBOM files; planning/export uses in-memory traversal results.
        // - Fixed visible-document leak/crash on large assemblies: export activation restores per-document ModelDoc2.Visible (never global DocumentVisible),
        //   drawing docs opened for export are force-closed, and a watchdog enforces the visible-doc baseline between exports.
        // - Added per-export diagnostics (activation errors, SaveAs errors/warnings, file-size validation) to the per-run temp log.
        // Flip these to true when diagnosing hide-features issues.
        private static readonly bool EnableHideDebugLog = false;
        private static readonly bool EnableHideStatusLog = false;
        // Writes additional structured entries into the export run log (errorLog) to help diagnose batch issues.
        // Keep these entries terse and prefixed so they can be filtered easily.
        private static readonly bool EnableExportDebugLog = true;
        private const long MinPngBytes = 8 * 1024;
        private const long MinPdfBytes = 4 * 1024;
        private const long MinEdrawingBytes = 4 * 1024;
        private const long MinGenericMeshBytes = 128;
        private const long MinGenericCadBytes = 128;
        private const int ExportSessionSchemaVersion = 1;
        private const string ExportSessionStatusPlanned = "planned";
        private const string ExportSessionStatusRunning = "running";
        private const string ExportSessionStatusPauseRequested = "pause_requested";
        private const string ExportSessionStatusPaused = "paused";
        private const string ExportSessionStatusCancelled = "cancelled";
        private const string ExportSessionStatusCompleted = "completed";
        private const string ExportSessionStatusFailed = "failed";
        private const string ExportSessionStatusCrashedOrIncomplete = "crashed_or_incomplete";
        private const string ExportItemStatusPending = "pending";
        private const string ExportItemStatusRunning = "running";
        private const string ExportItemStatusDone = "done";
        private const string ExportItemStatusFailed = "failed";
        private const string ExportItemStatusSkipped = "skipped";
        private const string ExportSkipReasonEmptyPath = "empty path";
        private const string ExportSkipReasonNoRequiredOutputs = "no required outputs";
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

        private sealed class PlannedRef
        {
            public string ModelPath;
            public string ConfigurationName;
            public bool IsAssembly;
            public int MaxDepth;
            public int SubtreeEstimate;
            public bool IsRoot;
        }

        private sealed class ReopenDocInfo
        {
            public string Path;
            public int DocType;
            public string ConfigurationName;
            public int Order;

            public string Title;
        }

        private sealed class TraversedModel
        {
            public ModelDoc2 Model;
            public string ModelPath;
            public string ModelTitle;
            public string ConfigurationName;
            public string Revision;
            public int DocType;
            public bool IsRoot;

            public string Key;
        }

        private sealed class BatchTraverseResult
        {
            public readonly List<TraversedModel> Unique = new List<TraversedModel>();
            public readonly Dictionary<string, TraversedModel> ByKey = new Dictionary<string, TraversedModel>(StringComparer.OrdinalIgnoreCase);
            public readonly Dictionary<string, ModelDoc2> ModelByPath = new Dictionary<string, ModelDoc2>(StringComparer.OrdinalIgnoreCase);

            public int ComponentsScanned;
            public int UnresolvedComponents;
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
            public bool ExportDxfSelected;
            public bool ExportDxf;
            public bool ExportPngDrawing;
            public bool ExportEdrawingDrawing;
            public bool DrawingExists;

            public bool HasModelExports()
            {
                return ExportPngModel || ExportStep || ExportEdrawing || Export3mf || ExportPly || ExportStl;
            }

            public bool HasDrawingExports()
            {
                return DrawingExists && (ExportPdf || ExportDxf || ExportPngDrawing || ExportEdrawingDrawing);
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

        private sealed class ExportSummary
        {
            public HashSet<string> BaselineDocIds;
            public int InitialOpenDocs;
            public HashSet<string> BaselineVisibleDocIds;
            public int InitialVisibleDocs;
            public int FinalVisibleDocs;
            public int PlannedModelConfigPairs;
            public int FlatBomUnresolvedComponents;
            public int OpenDocsAfterRootClose;
            public long MemoryBeforeRootClose;
            public long MemoryAfterRootClose;
            public long FinalPrivateMemoryBytes;
            public string DeliverablesPlanPath;

            public int DeliverableGroupsPlanned;
            public int DeliverableGroupsProcessed;
            public int DeliverableGroupsSkipped;
            public int DeliverablePlansPlanned;
            public int DeliverablePlansExecuted;
            public int DeliverablePlansSkipped;
            public int DeliverableItemsProcessed;
            public int DeliverableItemsSkipped;
            public int DeliverableItemsFailed;

            public int ModelAttempt3mf;
            public int ModelOk3mf;
            public int ModelFail3mf;

            public int ModelAttemptStl;
            public int ModelOkStl;
            public int ModelFailStl;

            public int ModelAttemptPly;
            public int ModelOkPly;
            public int ModelFailPly;

            public int ModelAttemptStep;
            public int ModelOkStep;
            public int ModelFailStep;

            public int ModelAttemptEdraw;
            public int ModelOkEdraw;
            public int ModelFailEdraw;

            public int ModelAttemptPng;
            public int ModelOkPng;
            public int ModelFailPng;

            public int DwgAttemptPdf;
            public int DwgOkPdf;
            public int DwgFailPdf;

            public int DwgAttemptEdraw;
            public int DwgOkEdraw;
            public int DwgFailEdraw;

            public int DwgAttemptPng;
            public int DwgOkPng;
            public int DwgFailPng;

            public int DwgAttemptDxf;
            public int DwgOkDxf;
            public int DwgFailDxf;

            public int FinalOpenDocs;
        }

        private sealed class ExportedOutputState
        {
            public string Type;
            public string Path;
            public long Bytes;
            public bool Validated;
            public string ValidationReason;
        }

        private sealed class ExportSessionItem
        {
            public string ItemId;
            public string ModelPath;
            public string ConfigurationName;
            public bool IsAssembly;
            public int MaxDepth;
            public int SubtreeEstimate;
            public bool IsRoot;
            public string Status;
            public string StartedUtc;
            public string CompletedUtc;
            public int Attempts;
            public string LastError;
            public string PlyValidationReason;
            public List<ExportedOutputState> Outputs = new List<ExportedOutputState>();
        }

        private sealed class ExportSessionState
        {
            public int SchemaVersion;
            public string SessionId;
            public string CreatedUtc;
            public string UpdatedUtc;
            public string Status;
            public string RootModelPath;
            public string RootConfigurationName;
            public string DeliverablesFolder;
            public string BomFolder;
            public PublishOptions Options;
            public string PlanPath;
            public string LogPath;
            public List<ExportSessionItem> Queue = new List<ExportSessionItem>();
        }

        private sealed class ResumePreparationStats
        {
            public int TotalItems;
            public int CompletedItems;
            public int PendingItems;
            public int RunningReset;
            public int FailedReset;
            public int DoneReset;
            public int SkippedReset;
            public int UnknownReset;
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

        private sealed class ExportActivationScope : IDisposable
        {
            private readonly ISldWorks _swApp;
            private readonly int _docType;
            private readonly string _rootTitle;
            private readonly string _targetTitle;
            private readonly string _targetTitleNormalized;
            private readonly string _targetIdBefore;
            private readonly bool _targetWasVisibleBefore;
            private readonly Action<string> _errorLog;
            private readonly string _context;

            public bool Activated { get; private set; }
            public int ActivateErrors { get; private set; }

            public ExportActivationScope(
                ISldWorks swApp,
                string rootTitle,
                string targetDocTitle,
                int docType,
                Action<string> errorLog,
                string context = "")
            {
                _swApp = swApp;
                _docType = docType;
                _rootTitle = rootTitle ?? string.Empty;
                _errorLog = errorLog;
                _context = context ?? string.Empty;
                _targetTitle = targetDocTitle ?? string.Empty;
                _targetTitleNormalized = NormalizeDocTitle(_targetTitle);
                _targetIdBefore = string.Empty;
                _targetWasVisibleBefore = true;

                if (_swApp != null && !string.IsNullOrWhiteSpace(_targetTitle))
                {
                    // Per-document visibility tracking (never use global ISldWorks.DocumentVisible here).
                    // If the target doc was NOT visible before activation/export, we must hide it again on Dispose
                    // to prevent visible-tab leaks across large assemblies.
                    try
                    {
                        ModelDoc2 targetDoc = FindOpenDocByTitle(_targetTitle);
                        if (targetDoc != null)
                        {
                            bool wasVisible = true;
                            try
                            {
                                wasVisible = targetDoc.Visible;
                            }
                            catch
                            {
                                wasVisible = true;
                            }

                            _targetWasVisibleBefore = wasVisible;

                            string path = string.Empty;
                            try
                            {
                                path = targetDoc.GetPathName();
                            }
                            catch
                            {
                                path = string.Empty;
                            }

                            if (!string.IsNullOrWhiteSpace(path))
                            {
                                _targetIdBefore = path;
                            }
                            else
                            {
                                _targetIdBefore = !string.IsNullOrWhiteSpace(_targetTitleNormalized)
                                    ? _targetTitleNormalized
                                    : _targetTitle;
                            }
                        }
                        else
                        {
                            // Not found (should be rare). Default to "not visible" so Dispose will attempt to hide it if it appears.
                            _targetWasVisibleBefore = false;
                            _targetIdBefore = !string.IsNullOrWhiteSpace(_targetTitleNormalized)
                                ? _targetTitleNormalized
                                : _targetTitle;
                        }
                    }
                    catch
                    {
                        _targetWasVisibleBefore = true;
                        _targetIdBefore = !string.IsNullOrWhiteSpace(_targetTitleNormalized)
                            ? _targetTitleNormalized
                            : _targetTitle;
                    }
                }

                if (_swApp == null || string.IsNullOrWhiteSpace(_targetTitle))
                {
                    Activated = false;
                    ActivateErrors = 0;
                    return;
                }

                string activeBefore = SafeActiveDocTitle(_swApp);
                int visibleBefore = SafeVisibleDocCount(_swApp);

                int errors = 0;
                object activated = null;
                try
                {
                    string title = _targetTitleNormalized;
                    if (string.IsNullOrWhiteSpace(title))
                    {
                        title = _targetTitle;
                    }

                    activated = _swApp.ActivateDoc3(title, true,
                        (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref errors);
                }
                catch
                {
                    activated = null;
                }

                Activated = activated != null;
                ActivateErrors = errors;

                SafeWrite(
                    "ACTIVATE start context=" + _context +
                    " docType=" + _docType +
                    " targetWasVisibleBefore=" + _targetWasVisibleBefore +
                    " activeBefore=" + activeBefore +
                    " visibleBefore=" + visibleBefore +
                    " target=" + _targetTitle +
                    " ok=" + Activated +
                    " errors=" + errors);
            }

            public void Dispose()
            {
                if (_swApp == null)
                {
                    return;
                }

                string activeBefore = SafeActiveDocTitle(_swApp);
                int visibleBefore = SafeVisibleDocCount(_swApp);

                int rootActivateErrors = 0;
                bool hideAttempted = false;
                bool afterHideVisible = false;
                bool closeFallback = false;

                try
                {
                    if (!string.IsNullOrWhiteSpace(_rootTitle))
                    {
                        // Only re-activate the root if it's still open.
                        ModelDoc2 rootDoc = null;
                        try
                        {
                            rootDoc = FindOpenDocByTitle(_rootTitle);
                        }
                        catch
                        {
                            rootDoc = null;
                        }

                        if (rootDoc != null)
                        {
                            int errors = 0;
                            string root = NormalizeDocTitle(_rootTitle);
                            if (string.IsNullOrWhiteSpace(root))
                            {
                                root = _rootTitle;
                            }

                            _swApp.ActivateDoc3(root, true,
                                (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref errors);
                            rootActivateErrors = errors;
                        }
                    }
                }
                catch
                {
                    // ignore activation errors
                }

                try
                {
                    // Restore per-document visibility: if the target wasn't visible before the scope, hide it now.
                    if (!_targetWasVisibleBefore &&
                        !string.IsNullOrWhiteSpace(_targetTitle) &&
                        !TitlesMatch(_targetTitle, _rootTitle))
                    {
                        hideAttempted = true;
                        afterHideVisible = TryHideTargetDoc(_context + "|dispose", out closeFallback);
                    }
                }
                catch
                {
                    // ignore hide errors
                }

                try
                {
                    SafeWrite(
                        "ACTIVATION dispose context=" + _context +
                        " docType=" + _docType +
                        " targetWasVisibleBefore=" + _targetWasVisibleBefore +
                        " rootActivateErrors=" + rootActivateErrors +
                        " hideAttempted=" + hideAttempted +
                        " afterHideVisible=" + afterHideVisible +
                        " closeFallback=" + closeFallback +
                        " activeBefore=" + activeBefore +
                        " activeAfter=" + SafeActiveDocTitle(_swApp) +
                        " visibleBefore=" + visibleBefore +
                        " visibleAfter=" + SafeVisibleDocCount(_swApp));
                }
                catch
                {
                    // ignore log errors
                }
            }

            private void SafeWrite(string message)
            {
                if (_errorLog == null || string.IsNullOrWhiteSpace(message))
                {
                    return;
                }

                try
                {
                    _errorLog(message);
                }
                catch
                {
                    // ignore log errors
                }
            }

            private static string NormalizeDocTitle(string title)
            {
                if (string.IsNullOrWhiteSpace(title))
                {
                    return string.Empty;
                }

                string normalized = title.Trim();
                while (normalized.EndsWith("*", StringComparison.Ordinal))
                {
                    normalized = normalized.Substring(0, normalized.Length - 1).TrimEnd();
                }

                return normalized;
            }

            private ModelDoc2 FindOpenDocByTitle(string title)
            {
                if (_swApp == null || string.IsNullOrWhiteSpace(title))
                {
                    return null;
                }

                string expectedNorm = NormalizeDocTitle(title);
                foreach (ModelDoc2 doc in EnumerateOpenDocuments())
                {
                    if (doc == null)
                    {
                        continue;
                    }

                    string docTitle = string.Empty;
                    try
                    {
                        docTitle = doc.GetTitle();
                    }
                    catch
                    {
                        docTitle = string.Empty;
                    }

                    if (string.IsNullOrWhiteSpace(docTitle))
                    {
                        continue;
                    }

                    if (TitlesMatch(docTitle, expectedNorm) || TitlesMatch(docTitle, title))
                    {
                        return doc;
                    }
                }

                return null;
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

            private bool TryHideTargetDoc(string hideContext, out bool closeFallback)
            {
                closeFallback = false;

                if (_swApp == null)
                {
                    return false;
                }

                ModelDoc2 doc = null;
                try
                {
                    doc = FindOpenTargetDoc();
                }
                catch
                {
                    doc = null;
                }

                if (doc == null)
                {
                    SafeWrite("ACTIVATION hide context=" + (hideContext ?? string.Empty) + " targetNotFound title=" + _targetTitle);
                    return false;
                }

                bool beforeVisible = true;
                try
                {
                    beforeVisible = doc.Visible;
                }
                catch
                {
                    beforeVisible = true;
                }

                bool IsTargetVisible()
                {
                    ModelDoc2 target = null;
                    try
                    {
                        target = FindOpenTargetDoc();
                    }
                    catch
                    {
                        target = null;
                    }

                    if (target == null)
                    {
                        return false;
                    }

                    bool visible = true;
                    try
                    {
                        visible = target.Visible;
                    }
                    catch
                    {
                        visible = true;
                    }

                    return visible;
                }

                bool afterVisible = beforeVisible;
                try
                {
                    doc.Visible = false;
                }
                catch
                {
                    // ignore hide errors
                }

                afterVisible = IsTargetVisible();

                if (afterVisible)
                {
                    string closeTitle = _targetTitleNormalized;
                    if (string.IsNullOrWhiteSpace(closeTitle))
                    {
                        closeTitle = _targetTitle;
                    }

                    if (!string.IsNullOrWhiteSpace(closeTitle))
                    {
                        try
                        {
                            closeFallback = true;
                            _swApp.CloseDoc(closeTitle);
                        }
                        catch
                        {
                            // ignore close errors
                        }

                        afterVisible = IsTargetVisible();
                        if (afterVisible)
                        {
                            SafeWrite("WARNING: " + closeTitle + " still visible after CloseDoc, escalating to QuitDoc");
                            try
                            {
                                _swApp.QuitDoc(closeTitle);
                            }
                            catch
                            {
                                // ignore quit errors
                            }

                            afterVisible = IsTargetVisible();
                        }
                    }
                }

                SafeWrite(
                    "ACTIVATION hide context=" + (hideContext ?? string.Empty) +
                    " targetWasVisibleBefore=" + _targetWasVisibleBefore +
                    " beforeVisible=" + beforeVisible +
                    " afterVisible=" + afterVisible +
                    " closeFallback=" + closeFallback +
                    " title=" + _targetTitle);

                return afterVisible;
            }

            private ModelDoc2 FindOpenTargetDoc()
            {
                string targetId = _targetIdBefore ?? string.Empty;
                bool wantsPathMatch = !string.IsNullOrWhiteSpace(targetId) &&
                                      (targetId.IndexOf("\\", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                       targetId.IndexOf(":", StringComparison.OrdinalIgnoreCase) >= 0);

                foreach (ModelDoc2 doc in EnumerateOpenDocuments())
                {
                    if (doc == null)
                    {
                        continue;
                    }

                    if (wantsPathMatch)
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
                            string.Equals(path, targetId, StringComparison.OrdinalIgnoreCase))
                        {
                            return doc;
                        }
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

                    if (TitlesMatch(title, _targetTitle) || TitlesMatch(title, _targetTitleNormalized))
                    {
                        return doc;
                    }
                }

                return null;
            }

            private static bool TitlesMatch(string left, string right)
            {
                if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
                {
                    return false;
                }

                string ln = NormalizeDocTitle(left);
                string rn = NormalizeDocTitle(right);
                if (!string.IsNullOrWhiteSpace(ln) && !string.IsNullOrWhiteSpace(rn) &&
                    string.Equals(ln, rn, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }

                return string.Equals(left.Trim(), right.Trim(), StringComparison.OrdinalIgnoreCase);
            }

            private static int SafeVisibleDocCount(ISldWorks swApp)
            {
                if (swApp == null)
                {
                    return 0;
                }

                object docsObj = null;
                try
                {
                    docsObj = swApp.GetDocuments();
                }
                catch
                {
                    return 0;
                }

                if (docsObj == null)
                {
                    return 0;
                }

                Array docsArray = docsObj as Array;
                if (docsArray == null)
                {
                    ModelDoc2 single = docsObj as ModelDoc2;
                    if (single == null)
                    {
                        return 0;
                    }

                    try
                    {
                        return single.Visible ? 1 : 0;
                    }
                    catch
                    {
                        return 1;
                    }
                }

                int count = 0;
                foreach (object obj in docsArray)
                {
                    ModelDoc2 doc = obj as ModelDoc2;
                    if (doc == null)
                    {
                        continue;
                    }

                    try
                    {
                        if (doc.Visible)
                        {
                            count++;
                        }
                    }
                    catch
                    {
                        count++;
                    }
                }

                return count;
            }

            private static string SafeActiveDocTitle(ISldWorks swApp)
            {
                if (swApp == null)
                {
                    return "<no app>";
                }

                try
                {
                    ModelDoc2 doc = swApp.ActiveDoc as ModelDoc2;
                    if (doc == null)
                    {
                        return "<null>";
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

                    return !string.IsNullOrWhiteSpace(title) ? title : "<untitled>";
                }
                catch
                {
                    return "<error>";
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
        private volatile bool _pauseRequested;
        private readonly HashSet<string> _closeWarningOnce = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly HashSet<string> _debugOnce = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly object _sessionLock = new object();
        // Docs we explicitly opened with OpenDoc7 for batch exports (NOT the root or docs loaded only via assembly).
        private readonly HashSet<string> _explicitlyOpenedDocs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private ExportSummary _currentExportSummary;
        private ExportSessionState _activeExportSession;
        private string _activeBatchRootTitle = string.Empty;
        private int _activeBatchRootDocType = 0;

        public string LastRunLogPath { get; private set; } = string.Empty;

        public TinyMrpPublisher(ISldWorks swApp, TinyMrpConfig config)
        {
            _swApp = swApp;
            _config = config;
        }

        private void SetLastRunLogPath(ExportRunLog runLog)
        {
            try
            {
                LastRunLogPath = (runLog != null ? runLog.Path : string.Empty) ?? string.Empty;
            }
            catch
            {
                LastRunLogPath = string.Empty;
            }
        }

        private string UtcNowString()
        {
            return DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
        }

        private PublishOptions ClonePublishOptions(PublishOptions options)
        {
            if (options == null)
            {
                return new PublishOptions();
            }

            return new PublishOptions
            {
                DeliverablesFolder = options.DeliverablesFolder,
                BomFolder = options.BomFolder,
                ExportPngModel = options.ExportPngModel,
                ExportStep = options.ExportStep,
                ExportEdrawing = options.ExportEdrawing,
                Export3mf = options.Export3mf,
                ExportPly = options.ExportPly,
                ExportStl = options.ExportStl,
                ExportPngDrawing = options.ExportPngDrawing,
                ExportPdf = options.ExportPdf,
                ExportDxf = options.ExportDxf,
                ExportEdrawingDrawing = options.ExportEdrawingDrawing,
                OverwriteFiles = options.OverwriteFiles,
                TopLevelOnly = options.TopLevelOnly,
                CreateUploadPack = options.CreateUploadPack,
                UploadPackIncludeDeliverables = options.UploadPackIncludeDeliverables,
                UploadPackIncludeExtras = options.UploadPackIncludeExtras
            };
        }

        private ExportSessionItem CreateExportSessionItem(PlannedRef item)
        {
            if (item == null)
            {
                return null;
            }

            return new ExportSessionItem
            {
                ItemId = BuildPlannedRefKey(item.ModelPath, item.ConfigurationName),
                ModelPath = item.ModelPath ?? string.Empty,
                ConfigurationName = item.ConfigurationName ?? string.Empty,
                IsAssembly = item.IsAssembly,
                MaxDepth = item.MaxDepth,
                SubtreeEstimate = item.SubtreeEstimate,
                IsRoot = item.IsRoot,
                Status = ExportItemStatusPending
            };
        }

        private ExportSessionState CreateExportSessionState(List<PlannedRef> queue, PublishOptions options, string rootModelPath,
            string rootConfigName, string planPath, string logPath)
        {
            var state = new ExportSessionState
            {
                SchemaVersion = ExportSessionSchemaVersion,
                SessionId = Guid.NewGuid().ToString("N"),
                CreatedUtc = UtcNowString(),
                UpdatedUtc = UtcNowString(),
                Status = ExportSessionStatusPlanned,
                RootModelPath = rootModelPath ?? string.Empty,
                RootConfigurationName = rootConfigName ?? string.Empty,
                DeliverablesFolder = options != null ? (options.DeliverablesFolder ?? string.Empty) : string.Empty,
                BomFolder = options != null ? (options.BomFolder ?? string.Empty) : string.Empty,
                Options = ClonePublishOptions(options),
                PlanPath = planPath ?? string.Empty,
                LogPath = logPath ?? string.Empty
            };

            if (queue != null)
            {
                foreach (PlannedRef item in queue)
                {
                    ExportSessionItem sessionItem = CreateExportSessionItem(item);
                    if (sessionItem != null)
                    {
                        state.Queue.Add(sessionItem);
                    }
                }
            }

            return state;
        }

        private void SetActiveExportSession(ExportSessionState state)
        {
            lock (_sessionLock)
            {
                _activeExportSession = state;
            }
        }

        private ExportSessionState GetActiveExportSession()
        {
            lock (_sessionLock)
            {
                return _activeExportSession;
            }
        }

        private string GetExportSessionsDirectory()
        {
            string appData = System.Environment.GetFolderPath(System.Environment.SpecialFolder.ApplicationData);
            return Path.Combine(appData, "TinyMRP", "export-sessions");
        }

        private string GetActiveExportSessionPath()
        {
            return Path.Combine(GetExportSessionsDirectory(), "active-export-session.json");
        }

        private string BuildArchivedExportSessionPath(string prefix)
        {
            string safePrefix = string.IsNullOrWhiteSpace(prefix) ? "session" : prefix.Trim();
            string name = safePrefix + "-" + DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture) + ".json";
            return Path.Combine(GetExportSessionsDirectory(), name);
        }

        private System.Web.Script.Serialization.JavaScriptSerializer CreateJsonSerializer()
        {
            var serializer = new System.Web.Script.Serialization.JavaScriptSerializer();
            try
            {
                serializer.MaxJsonLength = int.MaxValue;
            }
            catch
            {
                // ignore
            }
            return serializer;
        }

        private string SerializeExportSession(ExportSessionState state)
        {
            if (state == null)
            {
                return string.Empty;
            }

            return CreateJsonSerializer().Serialize(state);
        }

        private ExportSessionState DeserializeExportSession(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return null;
            }

            try
            {
                return CreateJsonSerializer().Deserialize<ExportSessionState>(json);
            }
            catch
            {
                return null;
            }
        }

        private void SaveExportSessionAtomic(ExportSessionState state, Action<string> errorLog)
        {
            if (state == null)
            {
                return;
            }

            try
            {
                state.UpdatedUtc = UtcNowString();
                string dir = GetExportSessionsDirectory();
                Directory.CreateDirectory(dir);

                string finalPath = GetActiveExportSessionPath();
                string tempPath = finalPath + ".tmp";
                TextFileHelper.WriteAllTextUtf8NoBom(tempPath, SerializeExportSession(state));

                if (File.Exists(finalPath))
                {
                    try
                    {
                        string backupPath = finalPath + ".bak";
                        if (File.Exists(backupPath))
                        {
                            File.Delete(backupPath);
                        }

                        File.Replace(tempPath, finalPath, backupPath, true);
                        if (File.Exists(backupPath))
                        {
                            File.Delete(backupPath);
                        }
                    }
                    catch
                    {
                        if (File.Exists(finalPath))
                        {
                            File.Delete(finalPath);
                        }

                        File.Move(tempPath, finalPath);
                    }
                }
                else
                {
                    File.Move(tempPath, finalPath);
                }
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "SESSION save failed: " + ex.Message);
            }
        }

        private ExportSessionState LoadExportSession(string path, Action<string> errorLog)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return null;
            }

            try
            {
                string json = File.ReadAllText(path, TextFileHelper.Utf8NoBom);
                ExportSessionState state = DeserializeExportSession(json);
                if (state == null)
                {
                    SafeLog(errorLog, "SESSION load failed: invalid json path=" + path);
                    return null;
                }

                if (state.Queue == null)
                {
                    state.Queue = new List<ExportSessionItem>();
                }

                return state;
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "SESSION load failed: " + ex.Message);
                return null;
            }
        }

        private ExportSessionState LoadLatestIncompleteExportSession(Action<string> errorLog)
        {
            ExportSessionState state = LoadExportSession(GetActiveExportSessionPath(), errorLog);
            if (state == null)
            {
                return null;
            }

            if (!IsSessionResumable(state.Status))
            {
                return null;
            }

            return state;
        }

        private bool IsSessionResumable(string status)
        {
            if (string.IsNullOrWhiteSpace(status))
            {
                return true;
            }

            return !string.Equals(status, ExportSessionStatusCompleted, StringComparison.OrdinalIgnoreCase);
        }

        private void ArchiveCompletedExportSession(ExportSessionState state, Action<string> errorLog)
        {
            if (state == null)
            {
                return;
            }

            try
            {
                string activePath = GetActiveExportSessionPath();
                if (!File.Exists(activePath))
                {
                    return;
                }

                string archivePath = BuildArchivedExportSessionPath("completed");
                Directory.CreateDirectory(GetExportSessionsDirectory());
                if (File.Exists(archivePath))
                {
                    File.Delete(archivePath);
                }

                File.Move(activePath, archivePath);
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "SESSION archive failed: " + ex.Message);
            }
        }

        public bool HasIncompleteExportSession()
        {
            return LoadLatestIncompleteExportSession(null) != null;
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
            SetLastRunLogPath(runLog);
            errorLog?.Invoke("START deliverables export");

            _currentExportSummary = new ExportSummary();
            SetActiveExportSession(null);

            string BuildCompletionMessage(string statusLabel)
            {
                ExportSummary s = _currentExportSummary;
                int ok = 0;
                int fail = 0;
                if (s != null)
                {
                    ok = s.ModelOk3mf + s.ModelOkStl + s.ModelOkPly + s.ModelOkStep + s.ModelOkEdraw + s.ModelOkPng +
                         s.DwgOkPdf + s.DwgOkEdraw + s.DwgOkPng + s.DwgOkDxf;
                    fail = s.ModelFail3mf + s.ModelFailStl + s.ModelFailPly + s.ModelFailStep + s.ModelFailEdraw + s.ModelFailPng +
                           s.DwgFailPdf + s.DwgFailEdraw + s.DwgFailPng + s.DwgFailDxf;
                }

                string message = (statusLabel ?? "Export") + ": " + ok + " files created, " + fail + " failed.";
                return BuildRunLogMessage(message, runLog);
            }

            try
            {
                try
                {
                    HashSet<string> baselineIds = SnapshotOpenDocIds();
                    _currentExportSummary.BaselineDocIds = baselineIds;
                    _currentExportSummary.InitialOpenDocs = baselineIds.Count;
                }
                catch
                {
                    _currentExportSummary.BaselineDocIds = null;
                    _currentExportSummary.InitialOpenDocs = 0;
                }

                ResetCancel();
                ResetPause();
                _closeWarningOnce.Clear();
                _debugOnce.Clear();
                HashSet<string> uploadPackBases;
                List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras;
                string flatFile = TraverseModel(true, string.Empty, effective, log, null, progress, errorLog,
                    out uploadPackBases, out uploadPackExtras);

                ExportSessionState activeSession = GetActiveExportSession();
                if (activeSession != null &&
                    string.Equals(activeSession.Status, ExportSessionStatusPaused, StringComparison.OrdinalIgnoreCase))
                {
                    Log(log, BuildCompletionMessage("Export paused"));
                    return;
                }

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
                        if (ex is System.Runtime.InteropServices.COMException ||
                            (ex.InnerException is System.Runtime.InteropServices.COMException))
                        {
                            LogExceptionDetails(errorLog, "UploadPack", ex);
                        }
                    }
                }

                activeSession = GetActiveExportSession();
                if (activeSession != null && IsSessionResumable(activeSession.Status))
                {
                    activeSession.Status = ExportSessionStatusCompleted;
                    SaveExportSessionAtomic(activeSession, errorLog);
                    ArchiveCompletedExportSession(activeSession, errorLog);
                    SetActiveExportSession(null);
                }

                string completedLabel = "Export completed";
                try
                {
                    ExportSummary s = _currentExportSummary;
                    if (s != null)
                    {
                        int fail = s.ModelFail3mf + s.ModelFailStl + s.ModelFailPly + s.ModelFailStep + s.ModelFailEdraw + s.ModelFailPng +
                                   s.DwgFailPdf + s.DwgFailEdraw + s.DwgFailPng + s.DwgFailDxf;
                        if (fail > 0)
                        {
                            completedLabel = "Export completed with warnings";
                        }
                    }
                }
                catch
                {
                    // ignore label errors
                }

                Log(log, BuildCompletionMessage(completedLabel));
            }
            catch (OperationCanceledException)
            {
                ExportSessionState activeSession = GetActiveExportSession();
                if (activeSession != null &&
                    !string.Equals(activeSession.Status, ExportSessionStatusPaused, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(activeSession.Status, ExportSessionStatusCompleted, StringComparison.OrdinalIgnoreCase))
                {
                    activeSession.Status = ExportSessionStatusCancelled;
                    SaveExportSessionAtomic(activeSession, errorLog);
                }
                Log(log, BuildCompletionMessage("Export cancelled"));
            }
            catch (Exception ex)
            {
                ExportSessionState activeSession = GetActiveExportSession();
                if (activeSession != null &&
                    !string.Equals(activeSession.Status, ExportSessionStatusPaused, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(activeSession.Status, ExportSessionStatusCompleted, StringComparison.OrdinalIgnoreCase))
                {
                    activeSession.Status = ExportSessionStatusFailed;
                    SaveExportSessionAtomic(activeSession, errorLog);
                }

                LogExportFailure(log, errorLog, "File creation failed: " + ex.Message);
                if (ex is System.Runtime.InteropServices.COMException ||
                    (ex.InnerException is System.Runtime.InteropServices.COMException))
                {
                    LogExceptionDetails(errorLog, "ProcessFiles", ex);
                }
                Log(log, BuildCompletionMessage("Export failed"));
            }
            finally
            {
                try
                {
                    ExportSummary summary = _currentExportSummary;
                    if (summary != null)
                    {
                        HashSet<string> finalIds = null;
                        try
                        {
                            finalIds = SnapshotOpenDocIds();
                            summary.FinalOpenDocs = finalIds.Count;
                        }
                        catch
                        {
                            finalIds = null;
                            summary.FinalOpenDocs = 0;
                        }

                        summary.FinalPrivateMemoryBytes = GetPrivateMemoryBytes();

                        WriteExportSummary(errorLog, summary, finalIds);
                    }
                }
                catch
                {
                    // ignore summary errors
                }
                finally
                {
                    try
                    {
                        // Ensure the UI progress bar reaches 100% on completion/cancel/failure.
                        UpdateProgress(progress, 1, 1);
                    }
                    catch
                    {
                        // ignore progress errors
                    }

                    try
                    {
                        // Reset cancel state so the UI button returns to its idle state.
                        ResetCancel();
                        ResetPause();
                    }
                    catch
                    {
                        // ignore cancel-reset errors
                    }

                    _currentExportSummary = null;
                }
            }
        }

        private ExportRunLog OpenExportRunLog(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return CreateExportRunLog();
            }

            return new ExportRunLog(path);
        }

        public void ResumeLastExport(Action<string> log, Action<int, int> progress)
        {
            ExportSessionState session = LoadLatestIncompleteExportSession(null);
            if (session == null)
            {
                throw new InvalidOperationException("No incomplete export session available.");
            }

            PublishOptions effective = NormalizeOptions(ClonePublishOptions(session.Options));
            ExportRunLog runLog = OpenExportRunLog(session.LogPath);
            Action<string> errorLog = runLog != null ? new Action<string>(runLog.Write) : null;
            SetLastRunLogPath(runLog);
            session.LogPath = runLog != null ? (runLog.Path ?? string.Empty) : (session.LogPath ?? string.Empty);
            SetActiveExportSession(session);
            errorLog?.Invoke("RESUME deliverables export session=" + (session.SessionId ?? string.Empty) +
                             " status=" + (session.Status ?? string.Empty));

            _currentExportSummary = new ExportSummary();

            string BuildCompletionMessage(string statusLabel)
            {
                ExportSummary s = _currentExportSummary;
                int ok = 0;
                int fail = 0;
                if (s != null)
                {
                    ok = s.ModelOk3mf + s.ModelOkStl + s.ModelOkPly + s.ModelOkStep + s.ModelOkEdraw + s.ModelOkPng +
                         s.DwgOkPdf + s.DwgOkEdraw + s.DwgOkPng + s.DwgOkDxf;
                    fail = s.ModelFail3mf + s.ModelFailStl + s.ModelFailPly + s.ModelFailStep + s.ModelFailEdraw + s.ModelFailPng +
                           s.DwgFailPdf + s.DwgFailEdraw + s.DwgFailPng + s.DwgFailDxf;
                }

                return BuildRunLogMessage((statusLabel ?? "Export") + ": " + ok + " files created, " + fail + " failed.", runLog);
            }

            try
            {
                try
                {
                    HashSet<string> baselineIds = SnapshotOpenDocIds();
                    _currentExportSummary.BaselineDocIds = baselineIds;
                    _currentExportSummary.InitialOpenDocs = baselineIds.Count;
                }
                catch
                {
                    _currentExportSummary.BaselineDocIds = null;
                    _currentExportSummary.InitialOpenDocs = 0;
                }

                ResetCancel();
                ResetPause();
                _closeWarningOnce.Clear();
                _debugOnce.Clear();

                ResumePreparationStats resumeStats = PrepareSessionForResume(session, errorLog);
                SaveExportSessionAtomic(session, errorLog);

                var queue = BuildPendingResumeQueue(session, errorLog);
                int totalItems = session.Queue != null ? session.Queue.Count : 0;
                int completeItems = CountCompletedSessionItems(session);
                int pendingItems = queue.Count;

                errorLog?.Invoke(
                    "RESUME plan: total=" + totalItems +
                    " complete=" + completeItems +
                    " pending=" + pendingItems +
                    " failed=" + resumeStats.FailedReset +
                    " runningReset=" + resumeStats.RunningReset +
                    " doneReset=" + resumeStats.DoneReset +
                    " skippedReset=" + resumeStats.SkippedReset +
                    " unknownReset=" + resumeStats.UnknownReset);

                if (pendingItems > 0)
                {
                    PlannedRef firstPending = queue[0];
                    PlannedRef lastPending = queue[pendingItems - 1];
                    errorLog?.Invoke(
                        "RESUME pending range: first=" +
                        BuildPlannedRefKey(firstPending.ModelPath, firstPending.ConfigurationName) +
                        " path=" + (firstPending.ModelPath ?? string.Empty) +
                        " conf=" + (firstPending.ConfigurationName ?? string.Empty) +
                        " last=" +
                        BuildPlannedRefKey(lastPending.ModelPath, lastPending.ConfigurationName) +
                        " path=" + (lastPending.ModelPath ?? string.Empty) +
                        " conf=" + (lastPending.ConfigurationName ?? string.Empty));
                }

                UpdateProgress(progress, completeItems, totalItems);

                if (pendingItems == 0)
                {
                    session.Status = ExportSessionStatusCompleted;
                    SaveExportSessionAtomic(session, errorLog);
                    ArchiveCompletedExportSession(session, errorLog);
                    SetActiveExportSession(null);
                    Log(log, BuildRunLogMessage("Nothing left to resume. Existing completed items were kept.", runLog));
                    return;
                }

                Log(log, "Resuming export: " + completeItems + "/" + totalItems + " already complete, " + pendingItems + " remaining.");
                session.Status = ExportSessionStatusRunning;
                SaveExportSessionAtomic(session, errorLog);

                string deliverablesFolder = EnsureTrailingSlash(effective.DeliverablesFolder);
                if (string.IsNullOrWhiteSpace(deliverablesFolder))
                {
                    throw new InvalidOperationException("Deliverables folder is empty.");
                }

                Directory.CreateDirectory(deliverablesFolder);
                EnsureMediaFolders(deliverablesFolder);

                ProcessDeliverablesIsolated(
                    queue,
                    deliverablesFolder,
                    effective,
                    log,
                    errorLog,
                    progress,
                    session.RootModelPath ?? string.Empty,
                    session.RootConfigurationName ?? string.Empty,
                    session);

                ExportSessionState activeSession = GetActiveExportSession();
                if (activeSession != null &&
                    string.Equals(activeSession.Status, ExportSessionStatusPaused, StringComparison.OrdinalIgnoreCase))
                {
                    Log(log, BuildCompletionMessage("Export paused"));
                    return;
                }

                if (activeSession != null)
                {
                    activeSession.Status = ExportSessionStatusCompleted;
                    SaveExportSessionAtomic(activeSession, errorLog);
                    ArchiveCompletedExportSession(activeSession, errorLog);
                    SetActiveExportSession(null);
                }

                Log(log, BuildCompletionMessage("Export resumed and completed"));
            }
            catch (OperationCanceledException)
            {
                ExportSessionState activeSession = GetActiveExportSession();
                if (activeSession != null &&
                    !string.Equals(activeSession.Status, ExportSessionStatusPaused, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(activeSession.Status, ExportSessionStatusCompleted, StringComparison.OrdinalIgnoreCase))
                {
                    activeSession.Status = ExportSessionStatusCancelled;
                    SaveExportSessionAtomic(activeSession, errorLog);
                }

                Log(log, BuildCompletionMessage("Export cancelled"));
            }
            catch (Exception ex)
            {
                ExportSessionState activeSession = GetActiveExportSession();
                if (activeSession != null &&
                    !string.Equals(activeSession.Status, ExportSessionStatusPaused, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(activeSession.Status, ExportSessionStatusCompleted, StringComparison.OrdinalIgnoreCase))
                {
                    activeSession.Status = ExportSessionStatusFailed;
                    SaveExportSessionAtomic(activeSession, errorLog);
                }

                LogExportFailure(log, errorLog, "Resume failed: " + ex.Message);
                if (ex is System.Runtime.InteropServices.COMException ||
                    (ex.InnerException is System.Runtime.InteropServices.COMException))
                {
                    LogExceptionDetails(errorLog, "ResumeLastExport", ex);
                }
                Log(log, BuildCompletionMessage("Export resume failed"));
            }
            finally
            {
                try
                {
                    ExportSummary summary = _currentExportSummary;
                    if (summary != null)
                    {
                        HashSet<string> finalIds = null;
                        try
                        {
                            finalIds = SnapshotOpenDocIds();
                            summary.FinalOpenDocs = finalIds.Count;
                        }
                        catch
                        {
                            finalIds = null;
                            summary.FinalOpenDocs = 0;
                        }

                        summary.FinalPrivateMemoryBytes = GetPrivateMemoryBytes();
                        WriteExportSummary(errorLog, summary, finalIds);
                    }
                }
                catch
                {
                    // ignore summary errors
                }
                finally
                {
                    try
                    {
                        UpdateProgress(progress, 1, 1);
                    }
                    catch
                    {
                        // ignore
                    }

                    try
                    {
                        ResetCancel();
                        ResetPause();
                    }
                    catch
                    {
                        // ignore
                    }

                    _currentExportSummary = null;
                }
            }
        }

        public void ProcessBom(PublishOptions options, Action<string> log, Action<int, int> progress)
        {
            PublishOptions effective = NormalizeOptions(options);
            if (effective == null)
            {
                return;
            }

            ExportRunLog runLog = CreateRunLog("bom");
            Action<string> errorLog = runLog != null ? new Action<string>(runLog.Write) : null;
            SetLastRunLogPath(runLog);
            errorLog?.Invoke("START BOM export");

            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                Log(log, BuildRunLogMessage("BOM export aborted: no active document.", runLog));
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
                    Log(log, BuildRunLogMessage("BOM export aborted: no reference model found in the drawing.", runLog));
                    return;
                }
            }

            if (swConf == null)
            {
                Log(log, BuildRunLogMessage("BOM export aborted: no active configuration.", runLog));
                return;
            }

            if (!string.IsNullOrWhiteSpace(swConf.Name))
            {
                swModel.ShowConfiguration2(swConf.Name);
            }

            ModelDoc2 rootModel = swModel;
            string rootTitle = swModel.GetTitle();

            _activeBatchRootTitle = rootTitle ?? string.Empty;
            _activeBatchRootDocType = modelType;

            ResetCancel();
            try
            {
                errorLog?.Invoke("BOM start: title=" + (rootTitle ?? string.Empty) +
                                 " path=" + (rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty));
                string pubFolder = EnsureTrailingSlash(effective.BomFolder);
                if (string.IsNullOrWhiteSpace(pubFolder))
                {
                    Log(log, BuildRunLogMessage("BOM export aborted: BOM output folder is empty.", runLog));
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
                    Log(log, BuildRunLogMessage("BOM export aborted: active document must be saved before exporting BOM.", runLog));
                    return;
                }

                ThrowIfCancelled();
                TryBuildBomWithSavedTempAssembly(swModel, bomFile, "BOM export", log, errorLog);

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

                Log(log, BuildRunLogMessage("BOM file generation finished.", runLog));
            }
            catch (OperationCanceledException)
            {
                Log(log, BuildRunLogMessage("BOM export cancelled.", runLog));
            }
            catch (Exception ex)
            {
                errorLog?.Invoke("BOM export failed: " + ex);
                Log(log, BuildRunLogMessage("BOM export failed: " + ex.Message, runLog));
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

            ExportRunLog runLog = CreateRunLog("upload_pack");
            Action<string> errorLog = runLog != null ? new Action<string>(runLog.Write) : null;
            SetLastRunLogPath(runLog);
            errorLog?.Invoke("START upload pack");

            try
            {
                ResetCancel();
                HashSet<string> uploadPackBases;
                List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras;
                string flatFile = TraverseModel(false, string.Empty, effective, log, null, null, errorLog,
                    out uploadPackBases, out uploadPackExtras);
                CreateUploadPack(flatFile, uploadPackBases, uploadPackExtras, effective, log, errorLog);
                Log(log, BuildRunLogMessage("Upload pack created.", runLog));
            }
            catch (OperationCanceledException)
            {
                Log(log, BuildRunLogMessage("Upload pack cancelled.", runLog));
            }
            catch (Exception ex)
            {
                errorLog?.Invoke("Upload pack failed: " + ex);
                Log(log, BuildRunLogMessage("Upload pack failed: " + ex.Message, runLog));
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

            object compsObj = null;
            try
            {
                compsObj = root.GetChildren();
            }
            catch
            {
                compsObj = null;
            }

            foreach (object obj in ComInteropUtil.EnumerateCom(compsObj))
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

            object childrenObj = null;
            try
            {
                childrenObj = parent.GetChildren();
            }
            catch
            {
                childrenObj = null;
            }

            foreach (object obj in ComInteropUtil.EnumerateCom(childrenObj))
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
            string startPathSnapshot = string.Empty;
            try
            {
                startPathSnapshot = swModel.GetPathName() ?? string.Empty;
            }
            catch
            {
                startPathSnapshot = string.Empty;
            }

            // Baseline of VISIBLE docs/tabs the user has open at the start of the run.
            // Batch export must not leave extra visible documents behind.
            HashSet<string> initialVisibleDocs = GetOpenVisibleDocumentIds();
            if (_currentExportSummary != null)
            {
                _currentExportSummary.BaselineVisibleDocIds = new HashSet<string>(initialVisibleDocs, StringComparer.OrdinalIgnoreCase);
                _currentExportSummary.InitialVisibleDocs = initialVisibleDocs.Count;
            }

            SafeLog(errorLog, "BASELINE visible docs: count=" + initialVisibleDocs.Count);
            LogVisibleDocuments(errorLog, "BASELINE");
            try
            {
                List<ModelDoc2> baselineDocs = GetVisibleDocuments();
                var titles = new List<string>();
                foreach (ModelDoc2 doc in baselineDocs)
                {
                    if (doc == null)
                    {
                        continue;
                    }

                    string title = string.Empty;
                    try
                    {
                        title = doc.GetTitle() ?? string.Empty;
                    }
                    catch
                    {
                        title = string.Empty;
                    }

                    if (!string.IsNullOrWhiteSpace(title))
                    {
                        titles.Add(NormalizeDocTitleForClose(title));
                    }
                }

                SafeLog(errorLog, "BASELINE visible titles: [" + string.Join(", ", titles.ToArray()) + "]");
            }
            catch
            {
                // ignore baseline title errors
            }

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
                " initialVisibleDocs=" + (initialVisibleDocs != null ? initialVisibleDocs.Count : 0) +
                " visibleDocs=" + GetOpenVisibleDocumentIds().Count);

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

                BatchTraverseResult traverse = null;
                List<PlannedRef> plannedRefs = null;

                int planned = 0;
                if (!createFiles)
                {
                    traverse = TraverseModelsForBatch(swModel, swConf, modelType, options.TopLevelOnly, log, errorLog);
                    planned = traverse != null && traverse.Unique != null ? traverse.Unique.Count : 0;
                }
                else
                {
                    // Deliverables planning must remain list-based and avoid opening/resolving component models.
                    if (options != null && options.TopLevelOnly)
                    {
                        string rootPathOnly = string.Empty;
                        try
                        {
                            rootPathOnly = rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty;
                        }
                        catch
                        {
                            rootPathOnly = string.Empty;
                        }

                        plannedRefs = BuildTopLevelOnlyDeliverablesQueue(
                            rootPathOnly,
                            swConf != null ? (swConf.Name ?? string.Empty) : string.Empty,
                            modelType == (int)swDocumentTypes_e.swDocASSEMBLY);
                    }
                    else
                    {
                        SafeLog(errorLog, "PHASE PLAN start (deliverables, no doc opens)");
                        plannedRefs = PlanRefsForDeliverables(swModel, swConf, errorLog);
                        SafeLog(errorLog, "PHASE PLAN end (deliverables) plannedRefs=" + (plannedRefs != null ? plannedRefs.Count : 0));
                    }

                    planned = plannedRefs != null ? plannedRefs.Count : 0;
                }

                Log(log, "Planned unique model-config pairs: " + planned);
                SafeLog(errorLog, "Planned unique model-config pairs: " + planned);
                if (_currentExportSummary != null)
                {
                    _currentExportSummary.PlannedModelConfigPairs = planned;
                    _currentExportSummary.FlatBomUnresolvedComponents =
                        !createFiles && traverse != null ? traverse.UnresolvedComponents : 0;
                }

                bool shouldWriteFlatBomFile = !createFiles;
                string outputFile = string.Empty;
                if (shouldWriteFlatBomFile)
                {
                    if (string.IsNullOrWhiteSpace(exportTag))
                    {
                        outputFile = Path.Combine(bomFolder,
                            GetFileString(swModel, swConf.Name, errorLog) + "_" +
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

                    UpdateProgress(flatBomProgress, 0, planned);
                    WriteFlatBomFromTraverse(outputFile, traverse, log, flatBomProgress, uploadPackBases, uploadPackExtras, errorLog);
                    ThrowIfCancelled();
                }
                else
                {
                    // CreateFiles must not generate FlatBOM artifacts. Planning/export uses in-memory traversal results.
                    UpdateProgress(flatBomProgress, 0, 0);
                }

                if (createFiles)
                {
                    if (!AnyDeliverablesSelected(options))
                    {
                        UpdateProgress(deliverablesProgress, 0, 0);
                    }
                    else
                    {
                        if (plannedRefs == null || plannedRefs.Count == 0)
                        {
                            Log(log, "No deliverables to export (planning yielded no references).");
                            UpdateProgress(deliverablesProgress, 0, 0);
                        }
                        else
                        {
                            string planPath = SaveDeliverablesPlanToTempFile(plannedRefs, errorLog);
                            if (_currentExportSummary != null)
                            {
                                _currentExportSummary.DeliverablesPlanPath = planPath ?? string.Empty;
                            }
                            SafeLog(errorLog,
                                "PLAN file: " + (planPath ?? string.Empty) +
                                " items=" + plannedRefs.Count);

                            SortDeliverablesQueue(plannedRefs);

                            string rootPathSnapshot = string.Empty;
                            try
                            {
                                rootPathSnapshot = rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty;
                            }
                            catch
                            {
                                rootPathSnapshot = string.Empty;
                            }

                            string rootConfigName = swConf != null ? (swConf.Name ?? string.Empty) : string.Empty;
                            ExportSessionState sessionState = CreateExportSessionState(
                                plannedRefs,
                                options,
                                rootPathSnapshot,
                                rootConfigName,
                                planPath,
                                LastRunLogPath);
                            sessionState.Status = ExportSessionStatusPlanned;
                            SetActiveExportSession(sessionState);
                            SaveExportSessionAtomic(sessionState, errorLog);
                            List<ReopenDocInfo> cleanRoomReopen = null;
                            try
                            {
                                 EnsureRootDocSafeToCloseNoSave(rootModel, log, errorLog);
                                 cleanRoomReopen = CleanRoomCloseOtherVisibleDocuments(rootModel, log, errorLog);

                                 ProcessDeliverablesIsolated(
                                     plannedRefs,
                                     deliverablesFolder,
                                     options,
                                    log,
                                    errorLog,
                                    deliverablesProgress,
                                    rootPathSnapshot,
                                    rootConfigName,
                                    sessionState);
                            }
                            finally
                            {
                                try
                                {
                                    ReopenDocumentsSilent(cleanRoomReopen, errorLog);
                                }
                                catch
                                {
                                    // ignore reopen errors
                                }
                            }
                        }
                    }
                }

                return outputFile;
            }
            finally
            {
                _activeBatchRootTitle = string.Empty;
                _activeBatchRootDocType = 0;

                try
                {
                    if (swModel != null && swModel.FeatureManager != null)
                    {
                        swModel.FeatureManager.EnableFeatureTree = true;
                    }
                }
                catch
                {
                    // ignore (root doc may have been closed/reopened during isolated export)
                }

                try
                {
                    if (view != null)
                    {
                        view.EnableGraphicsUpdate = prevGraphics;
                    }
                }
                catch
                {
                    // ignore (view may be invalid after doc close/reopen)
                }

                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance, prevBgAppearance);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme, prevColorScheme);
                _swApp.SetUserPreferenceIntegerValue(
                    (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground, prevViewport);

                RestoreStartDocument(startTitle);

                try
                {
                    if (!IsDocOpenByIdOrTitle(startPathSnapshot, startTitle))
                    {
                        if (errorLog != null)
                        {
                            errorLog("CRITICAL: start document not open after batch export. title=" +
                                     (startTitle ?? string.Empty) + " path=" + (startPathSnapshot ?? string.Empty));
                        }
                    }
                }
                catch
                {
                    // ignore root-check errors
                }

                try
                {
                    if (_currentExportSummary != null)
                    {
                        HashSet<string> finalVisible = GetOpenVisibleDocumentIds();
                        _currentExportSummary.FinalVisibleDocs = finalVisible.Count;
                    }
                }
                catch
                {
                    // ignore visible-doc summary errors
                }

                LogVisibleDocDelta(initialVisibleDocs, errorLog, "TraverseModel end");
                DebugExport(errorLog,
                    "TraverseModel end startTitle=" + (startTitle ?? string.Empty) +
                    " visibleDocs=" + GetOpenVisibleDocumentIds().Count);

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

        private string GetBomTempRootDirectory()
        {
            return Path.Combine(Path.GetTempPath(), "TinyMRP", "bom-temp");
        }

        private string BuildBomTempAssemblyPath(string token, out string tempDirectory)
        {
            string safeToken = !string.IsNullOrWhiteSpace(token) ? token.Trim() : Guid.NewGuid().ToString("N");
            tempDirectory = Path.Combine(GetBomTempRootDirectory(), safeToken);
            return Path.Combine(tempDirectory, "tinymrp_treebom_" + safeToken + ".SLDASM");
        }

        private bool IsPathUnderDirectory(string path, string directory)
        {
            if (string.IsNullOrWhiteSpace(path) || string.IsNullOrWhiteSpace(directory))
            {
                return false;
            }

            try
            {
                string fullPath = Path.GetFullPath(path)
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string fullDirectory = Path.GetFullPath(directory)
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

                if (string.Equals(fullPath, fullDirectory, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }

                string prefix = fullDirectory + Path.DirectorySeparatorChar;
                return fullPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase);
            }
            catch
            {
                return false;
            }
        }

        private void TrySetDocumentVisible(ModelDoc2 doc, bool visible)
        {
            if (doc == null)
            {
                return;
            }

            try
            {
                doc.Visible = visible;
            }
            catch
            {
                // ignore visibility errors
            }
        }

        private string GetCurrentActiveDocumentTitle()
        {
            try
            {
                ModelDoc2 activeDoc = _swApp.ActiveDoc as ModelDoc2;
                return activeDoc != null ? (activeDoc.GetTitle() ?? string.Empty) : string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private void TryRestoreActiveDocument(string activeTitle, Action<string> errorLog, string context)
        {
            string activateTitle = NormalizeDocTitleForClose(activeTitle);
            if (string.IsNullOrWhiteSpace(activateTitle))
            {
                activateTitle = activeTitle ?? string.Empty;
            }

            if (string.IsNullOrWhiteSpace(activateTitle))
            {
                return;
            }

            try
            {
                _swApp.ActivateDoc(activateTitle);
                SafeLog(errorLog, "TEMP BOM ASM restore active ok=True title=" + activateTitle + " context=" + (context ?? string.Empty));
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "TEMP BOM ASM restore active ok=False title=" + activateTitle +
                    " context=" + (context ?? string.Empty) + " error=" + ex.Message);
            }
        }

        private void TryActivateDocument(ModelDoc2 doc, Action<string> errorLog, string context)
        {
            if (doc == null)
            {
                return;
            }

            string tempTitle = string.Empty;
            try
            {
                tempTitle = doc.GetTitle() ?? string.Empty;
            }
            catch
            {
                tempTitle = string.Empty;
            }

            string activateTitle = NormalizeDocTitleForClose(tempTitle);
            if (string.IsNullOrWhiteSpace(activateTitle))
            {
                activateTitle = tempTitle;
            }

            if (string.IsNullOrWhiteSpace(activateTitle))
            {
                return;
            }

            int errors = 0;
            bool ok = false;
            try
            {
                object activated = _swApp.ActivateDoc3(
                    activateTitle,
                    true,
                    (int)swRebuildOnActivation_e.swDontRebuildActiveDoc,
                    ref errors);
                ok = activated != null;
            }
            catch
            {
                ok = false;
            }

            SafeLog(errorLog, "TEMP BOM ASM activate ok=" + ok + " errors=" + errors +
                " title=" + activateTitle + " context=" + (context ?? string.Empty));
        }

        private void TryRebuildDocument(ModelDoc2 doc, Action<string> errorLog, string context)
        {
            if (doc == null)
            {
                return;
            }

            try
            {
                bool rebuildOk = doc.ForceRebuild3(false);
                SafeLog(errorLog, "TEMP BOM ASM rebuild ok=" + rebuildOk + " context=" + (context ?? string.Empty));
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "TEMP BOM ASM rebuild failed context=" + (context ?? string.Empty) + " error=" + ex.Message);
            }
        }

        private bool TrySilentSaveAs(ModelDoc2 doc, string targetPath, Action<string> errorLog, string context,
            out int errors, out int warnings)
        {
            errors = 0;
            warnings = 0;
            if (doc == null || string.IsNullOrWhiteSpace(targetPath))
            {
                return false;
            }

            try
            {
                string directory = Path.GetDirectoryName(targetPath);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                return doc.Extension.SaveAs(
                    targetPath,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                    null,
                    ref errors,
                    ref warnings);
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "TEMP BOM ASM saveas exception context=" + (context ?? string.Empty) +
                    " path=" + targetPath + " error=" + ex.Message);
                errors = 0;
                warnings = 0;
                return false;
            }
        }

        private bool TrySilentSaveCurrent(ModelDoc2 doc, Action<string> errorLog, string context,
            out int errors, out int warnings)
        {
            errors = 0;
            warnings = 0;
            if (doc == null)
            {
                return false;
            }

            try
            {
                return doc.Save3((int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref errors, ref warnings);
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "TEMP BOM ASM save exception context=" + (context ?? string.Empty) +
                    " error=" + ex.Message);
                errors = 0;
                warnings = 0;
                return false;
            }
        }

        private bool CloseSavedTempAssemblyNoPrompt(ModelDoc2 tempAssembly, string tempAssemblyPath, Action<string> errorLog, string context)
        {
            if (tempAssembly == null)
            {
                return true;
            }

            string title = string.Empty;
            try
            {
                title = tempAssembly.GetTitle() ?? string.Empty;
            }
            catch
            {
                title = string.Empty;
            }

            string closeTitle = NormalizeDocTitleForClose(title);
            if (string.IsNullOrWhiteSpace(closeTitle))
            {
                closeTitle = title ?? string.Empty;
            }

            bool dirty = false;
            try
            {
                dirty = tempAssembly.GetSaveFlag();
            }
            catch
            {
                dirty = false;
            }

            bool savedTempExists = false;
            try
            {
                savedTempExists = !string.IsNullOrWhiteSpace(tempAssemblyPath) && File.Exists(tempAssemblyPath);
            }
            catch
            {
                savedTempExists = false;
            }

            if (dirty && savedTempExists)
            {
                int preCloseErrors;
                int preCloseWarnings;
                bool preCloseSaveOk = TrySilentSaveCurrent(tempAssembly, errorLog, context + " pre-close", out preCloseErrors, out preCloseWarnings);
                SafeLog(errorLog, "TEMP BOM ASM pre-close save ok=" + preCloseSaveOk +
                    " errors=" + preCloseErrors + " warnings=" + preCloseWarnings +
                    " path=" + (tempAssemblyPath ?? string.Empty));
            }

            ForceCloseDocNoSave(tempAssembly, errorLog, context);

            bool closeOk = !IsDocOpenByIdOrTitle(tempAssemblyPath, closeTitle);
            if (!closeOk)
            {
                try
                {
                    if (!string.IsNullOrWhiteSpace(closeTitle))
                    {
                        _swApp.QuitDoc(closeTitle);
                    }
                }
                catch (Exception ex)
                {
                    SafeLog(errorLog, "TEMP BOM ASM QuitDoc title failed context=" + (context ?? string.Empty) +
                        " title=" + closeTitle + " error=" + ex.Message);
                }

                try
                {
                    string fileName = !string.IsNullOrWhiteSpace(tempAssemblyPath)
                        ? (Path.GetFileName(tempAssemblyPath) ?? string.Empty)
                        : string.Empty;
                    if (!string.IsNullOrWhiteSpace(fileName))
                    {
                        _swApp.QuitDoc(fileName);
                    }
                }
                catch (Exception ex)
                {
                    SafeLog(errorLog, "TEMP BOM ASM QuitDoc file failed context=" + (context ?? string.Empty) +
                        " path=" + (tempAssemblyPath ?? string.Empty) + " error=" + ex.Message);
                }

                try
                {
                    System.Windows.Forms.Application.DoEvents();
                }
                catch
                {
                    // ignore UI pump errors
                }

                closeOk = !IsDocOpenByIdOrTitle(tempAssemblyPath, closeTitle);
            }

            SafeLog(errorLog, "TEMP BOM ASM close ok=" + closeOk +
                " context=" + (context ?? string.Empty) +
                " title=" + (closeTitle ?? string.Empty) +
                " path=" + (tempAssemblyPath ?? string.Empty));
            return closeOk;
        }

        private bool TryDeleteTempBomDirectory(string tempDirectory, Action<string> errorLog, string context)
        {
            if (string.IsNullOrWhiteSpace(tempDirectory))
            {
                return true;
            }

            string tempRoot = GetBomTempRootDirectory();
            if (!IsPathUnderDirectory(tempDirectory, tempRoot))
            {
                SafeLog(errorLog, "TEMP BOM ASM delete ok=False context=" + (context ?? string.Empty) +
                    " path=" + tempDirectory + " reason=outside temp root");
                return false;
            }

            string lastError = string.Empty;
            for (int attempt = 0; attempt < 5; attempt++)
            {
                try
                {
                    if (!Directory.Exists(tempDirectory))
                    {
                        SafeLog(errorLog, "TEMP BOM ASM delete ok=True context=" + (context ?? string.Empty) +
                            " path=" + tempDirectory);
                        return true;
                    }

                    Directory.Delete(tempDirectory, true);
                    if (!Directory.Exists(tempDirectory))
                    {
                        SafeLog(errorLog, "TEMP BOM ASM delete ok=True context=" + (context ?? string.Empty) +
                            " path=" + tempDirectory);
                        return true;
                    }
                }
                catch (Exception ex)
                {
                    lastError = ex.Message;
                }

                try
                {
                    System.Threading.Thread.Sleep(150);
                }
                catch
                {
                    // ignore sleep errors
                }
            }

            SafeLog(errorLog, "TEMP BOM ASM delete ok=False context=" + (context ?? string.Empty) +
                " path=" + tempDirectory + " error=" + (lastError ?? string.Empty));
            return !Directory.Exists(tempDirectory);
        }

        private bool TryBuildBomWithSavedTempAssembly(
            ModelDoc2 rootModel,
            string outputBomPath,
            string context,
            Action<string> log,
            Action<string> errorLog)
        {
            string contextLabel = !string.IsNullOrWhiteSpace(context) ? context.Trim() : "BOM export";
            if (rootModel == null || string.IsNullOrWhiteSpace(outputBomPath))
            {
                return false;
            }

            string modelPath = string.Empty;
            try
            {
                modelPath = rootModel.GetPathName() ?? string.Empty;
            }
            catch
            {
                modelPath = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(modelPath))
            {
                Log(log, contextLabel + " aborted: active document must be saved before building the temporary BOM assembly.");
                return false;
            }

            HashSet<string> baseline;
            try
            {
                baseline = SnapshotOpenDocIds();
            }
            catch
            {
                baseline = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }

            string activeBeforeTemp = GetCurrentActiveDocumentTitle();
            string activeBeforeTempNorm = NormalizeDocTitleForClose(activeBeforeTemp);
            if (string.IsNullOrWhiteSpace(activeBeforeTempNorm))
            {
                activeBeforeTempNorm = activeBeforeTemp ?? string.Empty;
            }

            string template = string.Empty;
            try
            {
                template = _swApp.GetUserPreferenceStringValue(
                    (int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly) ?? string.Empty;
            }
            catch
            {
                template = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(template))
            {
                Log(log, contextLabel + " aborted: SolidWorks default assembly template is not set (Tools > Options > Default Templates).");
                return false;
            }

            bool templateExists = false;
            try
            {
                templateExists = File.Exists(template);
            }
            catch
            {
                templateExists = false;
            }

            if (!templateExists)
            {
                Log(log, contextLabel + " aborted: default assembly template not found or inaccessible: " + template);
                return false;
            }

            string tempDirectory;
            string tempToken = Guid.NewGuid().ToString("N");
            string tempAssemblyPath = BuildBomTempAssemblyPath(tempToken, out tempDirectory);
            Directory.CreateDirectory(tempDirectory);
            SafeLog(errorLog, "TEMP BOM ASM create path=" + tempAssemblyPath + " context=" + contextLabel);

            ModelDoc2 assyDoc = null;
            bool closeOk = true;
            try
            {
                assyDoc = _swApp.NewDocument(template, 0, 0, 0) as ModelDoc2;
                AssemblyDoc swAssembly = assyDoc as AssemblyDoc;
                if (assyDoc == null || swAssembly == null)
                {
                    Log(log, contextLabel + " aborted: failed to create temporary assembly (template: " + template + ").");
                    return false;
                }

                using (new ExportDialogSuppressionScope(_swApp))
                using (new ExternalReferenceBatchOpenScope(_swApp))
                {
                    TrySetDocumentVisible(assyDoc, false);
                    TryActivateDocument(assyDoc, errorLog, contextLabel);

                    int initialSaveErrors;
                    int initialSaveWarnings;
                    bool initialSaveOk = TrySilentSaveAs(assyDoc, tempAssemblyPath, errorLog, contextLabel + " initial",
                        out initialSaveErrors, out initialSaveWarnings);
                    SafeLog(errorLog, "TEMP BOM ASM initial save ok=" + initialSaveOk +
                        " errors=" + initialSaveErrors +
                        " warnings=" + initialSaveWarnings +
                        " path=" + tempAssemblyPath);
                    if (!initialSaveOk)
                    {
                        return false;
                    }

                    ThrowIfCancelled();

                    object addedComponent = null;
                    try
                    {
                        addedComponent = swAssembly.AddComponent5(modelPath, 0, string.Empty, false, string.Empty, 0, 0, 0);
                    }
                    catch (Exception ex)
                    {
                        SafeLog(errorLog, "TEMP BOM ASM add component exception context=" + contextLabel +
                            " modelPath=" + modelPath + " error=" + ex.Message);
                        addedComponent = null;
                    }

                    SafeLog(errorLog, "TEMP BOM ASM add component ok=" + (addedComponent != null) +
                        " modelPath=" + modelPath + " context=" + contextLabel);
                    if (addedComponent == null)
                    {
                        Log(log, contextLabel + ": failed to add the root model to the temporary assembly.");
                        return false;
                    }

                    TryRebuildDocument(assyDoc, errorLog, contextLabel + " post-component");

                    int postComponentSaveErrors;
                    int postComponentSaveWarnings;
                    bool postComponentSaveOk = TrySilentSaveCurrent(assyDoc, errorLog, contextLabel + " post-component",
                        out postComponentSaveErrors, out postComponentSaveWarnings);
                    SafeLog(errorLog, "TEMP BOM ASM post-component save ok=" + postComponentSaveOk +
                        " errors=" + postComponentSaveErrors +
                        " warnings=" + postComponentSaveWarnings +
                        " path=" + tempAssemblyPath);
                    if (!postComponentSaveOk)
                    {
                        return false;
                    }

                    ThrowIfCancelled();

                    Configuration assyConfig = assyDoc.GetActiveConfiguration() as Configuration;
                    if (assyConfig == null)
                    {
                        Log(log, contextLabel + ": failed to read temporary assembly configuration.");
                        return false;
                    }

                    SetUnitPreferences(assyDoc);

                    string outputDir = Path.GetDirectoryName(outputBomPath);
                    if (!string.IsNullOrWhiteSpace(outputDir))
                    {
                        Directory.CreateDirectory(outputDir);
                    }

                    int bomX = 69;
                    int bomY = 69;
                    BomTableAnnotation bomTable = assyDoc.Extension.InsertBomTable3(
                        _config.BomTemplatePath,
                        bomX,
                        bomY,
                        (int)swBomType_e.swBomType_Indented,
                        assyConfig.Name,
                        true,
                        (int)swNumberingType_e.swNumberingType_Detailed,
                        true);

                    SafeLog(errorLog, "TEMP BOM ASM bom table ok=" + (bomTable != null) +
                        " output=" + outputBomPath + " context=" + contextLabel);
                    if (bomTable == null)
                    {
                        Log(log, contextLabel + ": failed to create BOM table.");
                        return false;
                    }

                    ITableAnnotation tableAnn = (ITableAnnotation)bomTable;
                    tableAnn.SaveAsText(outputBomPath, "\t");
                    TextFileHelper.StripUtf8Bom(outputBomPath);
                    bool outputCreated = File.Exists(outputBomPath);
                    SafeLog(errorLog, "TEMP BOM ASM text export ok=" + outputCreated +
                        " output=" + outputBomPath + " context=" + contextLabel);
                    if (!outputCreated)
                    {
                        Log(log, contextLabel + ": BOM text export did not create the output file.");
                        return false;
                    }

                    TryRestoreActiveDocument(activeBeforeTempNorm, errorLog, contextLabel + " post-text-export");
                    TrySetDocumentVisible(assyDoc, false);

                    int postBomSaveErrors;
                    int postBomSaveWarnings;
                    bool postBomSaveOk = TrySilentSaveCurrent(assyDoc, errorLog, contextLabel + " post-bom",
                        out postBomSaveErrors, out postBomSaveWarnings);
                    SafeLog(errorLog, "TEMP BOM ASM post-bom save ok=" + postBomSaveOk +
                        " errors=" + postBomSaveErrors +
                        " warnings=" + postBomSaveWarnings +
                        " path=" + tempAssemblyPath);
                    if (!postBomSaveOk)
                    {
                        return false;
                    }

                    return true;
                }
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "TEMP BOM ASM failed context=" + contextLabel +
                    " path=" + tempAssemblyPath + " error=" + ex.Message);
                return false;
            }
            finally
            {
                TryRestoreActiveDocument(activeBeforeTempNorm, errorLog, contextLabel + " finally");
                TrySetDocumentVisible(assyDoc, false);

                if (assyDoc != null)
                {
                    using (new ExportDialogSuppressionScope(_swApp))
                    using (new ExternalReferenceBatchOpenScope(_swApp))
                    {
                        closeOk = CloseSavedTempAssemblyNoPrompt(assyDoc, tempAssemblyPath, errorLog, contextLabel + " temp assembly close");
                    }
                }

                CloseDocsNotInKeepSet(baseline, errorLog, "post " + contextLabel + " temp assembly cleanup");

                if (closeOk)
                {
                    TryDeleteTempBomDirectory(tempDirectory, errorLog, contextLabel);
                }
                else
                {
                    SafeLog(errorLog, "TEMP BOM ASM delete ok=False context=" + contextLabel +
                        " path=" + tempDirectory + " reason=document still open");
                }
            }
        }

        private bool TryBuildTreeBom(ModelDoc2 rootModel, string treeBomPath, Action<string> log, Action<string> errorLog)
        {
            return TryBuildBomWithSavedTempAssembly(rootModel, treeBomPath, "Upload pack TREEBOM", log, errorLog);
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

            object childrenObj = null;
            try
            {
                childrenObj = parent.GetChildren();
            }
            catch
            {
                childrenObj = null;
            }

            foreach (object obj in ComInteropUtil.EnumerateCom(childrenObj))
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

            if (modelType == (int)swDocumentTypes_e.swDocASSEMBLY &&
                !topLevelOnly && rootConfig != null)
            {
                Component2 rootComp = null;
                try
                {
                    rootComp = rootConfig.GetRootComponent() as Component2;
                }
                catch
                {
                    rootComp = null;
                }

                AssemblyDoc assy = rootModel as AssemblyDoc;
                List<BatchEntry> planned = PlanAssemblyComponentRefs(assy, rootComp);
                foreach (BatchEntry entry in planned)
                {
                    if (entry == null)
                    {
                        continue;
                    }

                    AddBatchEntry(entry.ModelPath, entry.ModelTitle, entry.ConfigurationName, false, entries, seen, true);
                }
            }

            return entries;
        }

        private BatchTraverseResult TraverseModelsForBatch(ModelDoc2 rootModel, Configuration rootConfig, int modelType, bool topLevelOnly,
            Action<string> log, Action<string> errorLog)
        {
            var result = new BatchTraverseResult();
            var timer = System.Diagnostics.Stopwatch.StartNew();
            SafeLog(errorLog,
                "PHASE TRAVERSE start modelType=" + modelType +
                " topLevelOnly=" + topLevelOnly);

            if (rootModel == null)
            {
                SafeLog(errorLog, "PHASE TRAVERSE abort: root model is null.");
                return result;
            }

            string rootConfigName = rootConfig != null ? rootConfig.Name : string.Empty;
            AddTraversedModel(result, rootModel, rootConfigName, isRoot: true, errorLog: errorLog);

            if (modelType == (int)swDocumentTypes_e.swDocASSEMBLY &&
                !topLevelOnly &&
                rootConfig != null)
            {
                AssemblyDoc rootAssy = rootModel as AssemblyDoc;
                Component2 rootComp = null;
                try
                {
                    rootComp = rootConfig.GetRootComponent() as Component2;
                }
                catch
                {
                    rootComp = null;
                }

                if (rootAssy != null)
                {
                    try
                    {
                        rootAssy.ResolveAllLightWeightComponents(true);
                    }
                    catch (Exception ex)
                    {
                        SafeLog(errorLog, "Traverse: ResolveAllLightWeightComponents failed: " + ex.Message);
                    }
                }

                int skippedEmptyPaths = 0;
                Dictionary<string, Component2> uniqueComponents;
                try
                {
                    uniqueComponents = PlanUniqueComponentRefsForFlatBom(rootAssy, rootComp, errorLog, out skippedEmptyPaths);
                }
                catch (Exception ex)
                {
                    if (ex is OperationCanceledException)
                    {
                        throw;
                    }

                    SafeLog(errorLog, "Traverse: planning component refs failed: " + ex.Message);
                    uniqueComponents = new Dictionary<string, Component2>(StringComparer.OrdinalIgnoreCase);
                }

                if (skippedEmptyPaths > 0)
                {
                    SafeLog(errorLog, "Traverse: skipped components with empty path count=" + skippedEmptyPaths);
                }

                if (uniqueComponents != null && uniqueComponents.Count > 0)
                {
                    var keys = new List<string>(uniqueComponents.Keys);
                    keys.Sort(StringComparer.OrdinalIgnoreCase);

                    int scanned = 0;
                    int unresolved = 0;
                    foreach (string key in keys)
                    {
                        scanned++;
                        if (scanned % 50 == 0)
                        {
                            ThrowIfCancelled();
                            System.Windows.Forms.Application.DoEvents();
                        }
                        if (scanned % 200 == 0)
                        {
                            SafeLog(errorLog,
                                "heartbeat componentsScanned=" + scanned +
                                " unresolved=" + unresolved +
                                " elapsedMs=" + timer.ElapsedMilliseconds);
                        }

                        Component2 comp = uniqueComponents[key];
                        if (comp == null)
                        {
                            continue;
                        }

                        int sep = key != null ? key.LastIndexOf('|') : -1;
                        string modelPath = sep >= 0 ? key.Substring(0, sep) : (key ?? string.Empty);
                        string confName = sep >= 0 && key != null && sep + 1 < key.Length ? key.Substring(sep + 1) : string.Empty;

                        ModelDoc2 model = null;
                        try
                        {
                            model = comp.GetModelDoc2() as ModelDoc2;
                        }
                        catch
                        {
                            model = null;
                        }

                        if (model == null)
                        {
                            unresolved++;
                            result.UnresolvedComponents = unresolved;
                            SafeLog(errorLog,
                                "UNRESOLVED component path=\"" + (modelPath ?? string.Empty) +
                                "\" conf=\"" + (confName ?? string.Empty) + "\"");
                            continue;
                        }

                        AddTraversedModel(result, model, confName, isRoot: false, errorLog: errorLog, preferredPath: modelPath);
                    }

                    result.ComponentsScanned = scanned;
                    result.UnresolvedComponents = unresolved;
                }
            }

            SafeLog(errorLog,
                "PHASE TRAVERSE end unique=" + result.Unique.Count +
                " componentsScanned=" + result.ComponentsScanned +
                " unresolved=" + result.UnresolvedComponents +
                " elapsedMs=" + timer.ElapsedMilliseconds);

            return result;
        }

        private void AddTraversedModel(BatchTraverseResult result, ModelDoc2 model, string configName, bool isRoot,
            Action<string> errorLog, string preferredPath = null)
        {
            if (result == null || model == null)
            {
                return;
            }

            string path = preferredPath ?? string.Empty;
            string title = string.Empty;
            try
            {
                if (string.IsNullOrWhiteSpace(path))
                {
                    path = model.GetPathName() ?? string.Empty;
                }
            }
            catch
            {
                path = preferredPath ?? string.Empty;
            }

            try
            {
                title = model.GetTitle() ?? string.Empty;
            }
            catch
            {
                title = string.Empty;
            }

            int docType = 0;
            try
            {
                docType = model.GetType();
            }
            catch
            {
                docType = 0;
            }

            string revision = string.Empty;
            try
            {
                revision = (GetEvalProperty(model, configName, "revision") ?? string.Empty).Trim();
            }
            catch
            {
                revision = string.Empty;
            }

            string identity = !string.IsNullOrWhiteSpace(path) ? path : title;
            string key = BuildComponentTag(identity, configName, revision);
            if (result.ByKey.ContainsKey(key))
            {
                return;
            }

            var entry = new TraversedModel
            {
                Model = model,
                ModelPath = path ?? string.Empty,
                ModelTitle = title ?? string.Empty,
                ConfigurationName = configName ?? string.Empty,
                Revision = revision ?? string.Empty,
                DocType = docType,
                IsRoot = isRoot,
                Key = key
            };

            result.ByKey[key] = entry;
            result.Unique.Add(entry);

            if (!string.IsNullOrWhiteSpace(path) && !result.ModelByPath.ContainsKey(path))
            {
                result.ModelByPath[path] = model;
            }
        }

        private string BuildComponentTag(string identity, string configName, string revision)
        {
            return (identity ?? string.Empty) + "|" + (configName ?? string.Empty) + "|" + (revision ?? string.Empty);
        }

        private List<BatchEntry> PlanAssemblyComponentRefs(AssemblyDoc assembly, Component2 rootComponent)
        {
            if (assembly == null)
            {
                return PlanComponentRefsByTree(rootComponent);
            }

            // Try both boolean values defensively (SolidWorks API semantics vary by version/language sample),
            // and pick the one that yields more unique model+configuration pairs.
            List<BatchEntry> a = PlanComponentRefsFromGetComponents(assembly, true);
            List<BatchEntry> b = PlanComponentRefsFromGetComponents(assembly, false);
            List<BatchEntry> planned = a.Count >= b.Count ? a : b;

            int topLevelCount = 0;
            bool anyTopLevelAssembly = false;
            GetTopLevelComponentStats(rootComponent, out topLevelCount, out anyTopLevelAssembly);

            // If GetComponents looks like it returned only top-level components for an assembly that appears to
            // contain sub-assemblies, fall back to an explicit tree walk (no doc opens).
            if ((planned.Count == 0 && rootComponent != null) ||
                (anyTopLevelAssembly && topLevelCount > 0 && planned.Count <= topLevelCount))
            {
                List<BatchEntry> fromTree = PlanComponentRefsByTree(rootComponent);
                if (fromTree.Count > planned.Count)
                {
                    planned = fromTree;
                }
            }

            return planned;
        }

        private struct ComponentDepthFrame
        {
            public Component2 Component;
            public int Depth;
        }

        private string BuildPlannedRefKey(string modelPath, string configurationName)
        {
            return (modelPath ?? string.Empty) + "|" + (configurationName ?? string.Empty);
        }

        private List<PlannedRef> BuildTopLevelOnlyDeliverablesQueue(string rootPath, string configurationName, bool isAssembly)
        {
            return new List<PlannedRef>
            {
                new PlannedRef
                {
                    ModelPath = rootPath ?? string.Empty,
                    ConfigurationName = configurationName ?? string.Empty,
                    IsAssembly = isAssembly,
                    MaxDepth = 0,
                    SubtreeEstimate = 0,
                    IsRoot = true
                }
            };
        }

        private PlannedRef BuildPlannedRefFromSessionItem(ExportSessionItem item)
        {
            if (item == null)
            {
                return null;
            }

            return new PlannedRef
            {
                ModelPath = item.ModelPath ?? string.Empty,
                ConfigurationName = item.ConfigurationName ?? string.Empty,
                IsAssembly = item.IsAssembly,
                MaxDepth = item.MaxDepth,
                SubtreeEstimate = item.SubtreeEstimate,
                IsRoot = item.IsRoot
            };
        }

        private ExportSessionItem FindSessionItem(ExportSessionState session, PlannedRef item)
        {
            if (session == null || session.Queue == null || item == null)
            {
                return null;
            }

            string id = BuildPlannedRefKey(item.ModelPath, item.ConfigurationName);
            for (int i = 0; i < session.Queue.Count; i++)
            {
                ExportSessionItem candidate = session.Queue[i];
                if (candidate == null)
                {
                    continue;
                }

                if (string.Equals(candidate.ItemId, id, StringComparison.OrdinalIgnoreCase))
                {
                    return candidate;
                }
            }

            return null;
        }

        private List<ExportedOutputState> BuildExpectedOutputsFromModel(ModelDoc2 model, string confName, string deliverablesFolder,
            PublishOptions options, Action<string> errorLog)
        {
            var outputs = new List<ExportedOutputState>();
            if (model == null || options == null)
            {
                return outputs;
            }

            string fileString = GetFileString(model, confName, errorLog);
            if (string.IsNullOrWhiteSpace(fileString))
            {
                return outputs;
            }

            string modelPath = string.Empty;
            string partNumber = string.Empty;
            bool drawingExists = false;
            try
            {
                modelPath = model.GetPathName() ?? string.Empty;
            }
            catch
            {
                modelPath = string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(modelPath))
            {
                try
                {
                    Configuration modelConf = model.GetConfigurationByName(confName) as Configuration;
                    partNumber = BomPartNumber(modelConf, model, errorLog);
                }
                catch
                {
                    partNumber = string.Empty;
                }

                if (!string.IsNullOrWhiteSpace(partNumber))
                {
                    string drawingPath = OnlyFolder(modelPath) + partNumber + ".SLDDRW";
                    drawingExists = File.Exists(drawingPath);
                }
            }

            bool expectStep = options.ExportStep ||
                              HasProcess(model, confName, "FOLDING") ||
                              HasProcess(model, confName, "MACHINE") ||
                              HasProcess(model, confName, "3D Laser");

            if (options.ExportPngModel)
            {
                outputs.Add(new ExportedOutputState { Type = "png", Path = Path.Combine(deliverablesFolder, "png", fileString + ".png") });
            }
            if (expectStep)
            {
                outputs.Add(new ExportedOutputState { Type = "step", Path = Path.Combine(deliverablesFolder, "step", fileString + ".step") });
            }
            if (options.Export3mf)
            {
                outputs.Add(new ExportedOutputState { Type = "3mf", Path = Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf") });
            }
            if (options.ExportPly)
            {
                outputs.Add(new ExportedOutputState { Type = "ply", Path = Path.Combine(deliverablesFolder, "ply", fileString + ".ply") });
            }
            if (options.ExportStl)
            {
                outputs.Add(new ExportedOutputState { Type = "stl", Path = Path.Combine(deliverablesFolder, "stl", fileString + ".stl") });
            }
            if (options.ExportEdrawing)
            {
                string ext = model.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt";
                outputs.Add(new ExportedOutputState { Type = "edr", Path = Path.Combine(deliverablesFolder, "edr", fileString + ext) });
            }
            if (drawingExists && options.ExportPdf)
            {
                outputs.Add(new ExportedOutputState { Type = "pdf", Path = Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf") });
            }
            if (drawingExists && options.ExportDxf)
            {
                outputs.Add(new ExportedOutputState { Type = "dxf", Path = Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf") });
            }
            if (drawingExists && options.ExportPngDrawing)
            {
                outputs.Add(new ExportedOutputState { Type = "png", Path = Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png") });
            }
            if (drawingExists && options.ExportEdrawingDrawing)
            {
                outputs.Add(new ExportedOutputState { Type = "edrw", Path = Path.Combine(deliverablesFolder, "edr", fileString + ".edrw") });
            }

            return outputs;
        }

        private bool ValidateExpectedOutputs(List<ExportedOutputState> outputs, Action<string> errorLog, out string reason, out string plyReason)
        {
            reason = string.Empty;
            plyReason = string.Empty;

            if (outputs == null || outputs.Count == 0)
            {
                return false;
            }

            var failed = new List<string>();
            foreach (ExportedOutputState output in outputs)
            {
                if (output == null)
                {
                    continue;
                }

                string outputReason;
                bool valid = ValidateExportedOutput(output.Type, output.Path, errorLog, out outputReason);
                output.Validated = valid;
                output.ValidationReason = outputReason ?? string.Empty;
                try
                {
                    output.Bytes = !string.IsNullOrWhiteSpace(output.Path) && File.Exists(output.Path)
                        ? new FileInfo(output.Path).Length
                        : 0;
                }
                catch
                {
                    output.Bytes = 0;
                }

                if (!valid)
                {
                    failed.Add((output.Type ?? string.Empty) + ":" + (outputReason ?? string.Empty));
                    if (string.Equals(output.Type, "ply", StringComparison.OrdinalIgnoreCase))
                    {
                        plyReason = outputReason ?? string.Empty;
                    }
                }
            }

            if (failed.Count > 0)
            {
                reason = string.Join("; ", failed.ToArray());
                return false;
            }

            return true;
        }

        private bool HasRecordedOutputs(ExportSessionItem item)
        {
            return item != null && item.Outputs != null && item.Outputs.Count > 0;
        }

        private string GetPlyValidationReason(List<ExportedOutputState> outputs)
        {
            if (outputs == null)
            {
                return string.Empty;
            }

            for (int i = 0; i < outputs.Count; i++)
            {
                ExportedOutputState output = outputs[i];
                if (output == null)
                {
                    continue;
                }

                if (string.Equals(output.Type, "ply", StringComparison.OrdinalIgnoreCase))
                {
                    return output.ValidationReason ?? string.Empty;
                }
            }

            return string.Empty;
        }

        private bool IsDurableSkippedReason(string reason)
        {
            string normalized = (reason ?? string.Empty).Trim();
            return string.Equals(normalized, ExportSkipReasonEmptyPath, StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(normalized, ExportSkipReasonNoRequiredOutputs, StringComparison.OrdinalIgnoreCase);
        }

        private bool IsSessionItemCompleteForResume(ExportSessionItem item, PublishOptions options, Action<string> errorLog,
            out string reason)
        {
            _ = options;
            reason = string.Empty;
            if (item == null)
            {
                reason = "missing session item";
                return false;
            }

            string status = (item.Status ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(status))
            {
                reason = "unknown or empty status";
                return false;
            }

            if (string.Equals(status, ExportItemStatusPending, StringComparison.OrdinalIgnoreCase))
            {
                reason = !string.IsNullOrWhiteSpace(item.LastError) ? item.LastError : "item still pending";
                return false;
            }

            if (string.Equals(status, ExportItemStatusFailed, StringComparison.OrdinalIgnoreCase))
            {
                reason = !string.IsNullOrWhiteSpace(item.LastError) ? item.LastError : "previous attempt failed";
                return false;
            }

            if (string.Equals(status, ExportItemStatusRunning, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(status, ExportItemStatusDone, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(status, ExportItemStatusSkipped, StringComparison.OrdinalIgnoreCase))
            {
                if (HasRecordedOutputs(item))
                {
                    string outputReason;
                    string plyReason;
                    bool valid = ValidateExpectedOutputs(item.Outputs, errorLog, out outputReason, out plyReason);
                    if (valid)
                    {
                        return true;
                    }

                    reason = !string.IsNullOrWhiteSpace(outputReason) ? outputReason : "saved outputs invalid";
                    return false;
                }

                if (string.Equals(status, ExportItemStatusSkipped, StringComparison.OrdinalIgnoreCase) &&
                    IsDurableSkippedReason(item.LastError))
                {
                    reason = item.LastError ?? string.Empty;
                    return true;
                }

                if (string.Equals(status, ExportItemStatusRunning, StringComparison.OrdinalIgnoreCase))
                {
                    reason = "item was running when previous export stopped";
                    return false;
                }

                if (string.Equals(status, ExportItemStatusDone, StringComparison.OrdinalIgnoreCase))
                {
                    reason = "missing output records";
                    return false;
                }

                reason = !string.IsNullOrWhiteSpace(item.LastError) ? item.LastError : "skipped item could not be verified";
                return false;
            }

            reason = "unknown status: " + status;
            return false;
        }

        private ResumePreparationStats PrepareSessionForResume(ExportSessionState session, Action<string> errorLog)
        {
            var stats = new ResumePreparationStats();
            if (session == null || session.Queue == null)
            {
                return stats;
            }

            stats.TotalItems = session.Queue.Count;
            for (int i = 0; i < session.Queue.Count; i++)
            {
                ExportSessionItem item = session.Queue[i];
                if (item == null)
                {
                    continue;
                }

                string status = (item.Status ?? string.Empty).Trim();
                string reason;
                bool complete = IsSessionItemCompleteForResume(item, session.Options, null, out reason);
                if (complete)
                {
                    if (HasRecordedOutputs(item))
                    {
                        item.Status = ExportItemStatusDone;
                        item.LastError = string.Empty;
                        item.PlyValidationReason = string.Empty;
                    }
                    else
                    {
                        item.Status = ExportItemStatusSkipped;
                        if (string.IsNullOrWhiteSpace(item.LastError))
                        {
                            item.LastError = ExportSkipReasonNoRequiredOutputs;
                        }
                    }

                    continue;
                }

                if (string.Equals(status, ExportItemStatusRunning, StringComparison.OrdinalIgnoreCase))
                {
                    stats.RunningReset++;
                }
                else if (string.Equals(status, ExportItemStatusFailed, StringComparison.OrdinalIgnoreCase))
                {
                    stats.FailedReset++;
                }
                else if (string.Equals(status, ExportItemStatusDone, StringComparison.OrdinalIgnoreCase))
                {
                    stats.DoneReset++;
                }
                else if (string.Equals(status, ExportItemStatusSkipped, StringComparison.OrdinalIgnoreCase))
                {
                    stats.SkippedReset++;
                }
                else if (!string.Equals(status, ExportItemStatusPending, StringComparison.OrdinalIgnoreCase))
                {
                    stats.UnknownReset++;
                }

                item.Status = ExportItemStatusPending;
                if (!string.IsNullOrWhiteSpace(reason))
                {
                    item.LastError = reason;
                }
                item.PlyValidationReason = GetPlyValidationReason(item.Outputs);
            }

            if (string.Equals(session.Status, ExportSessionStatusRunning, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(session.Status, ExportSessionStatusPauseRequested, StringComparison.OrdinalIgnoreCase))
            {
                session.Status = ExportSessionStatusCrashedOrIncomplete;
            }

            stats.CompletedItems = CountCompletedSessionItems(session);
            stats.PendingItems = stats.TotalItems - stats.CompletedItems;
            SafeLog(errorLog,
                "RESUME normalize: total=" + stats.TotalItems +
                " complete=" + stats.CompletedItems +
                " pending=" + stats.PendingItems +
                " runningReset=" + stats.RunningReset +
                " failedReset=" + stats.FailedReset +
                " doneReset=" + stats.DoneReset +
                " skippedReset=" + stats.SkippedReset +
                " unknownReset=" + stats.UnknownReset);
            return stats;
        }

        private List<PlannedRef> BuildPendingResumeQueue(ExportSessionState session, Action<string> errorLog)
        {
            var queue = new List<PlannedRef>();
            if (session == null || session.Queue == null)
            {
                return queue;
            }

            for (int i = 0; i < session.Queue.Count; i++)
            {
                ExportSessionItem item = session.Queue[i];
                string reason;
                if (IsSessionItemCompleteForResume(item, session.Options, null, out reason))
                {
                    continue;
                }

                PlannedRef planned = BuildPlannedRefFromSessionItem(item);
                if (planned != null)
                {
                    queue.Add(planned);
                }
                else
                {
                    SafeLog(errorLog, "RESUME queue skipped invalid item: " + (item != null ? (item.ItemId ?? string.Empty) : string.Empty));
                }
            }

            return queue;
        }

        private int CountCompletedSessionItems(ExportSessionState session)
        {
            if (session == null || session.Queue == null)
            {
                return 0;
            }

            int count = 0;
            for (int i = 0; i < session.Queue.Count; i++)
            {
                ExportSessionItem item = session.Queue[i];
                if (item == null)
                {
                    continue;
                }

                if (string.Equals(item.Status, ExportItemStatusDone, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(item.Status, ExportItemStatusSkipped, StringComparison.OrdinalIgnoreCase))
                {
                    count++;
                }
            }

            return count;
        }

        private bool IsItemAlreadyHandled(ExportSessionItem item)
        {
            if (item == null)
            {
                return false;
            }

            return string.Equals(item.Status, ExportItemStatusDone, StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(item.Status, ExportItemStatusSkipped, StringComparison.OrdinalIgnoreCase);
        }

        private List<PlannedRef> PlanRefsForDeliverables(ModelDoc2 rootModel, Configuration rootConfig, Action<string> errorLog)
        {
            var planned = new Dictionary<string, PlannedRef>(StringComparer.OrdinalIgnoreCase);

            if (rootModel == null)
            {
                return new List<PlannedRef>();
            }

            string rootPath = string.Empty;
            string rootTitle = string.Empty;
            try
            {
                rootPath = rootModel.GetPathName() ?? string.Empty;
            }
            catch
            {
                rootPath = string.Empty;
            }

            try
            {
                rootTitle = rootModel.GetTitle() ?? string.Empty;
            }
            catch
            {
                rootTitle = string.Empty;
            }

            string rootConfigName = rootConfig != null ? (rootConfig.Name ?? string.Empty) : string.Empty;

            bool rootIsAssembly = false;
            try
            {
                rootIsAssembly = rootModel.GetType() == (int)swDocumentTypes_e.swDocASSEMBLY;
            }
            catch
            {
                rootIsAssembly = DocumentTypeFromPath(rootPath) == (int)swDocumentTypes_e.swDocASSEMBLY;
            }

            var rootRef = new PlannedRef
            {
                ModelPath = rootPath ?? string.Empty,
                ConfigurationName = rootConfigName ?? string.Empty,
                IsAssembly = rootIsAssembly,
                MaxDepth = 0,
                SubtreeEstimate = 0,
                IsRoot = true
            };

            planned[BuildPlannedRefKey(rootRef.ModelPath, rootRef.ConfigurationName)] = rootRef;

            int modelType = 0;
            try
            {
                modelType = rootModel.GetType();
            }
            catch
            {
                modelType = 0;
            }

            if (modelType != (int)swDocumentTypes_e.swDocASSEMBLY || rootConfig == null)
            {
                return new List<PlannedRef>(planned.Values);
            }

            AssemblyDoc rootAssy = rootModel as AssemblyDoc;
            Component2 rootComp = null;
            try
            {
                rootComp = rootConfig.GetRootComponent() as Component2;
            }
            catch
            {
                rootComp = null;
            }

            // Base planning (no doc opens): GetComponents + fallback tree walk; depth not available here -> default 1.
            try
            {
                List<BatchEntry> refs = PlanAssemblyComponentRefs(rootAssy, rootComp);
                foreach (BatchEntry entry in refs)
                {
                    if (entry == null)
                    {
                        continue;
                    }

                    if (string.IsNullOrWhiteSpace(entry.ModelPath))
                    {
                        continue;
                    }

                    string key = BuildPlannedRefKey(entry.ModelPath, entry.ConfigurationName);
                    if (planned.ContainsKey(key))
                    {
                        continue;
                    }

                    planned[key] = new PlannedRef
                    {
                        ModelPath = entry.ModelPath ?? string.Empty,
                        ConfigurationName = entry.ConfigurationName ?? string.Empty,
                        IsAssembly = DocumentTypeFromPath(entry.ModelPath) == (int)swDocumentTypes_e.swDocASSEMBLY,
                        MaxDepth = 1,
                        SubtreeEstimate = 0,
                        IsRoot = false
                    };
                }
            }
            catch (Exception ex)
            {
                if (ex is OperationCanceledException)
                {
                    throw;
                }

                SafeLog(errorLog,
                    "PlanRefsForDeliverables: PlanAssemblyComponentRefs failed root=" + DescribeModel(rootPath, rootTitle) +
                    " (" + ex.Message + ")");
            }

            // Prefer explicit tree walk for depth/subtree estimates where available.
            try
            {
                UpdatePlannedRefsFromTree(rootComp, planned, rootRef, errorLog);
            }
            catch (Exception ex)
            {
                if (ex is OperationCanceledException)
                {
                    throw;
                }

                SafeLog(errorLog,
                    "PlanRefsForDeliverables: depth walk failed root=" + DescribeModel(rootPath, rootTitle) +
                    " (" + ex.Message + ")");
            }

            return new List<PlannedRef>(planned.Values);
        }

        private void UpdatePlannedRefsFromTree(Component2 rootComponent, Dictionary<string, PlannedRef> plannedByKey, PlannedRef rootRef,
            Action<string> errorLog)
        {
            if (rootComponent == null || plannedByKey == null)
            {
                return;
            }

            var stack = new Stack<ComponentDepthFrame>();
            stack.Push(new ComponentDepthFrame { Component = rootComponent, Depth = 0 });

            while (stack.Count > 0)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                ComponentDepthFrame frame = stack.Pop();
                Component2 parent = frame.Component;
                int parentDepth = frame.Depth;

                object childrenObj = null;
                try
                {
                    childrenObj = parent.GetChildren();
                }
                catch
                {
                    childrenObj = null;
                }

                int includedChildCount = 0;
                foreach (object obj in ComInteropUtil.EnumerateCom(childrenObj))
                {
                    Component2 child = obj as Component2;
                    if (child == null)
                    {
                        continue;
                    }

                    if (IsComponentSuppressedOrExcluded(child))
                    {
                        continue;
                    }

                    includedChildCount++;
                    int childDepth = parentDepth + 1;

                    string path = SafeGetComponentPath(child);
                    string confName = SafeGetReferencedConfiguration(child);

                    if (string.IsNullOrWhiteSpace(path))
                    {
                        string componentName = string.Empty;
                        try
                        {
                            componentName = child.Name2 ?? string.Empty;
                        }
                        catch
                        {
                            componentName = string.Empty;
                        }

                        SafeLog(errorLog,
                            "PLAN skip unresolved component: depth=" + childDepth +
                            " name=" + (componentName ?? string.Empty) +
                            " config=" + (confName ?? string.Empty));
                    }
                    else
                    {
                        string key = BuildPlannedRefKey(path, confName);
                        PlannedRef planned;
                        if (!plannedByKey.TryGetValue(key, out planned) || planned == null)
                        {
                            planned = new PlannedRef
                            {
                                ModelPath = path ?? string.Empty,
                                ConfigurationName = confName ?? string.Empty,
                                IsAssembly = DocumentTypeFromPath(path) == (int)swDocumentTypes_e.swDocASSEMBLY,
                                MaxDepth = childDepth,
                                SubtreeEstimate = 0,
                                IsRoot = false
                            };
                            plannedByKey[key] = planned;
                        }
                        else if (childDepth > planned.MaxDepth)
                        {
                            planned.MaxDepth = childDepth;
                        }
                    }

                    // Continue traversal even if path is empty; nested components may still be saved.
                    stack.Push(new ComponentDepthFrame { Component = child, Depth = childDepth });
                }

                // SubtreeEstimate: cheap estimate based on immediate child count (max over occurrences).
                if (parentDepth == 0 && rootRef != null)
                {
                    if (includedChildCount > rootRef.SubtreeEstimate)
                    {
                        rootRef.SubtreeEstimate = includedChildCount;
                    }
                }
                else
                {
                    string parentPath = SafeGetComponentPath(parent);
                    if (!string.IsNullOrWhiteSpace(parentPath))
                    {
                        string parentConf = SafeGetReferencedConfiguration(parent);
                        string parentKey = BuildPlannedRefKey(parentPath, parentConf);
                        PlannedRef parentPlanned;
                        if (plannedByKey.TryGetValue(parentKey, out parentPlanned) && parentPlanned != null &&
                            includedChildCount > parentPlanned.SubtreeEstimate)
                        {
                            parentPlanned.SubtreeEstimate = includedChildCount;
                        }
                    }
                }
            }
        }

        private void GetTopLevelComponentStats(Component2 rootComponent, out int topLevelCount, out bool anyTopLevelAssembly)
        {
            topLevelCount = 0;
            anyTopLevelAssembly = false;

            if (rootComponent == null)
            {
                return;
            }

            object childrenObj = null;
            try
            {
                childrenObj = rootComponent.GetChildren();
            }
            catch
            {
                childrenObj = null;
            }

            foreach (object obj in ComInteropUtil.EnumerateCom(childrenObj))
            {
                Component2 child = obj as Component2;
                if (child == null)
                {
                    continue;
                }

                if (IsComponentSuppressedOrExcluded(child))
                {
                    continue;
                }

                topLevelCount++;
                string path = SafeGetComponentPath(child);
                if (!string.IsNullOrWhiteSpace(path) &&
                    path.EndsWith(".sldasm", StringComparison.OrdinalIgnoreCase))
                {
                    anyTopLevelAssembly = true;
                }
            }
        }

        private List<BatchEntry> PlanComponentRefsFromGetComponents(AssemblyDoc assembly, bool topLevelOnly)
        {
            object compsObj = null;
            try
            {
                compsObj = assembly.GetComponents(topLevelOnly);
            }
            catch
            {
                compsObj = null;
            }

            return PlanComponentRefsFromComponentObjects(compsObj);
        }

        private List<BatchEntry> PlanComponentRefsFromComponentObjects(object componentsObj)
        {
            var planned = new List<BatchEntry>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (object obj in ComInteropUtil.EnumerateCom(componentsObj))
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                Component2 comp = obj as Component2;
                if (comp == null)
                {
                    continue;
                }

                if (IsComponentSuppressedOrExcluded(comp))
                {
                    continue;
                }

                string path = SafeGetComponentPath(comp);
                if (string.IsNullOrWhiteSpace(path))
                {
                    continue;
                }

                string confName = SafeGetReferencedConfiguration(comp);
                string key = path + "|" + (confName ?? string.Empty);
                if (!seen.Add(key))
                {
                    continue;
                }

                planned.Add(new BatchEntry
                {
                    ModelPath = path,
                    ModelTitle = string.Empty,
                    ConfigurationName = confName ?? string.Empty,
                    IsRoot = false
                });
            }

            return planned;
        }

        private Dictionary<string, Component2> PlanUniqueComponentRefsForFlatBom(AssemblyDoc assembly, Component2 rootComponent,
            Action<string> errorLog, out int skippedEmptyPaths)
        {
            skippedEmptyPaths = 0;

            if (assembly == null)
            {
                return PlanUniqueComponentRefsByTreeForFlatBom(rootComponent, errorLog, ref skippedEmptyPaths);
            }

            int skippedA = 0;
            int skippedB = 0;
            Dictionary<string, Component2> a = PlanUniqueComponentRefsFromGetComponentsForFlatBom(assembly, true, ref skippedA);
            Dictionary<string, Component2> b = PlanUniqueComponentRefsFromGetComponentsForFlatBom(assembly, false, ref skippedB);

            Dictionary<string, Component2> planned = a.Count >= b.Count ? a : b;
            skippedEmptyPaths = a.Count >= b.Count ? skippedA : skippedB;

            int topLevelCount = 0;
            bool anyTopLevelAssembly = false;
            GetTopLevelComponentStats(rootComponent, out topLevelCount, out anyTopLevelAssembly);

            if ((planned.Count == 0 && rootComponent != null) ||
                (anyTopLevelAssembly && topLevelCount > 0 && planned.Count <= topLevelCount))
            {
                int skippedTree = 0;
                Dictionary<string, Component2> fromTree = PlanUniqueComponentRefsByTreeForFlatBom(rootComponent, errorLog, ref skippedTree);
                if (fromTree.Count > planned.Count)
                {
                    planned = fromTree;
                    skippedEmptyPaths = skippedTree;
                }
            }

            if (skippedEmptyPaths > 0)
            {
                DebugExport(errorLog, "FlatBOM: skipped components with empty path count=" + skippedEmptyPaths);
            }

            return planned;
        }

        private Dictionary<string, Component2> PlanUniqueComponentRefsFromGetComponentsForFlatBom(AssemblyDoc assembly, bool topLevelOnly,
            ref int skippedEmptyPaths)
        {
            object compsObj = null;
            try
            {
                compsObj = assembly.GetComponents(topLevelOnly);
            }
            catch
            {
                compsObj = null;
            }

            return PlanUniqueComponentRefsFromComponentObjectsForFlatBom(compsObj, ref skippedEmptyPaths);
        }

        private Dictionary<string, Component2> PlanUniqueComponentRefsFromComponentObjectsForFlatBom(object componentsObj,
            ref int skippedEmptyPaths)
        {
            var planned = new Dictionary<string, Component2>(StringComparer.OrdinalIgnoreCase);

            int scanned = 0;
            foreach (Component2 comp in ComInteropUtil.EnumerateComAs<Component2>(componentsObj))
            {
                scanned++;
                if (scanned % 50 == 0)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();
                }

                if (IsComponentSuppressedOrExcluded(comp))
                {
                    continue;
                }

                string path = SafeGetComponentPath(comp);
                string confName = SafeGetReferencedConfiguration(comp);

                if (string.IsNullOrWhiteSpace(path))
                {
                    skippedEmptyPaths++;
                    continue;
                }

                string key = path + "|" + (confName ?? string.Empty);
                if (!planned.ContainsKey(key))
                {
                    planned[key] = comp;
                }
            }

            return planned;
        }

        private Dictionary<string, Component2> PlanUniqueComponentRefsByTreeForFlatBom(Component2 rootComponent, Action<string> errorLog,
            ref int skippedEmptyPaths)
        {
            var planned = new Dictionary<string, Component2>(StringComparer.OrdinalIgnoreCase);
            if (rootComponent == null)
            {
                return planned;
            }

            var stack = new Stack<Component2>();
            stack.Push(rootComponent);

            int scanned = 0;
            while (stack.Count > 0)
            {
                Component2 parent = stack.Pop();
                object childrenObj = null;
                try
                {
                    childrenObj = parent.GetChildren();
                }
                catch
                {
                    childrenObj = null;
                }

                foreach (Component2 child in ComInteropUtil.EnumerateComAs<Component2>(childrenObj))
                {
                    scanned++;
                    if (scanned % 50 == 0)
                    {
                        ThrowIfCancelled();
                        System.Windows.Forms.Application.DoEvents();
                    }

                    if (child == null)
                    {
                        continue;
                    }

                    if (IsComponentSuppressedOrExcluded(child))
                    {
                        continue;
                    }

                    string path = SafeGetComponentPath(child);
                    string confName = SafeGetReferencedConfiguration(child);

                    if (string.IsNullOrWhiteSpace(path))
                    {
                        skippedEmptyPaths++;
                    }
                    else
                    {
                        string key = path + "|" + (confName ?? string.Empty);
                        if (!planned.ContainsKey(key))
                        {
                            planned[key] = child;
                        }
                    }

                    // Continue traversal even if path is empty; nested components may still be saved.
                    stack.Push(child);
                }
            }

            if (skippedEmptyPaths > 0)
            {
                DebugExport(errorLog, "FlatBOM: skipped components with empty path count=" + skippedEmptyPaths);
            }

            return planned;
        }

        private List<BatchEntry> PlanComponentRefsByTree(Component2 rootComponent)
        {
            var planned = new List<BatchEntry>();
            if (rootComponent == null)
            {
                return planned;
            }

            var stack = new Stack<Component2>();
            stack.Push(rootComponent);

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            while (stack.Count > 0)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                Component2 parent = stack.Pop();
                object childrenObj = null;
                try
                {
                    childrenObj = parent.GetChildren();
                }
                catch
                {
                    childrenObj = null;
                }

                foreach (object obj in ComInteropUtil.EnumerateCom(childrenObj))
                {
                    Component2 child = obj as Component2;
                    if (child == null)
                    {
                        continue;
                    }

                    if (IsComponentSuppressedOrExcluded(child))
                    {
                        continue;
                    }

                    string path = SafeGetComponentPath(child);
                    string confName = SafeGetReferencedConfiguration(child);
                    if (!string.IsNullOrWhiteSpace(path))
                    {
                        string key = path + "|" + (confName ?? string.Empty);
                        if (seen.Add(key))
                        {
                            planned.Add(new BatchEntry
                            {
                                ModelPath = path,
                                ModelTitle = string.Empty,
                                ConfigurationName = confName ?? string.Empty,
                                IsRoot = false
                            });
                        }
                    }

                    // Continue traversal even if path is empty; nested components may still be saved.
                    stack.Push(child);
                }
            }

            return planned;
        }

        private bool IsComponentSuppressedOrExcluded(Component2 comp)
        {
            if (comp == null)
            {
                return true;
            }

            bool suppressed = false;
            try
            {
                suppressed = comp.IsSuppressed();
            }
            catch
            {
                suppressed = false;
            }
            if (suppressed)
            {
                return true;
            }

            bool isEnvelope = false;
            try
            {
                isEnvelope = IsEnvelopeComponent(comp);
            }
            catch
            {
                isEnvelope = false;
            }
            if (isEnvelope)
            {
                return true;
            }

            bool excluded = false;
            try
            {
                excluded = comp.ExcludeFromBOM;
            }
            catch
            {
                excluded = false;
            }

            return excluded;
        }

        private string SafeGetComponentPath(Component2 comp)
        {
            if (comp == null)
            {
                return string.Empty;
            }

            try
            {
                return comp.GetPathName() ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }

        private string SafeGetReferencedConfiguration(Component2 comp)
        {
            if (comp == null)
            {
                return string.Empty;
            }

            try
            {
                return comp.ReferencedConfiguration ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
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
                int docType = DocumentTypeFromPath(entry.ModelPath);
                ModelDoc2 opened = null;

                DocumentSpecification spec = null;
                try
                {
                    spec = _swApp.GetOpenDocSpec(entry.ModelPath) as DocumentSpecification;
                }
                catch
                {
                    spec = null;
                }

                if (spec == null)
                {
                    DebugExport(errorLog, "ResolveBatchModel: open spec FAILED " + entry.ModelPath);
                    return null;
                }

                spec.DocumentType = docType;
                spec.ReadOnly = true;
                spec.Silent = true;
                if (!string.IsNullOrWhiteSpace(entry.ConfigurationName))
                {
                    try
                    {
                        spec.ConfigurationName = entry.ConfigurationName;
                    }
                    catch
                    {
                        // ignore spec config errors
                    }
                }

                int specErr = 0;
                int specWarn = 0;
                try
                {
                    specErr = spec.Error;
                }
                catch
                {
                    specErr = 0;
                }
                try
                {
                    specWarn = spec.Warning;
                }
                catch
                {
                    specWarn = 0;
                }

                DebugExport(errorLog, "ResolveBatchModel: opening " + entry.ModelPath + " type=" + docType +
                                     " specErr=" + specErr + " specWarn=" + specWarn +
                                     " readOnly=" + spec.ReadOnly + " silent=" + spec.Silent);
                using (new ExportDialogSuppressionScope(_swApp))
                using (new ExternalReferenceBatchOpenScope(_swApp))
                {
                    ThrowIfCancelled();
                    opened = _swApp.OpenDoc7(spec) as ModelDoc2;
                }
                ComInteropUtil.TryFinalReleaseComObject(spec);
                if (opened != null)
                {
                    openedHere = true;
                    DebugExport(errorLog, "ResolveBatchModel: opened OK title=" + opened.GetTitle());
                    TryShowConfiguration(opened, entry.ConfigurationName);
                }
                else
                {
                    DebugExport(errorLog, "ResolveBatchModel: open FAILED " + entry.ModelPath +
                                         " specErr=" + specErr + " specWarn=" + specWarn);
                }
                return opened;
            }

            return null;
        }

        private void TrackExplicitlyOpenedDoc(ModelDoc2 doc)
        {
            if (doc == null)
            {
                return;
            }

            string id = GetDocumentId(doc);
            if (!string.IsNullOrWhiteSpace(id))
            {
                _explicitlyOpenedDocs.Add(id);
            }
        }

        private bool IsExplicitlyOpenedDoc(ModelDoc2 doc)
        {
            if (doc == null)
            {
                return false;
            }

            string id = GetDocumentId(doc);
            return !string.IsNullOrWhiteSpace(id) && _explicitlyOpenedDocs.Contains(id);
        }

        private void CloseExplicitlyOpenedDoc(ModelDoc2 doc, Action<string> errorLog)
        {
            if (doc == null)
            {
                return;
            }

            string id = GetDocumentId(doc);
            if (string.IsNullOrWhiteSpace(id) || !_explicitlyOpenedDocs.Contains(id))
            {
                // This doc was not explicitly opened by the batch; do not close it here.
                return;
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

            string closeTitle = NormalizeDocTitleForClose(title);
            if (string.IsNullOrWhiteSpace(closeTitle))
            {
                closeTitle = title;
            }

            try
            {
                // Hide it first to avoid UI flicker.
                try
                {
                    doc.Visible = false;
                }
                catch
                {
                    // ignore
                }

                // Close via CloseDoc(title).
                try
                {
                    if (!string.IsNullOrWhiteSpace(closeTitle))
                    {
                        _swApp.CloseDoc(closeTitle);
                    }
                }
                catch (Exception ex)
                {
                    SafeLog(errorLog, "CLOSE explicitly-opened FAILED via CloseDoc: " + closeTitle + " | " + ex.Message);
                }

                // Verify whether it’s still in the open list; if so, as a last resort, try QuitDoc(title).
                bool stillOpen = false;
                try
                {
                    foreach (ModelDoc2 d in EnumerateOpenDocuments())
                    {
                        if (d == null)
                        {
                            continue;
                        }

                        string t = string.Empty;
                        try
                        {
                            t = d.GetTitle();
                        }
                        catch
                        {
                            t = string.Empty;
                        }

                        if (NormalizeDocTitleForClose(t) == closeTitle)
                        {
                            stillOpen = true;
                            break;
                        }
                    }
                }
                catch
                {
                    // ignore
                }

                if (stillOpen)
                {
                    try
                    {
                        if (!string.IsNullOrWhiteSpace(closeTitle))
                        {
                            _swApp.QuitDoc(closeTitle);
                        }
                    }
                    catch (Exception ex)
                    {
                        SafeLog(errorLog, "CLOSE explicitly-opened FAILED via QuitDoc: " + closeTitle + " | " + ex.Message);
                    }
                }

                _explicitlyOpenedDocs.Remove(id);
                SafeLog(errorLog, "CLOSE explicitly-opened: " + closeTitle);
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "CLOSE explicitly-opened UNHANDLED: " + closeTitle + " | " + ex.Message);
            }
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

        private void WriteFlatBomFromTraverse(string outputFile, BatchTraverseResult traverse, Action<string> log,
            Action<int, int> progress, HashSet<string> uploadPackBases, List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras,
            Action<string> errorLog)
        {
            if (string.IsNullOrWhiteSpace(outputFile))
            {
                throw new InvalidOperationException("FlatBOM output file path is empty.");
            }

            int total = traverse != null && traverse.Unique != null ? traverse.Unique.Count : 0;
            UpdateProgress(progress, 0, total);
            SafeLog(errorLog, "PHASE FLATBOM start entries=" + total);

            int processed = 0;
            using (var writer = TextFileHelper.CreateUtf8NoBomWriter(outputFile))
            {
                if (traverse != null && traverse.Unique != null)
                {
                    foreach (TraversedModel entry in traverse.Unique)
                    {
                        if (processed % 50 == 0)
                        {
                            ThrowIfCancelled();
                            System.Windows.Forms.Application.DoEvents();
                        }

                        if (entry == null || entry.Model == null)
                        {
                            processed++;
                            UpdateProgress(progress, processed, total);
                            continue;
                        }

                        string confName = entry.ConfigurationName ?? string.Empty;
                        try
                        {
                            writer.WriteLine(GetDocDict(entry.Model, confName, errorLog));

                            if (uploadPackBases != null)
                            {
                                string fileKey = GetFileString(entry.Model, confName, errorLog);
                                if (!string.IsNullOrWhiteSpace(fileKey))
                                {
                                    uploadPackBases.Add(fileKey);
                                }
                            }

                            if (uploadPackExtras != null)
                            {
                                try
                                {
                                    AddAssociatedFiles(uploadPackExtras, entry.Model, confName, log);
                                }
                                catch
                                {
                                    // ignore associated-files errors
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            LogExportFailure(log, errorLog,
                                "FlatBOM: error building properties for model: " +
                                DescribeModel(entry.ModelPath, entry.ModelTitle) + " (" + ex.Message + ")");

                            try
                            {
                                Configuration entryConf = entry.Model.GetConfigurationByName(confName) as Configuration;
                                string fallback = "{'partnumber':'" +
                                                  SanitizeString(BomPartNumber(entryConf, entry.Model, errorLog)) + "'}";
                                writer.WriteLine(fallback);
                            }
                            catch
                            {
                                writer.WriteLine("{'partnumber':''}");
                            }
                        }

                        processed++;
                        UpdateProgress(progress, processed, total);
                    }
                }
            }

            if (traverse != null && traverse.UnresolvedComponents > 0)
            {
                LogExportFailure(log, errorLog, "FlatBOM unresolved components count=" + traverse.UnresolvedComponents);
                if (_currentExportSummary != null)
                {
                    _currentExportSummary.FlatBomUnresolvedComponents = traverse.UnresolvedComponents;
                }
            }

            SafeLog(errorLog, "PHASE FLATBOM end processed=" + processed);
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
#if LEGACY_DOC_CLEANUP
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

                    int openDocsBefore = SnapshotOpenDocIds().Count;
                    if (errorLog != null && entry != null && !entry.IsRoot)
                    {
                        try
                        {
                            errorLog("OPEN: " + (entry.ModelPath ?? string.Empty) + " " + (entry.ConfigurationName ?? string.Empty) +
                                     " | openDocsBefore=" + openDocsBefore);
                        }
                        catch
                        {
                            // ignore logging errors
                        }
                    }

                    bool openedHere = false;
                    ModelDoc2 model = null;
                    string modelTitleForLog = string.Empty;
                    try
                    {
                        try
                        {
                            model = ResolveBatchModel(entry, rootModel, errorLog, out openedHere);
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
                            LogExportFailure(log, errorLog,
                                "Flat BOM entry open failed: " +
                                DescribeModel(entry != null ? entry.ModelPath : string.Empty,
                                    entry != null ? entry.ModelTitle : string.Empty) +
                                " (" + ex.Message + ")");
                            model = null;
                            openedHere = false;
                        }
                        if (model != null)
                        {
                            try
                            {
                                modelTitleForLog = model.GetTitle();
                            }
                            catch
                            {
                                modelTitleForLog = string.Empty;
                            }

                            if (openedHere)
                            {
                                var keepWithCurrent = new HashSet<string>(keepBase, StringComparer.OrdinalIgnoreCase);
                                AddDocToKeepSet(keepWithCurrent, model, modelTitleForLog);
                                EnsureDocBaseline(keepWithCurrent, log, errorLog, "post-open flatbom entry", allowCancel: true);
                            }

                            try
                            {
                                writer.WriteLine(GetDocDict(model, entry.ConfigurationName, errorLog));
                                if (uploadPackBases != null)
                                {
                                    string fileKey = GetFileString(model, entry.ConfigurationName, errorLog);
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
                                                      SanitizeString(BomPartNumber(entryConf, model, errorLog)) + "'}";
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
                            ComInteropUtil.TryFinalReleaseComObject(model);
                        }
                        EnsureDocBaseline(keepBase, log, errorLog, "post-close flatbom entry", allowCancel: true);

                        if (errorLog != null && openedHere && model != null)
                        {
                            try
                            {
                                string closeLabel = !string.IsNullOrWhiteSpace(modelTitleForLog)
                                    ? modelTitleForLog
                                    : DescribeModel(entry != null ? entry.ModelPath : string.Empty,
                                        entry != null ? entry.ModelTitle : string.Empty);
                                errorLog("CLOSE: " + closeLabel + " | openDocsAfter=" + SnapshotOpenDocIds().Count);
                            }
                            catch
                            {
                                // ignore logging errors
                            }
                        }
                    }

                    processed++;
                    UpdateProgress(progress, processed, entries.Count);
                }

                DebugExport(errorLog, "FlatBOM end openDocs=" + SnapshotOpenDocIds().Count);
#else
                // Macro-inspired FlatBOM scan: traverse from the already-open root assembly tree, without opening documents.
                int skippedEmptyPaths = 0;
                int unresolved = 0;
                int processed = 0;

                using (var scope = new DocScope(this, keepBase, errorLog, "flatbom-scan"))
                {
                    string rootConfigName = string.Empty;
                    try
                    {
                        Configuration rootConf = rootModel != null ? rootModel.GetActiveConfiguration() as Configuration : null;
                        if (rootConf != null)
                        {
                            rootConfigName = rootConf.Name;
                        }
                    }
                    catch
                    {
                        rootConfigName = string.Empty;
                    }

                    AssemblyDoc rootAssy = rootModel as AssemblyDoc;
                    Component2 rootComp = null;
                    var unique = new Dictionary<string, Component2>(StringComparer.OrdinalIgnoreCase);

                    if (rootAssy != null && rootModel != null)
                    {
                        try
                        {
                            rootAssy.ResolveAllLightWeightComponents(true);
                        }
                        catch (Exception ex)
                        {
                            DebugExport(errorLog, "FlatBOM: ResolveAllLightWeightComponents failed: " + ex.Message);
                        }

                        try
                        {
                            Configuration conf = rootModel.GetActiveConfiguration() as Configuration;
                            if (conf != null)
                            {
                                rootComp = conf.GetRootComponent() as Component2;
                            }
                        }
                        catch
                        {
                            rootComp = null;
                        }

                        try
                        {
                            unique = PlanUniqueComponentRefsForFlatBom(rootAssy, rootComp, errorLog, out skippedEmptyPaths);
                        }
                        catch (Exception ex)
                        {
                            if (ex is OperationCanceledException)
                            {
                                throw;
                            }

                            DebugExport(errorLog, "FlatBOM: planning component refs failed: " + ex.Message);
                            unique = new Dictionary<string, Component2>(StringComparer.OrdinalIgnoreCase);
                        }
                    }

                    int total = 1 + (unique != null ? unique.Count : 0);
                    UpdateProgress(progress, 0, total);

                    if (errorLog != null)
                    {
                        errorLog("Planned unique model-config pairs: " + total);
                    }

                    DebugExport(errorLog,
                        "FlatBOM scan planned children=" + (unique != null ? unique.Count : 0) +
                        " skippedEmptyPaths=" + skippedEmptyPaths +
                        " openDocs=" + SnapshotOpenDocIds().Count);

                    // Root/start model row first.
                    if (rootModel != null)
                    {
                        try
                        {
                            writer.WriteLine(GetDocDict(rootModel, rootConfigName, errorLog));
                            if (uploadPackBases != null)
                            {
                                string fileKey = GetFileString(rootModel, rootConfigName, errorLog);
                                if (!string.IsNullOrWhiteSpace(fileKey))
                                {
                                    uploadPackBases.Add(fileKey);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Log(log, "Error building properties for root model: " + ex.Message);
                            try
                            {
                                Configuration entryConf = rootModel.GetConfigurationByName(rootConfigName) as Configuration;
                                string fallback = "{'partnumber':'" +
                                                  SanitizeString(BomPartNumber(entryConf, rootModel, errorLog)) + "'}";
                                writer.WriteLine(fallback);
                            }
                            catch
                            {
                                writer.WriteLine("{'partnumber':''}");
                            }
                        }

                        if (uploadPackExtras != null)
                        {
                            try
                            {
                                AddAssociatedFiles(uploadPackExtras, rootModel, rootConfigName, log);
                            }
                            catch
                            {
                                // ignore associated-files errors
                            }
                        }
                    }

                    processed++;
                    UpdateProgress(progress, processed, total);

                    if (unique != null && unique.Count > 0)
                    {
                        var keys = new List<string>(unique.Keys);
                        keys.Sort(StringComparer.OrdinalIgnoreCase);

                        foreach (string key in keys)
                        {
                            ThrowIfCancelled();
                            System.Windows.Forms.Application.DoEvents();

                            int sep = key != null ? key.LastIndexOf('|') : -1;
                            string modelPath = sep >= 0 ? key.Substring(0, sep) : (key ?? string.Empty);
                            string confName = sep >= 0 && key != null && sep + 1 < key.Length ? key.Substring(sep + 1) : string.Empty;

                            Component2 comp = unique[key];
                            ModelDoc2 model = null;
                            try
                            {
                                model = comp != null ? (comp.GetModelDoc2() as ModelDoc2) : null;
                            }
                            catch
                            {
                                model = null;
                            }

                            if (model == null)
                            {
                                unresolved++;
                                if (errorLog != null)
                                {
                                    errorLog("UNRESOLVED: " + (modelPath ?? string.Empty) + " conf=" + (confName ?? string.Empty));
                                }

                                processed++;
                                UpdateProgress(progress, processed, total);
                                continue;
                            }

                            if (string.IsNullOrWhiteSpace(confName))
                            {
                                try
                                {
                                    Configuration active = model.GetActiveConfiguration() as Configuration;
                                    if (active != null && !string.IsNullOrWhiteSpace(active.Name))
                                    {
                                        confName = active.Name;
                                    }
                                }
                                catch
                                {
                                    // ignore active-config errors
                                }
                            }

                            try
                            {
                                writer.WriteLine(GetDocDict(model, confName, errorLog));
                                if (uploadPackBases != null)
                                {
                                    string fileKey = GetFileString(model, confName, errorLog);
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
                                    Configuration entryConf = model.GetConfigurationByName(confName) as Configuration;
                                    string fallback = "{'partnumber':'" +
                                                      SanitizeString(BomPartNumber(entryConf, model, errorLog)) + "'}";
                                    writer.WriteLine(fallback);
                                }
                                catch
                                {
                                    writer.WriteLine("{'partnumber':''}");
                                }
                            }

                            if (uploadPackExtras != null)
                            {
                                try
                                {
                                    AddAssociatedFiles(uploadPackExtras, model, confName, log);
                                }
                                catch
                                {
                                    // ignore associated-files errors
                                }
                            }

                            processed++;
                            UpdateProgress(progress, processed, total);
                        }
                    }

                    if (unresolved > 0)
                    {
                        LogExportFailure(log, errorLog, "FlatBOM unresolved components count=" + unresolved);
                    }

                    if (_currentExportSummary != null)
                    {
                        _currentExportSummary.FlatBomUnresolvedComponents = unresolved;
                    }
                }

                CloseDocsNotInKeepSet(keepBase, errorLog, "post-flatbom cleanup");
                DebugExport(errorLog, "FlatBOM end openDocs=" + SnapshotOpenDocIds().Count);
#endif
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
                   options.ExportDxf ||
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
                             ShouldExportPlyOutput(Path.Combine(deliverablesFolder, "ply", fileString + ".ply"),
                                 options.OverwriteFiles, null);

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

            bool dxfSelected = drawingExists && options.ExportDxf;
            bool createDxf = dxfSelected &&
                             ShouldExport(Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf"),
                                 options.OverwriteFiles);

            bool createPngD = drawingExists && options.ExportPngDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png"),
                                  options.OverwriteFiles);

            bool createEdrD = drawingExists && options.ExportEdrawingDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString + ".edrw"),
                                  options.OverwriteFiles);

            if (!createPng && !createStep && !create3mf && !createPly && !createStl && !createEdr &&
                !createPdf && !createDxf && !createPngD && !createEdrD)
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
                ExportDxfSelected = dxfSelected,
                ExportDxf = createDxf,
                ExportPngDrawing = createPngD,
                ExportEdrawingDrawing = createEdrD
            };
        }

        private DeliverablePlan BuildDeliverablePlanFromModel(ModelDoc2 model, string confName, string deliverablesFolder,
            PublishOptions options, Action<string> errorLog = null)
        {
            if (model == null || options == null)
            {
                return null;
            }

            string fileString = GetFileString(model, confName, errorLog);
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
                partNumber = BomPartNumber(modelConf, model, errorLog);
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

            bool dxfSelected = drawingExists && options.ExportDxf;
            bool createDxf = dxfSelected &&
                             ShouldExport(Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf"),
                                 options.OverwriteFiles);

            bool createPngD = drawingExists && options.ExportPngDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png"),
                                  options.OverwriteFiles);

            bool createEdrD = drawingExists && options.ExportEdrawingDrawing &&
                              ShouldExport(Path.Combine(deliverablesFolder, "edr", fileString + ".edrw"),
                                  options.OverwriteFiles);

            if (!createPng && !createStep && !create3mf && !createPly && !createStl && !createEdr &&
                !createPdf && !createDxf && !createPngD && !createEdrD)
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
                ExportDxfSelected = dxfSelected,
                ExportDxf = createDxf,
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

        private List<DeliverablePlan> BuildDeliverablePlansFromTraverse(BatchTraverseResult traverse, string deliverablesFolder,
            PublishOptions options, Action<string> log, Action<string> errorLog)
        {
            var plans = new List<DeliverablePlan>();
            if (traverse == null || traverse.Unique == null || traverse.Unique.Count == 0 || options == null)
            {
                return plans;
            }

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            int scanned = 0;
            foreach (TraversedModel traversed in traverse.Unique)
            {
                scanned++;
                if (scanned % 50 == 0)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();
                }

                if (traversed == null || traversed.Model == null)
                {
                    continue;
                }

                DeliverablePlan plan = null;
                try
                {
                    plan = BuildDeliverablePlanFromModel(traversed.Model, traversed.ConfigurationName, deliverablesFolder,
                        options, errorLog);
                }
                catch (Exception ex)
                {
                    if (ex is OperationCanceledException)
                    {
                        throw;
                    }

                    string modelLabel = !string.IsNullOrWhiteSpace(traversed.ModelPath)
                        ? traversed.ModelPath
                        : (traversed.ModelTitle ?? string.Empty);
                    LogExportFailure(log, errorLog,
                        "Deliverables planning skipped: failed to read model " + modelLabel + " (" + ex.Message + ")");

                    if (ex is System.Runtime.InteropServices.COMException ||
                        (ex.InnerException is System.Runtime.InteropServices.COMException))
                    {
                        LogExceptionDetails(errorLog, "DeliverablesPlanBuild|" + modelLabel, ex);
                    }

                    continue;
                }

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

        private void TrySetComProperty(object target, string propertyName, object value)
        {
            if (target == null || string.IsNullOrWhiteSpace(propertyName))
            {
                return;
            }

            try
            {
                target.GetType().InvokeMember(
                    propertyName,
                    BindingFlags.SetProperty,
                    null,
                    target,
                    new[] { value },
                    CultureInfo.InvariantCulture);
            }
            catch
            {
                // ignore missing property / reflection errors
            }
        }

        private long GetPrivateMemoryBytes()
        {
            try
            {
                return System.Diagnostics.Process.GetCurrentProcess().PrivateMemorySize64;
            }
            catch
            {
                return 0;
            }
        }

        private string SaveDeliverablesPlanToTempFile(List<PlannedRef> planned, Action<string> errorLog)
        {
            if (planned == null)
            {
                return string.Empty;
            }

            try
            {
                string dir = Path.Combine(Path.GetTempPath(), "TinyMRP");
                Directory.CreateDirectory(dir);

                string name = "deliverables_plan_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".json";
                string path = Path.Combine(dir, name);

                var serializer = new System.Web.Script.Serialization.JavaScriptSerializer();
                try
                {
                    serializer.MaxJsonLength = int.MaxValue;
                }
                catch
                {
                    // ignore
                }

                using (var writer = TextFileHelper.CreateUtf8NoBomWriter(path))
                {
                    writer.WriteLine("[");
                    for (int i = 0; i < planned.Count; i++)
                    {
                        PlannedRef r = planned[i];
                        string line = serializer.Serialize(new
                        {
                            path = r != null ? (r.ModelPath ?? string.Empty) : string.Empty,
                            config = r != null ? (r.ConfigurationName ?? string.Empty) : string.Empty,
                            isAssembly = r != null && r.IsAssembly,
                            depth = r != null ? r.MaxDepth : 0,
                            subtreeEstimate = r != null ? r.SubtreeEstimate : 0,
                            isRoot = r != null && r.IsRoot
                        });

                        if (i < planned.Count - 1)
                        {
                            line += ",";
                        }

                        writer.WriteLine(line);
                    }
                    writer.WriteLine("]");
                }

                return path;
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "PLAN file write failed: " + ex.Message);
                return string.Empty;
            }
        }

        private void SortDeliverablesQueue(List<PlannedRef> queue)
        {
            if (queue == null || queue.Count <= 1)
            {
                return;
            }

            queue.Sort((a, b) =>
            {
                if (ReferenceEquals(a, b))
                {
                    return 0;
                }

                if (a == null)
                {
                    return 1;
                }

                if (b == null)
                {
                    return -1;
                }

                // Root last.
                int cmp = a.IsRoot.CompareTo(b.IsRoot);
                if (cmp != 0)
                {
                    return cmp;
                }

                // Parts before assemblies.
                cmp = a.IsAssembly.CompareTo(b.IsAssembly);
                if (cmp != 0)
                {
                    return cmp;
                }

                // Deeper first (leaf-ish first).
                cmp = b.MaxDepth.CompareTo(a.MaxDepth);
                if (cmp != 0)
                {
                    return cmp;
                }

                // Smaller subtrees first (if available).
                cmp = a.SubtreeEstimate.CompareTo(b.SubtreeEstimate);
                if (cmp != 0)
                {
                    return cmp;
                }

                // Stable path/config tie-breakers.
                cmp = string.Compare(a.ModelPath ?? string.Empty, b.ModelPath ?? string.Empty, StringComparison.OrdinalIgnoreCase);
                if (cmp != 0)
                {
                    return cmp;
                }

                return string.Compare(a.ConfigurationName ?? string.Empty, b.ConfigurationName ?? string.Empty, StringComparison.OrdinalIgnoreCase);
            });
        }

        private void ResolveAllLightweightComponentsForDeliverablesPlanning(ModelDoc2 rootModel, string rootTitle, Action<string> errorLog)
        {
            if (rootModel == null)
            {
                return;
            }

            bool wasDirty = false;
            try
            {
                wasDirty = rootModel.GetSaveFlag();
            }
            catch
            {
                wasDirty = false;
            }

            int docType = 0;
            try
            {
                docType = rootModel.GetType();
            }
            catch
            {
                docType = 0;
            }

            if (docType != (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                return;
            }

            AssemblyDoc assy = rootModel as AssemblyDoc;
            if (assy == null)
            {
                return;
            }

            string title = string.Empty;
            try
            {
                title = rootModel.GetTitle() ?? string.Empty;
            }
            catch
            {
                title = string.Empty;
            }
            if (string.IsNullOrWhiteSpace(title))
            {
                title = rootTitle ?? string.Empty;
            }

            string activateTitle = NormalizeDocTitleForClose(title);
            if (string.IsNullOrWhiteSpace(activateTitle))
            {
                activateTitle = title;
            }

            bool wasVisible = true;
            try
            {
                wasVisible = rootModel.Visible;
            }
            catch
            {
                wasVisible = true;
            }

            var t = System.Diagnostics.Stopwatch.StartNew();
            SafeLog(errorLog,
                "LWT resolve start: title=" + (activateTitle ?? string.Empty) +
                " visibleBefore=" + wasVisible);

            using (new ExportDialogSuppressionScope(_swApp))
            using (new ExternalReferenceBatchOpenScope(_swApp))
            {
                YieldAndCheckCancel();

                try
                {
                    rootModel.Visible = true;
                }
                catch
                {
                    // ignore
                }

                try
                {
                    int errors = 0;
                    if (!string.IsNullOrWhiteSpace(activateTitle))
                    {
                        _swApp.ActivateDoc3(activateTitle, true,
                            (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref errors);
                    }

                    SafeLog(errorLog,
                        "LWT activate: title=" + (activateTitle ?? string.Empty) +
                        " errors=" + errors);
                }
                catch
                {
                    // ignore activation errors
                }

                YieldAndCheckCancel();

                try
                {
                    assy.ResolveAllLightWeightComponents(true);
                }
                catch (Exception ex)
                {
                    SafeLog(errorLog, "LWT resolve failed: " + ex.Message);
                    if (ex is System.Runtime.InteropServices.COMException ||
                        (ex.InnerException is System.Runtime.InteropServices.COMException))
                    {
                        LogExceptionDetails(errorLog, "ResolveAllLightWeightComponents", ex);
                    }
                }

                // ResolveAllLightWeightComponents can dirty the root assembly even when the user hasn't changed it.
                // SolidWorks does not expose an API to clear the save flag without saving; do not attempt to clear it here.

                YieldAndCheckCancel();
            }

            t.Stop();

            try
            {
                if (!wasVisible)
                {
                    rootModel.Visible = false;
                }
            }
            catch
            {
                // ignore
            }

            if (!wasDirty)
            {
                bool nowDirty = false;
                try
                {
                    nowDirty = rootModel.GetSaveFlag();
                }
                catch
                {
                    nowDirty = false;
                }

                if (nowDirty)
                {
                    SafeLog(errorLog,
                        "WARN: LWT resolve dirtied root document (was clean before resolve); will not attempt to clear save flag.");
                }
            }

            SafeLog(errorLog,
                "LWT resolve end: ms=" + t.ElapsedMilliseconds +
                " visibleAfter=" + GetOpenVisibleDocumentIds().Count);
        }

        private List<ModelDoc2> GetOpenVisibleDocuments()
        {
            var docs = new List<ModelDoc2>();
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                if (doc == null)
                {
                    continue;
                }

                bool visible = true;
                try
                {
                    visible = doc.Visible;
                }
                catch
                {
                    visible = true;
                }

                if (visible)
                {
                    docs.Add(doc);
                }
            }

            return docs;
        }

        private bool IsDocDirtyOrUnsaved(ModelDoc2 doc, out string reason)
        {
            reason = string.Empty;
            if (doc == null)
            {
                return false;
            }

            string path = string.Empty;
            try
            {
                path = doc.GetPathName() ?? string.Empty;
            }
            catch
            {
                path = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(path))
            {
                reason = "unsaved";
                return true;
            }

            try
            {
                if (!File.Exists(path))
                {
                    reason = "missingFile";
                    return true;
                }
            }
            catch
            {
                reason = "missingFile";
                return true;
            }

            bool dirty = false;
            try
            {
                dirty = doc.GetSaveFlag();
            }
            catch
            {
                dirty = false;
            }

            if (dirty)
            {
                reason = "modified";
                return true;
            }

            return false;
        }

        private ReopenDocInfo CaptureReopenInfo(ModelDoc2 doc, int order)
        {
            if (doc == null)
            {
                return null;
            }

            string path = string.Empty;
            string title = string.Empty;
            int docType = 0;
            try
            {
                path = doc.GetPathName() ?? string.Empty;
                title = doc.GetTitle() ?? string.Empty;
                docType = doc.GetType();
            }
            catch
            {
                path = string.Empty;
                title = string.Empty;
                docType = 0;
            }

            if (string.IsNullOrWhiteSpace(path))
            {
                return null;
            }

            string configName = string.Empty;
            if (docType != (int)swDocumentTypes_e.swDocDRAWING)
            {
                try
                {
                    Configuration conf = doc.GetActiveConfiguration() as Configuration;
                    configName = conf != null ? (conf.Name ?? string.Empty) : string.Empty;
                }
                catch
                {
                    configName = string.Empty;
                }
            }

            return new ReopenDocInfo
            {
                Path = path ?? string.Empty,
                DocType = docType,
                ConfigurationName = configName ?? string.Empty,
                Order = order,
                Title = title ?? string.Empty
            };
        }

        private string GetRootCloseRequiredAbortMessage()
        {
            return "Batch export aborted: root document must be saved and unmodified because the exporter closes/reopens it.";
        }

        private void EnsureRootDocSafeToCloseNoSave(ModelDoc2 rootModel, Action<string> log, Action<string> errorLog)
        {
            if (rootModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            string reason;
            if (IsDocDirtyOrUnsaved(rootModel, out reason))
            {
                string title = string.Empty;
                string path = string.Empty;
                try
                {
                    title = rootModel.GetTitle() ?? string.Empty;
                    path = rootModel.GetPathName() ?? string.Empty;
                }
                catch
                {
                    title = string.Empty;
                    path = string.Empty;
                }

                string message = GetRootCloseRequiredAbortMessage();
                LogExportFailure(log, errorLog,
                    message +
                    " title=" + (title ?? string.Empty) +
                    " path=" + (path ?? string.Empty) +
                    " reason=" + (reason ?? string.Empty));
                throw new InvalidOperationException(message);
            }
        }

        private List<ReopenDocInfo> CleanRoomCloseOtherVisibleDocuments(ModelDoc2 rootModel, Action<string> log, Action<string> errorLog)
        {
            var reopen = new List<ReopenDocInfo>();
            if (rootModel == null)
            {
                return reopen;
            }

            string rootId = GetDocumentId(rootModel);
            string rootPath = string.Empty;
            string rootTitle = string.Empty;
            try
            {
                rootPath = rootModel.GetPathName() ?? string.Empty;
                rootTitle = rootModel.GetTitle() ?? string.Empty;
            }
            catch
            {
                rootPath = string.Empty;
                rootTitle = string.Empty;
            }

            string rootTitleNorm = NormalizeDocTitleForClose(rootTitle);

            List<ModelDoc2> visible = GetOpenVisibleDocuments();
            var toClose = new List<ModelDoc2>();
            var dirty = new List<string>();
            int order = 0;

            foreach (ModelDoc2 doc in visible)
            {
                order++;
                if (doc == null)
                {
                    continue;
                }

                string docId = GetDocumentId(doc);
                if (!string.IsNullOrWhiteSpace(rootId) &&
                    !string.IsNullOrWhiteSpace(docId) &&
                    string.Equals(docId, rootId, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string path = string.Empty;
                string title = string.Empty;
                int docType = 0;
                try
                {
                    path = doc.GetPathName() ?? string.Empty;
                    title = doc.GetTitle() ?? string.Empty;
                    docType = doc.GetType();
                }
                catch
                {
                    path = string.Empty;
                    title = string.Empty;
                    docType = 0;
                }

                string titleNorm = NormalizeDocTitleForClose(title);
                if ((!string.IsNullOrWhiteSpace(rootPath) && string.Equals(path, rootPath, StringComparison.OrdinalIgnoreCase)) ||
                    (!string.IsNullOrWhiteSpace(rootTitleNorm) && string.Equals(titleNorm, rootTitleNorm, StringComparison.OrdinalIgnoreCase)) ||
                    (!string.IsNullOrWhiteSpace(rootTitle) && string.Equals(title, rootTitle, StringComparison.OrdinalIgnoreCase)))
                {
                    continue;
                }

                string dirtyReason;
                if (IsDocDirtyOrUnsaved(doc, out dirtyReason))
                {
                    dirty.Add((string.IsNullOrWhiteSpace(title) ? "<untitled>" : title) +
                              " | " + (string.IsNullOrWhiteSpace(path) ? "<no path>" : path) +
                              " | type=" + docType +
                              " | " + dirtyReason);
                    continue;
                }

                ReopenDocInfo info = CaptureReopenInfo(doc, order);
                if (info != null)
                {
                    reopen.Add(info);
                    toClose.Add(doc);
                }
            }

            if (dirty.Count > 0)
            {
                var shown = new List<string>();
                for (int i = 0; i < dirty.Count && i < 15; i++)
                {
                    shown.Add(dirty[i]);
                }

                LogExportFailure(log, errorLog,
                    "Batch export aborted: other modified/unsaved documents are open (won't auto-close to avoid data loss): " +
                    "count=" + dirty.Count +
                    " items=[" + string.Join("; ", shown.ToArray()) + "]");

                throw new InvalidOperationException("Batch export aborted: other modified/unsaved documents are open.");
            }

            if (toClose.Count == 0)
            {
                return reopen;
            }

            using (new ExportDialogSuppressionScope(_swApp))
            using (new ExternalReferenceBatchOpenScope(_swApp))
            {
                for (int i = 0; i < toClose.Count; i++)
                {
                    YieldAndCheckCancel();

                    ModelDoc2 doc = toClose[i];
                    if (doc == null)
                    {
                        continue;
                    }

                    string title = string.Empty;
                    string path = string.Empty;
                    try
                    {
                        title = doc.GetTitle() ?? string.Empty;
                        path = doc.GetPathName() ?? string.Empty;
                    }
                    catch
                    {
                        title = string.Empty;
                        path = string.Empty;
                    }

                    SafeLog(errorLog,
                        "CLEANROOM close: " +
                        (string.IsNullOrWhiteSpace(title) ? "<untitled>" : title) +
                        " | " + (string.IsNullOrWhiteSpace(path) ? "<no path>" : path));

                    try
                    {
                        ForceCloseDocNoSave(doc, errorLog, "clean-room-preflight", allowCancel: true);
                    }
                    catch
                    {
                        // ignore close errors
                    }

                    try
                    {
                        ComInteropUtil.TryFinalReleaseComObject(doc);
                    }
                    catch
                    {
                        // ignore
                    }
                }
            }

            return reopen;
        }

        private void ReopenDocumentsSilent(List<ReopenDocInfo> reopen, Action<string> errorLog)
        {
            if (reopen == null || reopen.Count == 0)
            {
                return;
            }

            reopen.Sort((a, b) =>
            {
                if (ReferenceEquals(a, b))
                {
                    return 0;
                }

                if (a == null)
                {
                    return 1;
                }

                if (b == null)
                {
                    return -1;
                }

                return a.Order.CompareTo(b.Order);
            });

            using (new ExportDialogSuppressionScope(_swApp))
            using (new ExternalReferenceBatchOpenScope(_swApp))
            {
                foreach (ReopenDocInfo info in reopen)
                {
                    if (info == null || string.IsNullOrWhiteSpace(info.Path))
                    {
                        continue;
                    }

                    if (!File.Exists(info.Path))
                    {
                        SafeLog(errorLog, "CLEANROOM reopen skipped (missing file): " + info.Path);
                        continue;
                    }

                    if (IsDocOpenByIdOrTitle(info.Path, info.Title))
                    {
                        continue;
                    }

                    DocumentSpecification spec = null;
                    try
                    {
                        spec = _swApp.GetOpenDocSpec(info.Path) as DocumentSpecification;
                    }
                    catch
                    {
                        spec = null;
                    }

                    if (spec == null)
                    {
                        SafeLog(errorLog, "CLEANROOM reopen spec failed: " + info.Path);
                        continue;
                    }

                    try
                    {
                        spec.DocumentType = info.DocType;
                        spec.ReadOnly = false;
                        spec.Silent = true;
                        if (!string.IsNullOrWhiteSpace(info.ConfigurationName))
                        {
                            try
                            {
                                spec.ConfigurationName = info.ConfigurationName;
                            }
                            catch
                            {
                                // ignore
                            }
                        }

                        TrySetComProperty(spec, "DocumentVisible", true);

                        YieldAndCheckCancel();
                        ModelDoc2 opened = _swApp.OpenDoc7(spec) as ModelDoc2;
                        if (opened != null && !string.IsNullOrWhiteSpace(info.ConfigurationName) &&
                            info.DocType != (int)swDocumentTypes_e.swDocDRAWING)
                        {
                            TryShowConfiguration(opened, info.ConfigurationName);
                        }
                    }
                    catch (Exception ex)
                    {
                        SafeLog(errorLog, "CLEANROOM reopen failed: " + info.Path + " (" + ex.Message + ")");
                        if (ex is System.Runtime.InteropServices.COMException ||
                            (ex.InnerException is System.Runtime.InteropServices.COMException))
                        {
                            LogExceptionDetails(errorLog, "CleanRoomReopen|" + info.Path, ex);
                        }
                    }
                    finally
                    {
                        ComInteropUtil.TryFinalReleaseComObject(spec);
                    }
                }
            }
        }

        private ModelDoc2 OpenDocReadOnlySilent(string path, int docType, string configurationName, Action<string> errorLog,
            string context, out int specErr, out int specWarn)
        {
            specErr = 0;
            specWarn = 0;

            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                SafeLog(errorLog, "OPEN skipped (missing file) context=" + (context ?? string.Empty) + " path=" + (path ?? string.Empty));
                return null;
            }

            DocumentSpecification spec = null;
            try
            {
                spec = _swApp.GetOpenDocSpec(path) as DocumentSpecification;
            }
            catch
            {
                spec = null;
            }

            if (spec == null)
            {
                SafeLog(errorLog, "OPEN spec failed context=" + (context ?? string.Empty) + " path=" + (path ?? string.Empty));
                return null;
            }

            spec.DocumentType = docType;
            spec.ReadOnly = true;
            spec.Silent = true;
            if (!string.IsNullOrWhiteSpace(configurationName))
            {
                try
                {
                    spec.ConfigurationName = configurationName;
                }
                catch
                {
                    // ignore
                }
            }

            // If available in this API version, request an invisible open (avoid UI/tab churn).
            TrySetComProperty(spec, "DocumentVisible", false);

            try
            {
                specErr = spec.Error;
            }
            catch
            {
                specErr = 0;
            }
            try
            {
                specWarn = spec.Warning;
            }
            catch
            {
                specWarn = 0;
            }

            ModelDoc2 opened = null;
            try
            {
                using (new ExportDialogSuppressionScope(_swApp))
                using (new ExternalReferenceBatchOpenScope(_swApp))
                {
                    YieldAndCheckCancel();
                    opened = _swApp.OpenDoc7(spec) as ModelDoc2;
                }
            }
            finally
            {
                ComInteropUtil.TryFinalReleaseComObject(spec);
            }

            if (opened != null)
            {
                try
                {
                    opened.Visible = false;
                }
                catch
                {
                    // ignore hide errors
                }
            }

            return opened;
        }

        private void LogAndCloseAllNonEssentialDocs(HashSet<string> keep, Action<string> errorLog, string context)
        {
            if (keep == null)
            {
                keep = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }

            if (errorLog != null)
            {
                try
                {
                    List<ModelDoc2> toClose = GetOpenDocsNotInKeepSet(keep);
                    if (toClose.Count > 0)
                    {
                        errorLog("WATCHDOG cleanup: context=" + (context ?? string.Empty) + " closing=" + toClose.Count);
                        foreach (ModelDoc2 doc in toClose)
                        {
                            if (doc == null)
                            {
                                continue;
                            }

                            string title = string.Empty;
                            string path = string.Empty;
                            bool visible = true;
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
                            try
                            {
                                visible = doc.Visible;
                            }
                            catch
                            {
                                visible = true;
                            }

                            errorLog("WATCHDOG close: title=" + (title ?? string.Empty) +
                                     " | path=" + (path ?? string.Empty) +
                                     " | visible=" + visible);
                        }
                    }
                }
                catch
                {
                    // ignore
                }
            }

            CloseDocsNotInKeepSet(keep, errorLog, context);
        }

        private void ProcessDeliverablesIsolated(
            List<PlannedRef> queue,
            string deliverablesFolder,
            PublishOptions options,
            Action<string> log,
            Action<string> errorLog,
            Action<int, int> progress,
            string rootPath,
            string rootConfigName,
            ExportSessionState sessionState)
        {
            int total = sessionState != null && sessionState.Queue != null && sessionState.Queue.Count > 0
                ? sessionState.Queue.Count
                : (queue != null ? queue.Count : 0);
            int processed = CountCompletedSessionItems(sessionState);
            UpdateProgress(progress, processed, total);

            if (queue == null || queue.Count == 0)
            {
                return;
            }

            bool overwrite = options != null && options.OverwriteFiles;

            int visibleDocsStart = 0;
            try
            {
                visibleDocsStart = GetOpenVisibleDocumentIds().Count;
            }
            catch
            {
                visibleDocsStart = 0;
            }

            HashSet<string> keepBase = null;
            try
            {
                keepBase = GetOpenVisibleDocumentIds();
            }
            catch
            {
                keepBase = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }

            int openDocsStart = 0;
            try
            {
                openDocsStart = SnapshotOpenDocIds().Count;
            }
            catch
            {
                openDocsStart = 0;
            }

            SafeLog(errorLog,
                "ISOLATED baseline: openDocs=" + openDocsStart +
                " visibleDocs=" + visibleDocsStart +
                " keepSet=" + keepBase.Count +
                " mem=" + GetPrivateMemoryBytes());

            if (sessionState != null)
            {
                sessionState.Status = _pauseRequested ? ExportSessionStatusPauseRequested : ExportSessionStatusRunning;
                SaveExportSessionAtomic(sessionState, errorLog);
            }

            // Close the starting/root model so referenced model data can be released between items.
            string rootTitle = string.Empty;
            ModelDoc2 rootDoc = null;
            try
            {
                rootDoc = FindOpenDocument(rootPath, null);
            }
            catch
            {
                rootDoc = null;
            }
            if (rootDoc == null && string.IsNullOrWhiteSpace(rootPath))
            {
                try
                {
                    rootDoc = _swApp.ActiveDoc as ModelDoc2;
                }
                catch
                {
                    rootDoc = null;
                }
            }

            try
            {
                if (rootDoc != null)
                {
                    rootTitle = rootDoc.GetTitle() ?? string.Empty;
                }
            }
            catch
            {
                rootTitle = string.Empty;
            }

            string rootTitleNorm = NormalizeDocTitleForClose(rootTitle);
            if (!string.IsNullOrWhiteSpace(rootPath))
            {
                keepBase.Remove(rootPath);
            }
            if (!string.IsNullOrWhiteSpace(rootTitle))
            {
                keepBase.Remove(rootTitle);
            }
            if (!string.IsNullOrWhiteSpace(rootTitleNorm))
            {
                keepBase.Remove(rootTitleNorm);
            }

            try
            {
                int baselineAfterRootClose = openDocsStart;
                ExportSummary summary = _currentExportSummary;

                if (string.IsNullOrWhiteSpace(rootPath) || !File.Exists(rootPath))
                {
                    string message = GetRootCloseRequiredAbortMessage();
                    LogExportFailure(log, errorLog,
                        message +
                        " title=" + (rootTitle ?? string.Empty) +
                        " path=" + (rootPath ?? string.Empty) +
                        " reason=missingFile");
                    throw new InvalidOperationException(message);
                }
                else
                {
                    long memoryBeforeRootClose = GetPrivateMemoryBytes();
                    if (summary != null)
                    {
                        summary.MemoryBeforeRootClose = memoryBeforeRootClose;
                    }

                    SafeLog(errorLog,
                        "ROOT close start: title=" + (rootTitle ?? string.Empty) +
                        " path=" + (rootPath ?? string.Empty) +
                        " openDocsBefore=" + SnapshotOpenDocIds().Count +
                        " mem=" + memoryBeforeRootClose);

                    if (rootDoc != null)
                    {
                        try
                        {
                            ForceCloseDocNoSave(rootDoc, errorLog, "isolated-root-close");
                        }
                        catch
                        {
                            // ignore close errors; verification below will log warnings
                        }
                    }

                    bool stillOpen = false;
                    try
                    {
                        stillOpen = IsDocOpenByIdOrTitle(rootPath, rootTitle);
                    }
                    catch
                    {
                        stillOpen = false;
                    }

                    long memoryAfterRootClose = GetPrivateMemoryBytes();
                    if (summary != null)
                    {
                        summary.MemoryAfterRootClose = memoryAfterRootClose;
                    }

                    SafeLog(errorLog,
                        "ROOT close end: stillOpen=" + stillOpen +
                        " openDocsAfter=" + SnapshotOpenDocIds().Count +
                        " mem=" + memoryAfterRootClose);

                    if (stillOpen)
                    {
                        const string closeFailedMessage = "Batch export aborted: root document could not be closed cleanly for isolated export.";
                        LogExportFailure(log, errorLog,
                            closeFailedMessage +
                            " title=" + (rootTitle ?? string.Empty) +
                            " path=" + (rootPath ?? string.Empty));
                        throw new InvalidOperationException(closeFailedMessage);
                    }

                    // Close any leaked hidden reference docs now that the root is closed.
                    LogAndCloseAllNonEssentialDocs(keepBase, errorLog, "isolated-post-root-close");
                }

                try
                {
                    baselineAfterRootClose = SnapshotOpenDocIds().Count;
                }
                catch
                {
                    baselineAfterRootClose = 0;
                }

                if (summary != null)
                {
                    summary.OpenDocsAfterRootClose = baselineAfterRootClose;
                    summary.MemoryAfterRootClose = GetPrivateMemoryBytes();
                    summary.DeliverablePlansPlanned = total;
                }

                SafeLog(errorLog,
                    "ISOLATED after root close: openDocs=" + baselineAfterRootClose +
                    " visibleDocs=" + GetOpenVisibleDocumentIds().Count +
                    " keepVisible=" + keepBase.Count +
                    " mem=" + GetPrivateMemoryBytes());

                if (baselineAfterRootClose > keepBase.Count + 3)
                {
                    SafeLog(errorLog,
                        "WARN: baseline openDocs still high after root close: openDocs=" + baselineAfterRootClose +
                        " keepVisible=" + keepBase.Count +
                        " running cleanup pass.");

                    LogAndCloseAllNonEssentialDocs(keepBase, errorLog, "isolated-baseline-watchdog");

                    try
                    {
                        baselineAfterRootClose = SnapshotOpenDocIds().Count;
                    }
                    catch
                    {
                        baselineAfterRootClose = 0;
                    }

                    SafeLog(errorLog,
                        "ISOLATED baseline after cleanup: openDocs=" + baselineAfterRootClose +
                        " visibleDocs=" + GetOpenVisibleDocumentIds().Count +
                        " keepVisible=" + keepBase.Count +
                        " mem=" + GetPrivateMemoryBytes());
                }

                int watchdogThreshold = baselineAfterRootClose + 3;

                foreach (PlannedRef item in queue)
                {
                    var itemTimer = System.Diagnostics.Stopwatch.StartNew();
                    string modelDesc = string.Empty;
                    ModelDoc2 model = null;
                    bool modelWasOpenBefore = false;
                    ExportSessionItem sessionItem = FindSessionItem(sessionState, item);
                    List<ExportedOutputState> expectedOutputs = null;
                    string itemValidationReason = string.Empty;
                    string itemPlyReason = string.Empty;
                    bool itemValidated = false;
                    bool itemWorkStarted = false;
                    bool itemFailureCountedInSummary = false;
                    bool shouldPauseAfterItem = false;

                    try
                    {
                        YieldAndCheckCancel();

                        if (item == null)
                        {
                            continue;
                        }

                        modelDesc = (item.ModelPath ?? string.Empty) + "|" + (item.ConfigurationName ?? string.Empty);

                        if (IsItemAlreadyHandled(sessionItem))
                        {
                            continue;
                        }

                        itemWorkStarted = true;

                        if (string.IsNullOrWhiteSpace(item.ModelPath))
                        {
                            SafeLog(errorLog, "SKIP: planned item has empty path: " + modelDesc);
                            if (sessionItem != null)
                            {
                                sessionItem.Status = ExportItemStatusSkipped;
                                sessionItem.CompletedUtc = UtcNowString();
                                sessionItem.LastError = ExportSkipReasonEmptyPath;
                                SaveExportSessionAtomic(sessionState, errorLog);
                            }
                            if (summary != null)
                            {
                                summary.DeliverablePlansSkipped++;
                                summary.DeliverableItemsSkipped++;
                            }
                            continue;
                        }

                        if (sessionItem != null)
                        {
                            sessionItem.Status = ExportItemStatusRunning;
                            sessionItem.StartedUtc = UtcNowString();
                            sessionItem.CompletedUtc = string.Empty;
                            sessionItem.Attempts++;
                            sessionItem.LastError = string.Empty;
                            sessionItem.PlyValidationReason = string.Empty;
                            sessionItem.Outputs = new List<ExportedOutputState>();
                            sessionState.Status = _pauseRequested ? ExportSessionStatusPauseRequested : ExportSessionStatusRunning;
                            SaveExportSessionAtomic(sessionState, errorLog);
                        }

                        SafeLog(errorLog,
                            "ITEM start: " + modelDesc +
                            " isAsm=" + item.IsAssembly +
                            " depth=" + item.MaxDepth +
                            " subtree=" + item.SubtreeEstimate +
                            " isRoot=" + item.IsRoot +
                            " openDocs=" + SnapshotOpenDocIds().Count +
                            " visibleDocs=" + GetOpenVisibleDocumentIds().Count +
                            " mem=" + GetPrivateMemoryBytes());

                        // Enforce a tight doc budget between items.
                        LogAndCloseAllNonEssentialDocs(keepBase, errorLog, "isolated-pre-open|" + modelDesc);

                        // Reuse a user-visible document if it was open at baseline; never close those.
                        try
                        {
                            model = FindOpenDocument(item.ModelPath, null);
                        }
                        catch
                        {
                            model = null;
                        }

                        // If the model is open but NOT part of the visible-baseline keep set, close it now so we don't accumulate hidden docs.
                        if (model != null && !IsDocInKeepSet(model, keepBase))
                        {
                            try
                            {
                                ForceCloseDocNoSave(model, errorLog, "isolated-preexisting-close");
                            }
                            catch
                            {
                                // ignore close errors
                            }

                            try
                            {
                                ComInteropUtil.TryFinalReleaseComObject(model);
                            }
                            catch
                            {
                                // ignore
                            }

                            model = null;
                        }

                        modelWasOpenBefore = model != null;
                        if (modelWasOpenBefore)
                        {
                            string reuseTitle = string.Empty;
                            try
                            {
                                reuseTitle = model.GetTitle() ?? string.Empty;
                            }
                            catch
                            {
                                reuseTitle = string.Empty;
                            }

                            SafeLog(errorLog, "OPEN reuse: " + modelDesc + " title=" + (reuseTitle ?? string.Empty));
                        }
                        else
                        {
                            model = null;
                        }

                        int docType = item.IsAssembly ? (int)swDocumentTypes_e.swDocASSEMBLY : (int)swDocumentTypes_e.swDocPART;
                        int specErr = 0;
                        int specWarn = 0;
                        long openMs = 0;

                        if (model == null)
                        {
                            var openTimer = System.Diagnostics.Stopwatch.StartNew();
                            try
                            {
                                SafeLog(errorLog,
                                    "OPEN start: path=" + (item.ModelPath ?? string.Empty) +
                                    " type=" + docType +
                                    " conf=" + (item.ConfigurationName ?? string.Empty));

                                model = OpenDocReadOnlySilent(item.ModelPath, docType, item.ConfigurationName, errorLog,
                                    "isolated-open|" + modelDesc, out specErr, out specWarn);
                            }
                            catch (Exception ex)
                            {
                                if (ex is OperationCanceledException)
                                {
                                    throw;
                                }

                                SafeLog(errorLog, "OPEN exception: " + modelDesc + " (" + ex.Message + ")");
                                if (ex is System.Runtime.InteropServices.COMException ||
                                    (ex.InnerException is System.Runtime.InteropServices.COMException))
                                {
                                    LogExceptionDetails(errorLog, "IsolatedOpen|" + modelDesc, ex);
                                }

                                model = null;
                                specErr = 0;
                                specWarn = 0;
                            }
                            finally
                            {
                                openTimer.Stop();
                                openMs = openTimer.ElapsedMilliseconds;
                            }

                            string openedTitle = string.Empty;
                            try
                            {
                                openedTitle = model != null ? (model.GetTitle() ?? string.Empty) : string.Empty;
                            }
                            catch
                            {
                                openedTitle = string.Empty;
                            }

                            SafeLog(errorLog,
                                "OPEN end: ok=" + (model != null) +
                                " ms=" + openMs +
                                " specErr=" + specErr +
                                " specWarn=" + specWarn +
                                " title=" + (openedTitle ?? string.Empty) +
                                " openDocsNow=" + SnapshotOpenDocIds().Count +
                                " mem=" + GetPrivateMemoryBytes());
                        }

                        if (model == null)
                        {
                            if (sessionItem != null && string.IsNullOrWhiteSpace(sessionItem.LastError))
                            {
                                sessionItem.LastError = "source model could not be opened";
                            }
                            if (summary != null)
                            {
                                summary.DeliverablePlansSkipped++;
                                summary.DeliverableItemsSkipped++;
                            }
                            continue;
                        }

                        try
                        {
                            if (!string.IsNullOrWhiteSpace(item.ConfigurationName))
                            {
                                string activeConfName = string.Empty;
                                try
                                {
                                    Configuration active = model.GetActiveConfiguration() as Configuration;
                                    activeConfName = active != null ? (active.Name ?? string.Empty) : string.Empty;
                                }
                                catch
                                {
                                    activeConfName = string.Empty;
                                }

                                if (!string.Equals(activeConfName, item.ConfigurationName, StringComparison.OrdinalIgnoreCase))
                                {
                                    model.ShowConfiguration2(item.ConfigurationName);
                                }
                            }
                        }
                        catch
                        {
                            // ignore config switch errors
                        }

                        expectedOutputs = BuildExpectedOutputsFromModel(
                            model,
                            item.ConfigurationName,
                            deliverablesFolder,
                            options,
                            errorLog);

                        // Pre-export watchdog: if opening this model caused extra documents to open, close them now (keep baseline-visible + current model).
                        try
                        {
                            var keepWithCurrent = new HashSet<string>(keepBase, StringComparer.OrdinalIgnoreCase);
                            AddDocToKeepSet(keepWithCurrent, model, null);

                            int openWithCurrent = 0;
                            try
                            {
                                openWithCurrent = SnapshotOpenDocIds().Count;
                            }
                            catch
                            {
                                openWithCurrent = 0;
                            }

                            if (openWithCurrent > watchdogThreshold)
                            {
                                SafeLog(errorLog,
                                    "WATCHDOG pre-export: openDocs=" + openWithCurrent +
                                    " threshold=" + watchdogThreshold +
                                    " context=" + modelDesc);
                                LogAndCloseAllNonEssentialDocs(keepWithCurrent, errorLog, "isolated-pre-export|" + modelDesc);
                            }
                        }
                        catch
                        {
                            // ignore watchdog errors
                        }

                        DeliverablePlan plan = null;
                        try
                        {
                            plan = BuildDeliverablePlanFromModel(model, item.ConfigurationName, deliverablesFolder, options, errorLog);
                        }
                        catch (Exception ex)
                        {
                            if (ex is OperationCanceledException)
                            {
                                throw;
                            }

                            LogExportFailure(log, errorLog, "Deliverables planning failed: " + modelDesc + " (" + ex.Message + ")");
                            if (ex is System.Runtime.InteropServices.COMException ||
                                (ex.InnerException is System.Runtime.InteropServices.COMException))
                            {
                                LogExceptionDetails(errorLog, "IsolatedPlanBuild|" + modelDesc, ex);
                            }

                            itemValidationReason = "deliverables planning failed: " + ex.Message;
                            if (sessionItem != null)
                            {
                                sessionItem.LastError = itemValidationReason;
                            }
                            plan = null;
                        }

                        bool hasExports = plan != null && (plan.HasModelExports() || plan.HasDrawingExports());
                        if (!hasExports)
                        {
                            bool hasExpectedOutputs = expectedOutputs != null && expectedOutputs.Count > 0;
                            if (hasExpectedOutputs)
                            {
                                itemValidated = ValidateExpectedOutputs(expectedOutputs, errorLog, out itemValidationReason, out itemPlyReason);
                                SafeLog(errorLog,
                                    itemValidated
                                        ? "SKIP: outputs already valid: " + modelDesc
                                        : "SKIP validation failed for existing outputs: " + modelDesc + " reason=" + (itemValidationReason ?? string.Empty));
                            }
                            else
                            {
                                SafeLog(errorLog, "SKIP: no exports needed: " + modelDesc);
                            }

                            if (summary != null)
                            {
                                summary.DeliverablePlansSkipped++;
                                if (!hasExpectedOutputs)
                                {
                                    summary.DeliverableItemsSkipped++;
                                }
                            }
                            continue;
                        }

                        SafeLog(errorLog,
                            "EXPORT start: " + (plan.FileString ?? string.Empty) +
                            " exports=" + DescribePlanExports(plan) +
                            " openDocs=" + SnapshotOpenDocIds().Count +
                            " mem=" + GetPrivateMemoryBytes());

                        var exportTimer = System.Diagnostics.Stopwatch.StartNew();
                        int failCountBefore = GetFailedExportCount(summary);
                        try
                        {
                            ExecuteDeliverablePlan(model, plan, deliverablesFolder, overwrite, log, errorLog);
                        }
                        finally
                        {
                            exportTimer.Stop();
                        }

                        SafeLog(errorLog,
                            "EXPORT end: " + (plan.FileString ?? string.Empty) +
                            " ms=" + exportTimer.ElapsedMilliseconds +
                            " openDocs=" + SnapshotOpenDocIds().Count +
                            " mem=" + GetPrivateMemoryBytes());

                        itemValidated = ValidateExpectedOutputs(expectedOutputs, errorLog, out itemValidationReason, out itemPlyReason);

                        if (summary != null)
                        {
                            summary.DeliverablePlansExecuted++;
                            if (GetFailedExportCount(summary) > failCountBefore)
                            {
                                summary.DeliverableItemsFailed++;
                                itemFailureCountedInSummary = true;
                            }
                        }
                    }
                    finally
                    {
                        // Close model if we opened it (never close baseline-visible docs).
                        if (model != null && !modelWasOpenBefore)
                        {
                            var closeTimer = System.Diagnostics.Stopwatch.StartNew();
                            try
                            {
                                ForceCloseDocNoSave(model, errorLog, "isolated-model-close");
                            }
                            catch
                            {
                                // ignore close errors; watchdog below will log warnings if it remains open
                            }
                            finally
                            {
                                closeTimer.Stop();
                            }

                            try
                            {
                                ComInteropUtil.TryFinalReleaseComObject(model);
                            }
                            catch
                            {
                                // ignore
                            }

                            SafeLog(errorLog,
                                "MODEL close end: " + (modelDesc ?? string.Empty) +
                                " ms=" + closeTimer.ElapsedMilliseconds +
                                " openDocs=" + SnapshotOpenDocIds().Count +
                                " mem=" + GetPrivateMemoryBytes());
                        }

                        // Watchdog: close anything not in the visible-baseline keep set.
                        int openNow = 0;
                        try
                        {
                            openNow = SnapshotOpenDocIds().Count;
                        }
                        catch
                        {
                            openNow = 0;
                        }

                        if (openNow > watchdogThreshold)
                        {
                            SafeLog(errorLog,
                                "WATCHDOG trigger: openDocs=" + openNow +
                                " threshold=" + watchdogThreshold +
                                " context=" + (modelDesc ?? string.Empty));
                            LogAndCloseAllNonEssentialDocs(keepBase, errorLog, "isolated-watchdog|" + (modelDesc ?? string.Empty));
                        }
                        else
                        {
                            CloseDocsNotInKeepSet(keepBase, errorLog, "isolated-post-item|" + (modelDesc ?? string.Empty));
                        }

                        RunConservativeCleanupGc(errorLog, "isolated-post-item|" + (modelDesc ?? string.Empty));

                        if (sessionItem != null && itemWorkStarted && !IsItemAlreadyHandled(sessionItem))
                        {
                            sessionItem.Outputs = expectedOutputs ?? new List<ExportedOutputState>();
                            sessionItem.CompletedUtc = UtcNowString();

                            if (expectedOutputs != null && expectedOutputs.Count > 0)
                            {
                                if (itemValidated)
                                {
                                    sessionItem.Status = ExportItemStatusDone;
                                    sessionItem.LastError = string.Empty;
                                    sessionItem.PlyValidationReason = string.Empty;
                                }
                                else
                                {
                                    sessionItem.Status = ExportItemStatusFailed;
                                    sessionItem.LastError = !string.IsNullOrWhiteSpace(itemValidationReason)
                                        ? itemValidationReason
                                        : (sessionItem.LastError ?? "required outputs invalid");
                                    sessionItem.PlyValidationReason = itemPlyReason ?? string.Empty;
                                }
                            }
                            else if (string.Equals(sessionItem.Status, ExportItemStatusSkipped, StringComparison.OrdinalIgnoreCase))
                            {
                                // Already marked skipped.
                            }
                            else if (string.IsNullOrWhiteSpace(sessionItem.LastError))
                            {
                                sessionItem.Status = ExportItemStatusSkipped;
                                sessionItem.LastError = ExportSkipReasonNoRequiredOutputs;
                            }
                            else
                            {
                                sessionItem.Status = ExportItemStatusFailed;
                            }
                        }

                        if (summary != null &&
                            sessionItem != null &&
                            string.Equals(sessionItem.Status, ExportItemStatusFailed, StringComparison.OrdinalIgnoreCase) &&
                            !itemFailureCountedInSummary)
                        {
                            summary.DeliverableItemsFailed++;
                            itemFailureCountedInSummary = true;
                        }

                        if (sessionState != null)
                        {
                            sessionState.Status = _pauseRequested
                                ? ExportSessionStatusPauseRequested
                                : ExportSessionStatusRunning;
                            SaveExportSessionAtomic(sessionState, errorLog);
                        }

                        itemTimer.Stop();

                        if (itemWorkStarted)
                        {
                            processed++;
                            UpdateProgress(progress, processed, total);
                            if (summary != null)
                            {
                                summary.DeliverableItemsProcessed = processed;
                            }
                        }

                        SafeLog(errorLog,
                            "ITEM end: idx=" + processed + "/" + total +
                            " elapsedMs=" + itemTimer.ElapsedMilliseconds +
                            " openDocs=" + SnapshotOpenDocIds().Count +
                            " visibleDocs=" + GetOpenVisibleDocumentIds().Count +
                            " mem=" + GetPrivateMemoryBytes());

                        if (_pauseRequested && itemWorkStarted)
                        {
                            if (sessionState != null)
                            {
                                sessionState.Status = ExportSessionStatusPaused;
                                SaveExportSessionAtomic(sessionState, errorLog);
                            }

                            Log(log, "Export paused after item " + processed + "/" + total + ". Resume available.");
                            shouldPauseAfterItem = true;
                        }
                    }

                    if (shouldPauseAfterItem)
                    {
                        return;
                    }
                }
            }
            finally
            {
                if (!string.IsNullOrWhiteSpace(rootPath) && File.Exists(rootPath))
                {
                    try
                    {
                        if (!IsDocOpenByIdOrTitle(rootPath, rootTitle))
                        {
                            int docType = DocumentTypeFromPath(rootPath);
                            DocumentSpecification spec = null;
                            try
                            {
                                spec = _swApp.GetOpenDocSpec(rootPath) as DocumentSpecification;
                            }
                            catch
                            {
                                spec = null;
                            }

                            if (spec != null)
                            {
                                spec.DocumentType = docType;
                                spec.ReadOnly = false;
                                spec.Silent = true;
                                if (!string.IsNullOrWhiteSpace(rootConfigName))
                                {
                                    try
                                    {
                                        spec.ConfigurationName = rootConfigName;
                                    }
                                    catch
                                    {
                                        // ignore
                                    }
                                }

                                using (new ExternalReferenceBatchOpenScope(_swApp))
                                {
                                    try
                                    {
                                        _swApp.OpenDoc7(spec);
                                    }
                                    catch
                                    {
                                        // ignore open errors
                                    }
                                }
                            }

                            ComInteropUtil.TryFinalReleaseComObject(spec);
                        }

                        // Activate + restore configuration if possible.
                        ModelDoc2 rootOpen = FindOpenDocument(rootPath, rootTitle);
                        if (rootOpen != null)
                        {
                            string activateTitle = string.Empty;
                            try
                            {
                                activateTitle = NormalizeDocTitleForClose(rootOpen.GetTitle());
                                if (string.IsNullOrWhiteSpace(activateTitle))
                                {
                                    activateTitle = rootOpen.GetTitle();
                                }
                            }
                            catch
                            {
                                activateTitle = rootTitleNorm;
                            }

                            try
                            {
                                if (!string.IsNullOrWhiteSpace(activateTitle))
                                {
                                    _swApp.ActivateDoc(activateTitle);
                                }
                            }
                            catch
                            {
                                // ignore activate errors
                            }

                            TryShowConfiguration(rootOpen, rootConfigName);
                        }
                    }
                    catch
                    {
                        // ignore root-reopen errors
                    }
                }
            }
        }

        private void RunConservativeCleanupGc(Action<string> errorLog, string context)
        {
            try
            {
                GC.Collect();
                GC.WaitForPendingFinalizers();
                GC.Collect();
                GC.WaitForPendingFinalizers();
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "GC cleanup failed: context=" + (context ?? string.Empty) + " (" + ex.Message + ")");
            }
        }

        private void ProcessDeliverablePlansFast(List<DeliverablePlan> plans, BatchTraverseResult traverse, string deliverablesFolder,
            PublishOptions options, Action<string> log, Action<string> errorLog, HashSet<string> baselineVisibleDocs,
            ModelDoc2 rootModel, string rootTitle, Action<int, int> progress)
        {
            int total = plans != null ? plans.Count : 0;
            UpdateProgress(progress, 0, total);

            if (plans == null || plans.Count == 0)
            {
                return;
            }

            if (baselineVisibleDocs == null)
            {
                baselineVisibleDocs = GetOpenVisibleDocumentIds();
            }

            string rootDocId = string.Empty;
            try
            {
                rootDocId = GetDocumentId(rootModel);
            }
            catch
            {
                rootDocId = string.Empty;
            }

            List<DeliverableGroup> groups = BuildDeliverableGroups(plans, rootModel, rootTitle);
            if (_currentExportSummary != null)
            {
                _currentExportSummary.DeliverablePlansPlanned = total;
                _currentExportSummary.DeliverableGroupsPlanned = groups != null ? groups.Count : 0;
            }

            _explicitlyOpenedDocs.Clear();

            int openAtStart = 0;
            try
            {
                openAtStart = SnapshotOpenDocIds().Count;
            }
            catch
            {
                openAtStart = 0;
            }
            SafeLog(errorLog, "EXPORT PHASE START: openDocs=" + openAtStart +
                               " visibleBaseline=" + baselineVisibleDocs.Count);

            SafeLog(errorLog,
                "PHASE EXPORT start groups=" + (groups != null ? groups.Count : 0) +
                " plans=" + total +
                " visibleBaseline=" + baselineVisibleDocs.Count);

            bool overwrite = options != null && options.OverwriteFiles;
            int processed = 0;

            using (var openedDocs = new OpenTracker(this, errorLog))
            {
                foreach (DeliverableGroup group in groups)
                {
                    YieldAndCheckCancel();

                    if (group == null || group.Plans == null || group.Plans.Count == 0)
                    {
                        continue;
                    }

                    ModelDoc2 model = null;
                    bool openedHere = false;
                    try
                    {
                        if (group.IsRoot)
                        {
                            model = rootModel;
                        }
                        else if (traverse != null && !string.IsNullOrWhiteSpace(group.ModelPath))
                        {
                            traverse.ModelByPath.TryGetValue(group.ModelPath, out model);
                        }

                        // If traversal didn't yield a model pointer, explicitly open it for this group only.
                        if (model == null)
                        {
                            BatchEntry openEntry = BuildOpenEntry(group);
                            try
                            {
                                model = ResolveBatchModel(openEntry, rootModel, errorLog, out openedHere);
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

                                SafeLog(errorLog,
                                    "ResolveBatchModel failed for group model: " +
                                    DescribeModel(group.ModelPath, group.ModelTitle) +
                                    " (" + ex.Message + ")");
                                model = null;
                                openedHere = false;
                            }

                            if (openedHere && model != null)
                            {
                                string openedId = string.Empty;
                                try
                                {
                                    openedId = GetDocumentId(model);
                                }
                                catch
                                {
                                    openedId = string.Empty;
                                }

                                if (!string.IsNullOrWhiteSpace(openedId) &&
                                    !string.IsNullOrWhiteSpace(rootDocId) &&
                                    string.Equals(openedId, rootDocId, StringComparison.OrdinalIgnoreCase))
                                {
                                    openedHere = false;
                                }
                                else
                                {
                                    TrackExplicitlyOpenedDoc(model);
                                    openedHere = IsExplicitlyOpenedDoc(model);
                                }

                                try
                                {
                                    model.Visible = false;
                                }
                                catch
                                {
                                    // ignore visibility errors
                                }
                            }
                        }

                        if (model == null)
                        {
                            SafeLog(errorLog,
                                "UNRESOLVED export model group: " +
                                DescribeModel(group.ModelPath, group.ModelTitle));

                            if (_currentExportSummary != null)
                            {
                                _currentExportSummary.DeliverableGroupsSkipped++;
                                _currentExportSummary.DeliverablePlansSkipped += group.Plans.Count;
                            }

                            processed += group.Plans.Count;
                            UpdateProgress(progress, processed, total);
                            continue;
                        }

                        if (_currentExportSummary != null)
                        {
                            _currentExportSummary.DeliverableGroupsProcessed++;
                        }

                        string modelDesc = DescribeModel(group.ModelPath, group.ModelTitle);
                        SafeLog(errorLog,
                            "EXPORT model=" + modelDesc +
                            " plans=" + group.Plans.Count);

                        foreach (DeliverablePlan plan in group.Plans)
                        {
                            YieldAndCheckCancel();

                            string planKey = plan != null ? (plan.FileString ?? string.Empty) : string.Empty;

                            // Resilience: if any previous operation left extra visible tabs open, hide them now so
                            // we never start a plan above the baseline UI state.
                            EnforceVisibleDocBudget(baselineVisibleDocs, rootDocId, "before plan " + planKey, errorLog, 0);

                            SafeLog(errorLog,
                                "PLAN start key=" + planKey +
                                " path=" + (plan != null ? (plan.ModelPath ?? string.Empty) : string.Empty) +
                                " conf=" + (plan != null ? (plan.ConfigurationName ?? string.Empty) : string.Empty) +
                                " exports=" + DescribePlanExports(plan));

                            var planTimer = System.Diagnostics.Stopwatch.StartNew();
                            try
                            {
                                ExecuteDeliverablePlanFast(model, plan, deliverablesFolder, overwrite, log, errorLog, openedDocs,
                                    baselineVisibleDocs, rootDocId);
                                if (_currentExportSummary != null)
                                {
                                    _currentExportSummary.DeliverablePlansExecuted++;
                                }
                            }
                            catch (Exception ex)
                            {
                                if (ex is OperationCanceledException)
                                {
                                    throw;
                                }

                                LogExportFailure(log, errorLog, "Deliverables plan failed: " + planKey + " (" + ex.Message + ")");
                                if (ex is System.Runtime.InteropServices.COMException ||
                                    (ex.InnerException is System.Runtime.InteropServices.COMException))
                                {
                                    LogExceptionDetails(errorLog, "DeliverablesPlan|" + planKey, ex);
                                }
                            }
                            finally
                            {
                                openedDocs.CloseAll("deliverables-plan-finally");

                                try
                                {
                                    RestoreStartDocument(rootTitle);
                                }
                                catch
                                {
                                    // ignore activate errors
                                }

                                // Enforce "no visible doc creep": only manage VISIBLE tabs, never close in-memory
                                // referenced documents loaded by the root assembly.
                                EnforceVisibleDocBudget(baselineVisibleDocs, rootDocId, "after plan " + planKey, errorLog, 0);
                                LogVisibleDocDelta(baselineVisibleDocs, errorLog, "after plan " + planKey);
                            }

                            SafeLog(errorLog, "PLAN end key=" + planKey + " elapsedMs=" + planTimer.ElapsedMilliseconds);

                            processed++;
                            UpdateProgress(progress, processed, total);
                        }
                    }
                    finally
                    {
                        if (model != null)
                        {
                            CloseExplicitlyOpenedDoc(model, errorLog);
                        }

                        int openAfterGroup = 0;
                        try
                        {
                            openAfterGroup = SnapshotOpenDocIds().Count;
                        }
                        catch
                        {
                            openAfterGroup = 0;
                        }

                        SafeLog(errorLog, "AFTER group model=" + DescribeModel(group.ModelPath, group.ModelTitle) +
                                           " openDocs=" + openAfterGroup +
                                           " explicitlyOpened=" + _explicitlyOpenedDocs.Count);
                        if (openAfterGroup > 50)
                        {
                            SafeLog(errorLog, "WARNING: openDocs=" + openAfterGroup + " exceeds safe threshold 50.");
                        }
                    }
                }
            }

            SafeLog(errorLog, "PHASE EXPORT end processed=" + processed + " plans=" + total);
        }

        private void ExecuteDeliverablePlanFast(ModelDoc2 model, DeliverablePlan plan, string deliverablesFolder, bool overwriteFiles,
            Action<string> log, Action<string> errorLog, OpenTracker openedDocs, HashSet<string> baselineVisibleIds, string rootDocId)
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
                ModelPublish(model, plan.ConfigurationName, plan.FileString, deliverablesFolder,
                    plan.ExportPngModel, plan.ExportStep, plan.ExportEdrawing, plan.Export3mf,
                    plan.ExportPly, plan.ExportStl, log, errorLog);

                YieldAndCheckCancel();
                EnforceVisibleDocBudget(baselineVisibleIds, rootDocId, "after ModelPublish " + (plan.FileString ?? string.Empty),
                    errorLog, 0);
                LogVisibleDocDelta(baselineVisibleIds, errorLog, "after ModelPublish " + (plan.FileString ?? string.Empty));
            }

            if (plan.HasDrawingExports())
            {
                DwgPublishFast(model, plan.FileString, deliverablesFolder,
                    overwriteFiles, plan.ExportPdf, plan.ExportDxfSelected, plan.ExportPngDrawing, plan.ExportEdrawingDrawing,
                    log, errorLog, plan.PartNumber, openedDocs, baselineVisibleIds, rootDocId);

                YieldAndCheckCancel();
                EnforceVisibleDocBudget(baselineVisibleIds, rootDocId, "after DwgPublish " + (plan.FileString ?? string.Empty),
                    errorLog, 0);
                LogVisibleDocDelta(baselineVisibleIds, errorLog, "after DwgPublish " + (plan.FileString ?? string.Empty));
            }
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

            if (_currentExportSummary != null)
            {
                _currentExportSummary.DeliverablePlansPlanned = total;
                _currentExportSummary.DeliverableGroupsPlanned = groups != null ? groups.Count : 0;
            }

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

                // Ensure we never accumulate open documents between groups. Only keep the initial user-open docs (keepBase).
                CloseDocsNotInKeepSet(keepBase, errorLog, "pre-open deliverable group");
                ThrowIfCancelled();

                BatchEntry openEntry = BuildOpenEntry(group);
                int openDocsBefore = SnapshotOpenDocIds().Count;
                if (errorLog != null && openEntry != null && !openEntry.IsRoot)
                {
                    try
                    {
                        errorLog("OPEN: " + (openEntry.ModelPath ?? string.Empty) + " " + (openEntry.ConfigurationName ?? string.Empty) +
                                 " | openDocsBefore=" + openDocsBefore);
                    }
                    catch
                    {
                        // ignore logging errors
                    }
                }

                string modelDesc = DescribeModel(group != null ? group.ModelPath : string.Empty,
                    group != null ? group.ModelTitle : string.Empty);
                Log(log, "Opening model for deliverables: " + modelDesc);
                Log(log, "Open docs now: " + SnapshotOpenDocIds().Count);
                DebugExport(errorLog,
                    "DeliverablesGroup start model=" + modelDesc +
                    " plans=" + (group != null && group.Plans != null ? group.Plans.Count : 0) +
                    " openDocs=" + SnapshotOpenDocIds().Count);

                DocScope scope = new DocScope(this, keepBase, errorLog, "deliverables|" + modelDesc);
                bool openedHere = false;
                ModelDoc2 model = null;
                string modelTitleForLog = string.Empty;
                try
                {
                    try
                    {
                        model = ResolveBatchModel(openEntry, rootModel, errorLog, out openedHere);
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
                        LogExportFailure(log, errorLog, "Deliverables open failed: " + modelDesc + " (" + ex.Message + ")");
                        if (ex is System.Runtime.InteropServices.COMException ||
                            (ex.InnerException is System.Runtime.InteropServices.COMException))
                        {
                            LogExceptionDetails(errorLog, "DeliverablesOpen|" + modelDesc, ex);
                        }
                        model = null;
                        openedHere = false;
                    }
                    if (model == null)
                    {
                        LogExportFailure(log, errorLog,
                            "Deliverables skipped: unable to open model " + modelDesc);
                        if (_currentExportSummary != null)
                        {
                            _currentExportSummary.DeliverableGroupsSkipped++;
                            _currentExportSummary.DeliverablePlansSkipped += group != null && group.Plans != null ? group.Plans.Count : 0;
                        }
                        processed += group != null && group.Plans != null ? group.Plans.Count : 0;
                        UpdateProgress(progress, processed, total);
                        continue;
                    }

                    if (_currentExportSummary != null)
                    {
                        _currentExportSummary.DeliverableGroupsProcessed++;
                    }

                    try
                    {
                        modelTitleForLog = model.GetTitle();
                    }
                    catch
                    {
                        modelTitleForLog = string.Empty;
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
                        if (_currentExportSummary != null)
                        {
                            if (shouldExecute)
                            {
                                _currentExportSummary.DeliverablePlansExecuted++;
                            }
                            else
                            {
                                _currentExportSummary.DeliverablePlansSkipped++;
                            }
                        }
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
                        ComInteropUtil.TryFinalReleaseComObject(model);
                    }

                    try
                    {
                        scope.CloseOpenedDocs();
                    }
                    catch
                    {
                        // ignore scope cleanup errors
                    }

                    CloseDocsNotInKeepSet(keepBase, errorLog, "post-close deliverable group");
                    if (errorLog != null && openedHere && model != null && openEntry != null && !openEntry.IsRoot)
                    {
                        try
                        {
                            string closeLabel = !string.IsNullOrWhiteSpace(modelTitleForLog) ? modelTitleForLog : modelDesc;
                            errorLog("CLOSE: " + closeLabel + " | openDocsAfter=" + SnapshotOpenDocIds().Count);
                        }
                        catch
                        {
                            // ignore logging errors
                        }
                    }
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

            if (_currentExportSummary != null)
            {
                _currentExportSummary.DeliverablePlansPlanned = total;
                _currentExportSummary.DeliverableGroupsPlanned = groups != null ? groups.Count : 0;
            }

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

                // Ensure we never accumulate open documents between legacy groups. Only keep the initial user-open docs (keepBase).
                CloseDocsNotInKeepSet(keepBase, errorLog, "pre-open legacy deliverable group");
                ThrowIfCancelled();

                BatchEntry openEntry = group.OpenEntry;
                int openDocsBefore = SnapshotOpenDocIds().Count;
                if (errorLog != null && openEntry != null && !openEntry.IsRoot)
                {
                    try
                    {
                        errorLog("OPEN: " + (openEntry.ModelPath ?? string.Empty) + " " + (openEntry.ConfigurationName ?? string.Empty) +
                                 " | openDocsBefore=" + openDocsBefore);
                    }
                    catch
                    {
                        // ignore logging errors
                    }
                }

                string modelDesc = DescribeModel(openEntry != null ? openEntry.ModelPath : string.Empty,
                    openEntry != null ? openEntry.ModelTitle : string.Empty);
                Log(log, "Opening model for deliverables (legacy): " + modelDesc);
                Log(log, "Open docs now: " + SnapshotOpenDocIds().Count);
                DebugExport(errorLog,
                    "LegacyGroup start model=" + modelDesc +
                    " entries=" + (group != null && group.Entries != null ? group.Entries.Count : 0) +
                    " openDocs=" + SnapshotOpenDocIds().Count);

                DocScope scope = new DocScope(this, keepBase, errorLog, "legacy-deliverables|" + modelDesc);
                bool openedHere = false;
                ModelDoc2 model = null;
                string modelTitleForLog = string.Empty;
                try
                {
                    try
                    {
                        model = ResolveBatchModel(openEntry, rootModel, errorLog, out openedHere);
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
                        LogExportFailure(log, errorLog, "Deliverables open failed (legacy): " + modelDesc + " (" + ex.Message + ")");
                        if (ex is System.Runtime.InteropServices.COMException ||
                            (ex.InnerException is System.Runtime.InteropServices.COMException))
                        {
                            LogExceptionDetails(errorLog, "LegacyDeliverablesOpen|" + modelDesc, ex);
                        }
                        model = null;
                        openedHere = false;
                    }
                    if (model == null)
                    {
                        LogExportFailure(log, errorLog, "Deliverables skipped: unable to open model " + modelDesc);
                        if (_currentExportSummary != null)
                        {
                            _currentExportSummary.DeliverableGroupsSkipped++;
                            _currentExportSummary.DeliverablePlansSkipped += group != null && group.Entries != null ? group.Entries.Count : 0;
                        }
                        processed += group != null && group.Entries != null ? group.Entries.Count : 0;
                        UpdateProgress(progress, processed, total);
                        continue;
                    }

                    if (_currentExportSummary != null)
                    {
                        _currentExportSummary.DeliverableGroupsProcessed++;
                    }

                    try
                    {
                        modelTitleForLog = model.GetTitle();
                    }
                    catch
                    {
                        modelTitleForLog = string.Empty;
                    }

                    DebugExport(errorLog,
                        "LegacyGroup openedHere=" + openedHere +
                        " title=" + (model != null ? model.GetTitle() : string.Empty) +
                        " path=" + (model != null ? model.GetPathName() : string.Empty));

                    foreach (BatchEntry entry in group.Entries)
                    {
                        ThrowIfCancelled();
                        System.Windows.Forms.Application.DoEvents();

                        DeliverablePlan plan = BuildDeliverablePlanFromModel(model, entry.ConfigurationName, deliverablesFolder, options, errorLog);
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
                            if (_currentExportSummary != null)
                            {
                                _currentExportSummary.DeliverablePlansExecuted++;
                            }
                            ExecuteDeliverablePlan(model, plan, deliverablesFolder,
                                options != null && options.OverwriteFiles, log, errorLog);
                        }
                        else
                        {
                            if (_currentExportSummary != null)
                            {
                                _currentExportSummary.DeliverablePlansSkipped++;
                            }
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
                        ComInteropUtil.TryFinalReleaseComObject(model);
                    }

                    try
                    {
                        scope.CloseOpenedDocs();
                    }
                    catch
                    {
                        // ignore scope cleanup errors
                    }

                    CloseDocsNotInKeepSet(keepBase, errorLog, "post-close legacy deliverable group");
                    if (errorLog != null && openedHere && model != null && openEntry != null && !openEntry.IsRoot)
                    {
                        try
                        {
                            string closeLabel = !string.IsNullOrWhiteSpace(modelTitleForLog) ? modelTitleForLog : modelDesc;
                            errorLog("CLOSE: " + closeLabel + " | openDocsAfter=" + SnapshotOpenDocIds().Count);
                        }
                        catch
                        {
                            // ignore logging errors
                        }
                    }
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
                    if (ex is System.Runtime.InteropServices.COMException ||
                        (ex.InnerException is System.Runtime.InteropServices.COMException))
                    {
                        LogExceptionDetails(errorLog, "ModelPublish|" + (plan.FileString ?? string.Empty), ex);
                    }
                }
            }

            if (plan.HasDrawingExports())
            {
                try
                {
                    DwgPublish(model, plan.FileString, deliverablesFolder,
                        overwriteFiles, plan.ExportPdf, plan.ExportDxfSelected, plan.ExportPngDrawing, plan.ExportEdrawingDrawing, log, errorLog,
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
                    if (ex is System.Runtime.InteropServices.COMException ||
                        (ex.InnerException is System.Runtime.InteropServices.COMException))
                    {
                        LogExceptionDetails(errorLog, "DwgPublish|" + (plan.FileString ?? string.Empty), ex);
                    }
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
            if (plan.ExportDxf) parts.Add("dxf");
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

        private bool ShouldExportPlyOutput(string path, bool overwrite, Action<string> errorLog)
        {
            if (overwrite || string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return true;
            }

            string reason;
            bool valid = IsValidPlyFile(path, errorLog, out reason);
            if (!valid)
            {
                SafeLog(errorLog, "PLY existing invalid, regenerating: " + path + " reason=" + (reason ?? string.Empty));
            }

            return !valid;
        }

        private long WaitForFileStable(string path, int timeoutMs, Action<string> errorLog)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return 0;
            }

            DateTime deadline = DateTime.UtcNow.AddMilliseconds(Math.Max(250, timeoutMs));
            long lastSize = -1;
            int stableChecks = 0;

            while (DateTime.UtcNow <= deadline)
            {
                YieldAndCheckCancel();

                long size = 0;
                bool exists = false;
                try
                {
                    exists = File.Exists(path);
                    if (exists)
                    {
                        size = new FileInfo(path).Length;
                    }
                }
                catch
                {
                    exists = false;
                    size = 0;
                }

                if (exists)
                {
                    if (size == lastSize && size > 0)
                    {
                        stableChecks++;
                        if (stableChecks >= 3)
                        {
                            return size;
                        }
                    }
                    else
                    {
                        stableChecks = 0;
                        lastSize = size;
                    }
                }

                try
                {
                    System.Threading.Thread.Sleep(200);
                }
                catch
                {
                    // ignore
                }
            }

            SafeLog(errorLog, "WAIT stable timeout: path=" + path + " size=" + lastSize);
            return Math.Max(0, lastSize);
        }

        private bool ValidateExportedOutput(string type, string path, Action<string> errorLog, out string reason)
        {
            reason = string.Empty;
            string normalizedType = (type ?? string.Empty).Trim().ToLowerInvariant();

            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                reason = "missing file";
                return false;
            }

            long bytes = 0;
            try
            {
                bytes = new FileInfo(path).Length;
            }
            catch
            {
                bytes = 0;
            }

            if (normalizedType == "ply")
            {
                return IsValidPlyFile(path, errorLog, out reason);
            }

            if (normalizedType == "pdf")
            {
                if (bytes < MinPdfBytes)
                {
                    reason = "file too small";
                    return false;
                }

                return true;
            }

            if (normalizedType == "png")
            {
                if (bytes < MinPngBytes)
                {
                    reason = "file too small";
                    return false;
                }

                return true;
            }

            if (normalizedType == "edr" || normalizedType == "edrw" || normalizedType == "easm" || normalizedType == "eprt")
            {
                if (bytes < MinEdrawingBytes)
                {
                    reason = "file too small";
                    return false;
                }

                return true;
            }

            if (normalizedType == "stl" || normalizedType == "dxf")
            {
                if (bytes < MinGenericMeshBytes)
                {
                    reason = "file too small";
                    return false;
                }

                return true;
            }

            if (normalizedType == "step" || normalizedType == "3mf")
            {
                if (bytes < MinGenericCadBytes)
                {
                    reason = "file too small";
                    return false;
                }

                return true;
            }

            if (bytes <= 0)
            {
                reason = "empty file";
                return false;
            }

            return true;
        }

        private bool IsValidPlyFile(string path, Action<string> errorLog, out string reason)
        {
            reason = string.Empty;
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                reason = "missing file";
                return false;
            }

            long length = 0;
            try
            {
                length = new FileInfo(path).Length;
            }
            catch
            {
                length = 0;
            }

            if (length <= 0)
            {
                reason = "empty file";
                return false;
            }

            byte[] headerBytes;
            int headerRead = 0;
            try
            {
                int headerBufferLength = (int)Math.Min(length, 64 * 1024);
                headerBytes = new byte[headerBufferLength];
                using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                {
                    headerRead = stream.Read(headerBytes, 0, headerBytes.Length);
                }
            }
            catch (Exception ex)
            {
                reason = "read failed: " + ex.Message;
                return false;
            }

            if (headerRead <= 0)
            {
                reason = "read failed";
                return false;
            }

            string ascii = Encoding.ASCII.GetString(headerBytes, 0, headerRead);
            int endHeaderIndex = ascii.IndexOf("end_header", StringComparison.Ordinal);
            if (endHeaderIndex < 0)
            {
                reason = "missing end_header";
                return false;
            }

            int lineEndIndex = ascii.IndexOf('\n', endHeaderIndex);
            if (lineEndIndex < 0)
            {
                lineEndIndex = endHeaderIndex + "end_header".Length;
            }

            int headerLength = lineEndIndex + 1;
            if (headerLength > headerRead)
            {
                headerLength = headerRead;
            }

            string headerText = ascii.Substring(0, Math.Min(headerLength, ascii.Length));
            string[] lines = headerText.Split(new[] { "\r\n", "\n", "\r" }, StringSplitOptions.RemoveEmptyEntries);
            if (lines.Length == 0 || !lines[0].TrimStart().StartsWith("ply", StringComparison.OrdinalIgnoreCase))
            {
                reason = "first line does not start with ply";
                return false;
            }

            int vertexCount = -1;
            int faceCount = -1;
            bool binaryFormat = false;
            for (int i = 0; i < lines.Length; i++)
            {
                string line = (lines[i] ?? string.Empty).Trim();
                if (line.StartsWith("format", StringComparison.OrdinalIgnoreCase) &&
                    line.IndexOf("binary", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    binaryFormat = true;
                }

                if (line.StartsWith("element vertex", StringComparison.OrdinalIgnoreCase))
                {
                    string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                    int parsed;
                    if (parts.Length >= 3 && int.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed))
                    {
                        vertexCount = parsed;
                    }
                }
                else if (line.StartsWith("element face", StringComparison.OrdinalIgnoreCase))
                {
                    string[] parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                    int parsed;
                    if (parts.Length >= 3 && int.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed))
                    {
                        faceCount = parsed;
                    }
                }
            }

            if (vertexCount <= 0)
            {
                reason = vertexCount == 0 ? "header has zero vertices" : "missing element vertex";
                return false;
            }

            long bodyLength = length - headerLength;
            if (bodyLength <= 0)
            {
                reason = "header-only file";
                return false;
            }

            if (binaryFormat)
            {
                long minExpectedBody = Math.Max(16L, vertexCount * 12L);
                if (faceCount > 0)
                {
                    minExpectedBody += faceCount * 4L;
                }

                if (bodyLength < minExpectedBody)
                {
                    reason = "no meaningful body after end_header";
                    return false;
                }
            }
            else
            {
                string bodyText = ascii.Length > headerLength
                    ? ascii.Substring(headerLength).Trim()
                    : string.Empty;

                if (string.IsNullOrWhiteSpace(bodyText) && bodyLength > 0)
                {
                    try
                    {
                        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                        {
                            stream.Position = headerLength;
                            byte[] bodyBuffer = new byte[(int)Math.Min(bodyLength, 512L)];
                            int bodyRead = stream.Read(bodyBuffer, 0, bodyBuffer.Length);
                            bodyText = bodyRead > 0
                                ? Encoding.ASCII.GetString(bodyBuffer, 0, bodyRead).Trim()
                                : string.Empty;
                        }
                    }
                    catch
                    {
                        bodyText = string.Empty;
                    }
                }

                if (string.IsNullOrWhiteSpace(bodyText))
                {
                    reason = "no meaningful body after end_header";
                    return false;
                }
            }

            if (length < MinGenericMeshBytes)
            {
                reason = "file too small";
                return false;
            }

            return true;
        }

        private string BuildUniqueTempFilePath(string directory, string fileString, string extension)
        {
            string safeDirectory = !string.IsNullOrWhiteSpace(directory) ? directory : Path.GetTempPath();
            Directory.CreateDirectory(safeDirectory);

            string baseName = string.IsNullOrWhiteSpace(fileString) ? "export" : fileString;
            string suffix = string.IsNullOrWhiteSpace(extension) ? ".tmp" : extension;
            if (!suffix.StartsWith(".", StringComparison.Ordinal))
            {
                suffix = "." + suffix;
            }

            return Path.Combine(safeDirectory, baseName + "_" + Guid.NewGuid().ToString("N") + ".tmp" + suffix);
        }

        private string QuarantineInvalidExistingFile(string path, string reason, Action<string> errorLog)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return string.Empty;
            }

            try
            {
                string badPath = path + ".bad";
                if (File.Exists(badPath))
                {
                    File.Delete(badPath);
                }

                File.Move(path, badPath);
                SafeLog(errorLog,
                    "OUTPUT quarantined invalid file: path=" + path +
                    " badPath=" + badPath +
                    " reason=" + (reason ?? string.Empty));
                return badPath;
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "OUTPUT quarantine failed: path=" + path + " (" + ex.Message + ")");
                return string.Empty;
            }
        }

        private bool PromoteTempFileToFinal(string tempPath, string finalPath, Action<string> errorLog)
        {
            if (string.IsNullOrWhiteSpace(tempPath) || string.IsNullOrWhiteSpace(finalPath) || !File.Exists(tempPath))
            {
                return false;
            }

            try
            {
                string dir = Path.GetDirectoryName(finalPath);
                if (!string.IsNullOrWhiteSpace(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                if (File.Exists(finalPath))
                {
                    try
                    {
                        string backupPath = finalPath + ".replacebak";
                        if (File.Exists(backupPath))
                        {
                            File.Delete(backupPath);
                        }

                        File.Replace(tempPath, finalPath, backupPath, true);
                        if (File.Exists(backupPath))
                        {
                            File.Delete(backupPath);
                        }
                    }
                    catch
                    {
                        File.Delete(finalPath);
                        File.Move(tempPath, finalPath);
                    }
                }
                else
                {
                    File.Move(tempPath, finalPath);
                }

                return true;
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "OUTPUT promote failed: temp=" + tempPath + " final=" + finalPath + " (" + ex.Message + ")");
                return false;
            }
        }

        private void TryDeleteFileQuietly(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return;
            }

            try
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch
            {
                // ignore cleanup errors
            }
        }

        private void ModelPublish(ModelDoc2 model, string confName, string fileString, string deliverablesFolder,
            bool png, bool step, bool edr, bool threeMf, bool ply, bool stl, Action<string> log, Action<string> errorLog)
        {
            using (new ExportDialogSuppressionScope(_swApp))
            {
                int docType = 0;
                try
                {
                    docType = model.GetType();
                }
                catch
                {
                    docType = 0;
                }

                string ActiveDocTitle()
                {
                    try
                    {
                        ModelDoc2 active = _swApp.ActiveDoc as ModelDoc2;
                        return active != null ? (active.GetTitle() ?? string.Empty) : "<null>";
                    }
                    catch
                    {
                        return "<error>";
                    }
                }

                long FileBytes(string path)
                {
                    if (string.IsNullOrWhiteSpace(path))
                    {
                        return 0;
                    }

                    try
                    {
                        return File.Exists(path) ? new FileInfo(path).Length : 0;
                    }
                    catch
                    {
                        return 0;
                    }
                }

                ModelView view = null;
                bool prevGraphicsUpdate = true;
                ExportActivationScope activation = null;
                bool modelVisibleForExport = false;

                ExportSummary summary = _currentExportSummary;

                // Model exports generally do not require activating the document. However, view-dependent PNG
                // export frequently requires the target model to be ACTIVE to avoid blank captures.
                // PLY export for assemblies is also more reliable when the current isolated item is active/visible.
                try
                {
                    if (png || ply)
                    {
                        string modelTitle = string.Empty;
                        try
                        {
                            modelTitle = model.GetTitle() ?? string.Empty;
                        }
                        catch
                        {
                            modelTitle = string.Empty;
                        }

                        if (!string.IsNullOrWhiteSpace(modelTitle))
                        {
                            activation = new ExportActivationScope(_swApp, _activeBatchRootTitle, modelTitle, docType, errorLog,
                                "MODEL PNG|" + (fileString ?? string.Empty));
                        }
                        try
                        {
                            // Ensure the model is visible while capturing; activation alone may not force a window refresh.
                            model.Visible = true;
                            modelVisibleForExport = true;
                        }
                        catch
                        {
                            // ignore
                        }

                        YieldAndCheckCancel();
                    }

                    TryShowConfiguration(model, confName);
                    YieldAndCheckCancel();

                    if (ply)
                    {
                        try
                        {
                            model.ForceRebuild3(false);
                        }
                        catch
                        {
                            // ignore rebuild errors
                        }

                        try
                        {
                            model.GraphicsRedraw2();
                        }
                        catch
                        {
                            // ignore redraw errors
                        }

                        try
                        {
                            System.Windows.Forms.Application.DoEvents();
                        }
                        catch
                        {
                            // ignore
                        }

                        try
                        {
                            System.Threading.Thread.Sleep(50);
                        }
                        catch
                        {
                            // ignore
                        }
                    }

                    if (png)
                    {
                        view = model.GetFirstModelView() as ModelView;
                        if (view != null)
                        {
                            prevGraphicsUpdate = view.EnableGraphicsUpdate;
                            view.EnableGraphicsUpdate = false;
                        }
                    }

                    int errors = 0;
                    int warnings = 0;

                    if (threeMf)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.ModelAttempt3mf++;
                        }

                        string path = Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf");
                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();
                        bool saveOk = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        long bytes = FileBytes(path);
                        bool ok = saveOk && bytes > 0;
                        t.Stop();
                        SafeLog(errorLog, "MODEL 3MF ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " saveOk=" + saveOk +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " path=" + path);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOk3mf++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.ModelFail3mf++;
                            }
                            LogExportFailure(log, errorLog, "3MF export failed: " + path);
                        }
                    }
                    YieldAndCheckCancel();

                    bool stlExported = false;
                    string stlPath = Path.Combine(deliverablesFolder, "stl", fileString + ".stl");
                    if (stl)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.ModelAttemptStl++;
                        }

                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();
                        bool saveOk = model.Extension.SaveAs(stlPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        long bytes = FileBytes(stlPath);
                        stlExported = saveOk && bytes > 0;
                        t.Stop();
                        SafeLog(errorLog, "MODEL STL ms=" + t.ElapsedMilliseconds +
                                          " ok=" + stlExported +
                                          " saveOk=" + saveOk +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " path=" + stlPath);
                        if (stlExported)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkStl++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.ModelFailStl++;
                            }
                            LogExportFailure(log, errorLog, "STL export failed: " + stlPath);
                        }
                    }
                    YieldAndCheckCancel();

                    if (ply)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.ModelAttemptPly++;
                        }

                        string plyPath = Path.Combine(deliverablesFolder, "ply", fileString + ".ply");
                        string tempPlyPath = BuildUniqueTempFilePath(Path.Combine(deliverablesFolder, "ply"), fileString, ".ply");
                        string tempFallbackPlyPath = BuildUniqueTempFilePath(Path.Combine(deliverablesFolder, "ply"), fileString, ".ply");
                        string tempStl = string.Empty;
                        string quarantinedExisting = string.Empty;
                        string activeBefore = ActiveDocTitle();
                        bool directSaveOk = false;
                        bool directValid = false;
                        bool fallbackAttempted = false;
                        bool fallbackValid = false;
                        bool finalValid = false;
                        long directBytes = 0;
                        string directInvalidReason = string.Empty;
                        string fallbackInvalidReason = string.Empty;
                        string fallbackStlPath = string.Empty;

                        try
                        {
                            if (File.Exists(plyPath))
                            {
                                string existingReason;
                                if (!IsValidPlyFile(plyPath, errorLog, out existingReason))
                                {
                                    quarantinedExisting = QuarantineInvalidExistingFile(plyPath, existingReason, errorLog);
                                }
                            }

                            errors = 0;
                            warnings = 0;
                            directSaveOk = model.Extension.SaveAs(tempPlyPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                            directBytes = WaitForFileStable(tempPlyPath, 8000, errorLog);
                            directValid = directSaveOk && IsValidPlyFile(tempPlyPath, errorLog, out directInvalidReason);
                            if (!directValid && string.IsNullOrWhiteSpace(directInvalidReason))
                            {
                                directInvalidReason = directSaveOk ? "invalid PLY output" : "SaveAs returned false";
                            }

                            if (!directValid)
                            {
                                SafeLog(errorLog,
                                    "PLY direct invalid: " + (directInvalidReason ?? string.Empty) +
                                    " path=" + tempPlyPath +
                                    " bytes=" + directBytes);
                                TryDeleteFileQuietly(tempPlyPath);

                                YieldAndCheckCancel();
                                fallbackAttempted = true;
                                fallbackStlPath = stlExported ? stlPath : string.Empty;

                                if (string.IsNullOrWhiteSpace(fallbackStlPath))
                                {
                                    tempStl = BuildUniqueTempFilePath(Path.GetTempPath(), fileString, ".stl");
                                    errors = 0;
                                    warnings = 0;
                                    bool tempStlOk = model.Extension.SaveAs(tempStl, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                                    long tempStlBytes = WaitForFileStable(tempStl, 8000, errorLog);
                                    string stlReason = string.Empty;
                                    if (tempStlOk && ValidateExportedOutput("stl", tempStl, errorLog, out stlReason))
                                    {
                                        fallbackStlPath = tempStl;
                                    }
                                    else
                                    {
                                        fallbackInvalidReason = "temporary STL invalid: " + (stlReason ?? string.Empty) +
                                            " bytes=" + tempStlBytes;
                                    }
                                }

                                if (!string.IsNullOrWhiteSpace(fallbackStlPath) && File.Exists(fallbackStlPath))
                                {
                                    if (TryConvertStlToPly(fallbackStlPath, tempFallbackPlyPath))
                                    {
                                        WaitForFileStable(tempFallbackPlyPath, 8000, errorLog);
                                        fallbackValid = IsValidPlyFile(tempFallbackPlyPath, errorLog, out fallbackInvalidReason);
                                        if (fallbackValid)
                                        {
                                            SafeLog(errorLog, "PLY fallback via STL ok path=" + tempFallbackPlyPath);
                                        }
                                        else
                                        {
                                            SafeLog(errorLog, "PLY fallback invalid: " + (fallbackInvalidReason ?? string.Empty));
                                            TryDeleteFileQuietly(tempFallbackPlyPath);
                                        }
                                    }
                                    else
                                    {
                                        fallbackInvalidReason = "STL conversion failed";
                                    }
                                }
                                else if (string.IsNullOrWhiteSpace(fallbackInvalidReason))
                                {
                                    fallbackInvalidReason = "STL source unavailable";
                                }
                            }

                            if (directValid)
                            {
                                PromoteTempFileToFinal(tempPlyPath, plyPath, errorLog);
                            }
                            else if (fallbackValid)
                            {
                                PromoteTempFileToFinal(tempFallbackPlyPath, plyPath, errorLog);
                            }

                            string finalInvalidReason;
                            finalValid = IsValidPlyFile(plyPath, errorLog, out finalInvalidReason);
                            if (!finalValid && string.IsNullOrWhiteSpace(fallbackInvalidReason))
                            {
                                fallbackInvalidReason = string.IsNullOrWhiteSpace(finalInvalidReason)
                                    ? "final PLY validation failed"
                                    : finalInvalidReason;
                            }
                        }
                        finally
                        {
                            if (!string.IsNullOrWhiteSpace(tempStl) &&
                                string.Equals(tempStl, fallbackStlPath, StringComparison.OrdinalIgnoreCase))
                            {
                                fallbackStlPath = tempStl;
                            }

                            if (!string.Equals(tempPlyPath, plyPath, StringComparison.OrdinalIgnoreCase))
                            {
                                TryDeleteFileQuietly(tempPlyPath);
                            }

                            if (!string.Equals(tempFallbackPlyPath, plyPath, StringComparison.OrdinalIgnoreCase))
                            {
                                TryDeleteFileQuietly(tempFallbackPlyPath);
                            }

                            if (!string.IsNullOrWhiteSpace(tempStl) &&
                                !string.Equals(tempStl, stlPath, StringComparison.OrdinalIgnoreCase))
                            {
                                TryDeleteFileQuietly(tempStl);
                            }
                        }

                        long bytes = FileBytes(plyPath);
                        t.Stop();
                        SafeLog(errorLog,
                            "MODEL PLY ms=" + t.ElapsedMilliseconds +
                            " ok=" + finalValid +
                            " directSaveOk=" + directSaveOk +
                            " directValid=" + directValid +
                            " directInvalidReason=" + (directInvalidReason ?? string.Empty) +
                            " directBytes=" + directBytes +
                            " fallbackAttempted=" + fallbackAttempted +
                            " fallbackStlPath=" + (fallbackStlPath ?? string.Empty) +
                            " fallbackValid=" + fallbackValid +
                            " fallbackInvalidReason=" + (fallbackInvalidReason ?? string.Empty) +
                            " finalValid=" + finalValid +
                            " finalBytes=" + bytes +
                            " activated=" + (activation != null && activation.Activated) +
                            " visibleDuringExport=" + modelVisibleForExport +
                            " activeBefore=" + activeBefore +
                            " activeAfter=" + ActiveDocTitle() +
                            " errors=" + errors +
                            " warnings=" + warnings +
                            " quarantinedExisting=" + (quarantinedExisting ?? string.Empty) +
                            " path=" + plyPath);
                        if (summary != null)
                        {
                            if (finalValid)
                            {
                                summary.ModelOkPly++;
                            }
                            else
                            {
                                summary.ModelFailPly++;
                            }
                        }

                        if (!finalValid)
                        {
                            LogExportFailure(log, errorLog,
                                "PLY export failed: direct invalid and STL fallback failed. final=" + plyPath +
                                " directReason=" + (directInvalidReason ?? string.Empty) +
                                " fallbackReason=" + (fallbackInvalidReason ?? string.Empty));
                        }
                    }
                    YieldAndCheckCancel();

                    if (step)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.ModelAttemptStep++;
                        }

                        string path = Path.Combine(deliverablesFolder, "step", fileString + ".step");
                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();
                        bool saveOk = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        long bytes = FileBytes(path);
                        bool ok = saveOk && bytes > 0;
                        t.Stop();
                        SafeLog(errorLog, "MODEL STEP ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " saveOk=" + saveOk +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " path=" + path);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkStep++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.ModelFailStep++;
                            }
                            LogExportFailure(log, errorLog, "STEP export failed: " + path);
                        }
                    }
                    YieldAndCheckCancel();

                    if (edr)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.ModelAttemptEdraw++;
                        }

                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                            (int)swEdrawingSaveAsOption_e.swEdrawingSaveActive);

                        string ext = docType == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt";
                        string path = Path.Combine(deliverablesFolder, "edr", fileString + ext);
                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();
                        bool saveOk = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        long bytes = FileBytes(path);
                        bool ok = saveOk && bytes >= MinEdrawingBytes;
                        t.Stop();
                        SafeLog(errorLog, "MODEL EDR ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " saveOk=" + saveOk +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " path=" + path);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkEdraw++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.ModelFailEdraw++;
                            }
                            LogExportFailure(log, errorLog, "eDrawing export failed: " + path);
                        }
                    }
                    YieldAndCheckCancel();

                    if (png)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.ModelAttemptPng++;
                        }

                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();

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

                        string path = Path.Combine(deliverablesFolder, "png", fileString + ".png");

                        bool saveOk = false;
                        string exceptionText = string.Empty;
                        try
                        {
                            // Macro parity: rebuild + iso view + zoom fit + redraw before capture.
                            model.ForceRebuild3(true);
                            model.ShowNamedView2("Isometric", 7);
                            model.ViewZoomtofit2();

                            if (view != null)
                            {
                                view.EnableGraphicsUpdate = true;
                            }

                            model.GraphicsRedraw2();
                            try
                            {
                                System.Windows.Forms.Application.DoEvents();
                            }
                            catch
                            {
                                // ignore
                            }
                            try
                            {
                                System.Threading.Thread.Sleep(50);
                            }
                            catch
                            {
                                // ignore
                            }

                            saveOk = model.Extension.SaveAs(path, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        }
                        catch (Exception ex)
                        {
                            exceptionText = ex.Message ?? string.Empty;
                        }

                        long bytes = FileBytes(path);
                        bool blankSuspect = bytes > 0 && bytes < MinPngBytes;
                        bool ok = saveOk && bytes >= MinPngBytes;
                        t.Stop();

                        SafeLog(errorLog, "MODEL PNG ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " saveOk=" + saveOk +
                                          " blankSuspect=" + blankSuspect +
                                          " activated=" + (activation != null && activation.Activated) +
                                          " actErr=" + (activation != null ? activation.ActivateErrors : 0) +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          (string.IsNullOrWhiteSpace(exceptionText) ? "" : (" ex=" + exceptionText)) +
                                          " path=" + path);

                        if (!ok && blankSuspect)
                        {
                            LogExportFailure(log, errorLog, "PNG export suspect blank (size " + bytes + "): " + path);
                        }
                        else if (!ok)
                        {
                            LogExportFailure(log, errorLog, "PNG export failed: " + path);
                        }

                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkPng++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.ModelFailPng++;
                            }
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

                    if (activation != null)
                    {
                        try
                        {
                            activation.Dispose();
                        }
                        catch
                        {
                            // ignore activation-scope errors
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

        private static string NormalizeSheetNameForMatch(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
            {
                return string.Empty;
            }

            string trimmed = name.Trim();
            var sb = new StringBuilder(trimmed.Length);
            for (int i = 0; i < trimmed.Length; i++)
            {
                char c = trimmed[i];
                if (char.IsLetterOrDigit(c))
                {
                    sb.Append(char.ToLowerInvariant(c));
                }
            }
            return sb.ToString();
        }

        private HashSet<string> BuildDxfSheetNameTokens()
        {
            string raw = string.Empty;
            try
            {
                raw = _config != null ? (_config.DxfSheetNames ?? string.Empty) : string.Empty;
            }
            catch
            {
                raw = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(raw))
            {
                raw = "flatpattern;flat_pattern;dxf;dxf sheet";
            }

            string[] parts = raw.Split(new[] { ';', ',', '|', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            var tokens = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            for (int i = 0; i < parts.Length; i++)
            {
                string token = NormalizeSheetNameForMatch(parts[i]);
                if (!string.IsNullOrWhiteSpace(token))
                {
                    tokens.Add(token);
                }
            }

            return tokens;
        }

        private bool IsDxfSheetName(string sheetName, HashSet<string> normalizedTokens)
        {
            if (string.IsNullOrWhiteSpace(sheetName) || normalizedTokens == null || normalizedTokens.Count == 0)
            {
                return false;
            }

            string norm = NormalizeSheetNameForMatch(sheetName);
            if (string.IsNullOrWhiteSpace(norm))
            {
                return false;
            }

            // "Forgiving" match: treat configured tokens as patterns, so "dxf" matches "DXF Sheet", "DXF_SHEET_1", etc.
            foreach (string token in normalizedTokens)
            {
                if (string.IsNullOrWhiteSpace(token))
                {
                    continue;
                }

                if (norm.Contains(token))
                {
                    return true;
                }
            }

            return false;
        }

        private void DwgPublishFast(ModelDoc2 model, string fileString, string deliverablesFolder,
            bool overwriteFiles, bool pdf, bool dxf, bool png, bool edr, Action<string> log, Action<string> errorLog, string partNumberOverride,
            OpenTracker openedDocs, HashSet<string> baselineVisibleIds, string rootDocId)
        {
            using (new ExportDialogSuppressionScope(_swApp))
            {
                if (model == null)
                {
                    return;
                }

                Configuration conf = null;
                try
                {
                    conf = model.GetActiveConfiguration() as Configuration;
                }
                catch
                {
                    conf = null;
                }
                if (conf == null)
                {
                    return;
                }

                string modelPath = string.Empty;
                try
                {
                    modelPath = model.GetPathName();
                }
                catch
                {
                    modelPath = string.Empty;
                }
                if (string.IsNullOrWhiteSpace(modelPath))
                {
                    return;
                }

                string pn = !string.IsNullOrWhiteSpace(partNumberOverride)
                    ? partNumberOverride
                    : BomPartNumber(conf, model, errorLog);
                string drawingPath = OnlyFolder(modelPath) + pn + ".SLDDRW";
                if (!File.Exists(drawingPath))
                {
                    return;
                }

                string pdfPath = Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf");
                string dxfPath = Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf");
                string pngPath = Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png");
                string edrPath = Path.Combine(deliverablesFolder, "edr", fileString + ".edrw");
                bool dxfSelected = dxf;
                bool dxfRequested = dxfSelected && ShouldExport(dxfPath, overwriteFiles);

                bool drawingWasOpenBefore = false;
                bool drawingWasVisibleBefore = false;
                try
                {
                    drawingWasOpenBefore = IsDocOpenByIdOrTitle(drawingPath, null);
                    if (drawingWasOpenBefore)
                    {
                        ModelDoc2 existing = FindOpenDocument(drawingPath, null);
                        if (existing != null)
                        {
                            try
                            {
                                drawingWasVisibleBefore = existing.Visible;
                            }
                            catch
                            {
                                drawingWasVisibleBefore = true;
                            }
                        }
                    }
                }
                catch
                {
                    drawingWasOpenBefore = false;
                    drawingWasVisibleBefore = false;
                }

                string ActiveDocTitle()
                {
                    try
                    {
                        ModelDoc2 active = _swApp.ActiveDoc as ModelDoc2;
                        return active != null ? (active.GetTitle() ?? string.Empty) : "<null>";
                    }
                    catch
                    {
                        return "<error>";
                    }
                }

                long FileBytes(string path)
                {
                    if (string.IsNullOrWhiteSpace(path))
                    {
                        return 0;
                    }

                    try
                    {
                        return File.Exists(path) ? new FileInfo(path).Length : 0;
                    }
                    catch
                    {
                        return 0;
                    }
                }

                int visibleDocsBeforeOpen = GetOpenVisibleDocumentIds().Count;
                SafeLog(errorLog,
                    "DRAWING open: " + drawingPath +
                    " | wasOpen=" + drawingWasOpenBefore +
                    " | wasVisible=" + drawingWasVisibleBefore +
                    " | visibleDocsBefore=" + visibleDocsBeforeOpen);

                DocumentSpecification spec = null;
                ModelDoc2 drawDoc = null;
                DrawingDoc drawing = null;
                bool openedHere = false;
                string drawTitle = string.Empty;
                try
                {
                    spec = _swApp.GetOpenDocSpec(drawingPath) as DocumentSpecification;
                    if (spec == null)
                    {
                        SafeLog(errorLog, "DwgPublishFast: open spec failed: " + drawingPath);
                        return;
                    }
                    spec.DocumentType = (int)swDocumentTypes_e.swDocDRAWING;
                    spec.ReadOnly = true;
                    spec.Silent = true;

                    using (new ExternalReferenceBatchOpenScope(_swApp))
                    {
                        YieldAndCheckCancel();
                        drawDoc = _swApp.OpenDoc7(spec) as ModelDoc2;
                    }
                    if (drawDoc == null)
                    {
                        SafeLog(errorLog, "DwgPublishFast: open failed: " + drawingPath);
                        return;
                    }

                    openedHere = !drawingWasOpenBefore;

                    try
                    {
                        drawTitle = drawDoc.GetTitle() ?? string.Empty;
                    }
                    catch
                    {
                        drawTitle = string.Empty;
                    }

                    if (openedDocs != null && openedHere)
                    {
                        openedDocs.Track(drawDoc, "drawing|" + drawingPath);
                    }

                    bool visibleAfterOpen = true;
                    try
                    {
                        visibleAfterOpen = drawDoc.Visible;
                    }
                    catch
                    {
                        visibleAfterOpen = true;
                    }

                    // Activate for view-dependent exports (PDF/PNG/eDrawings)
                    try
                    {
                        string activateTitle = NormalizeDocTitleForClose(drawTitle);
                        if (string.IsNullOrWhiteSpace(activateTitle))
                        {
                            activateTitle = drawTitle;
                        }

                        int actErrors = 0;
                        if (!string.IsNullOrWhiteSpace(activateTitle))
                        {
                            _swApp.ActivateDoc3(activateTitle, true,
                                (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref actErrors);
                        }

                        SafeLog(errorLog,
                            "DRAWING activate: title=" + (activateTitle ?? string.Empty) +
                            " errors=" + actErrors +
                            " activeNow=" + ActiveDocTitle());
                    }
                    catch
                    {
                        // ignore activation errors
                    }

                    SafeLog(errorLog,
                        "DRAWING opened: title=" + (drawTitle ?? string.Empty) +
                        " | openedHere=" + openedHere +
                        " | visibleAfterOpen=" + visibleAfterOpen +
                        " | visibleDocsNow=" + GetOpenVisibleDocumentIds().Count);

                    drawing = drawDoc as DrawingDoc;
                    if (drawing == null)
                    {
                        return;
                    }

                    object sheetNamesObj = null;
                    try
                    {
                        sheetNamesObj = drawing.GetSheetNames();
                    }
                    catch
                    {
                        sheetNamesObj = null;
                    }

                    string[] sheetNames = ToStringArray(sheetNamesObj);
                    if (sheetNames == null || sheetNames.Length == 0)
                    {
                        return;
                    }

                    HashSet<string> dxfSheetTokens = null;
                    if (pdf || dxfSelected)
                    {
                        dxfSheetTokens = BuildDxfSheetNameTokens();
                    }

                    string dxfSheetName = string.Empty;
                    if (dxfRequested && dxfSheetTokens != null && dxfSheetTokens.Count > 0)
                    {
                        for (int i = 0; i < sheetNames.Length; i++)
                        {
                            ThrowIfCancelled();
                            if (IsDxfSheetName(sheetNames[i], dxfSheetTokens))
                            {
                                dxfSheetName = sheetNames[i];
                                break;
                            }
                        }
                    }

                    int errors = 0;
                    int warnings = 0;
                    ExportSummary summary = _currentExportSummary;

                    try
                    {
                        drawDoc.ForceRebuild3(true);
                    }
                    catch
                    {
                        // ignore rebuild errors
                    }

                    if (pdf)
                    {
                        YieldAndCheckCancel();
                        ExportPdfData exportData = _swApp.GetExportFileData(
                            (int)swExportDataFileType_e.swExportPdfData) as ExportPdfData;
                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();

                        bool saveOk = false;
                        if (exportData != null)
                        {
                            try
                            {
                                exportData.ViewPdfAfterSaving = false;
                            }
                            catch
                            {
                                // ignore
                            }

                            // Determine which sheets to export to PDF (exclude DXF/flatpattern sheets).
                            var excludedSheets = new List<string>();
                            var includedSheets = new List<string>();
                            if (dxfSheetTokens != null && dxfSheetTokens.Count > 0)
                            {
                                for (int i = 0; i < sheetNames.Length; i++)
                                {
                                    string name = sheetNames[i];
                                    if (IsDxfSheetName(name, dxfSheetTokens))
                                    {
                                        excludedSheets.Add(name);
                                    }
                                    else
                                    {
                                        includedSheets.Add(name);
                                    }
                                }
                            }
                            else
                            {
                                includedSheets.AddRange(sheetNames);
                            }

                            List<string> tokensSorted = null;
                            try
                            {
                                if (dxfSheetTokens != null)
                                {
                                    tokensSorted = new List<string>();
                                    foreach (string t in dxfSheetTokens)
                                    {
                                        if (!string.IsNullOrWhiteSpace(t))
                                        {
                                            tokensSorted.Add(t);
                                        }
                                    }
                                    tokensSorted.Sort(StringComparer.OrdinalIgnoreCase);
                                }
                            }
                            catch
                            {
                                tokensSorted = null;
                            }

                            string FormatList(IList<string> values)
                            {
                                if (values == null)
                                {
                                    return "<null>";
                                }

                                int max = 50;
                                var sb = new StringBuilder();
                                sb.Append("[");
                                for (int i = 0; i < values.Count; i++)
                                {
                                    if (i > 0) sb.Append(", ");
                                    if (i >= max)
                                    {
                                        sb.Append("... +").Append(values.Count - i);
                                        break;
                                    }
                                    sb.Append(values[i] ?? string.Empty);
                                }
                                sb.Append("]");
                                return sb.ToString();
                            }

                            bool hasExclusions = excludedSheets.Count > 0;
                            if (hasExclusions)
                            {
                                SafeLog(errorLog,
                                    "DWG PDF sheets: dxfSheetNamesRaw=" + (_config != null ? (_config.DxfSheetNames ?? string.Empty) : string.Empty) +
                                    " tokens=" + FormatList(tokensSorted) +
                                    " all=" + FormatList(new List<string>(sheetNames)) +
                                    " excluded=" + FormatList(excludedSheets) +
                                    " included=" + FormatList(includedSheets));
                            }

                            if (hasExclusions && includedSheets.Count == 0)
                            {
                                // Excluding the DXF/flatpattern sheets would result in an empty PDF.
                                SafeLog(errorLog,
                                    "DWG PDF skipped: all sheets match DXF patterns; no non-DXF sheets available. path=" + pdfPath);
                            }
                            else
                            {
                                var t = System.Diagnostics.Stopwatch.StartNew();
                                if (summary != null)
                                {
                                    summary.DwgAttemptPdf++;
                                }

                                string[] pdfSheetNames = (hasExclusions && includedSheets.Count > 0 && includedSheets.Count < sheetNames.Length)
                                    ? includedSheets.ToArray()
                                    : sheetNames;

                                bool setOk = false;
                                string setArgType = "<none>";
                                try
                                {
                                    // Prefer strongly typed string[] (marshals to SAFEARRAY of BSTR).
                                    setOk = exportData.SetSheets(
                                        (int)swExportDataSheetsToExport_e.swExportData_ExportSpecifiedSheets,
                                        pdfSheetNames);
                                    setArgType = pdfSheetNames != null ? pdfSheetNames.GetType().FullName : "<null>";
                                }
                                catch (Exception ex)
                                {
                                    setOk = false;
                                    SafeLog(errorLog, "DWG PDF SetSheets exception (string[]): " + ex.Message);
                                }

                                if (!setOk)
                                {
                                    try
                                    {
                                        // Fallback: VT_VARIANT[] (some SW versions are pickier).
                                        var pdfVariant = new object[pdfSheetNames != null ? pdfSheetNames.Length : 0];
                                        for (int i = 0; i < pdfVariant.Length; i++)
                                        {
                                            pdfVariant[i] = pdfSheetNames[i];
                                        }

                                        setOk = exportData.SetSheets(
                                            (int)swExportDataSheetsToExport_e.swExportData_ExportSpecifiedSheets,
                                            pdfVariant);
                                        setArgType = pdfVariant.GetType().FullName;
                                    }
                                    catch (Exception ex)
                                    {
                                        setOk = false;
                                        SafeLog(errorLog, "DWG PDF SetSheets exception (variant[]): " + ex.Message);
                                    }
                                }

                                SafeLog(errorLog,
                                    "DWG PDF SetSheets ok=" + setOk +
                                    " argType=" + (setArgType ?? string.Empty) +
                                    " count=" + (pdfSheetNames != null ? pdfSheetNames.Length : 0) +
                                    " export=" + FormatList(new List<string>(pdfSheetNames ?? new string[0])));

                                bool skippedPdf = false;
                                if (!setOk && hasExclusions)
                                {
                                    skippedPdf = true;
                                    SafeLog(errorLog,
                                        "DWG PDF skipped: failed to apply sheet filter; refusing to export PDF that would include DXF sheets. path=" + pdfPath);
                                }
                                else
                                {
                                    saveOk = drawDoc.Extension.SaveAs(pdfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, exportData, ref errors, ref warnings);
                                }

                                long bytes = 0;
                                bool blankSuspect = false;
                                bool ok = false;
                                if (!skippedPdf)
                                {
                                    bytes = FileBytes(pdfPath);
                                    blankSuspect = bytes > 0 && bytes < MinPdfBytes;
                                    ok = saveOk && bytes >= MinPdfBytes;
                                }

                                t.Stop();
                                if (!skippedPdf)
                                {
                                    SafeLog(errorLog, "DWG PDF ms=" + t.ElapsedMilliseconds +
                                                      " ok=" + ok +
                                                      " saveOk=" + saveOk +
                                                      " blankSuspect=" + blankSuspect +
                                                      " activeBefore=" + activeBefore +
                                                      " activeAfter=" + ActiveDocTitle() +
                                                      " errors=" + errors +
                                                      " warnings=" + warnings +
                                                      " bytes=" + bytes +
                                                      " path=" + pdfPath);

                                    if (ok)
                                    {
                                        if (summary != null)
                                        {
                                            summary.DwgOkPdf++;
                                        }
                                    }
                                    else
                                    {
                                        if (summary != null)
                                        {
                                            summary.DwgFailPdf++;
                                        }
                                        LogExportFailure(log, errorLog, exportData != null
                                            ? (blankSuspect
                                                ? ("PDF export suspect blank (size " + bytes + "): " + pdfPath)
                                                : ("PDF export failed: " + pdfPath))
                                            : "PDF export failed: export data unavailable.");
                                    }
                                }
                                else
                                {
                                    SafeLog(errorLog,
                                        "DWG PDF skipped: elapsedMs=" + t.ElapsedMilliseconds + " path=" + pdfPath);
                                }
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.DwgFailPdf++;
                            }
                            LogExportFailure(log, errorLog, "PDF export failed: export data unavailable.");
                        }
                    }

                    if (edr)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.DwgAttemptEdraw++;
                        }

                        YieldAndCheckCancel();
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                            (int)swEdrawingSaveAsOption_e.swEdrawingSaveAll);
                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();
                        bool saveOk = drawDoc.Extension.SaveAs(edrPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        long bytes = FileBytes(edrPath);
                        bool ok = saveOk && bytes >= MinEdrawingBytes;
                        t.Stop();
                        SafeLog(errorLog, "DWG EDRW ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " saveOk=" + saveOk +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " path=" + edrPath);

                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.DwgOkEdraw++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.DwgFailEdraw++;
                            }
                            LogExportFailure(log, errorLog, "eDrawing export failed: " + edrPath);
                        }
                    }

                    if (png)
                    {
                        var t = System.Diagnostics.Stopwatch.StartNew();
                        if (summary != null)
                        {
                            summary.DwgAttemptPng++;
                        }

                        YieldAndCheckCancel();
                        errors = 0;
                        warnings = 0;
                        string activeBefore = ActiveDocTitle();
                        try
                        {
                            drawing.ActivateSheet(sheetNames[0]);
                            drawing.ViewFullPage();
                        }
                        catch
                        {
                            // ignore view activation errors
                        }

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

                        bool saveOk = drawDoc.Extension.SaveAs(pngPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        long bytes = FileBytes(pngPath);
                        bool blankSuspect = bytes > 0 && bytes < MinPngBytes;
                        bool ok = saveOk && bytes >= MinPngBytes;
                        t.Stop();
                        SafeLog(errorLog, "DWG PNG ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " saveOk=" + saveOk +
                                          " blankSuspect=" + blankSuspect +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " path=" + pngPath);

                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.DwgOkPng++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.DwgFailPng++;
                            }
                            LogExportFailure(log, errorLog, blankSuspect
                                ? ("Drawing PNG export suspect blank (size " + bytes + "): " + pngPath)
                                : ("Drawing PNG export failed: " + pngPath));
                        }
                    }

                    if (dxfRequested)
                    {
                        // DXF is only required when the drawing has a designated DXF/flatpattern sheet.
                        // Do not treat "no drawing DXF page" as an export error.
                        if (string.IsNullOrWhiteSpace(dxfSheetName))
                        {
                            SafeLog(errorLog, "DWG DXF skipped: no designated DXF sheet found (configure Advanced > Drawing export > DXF sheet names; current: " +
                                              (_config != null ? (_config.DxfSheetNames ?? string.Empty) : string.Empty) + ").");
                        }
                        else
                        {
                            try
                            {
                                _swApp.SetUserPreferenceIntegerValue(
                                    (int)swUserPreferenceIntegerValue_e.swDxfMultiSheetOption,
                                    (int)swDxfMultisheet_e.swDxfActiveSheetOnly);
                                _swApp.SetUserPreferenceIntegerValue(
                                    (int)swUserPreferenceIntegerValue_e.swDxfOutputNoScale, 1);
                            }
                            catch
                            {
                                // ignore preference errors
                            }

                            var t = System.Diagnostics.Stopwatch.StartNew();
                            if (summary != null)
                            {
                                summary.DwgAttemptDxf++;
                            }

                            YieldAndCheckCancel();
                            bool exported = false;

                            try
                            {
                                errors = 0;
                                warnings = 0;
                                string activeBefore = ActiveDocTitle();
                                drawing.ActivateSheet(dxfSheetName);
                                bool saveOk = drawDoc.SaveAs4(dxfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref errors, ref warnings);
                                long bytes = FileBytes(dxfPath);
                                exported = saveOk && bytes > 0;
                                SafeLog(errorLog, "DWG DXF direct ok=" + exported +
                                                  " saveOk=" + saveOk +
                                                  " activeBefore=" + activeBefore +
                                                  " activeAfter=" + ActiveDocTitle() +
                                                  " errors=" + errors +
                                                  " warnings=" + warnings +
                                                  " bytes=" + bytes +
                                                  " path=" + dxfPath);
                            }
                            catch
                            {
                                exported = false;
                            }

                            // Fallback: if direct export fails, try exporting the FLATPATTERN view.
                            if (!exported)
                            {
                                View flatView = drawing.GetFirstView() as View;
                                View flatPatternView = null;
                                while (flatView != null)
                                {
                                    ThrowIfCancelled();
                                    string viewName = string.Empty;
                                    try
                                    {
                                        viewName = flatView.GetName2() ?? string.Empty;
                                    }
                                    catch
                                    {
                                        viewName = string.Empty;
                                    }

                                    if (NormalizeSheetNameForMatch(viewName) == "flatpattern")
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

                            t.Stop();
                            SafeLog(errorLog, "DWG DXF ms=" + t.ElapsedMilliseconds + " ok=" + exported + " path=" + dxfPath);

                            if (!exported)
                            {
                                if (summary != null)
                                {
                                    summary.DwgFailDxf++;
                                }
                                LogExportFailure(log, errorLog, "DXF export failed: " + dxfPath);
                            }
                            else
                            {
                                if (summary != null)
                                {
                                    summary.DwgOkDxf++;
                                }
                            }
                        }
                    }
                }
                finally
                {
                    try
                    {
                        if (drawDoc != null)
                        {
                            bool visibleBeforeClose = true;
                            try
                            {
                                visibleBeforeClose = drawDoc.Visible;
                            }
                            catch
                            {
                                visibleBeforeClose = true;
                            }

                            // If we opened this drawing for export, force-close it (VBA macro parity).
                            if (openedHere)
                            {
                                try
                                {
                                    drawDoc.Visible = false;
                                }
                                catch
                                {
                                    // ignore hide errors
                                }

                                string closeTitle = NormalizeDocTitleForClose(drawTitle);
                                if (string.IsNullOrWhiteSpace(closeTitle))
                                {
                                    closeTitle = drawTitle;
                                }
                                if (string.IsNullOrWhiteSpace(closeTitle))
                                {
                                    try
                                    {
                                        closeTitle = drawDoc.GetTitle() ?? string.Empty;
                                    }
                                    catch
                                    {
                                        closeTitle = string.Empty;
                                    }
                                }

                                SafeLog(errorLog,
                                    "DRAWING close: title=" + (closeTitle ?? string.Empty) +
                                    " | path=" + drawingPath +
                                    " | wasOpenBefore=" + drawingWasOpenBefore +
                                    " | wasVisibleBefore=" + drawingWasVisibleBefore +
                                    " | visibleBeforeClose=" + visibleBeforeClose +
                                    " | visibleDocsBeforeClose=" + GetOpenVisibleDocumentIds().Count);

                                try
                                {
                                    if (!string.IsNullOrWhiteSpace(closeTitle))
                                    {
                                        _swApp.CloseDoc(closeTitle);
                                    }
                                }
                                catch
                                {
                                    // ignore close errors
                                }

                                bool stillVisible = false;
                                try
                                {
                                    if (!string.IsNullOrWhiteSpace(drawingPath))
                                    {
                                        stillVisible = GetOpenVisibleDocumentIds().Contains(drawingPath);
                                    }

                                    if (!stillVisible)
                                    {
                                        string closeTitleNorm = NormalizeTitle(closeTitle);
                                        if (string.IsNullOrWhiteSpace(closeTitleNorm))
                                        {
                                            closeTitleNorm = NormalizeTitle(drawTitle);
                                        }

                                        if (!string.IsNullOrWhiteSpace(closeTitleNorm))
                                        {
                                            foreach (ModelDoc2 d in GetVisibleDocuments())
                                            {
                                                if (d == null)
                                                {
                                                    continue;
                                                }

                                                string t = string.Empty;
                                                try
                                                {
                                                    t = d.GetTitle() ?? string.Empty;
                                                }
                                                catch
                                                {
                                                    t = string.Empty;
                                                }

                                                if (!string.IsNullOrWhiteSpace(t) &&
                                                    string.Equals(NormalizeTitle(t), closeTitleNorm, StringComparison.OrdinalIgnoreCase))
                                                {
                                                    stillVisible = true;
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                }
                                catch
                                {
                                    stillVisible = false;
                                }

                                if (stillVisible)
                                {
                                    SafeLog(errorLog,
                                        "WARNING: " + (closeTitle ?? string.Empty) +
                                        " still visible after CloseDoc, escalating to QuitDoc");
                                    try
                                    {
                                        if (!string.IsNullOrWhiteSpace(closeTitle))
                                        {
                                            _swApp.QuitDoc(closeTitle);
                                        }
                                    }
                                    catch
                                    {
                                        // ignore quit errors
                                    }
                                }

                                bool stillVisibleAfter = false;
                                try
                                {
                                    if (!string.IsNullOrWhiteSpace(drawingPath))
                                    {
                                        stillVisibleAfter = GetOpenVisibleDocumentIds().Contains(drawingPath);
                                    }

                                    if (!stillVisibleAfter)
                                    {
                                        string closeTitleNorm = NormalizeTitle(closeTitle);
                                        if (string.IsNullOrWhiteSpace(closeTitleNorm))
                                        {
                                            closeTitleNorm = NormalizeTitle(drawTitle);
                                        }

                                        if (!string.IsNullOrWhiteSpace(closeTitleNorm))
                                        {
                                            foreach (ModelDoc2 d in GetVisibleDocuments())
                                            {
                                                if (d == null)
                                                {
                                                    continue;
                                                }

                                                string t = string.Empty;
                                                try
                                                {
                                                    t = d.GetTitle() ?? string.Empty;
                                                }
                                                catch
                                                {
                                                    t = string.Empty;
                                                }

                                                if (!string.IsNullOrWhiteSpace(t) &&
                                                    string.Equals(NormalizeTitle(t), closeTitleNorm, StringComparison.OrdinalIgnoreCase))
                                                {
                                                    stillVisibleAfter = true;
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                }
                                catch
                                {
                                    stillVisibleAfter = false;
                                }

                                SafeLog(errorLog,
                                    "DRAWING closed: title=" + (closeTitle ?? string.Empty) +
                                    " | stillVisible=" + stillVisibleAfter +
                                    " | visibleDocsNow=" + GetOpenVisibleDocumentIds().Count);
                            }
                            else
                            {
                                // Drawing was already open: restore only if it wasn't visible before.
                                if (!drawingWasVisibleBefore)
                                {
                                    try
                                    {
                                        drawDoc.Visible = false;
                                    }
                                    catch
                                    {
                                        // ignore hide errors
                                    }
                                }
                            }
                        }
                    }
                    finally
                    {
                        if (openedDocs != null && drawDoc != null)
                        {
                            openedDocs.Untrack(drawDoc);
                        }

                        // Ensure any drawing open/close does not accumulate visible tabs.
                        try
                        {
                            EnforceVisibleDocBudget(baselineVisibleIds, rootDocId,
                                "after drawing " + (fileString ?? string.Empty), errorLog, 0);
                        }
                        catch
                        {
                            // ignore watchdog errors
                        }

                        ComInteropUtil.TryFinalReleaseComObject(drawing);
                        ComInteropUtil.TryFinalReleaseComObject(drawDoc);
                        ComInteropUtil.TryFinalReleaseComObject(spec);
                    }
                }

                SafeLog(errorLog, "DRAWING end: " + drawingPath + " | visibleDocsNow=" + GetOpenVisibleDocumentIds().Count);
            }
        }

        private void DwgPublish(ModelDoc2 model, string fileString, string deliverablesFolder,
            bool overwriteFiles, bool pdf, bool dxf, bool png, bool edr, Action<string> log, Action<string> errorLog, string partNumberOverride)
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
                    : BomPartNumber(conf, model, errorLog);
                string drawingPath = OnlyFolder(modelPath) + pn + ".SLDDRW";
                if (!File.Exists(drawingPath))
                {
                    return;
                }

                string pdfPath = Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf");
                string dxfPath = Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf");
                string pngPath = Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png");
                string edrPath = Path.Combine(deliverablesFolder, "edr", fileString + ".edrw");
                bool dxfSelected = dxf;
                bool dxfRequested = dxfSelected && ShouldExport(dxfPath, overwriteFiles);

                HashSet<string> keep = SnapshotOpenDocIds();
                AddDocToKeepSet(keep, model, null);
                DocScope scope = new DocScope(this, keep, errorLog, "dwgpublish|" + drawingPath);

                DocumentSpecification spec = null;
                ModelDoc2 drawDoc = null;
                try
                {
                    spec = _swApp.GetOpenDocSpec(drawingPath) as DocumentSpecification;
                    if (spec == null)
                    {
                        DebugExport(errorLog, "DwgPublish: open spec failed: " + drawingPath);
                        return;
                    }
                    spec.DocumentType = (int)swDocumentTypes_e.swDocDRAWING;
                    spec.ReadOnly = true;
                    spec.Silent = true;

                    using (new ExternalReferenceBatchOpenScope(_swApp))
                    {
                        ThrowIfCancelled();
                        drawDoc = _swApp.OpenDoc7(spec) as ModelDoc2;
                    }
                    if (drawDoc == null)
                    {
                        DebugExport(errorLog, "DwgPublish: open failed: " + drawingPath);
                        return;
                    }

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

                    HashSet<string> dxfSheetTokens = null;
                    if (pdf || dxfSelected)
                    {
                        dxfSheetTokens = BuildDxfSheetNameTokens();
                    }

                    string dxfSheetName = string.Empty;
                    if (dxfRequested && dxfSheetTokens != null && dxfSheetTokens.Count > 0)
                    {
                        for (int i = 0; i < sheetNames.Length; i++)
                        {
                            ThrowIfCancelled();
                            if (IsDxfSheetName(sheetNames[i], dxfSheetTokens))
                            {
                                dxfSheetName = sheetNames[i];
                                break;
                            }
                        }
                    }

                    int errors = 0;
                    int warnings = 0;
                    ExportSummary summary = _currentExportSummary;

                    if (pdf)
                    {
                        ThrowIfCancelled();
                        ExportPdfData exportData = _swApp.GetExportFileData(
                            (int)swExportDataFileType_e.swExportPdfData) as ExportPdfData;
                        if (exportData != null)
                        {
                            try
                            {
                                exportData.ViewPdfAfterSaving = false;
                            }
                            catch
                            {
                                // ignore
                            }

                            var excludedSheets = new List<string>();
                            var includedSheets = new List<string>();
                            if (dxfSheetTokens != null && dxfSheetTokens.Count > 0)
                            {
                                for (int i = 0; i < sheetNames.Length; i++)
                                {
                                    string name = sheetNames[i];
                                    if (IsDxfSheetName(name, dxfSheetTokens))
                                    {
                                        excludedSheets.Add(name);
                                    }
                                    else
                                    {
                                        includedSheets.Add(name);
                                    }
                                }
                            }
                            else
                            {
                                includedSheets.AddRange(sheetNames);
                            }

                            List<string> tokensSorted = null;
                            try
                            {
                                if (dxfSheetTokens != null)
                                {
                                    tokensSorted = new List<string>();
                                    foreach (string t in dxfSheetTokens)
                                    {
                                        if (!string.IsNullOrWhiteSpace(t))
                                        {
                                            tokensSorted.Add(t);
                                        }
                                    }
                                    tokensSorted.Sort(StringComparer.OrdinalIgnoreCase);
                                }
                            }
                            catch
                            {
                                tokensSorted = null;
                            }

                            string FormatList(IList<string> values)
                            {
                                if (values == null)
                                {
                                    return "<null>";
                                }

                                int max = 50;
                                var sb = new StringBuilder();
                                sb.Append("[");
                                for (int i = 0; i < values.Count; i++)
                                {
                                    if (i > 0) sb.Append(", ");
                                    if (i >= max)
                                    {
                                        sb.Append("... +").Append(values.Count - i);
                                        break;
                                    }
                                    sb.Append(values[i] ?? string.Empty);
                                }
                                sb.Append("]");
                                return sb.ToString();
                            }

                            bool hasExclusions = excludedSheets.Count > 0;
                            if (hasExclusions)
                            {
                                SafeLog(errorLog,
                                    "DWG PDF sheets: dxfSheetNamesRaw=" + (_config != null ? (_config.DxfSheetNames ?? string.Empty) : string.Empty) +
                                    " tokens=" + FormatList(tokensSorted) +
                                    " all=" + FormatList(new List<string>(sheetNames)) +
                                    " excluded=" + FormatList(excludedSheets) +
                                    " included=" + FormatList(includedSheets));
                            }

                            bool saveOk = false;
                            bool skippedPdf = false;
                            if (hasExclusions && includedSheets.Count == 0)
                            {
                                skippedPdf = true;
                                SafeLog(errorLog,
                                    "DWG PDF skipped: all sheets match DXF patterns; no non-DXF sheets available. path=" + pdfPath);
                            }
                            else
                            {
                                if (summary != null)
                                {
                                    summary.DwgAttemptPdf++;
                                }

                                string[] pdfSheetNames = (hasExclusions && includedSheets.Count > 0 && includedSheets.Count < sheetNames.Length)
                                    ? includedSheets.ToArray()
                                    : sheetNames;

                                bool setOk = false;
                                string setArgType = "<none>";
                                try
                                {
                                    setOk = exportData.SetSheets(
                                        (int)swExportDataSheetsToExport_e.swExportData_ExportSpecifiedSheets,
                                        pdfSheetNames);
                                    setArgType = pdfSheetNames != null ? pdfSheetNames.GetType().FullName : "<null>";
                                }
                                catch (Exception ex)
                                {
                                    setOk = false;
                                    SafeLog(errorLog, "DWG PDF SetSheets exception (string[]): " + ex.Message);
                                }

                                if (!setOk)
                                {
                                    try
                                    {
                                        var pdfVariant = new object[pdfSheetNames != null ? pdfSheetNames.Length : 0];
                                        for (int i = 0; i < pdfVariant.Length; i++)
                                        {
                                            pdfVariant[i] = pdfSheetNames[i];
                                        }

                                        setOk = exportData.SetSheets(
                                            (int)swExportDataSheetsToExport_e.swExportData_ExportSpecifiedSheets,
                                            pdfVariant);
                                        setArgType = pdfVariant.GetType().FullName;
                                    }
                                    catch (Exception ex)
                                    {
                                        setOk = false;
                                        SafeLog(errorLog, "DWG PDF SetSheets exception (variant[]): " + ex.Message);
                                    }
                                }

                                SafeLog(errorLog,
                                    "DWG PDF SetSheets ok=" + setOk +
                                    " argType=" + (setArgType ?? string.Empty) +
                                    " count=" + (pdfSheetNames != null ? pdfSheetNames.Length : 0) +
                                    " export=" + FormatList(new List<string>(pdfSheetNames ?? new string[0])) +
                                    " path=" + pdfPath);

                                if (!setOk && hasExclusions)
                                {
                                    skippedPdf = true;
                                    SafeLog(errorLog,
                                        "DWG PDF skipped: failed to apply sheet filter; refusing to export PDF that would include DXF sheets. path=" + pdfPath);
                                }
                                else
                                {
                                    saveOk = drawDoc.Extension.SaveAs(pdfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, exportData, ref errors, ref warnings);
                                }
                            }

                            if (!skippedPdf)
                            {
                                bool ok = saveOk && File.Exists(pdfPath);
                                if (ok)
                                {
                                    if (summary != null)
                                    {
                                        summary.DwgOkPdf++;
                                    }
                                }
                                else
                                {
                                    if (summary != null)
                                    {
                                        summary.DwgFailPdf++;
                                    }
                                    LogExportFailure(log, errorLog, "PDF export failed: " + pdfPath);
                                }
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.DwgFailPdf++;
                            }
                            LogExportFailure(log, errorLog, "PDF export failed: export data unavailable.");
                        }
                    }

                    if (edr)
                    {
                        if (summary != null)
                        {
                            summary.DwgAttemptEdraw++;
                        }

                        ThrowIfCancelled();
                        _swApp.SetUserPreferenceIntegerValue(
                            (int)swUserPreferenceIntegerValue_e.swEdrawingsSaveAsSelectionOption,
                            (int)swEdrawingSaveAsOption_e.swEdrawingSaveAll);
                        bool ok = drawDoc.Extension.SaveAs(edrPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        ok = ok && File.Exists(edrPath);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.DwgOkEdraw++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.DwgFailEdraw++;
                            }
                            LogExportFailure(log, errorLog, "eDrawing export failed: " + edrPath);
                        }
                    }

                    if (png)
                    {
                        if (summary != null)
                        {
                            summary.DwgAttemptPng++;
                        }

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
                        ok = ok && File.Exists(pngPath);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.DwgOkPng++;
                            }
                        }
                        else
                        {
                            if (summary != null)
                            {
                                summary.DwgFailPng++;
                            }
                            LogExportFailure(log, errorLog, "Drawing PNG export failed: " + pngPath);
                        }
                    }

                    if (dxfRequested)
                    {
                        // DXF is only required when the drawing has a designated DXF/flatpattern sheet.
                        // Do not treat "no drawing DXF page" as an export error.
                        if (string.IsNullOrWhiteSpace(dxfSheetName))
                        {
                            SafeLog(errorLog, "DWG DXF skipped: no designated DXF sheet found (configure Advanced > Drawing export > DXF sheet names; current: " +
                                              (_config != null ? (_config.DxfSheetNames ?? string.Empty) : string.Empty) + ").");
                        }
                        else
                        {
                            try
                            {
                                _swApp.SetUserPreferenceIntegerValue(
                                    (int)swUserPreferenceIntegerValue_e.swDxfMultiSheetOption,
                                    (int)swDxfMultisheet_e.swDxfActiveSheetOnly);
                                _swApp.SetUserPreferenceIntegerValue(
                                    (int)swUserPreferenceIntegerValue_e.swDxfOutputNoScale, 1);
                            }
                            catch
                            {
                                // ignore preference errors
                            }

                            if (summary != null)
                            {
                                summary.DwgAttemptDxf++;
                            }

                            ThrowIfCancelled();
                            bool exported = false;

                            // If the drawing has a dedicated DXF/flat pattern sheet, export it directly without
                            // mutating the sheet format (mutations can dirty the doc and trigger save prompts).
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

                            // Fallback: if direct export fails, try exporting the FLATPATTERN view.
                            if (!exported)
                            {
                                View flatView = drawing.GetFirstView() as View;
                                View flatPatternView = null;
                                while (flatView != null)
                                {
                                    ThrowIfCancelled();
                                    string viewName = string.Empty;
                                    try
                                    {
                                        viewName = flatView.GetName2() ?? string.Empty;
                                    }
                                    catch
                                    {
                                        viewName = string.Empty;
                                    }

                                    if (NormalizeSheetNameForMatch(viewName) == "flatpattern")
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
                                if (summary != null)
                                {
                                    summary.DwgFailDxf++;
                                }
                                LogExportFailure(log, errorLog, "DXF export failed: " + dxfPath);
                            }
                            else
                            {
                                if (summary != null)
                                {
                                    summary.DwgOkDxf++;
                                }
                            }
                        }
                    }
                }
                finally
                {
                    if (drawDoc != null)
                    {
                        ForceCloseDocNoSave(drawDoc, errorLog, "DwgPublish close");
                    }
                    try
                    {
                        scope.CloseOpenedDocs();
                    }
                    catch
                    {
                        // ignore scope cleanup errors
                    }

                    CloseDocsNotInKeepSet(keep, errorLog, "post-close drawing publish");
                    ComInteropUtil.TryFinalReleaseComObject(drawDoc);
                    ComInteropUtil.TryFinalReleaseComObject(spec);
                }
            }
        }

        private void ReplaceSheetFormat(DrawingDoc draw, Sheet sheet, string targetSheetFormatFile)
        {
            object propsObj = sheet.GetProperties();
            Array props = propsObj as Array;
            if (props == null || props.Length < 7)
            {
                return;
            }

            int paperSize = Convert.ToInt32(props.GetValue(0));
            int templateType = Convert.ToInt32(props.GetValue(1));
            double scale1 = Convert.ToDouble(props.GetValue(2));
            double scale2 = Convert.ToDouble(props.GetValue(3));
            bool firstAngle = Convert.ToBoolean(props.GetValue(4));
            double width = Convert.ToDouble(props.GetValue(5));
            double height = Convert.ToDouble(props.GetValue(6));
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
                ComInteropUtil.TryFinalReleaseComObject(viewModel);

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

            object viewsObj = null;
            try
            {
                viewsObj = sheet.GetViews();
            }
            catch
            {
                viewsObj = null;
            }

            View view = null;
            foreach (object obj in ComInteropUtil.EnumerateCom(viewsObj))
            {
                view = obj as View;
                if (view != null)
                {
                    break;
                }
            }
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
            var toDelete = new List<Annotation>();
            foreach (object obj in ComInteropUtil.EnumerateCom(annotationsObj))
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
            Array sheets = sheetsObj as Array;
            if (sheets == null || sheets.Length == 0)
            {
                return;
            }

            object firstSheetViewsObj = sheets.GetValue(0);
            var firstSheetViews = new List<View>();
            foreach (object obj in ComInteropUtil.EnumerateCom(firstSheetViewsObj))
            {
                View v = obj as View;
                if (v != null)
                {
                    firstSheetViews.Add(v);
                }
            }

            if (firstSheetViews.Count == 0)
            {
                return;
            }

            View sheetView = firstSheetViews[0];
            if (sheetView == null)
            {
                return;
            }

            object tablesObj = sheetView.GetTableAnnotations();
            var tables = new List<object>();
            foreach (object obj in ComInteropUtil.EnumerateCom(tablesObj))
            {
                if (obj != null)
                {
                    tables.Add(obj);
                }
            }

            if (tables.Count == 0)
            {
                return;
            }

            int selected = model.Extension.MultiSelect2(tables.ToArray(), false, null);
            if (selected == tables.Count)
            {
                model.Extension.DeleteSelection2((int)swDeleteSelectionOptions_e.swDelete_Absorbed);
            }
        }

        private void FitSheetToView(Sheet sheet, View view)
        {
            double[] outline = ToDoubleArray(view.GetOutline());
            if (outline == null || outline.Length < 4)
            {
                return;
            }

            double width = outline[2] - outline[0];
            double height = outline[3] - outline[1];
            sheet.SetSize((int)swDwgPaperSizes_e.swDwgPapersUserDefined, width, height);

            double[] position = ToDoubleArray(view.Position);
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
            foreach (object sheetViewsObj in ComInteropUtil.EnumerateCom(viewsObj))
            {
                var views = new List<View>();
                foreach (object obj in ComInteropUtil.EnumerateCom(sheetViewsObj))
                {
                    View v = obj as View;
                    if (v != null)
                    {
                        views.Add(v);
                    }
                }

                if (views.Count == 0)
                {
                    continue;
                }

                View sheetView = views[0];
                if (sheetView != null &&
                    string.Equals(sheetView.Name, sheet.GetName(), StringComparison.OrdinalIgnoreCase))
                {
                    if (views.Count <= 1)
                    {
                        return new View[0];
                    }

                    var result = new View[views.Count - 1];
                    for (int i = 1; i < views.Count; i++)
                    {
                        result[i - 1] = views[i];
                    }

                    return result;
                }
            }

            return new View[0];
        }

        private string GetFileString(ModelDoc2 model, string configName, Action<string> errorLog = null)
        {
            string tempRev = (GetEvalProperty(model, configName, "revision") ?? string.Empty).Trim();
            Configuration config = model.GetConfigurationByName(configName) as Configuration;
            string fileString = BomPartNumber(config, model, errorLog) + "_REV_" + tempRev;
            return fileString.ToUpperInvariant();
        }

        private string BomPartNumber(Configuration config, ModelDoc2 document, Action<string> errorLog = null)
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
                        partNumber = BomPartNumber(parent, document, errorLog);
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
                string source = partNumber;
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

                if (errorLog != null)
                {
                    string docId = string.Empty;
                    try
                    {
                        docId = document.GetPathName();
                    }
                    catch
                    {
                        docId = string.Empty;
                    }
                    if (string.IsNullOrWhiteSpace(docId))
                    {
                        try
                        {
                            docId = document.GetTitle();
                        }
                        catch
                        {
                            docId = string.Empty;
                        }
                    }

                    string key = "BomFallback|" + (docId ?? string.Empty) + "|" + (config.Name ?? string.Empty);
                    if (_debugOnce.Add(key))
                    {
                        try
                        {
                            errorLog("Warning: BOM part number fallback used (no mutation): source=\"" + (source ?? string.Empty) +
                                     "\" derived=\"" + (partNumber ?? string.Empty) +
                                     "\" config=\"" + (config.Name ?? string.Empty) +
                                     "\" doc=\"" + (docId ?? string.Empty) + "\"");
                        }
                        catch
                        {
                            // ignore logging errors
                        }
                    }
                }
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

        private string GetDocDict(ModelDoc2 model, string confName, Action<string> errorLog = null)
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
                .Append(SanitizeString(BomPartNumber(modelConf, model, errorLog)))
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

            if (values == null)
            {
                return null;
            }

            var result = new List<string>();
            foreach (object obj in ComInteropUtil.EnumerateCom(values))
            {
                result.Add(obj != null ? obj.ToString() : string.Empty);
            }

            return result.Count > 0 ? result.ToArray() : null;
        }

        private static double[] ToDoubleArray(object values)
        {
            double[] doubles = values as double[];
            if (doubles != null)
            {
                return doubles;
            }

            if (values == null)
            {
                return null;
            }

            var result = new List<double>();
            foreach (object obj in ComInteropUtil.EnumerateCom(values))
            {
                if (obj == null)
                {
                    continue;
                }

                if (obj is double)
                {
                    result.Add((double)obj);
                }
                else if (obj is float)
                {
                    result.Add((double)(float)obj);
                }
                else if (obj is int)
                {
                    result.Add((int)obj);
                }
                else if (obj is short)
                {
                    result.Add((short)obj);
                }
                else if (obj is long)
                {
                    result.Add((long)obj);
                }
                else
                {
                    double parsed;
                    string text = obj.ToString();
                    if (double.TryParse(text, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture, out parsed) ||
                        double.TryParse(text, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.CurrentCulture, out parsed))
                    {
                        result.Add(parsed);
                    }
                }
            }

            return result.Count > 0 ? result.ToArray() : null;
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

        private void SafeLog(Action<string> errorLog, string message)
        {
            if (errorLog == null || string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            try
            {
                errorLog(message);
            }
            catch
            {
                // ignore logging errors
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

        private void LogExceptionDetails(Action<string> errorLog, string context, Exception ex)
        {
            if (errorLog == null || ex == null)
            {
                return;
            }

            try
            {
                System.Runtime.InteropServices.COMException com = null;
                Exception cur = ex;
                while (cur != null && com == null)
                {
                    com = cur as System.Runtime.InteropServices.COMException;
                    cur = cur.InnerException;
                }

                if (com != null)
                {
                    errorLog("COMException: context=" + (context ?? string.Empty) +
                             " hr=0x" + com.ErrorCode.ToString("X8") +
                             " message=" + (com.Message ?? string.Empty));
                }
                else
                {
                    errorLog("Exception: context=" + (context ?? string.Empty) +
                             " type=" + ex.GetType().FullName +
                             " message=" + (ex.Message ?? string.Empty));
                }

                if (!string.IsNullOrWhiteSpace(ex.StackTrace))
                {
                    errorLog(ex.StackTrace);
                }

                try
                {
                    ModelDoc2 active = _swApp.ActiveDoc as ModelDoc2;
                    if (active == null)
                    {
                        errorLog("ActiveDoc: <null>");
                    }
                    else
                    {
                        string activeTitle = string.Empty;
                        string activePath = string.Empty;
                        try
                        {
                            activeTitle = active.GetTitle();
                            activePath = active.GetPathName();
                        }
                        catch
                        {
                            activeTitle = string.Empty;
                            activePath = string.Empty;
                        }

                        errorLog("ActiveDoc: title=" + (activeTitle ?? string.Empty) + " | path=" + (activePath ?? string.Empty));
                    }
                }
                catch
                {
                    // ignore active-doc lookup errors
                }

                LogVisibleDocuments(errorLog, "VisibleDoc");
            }
            catch
            {
                // ignore exception-logging errors
            }
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
                return CreateRunLog("deliverables");
            }
            catch
            {
                return null;
            }
        }

        private ExportRunLog CreateRunLog(string prefix)
        {
            try
            {
                string dir = Path.Combine(Path.GetTempPath(), "TinyMRP", "export-logs");
                string safePrefix = string.IsNullOrWhiteSpace(prefix) ? "run" : prefix.Trim();
                string name = safePrefix + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".log";
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
            if (runLog != null && !string.IsNullOrWhiteSpace(runLog.Path))
            {
                return baseMessage + " Log: " + runLog.Path;
            }

            return baseMessage;
        }

        private void WriteExportSummary(Action<string> errorLog, ExportSummary summary, HashSet<string> finalDocIds)
        {
            if (errorLog == null || summary == null)
            {
                return;
            }

            try
            {
                errorLog("===== SUMMARY =====");
                errorLog("Planned model-config pairs: " + summary.PlannedModelConfigPairs);
                errorLog("Unresolved components: " + summary.FlatBomUnresolvedComponents);
                if (!string.IsNullOrWhiteSpace(summary.DeliverablesPlanPath))
                {
                    errorLog("Deliverables plan file: " + summary.DeliverablesPlanPath);
                }
                errorLog("Deliverable items planned=" + summary.DeliverablePlansPlanned +
                         " processed=" + summary.DeliverableItemsProcessed +
                         " skipped=" + summary.DeliverableItemsSkipped +
                         " itemFailures=" + summary.DeliverableItemsFailed +
                         " failedExports=" + GetFailedExportCount(summary));
                errorLog("Deliverable groups planned=" + summary.DeliverableGroupsPlanned +
                         " processed=" + summary.DeliverableGroupsProcessed +
                         " skipped=" + summary.DeliverableGroupsSkipped);
                errorLog("Deliverable plans planned=" + summary.DeliverablePlansPlanned +
                         " executed=" + summary.DeliverablePlansExecuted +
                         " skipped=" + summary.DeliverablePlansSkipped);

                errorLog("Exports(model) 3mf: " + FormatCounts(summary.ModelAttempt3mf, summary.ModelOk3mf, summary.ModelFail3mf));
                errorLog("Exports(model) stl: " + FormatCounts(summary.ModelAttemptStl, summary.ModelOkStl, summary.ModelFailStl));
                errorLog("Exports(model) ply: " + FormatCounts(summary.ModelAttemptPly, summary.ModelOkPly, summary.ModelFailPly));
                errorLog("Exports(model) step: " + FormatCounts(summary.ModelAttemptStep, summary.ModelOkStep, summary.ModelFailStep));
                errorLog("Exports(model) edraw: " + FormatCounts(summary.ModelAttemptEdraw, summary.ModelOkEdraw, summary.ModelFailEdraw));
                errorLog("Exports(model) png: " + FormatCounts(summary.ModelAttemptPng, summary.ModelOkPng, summary.ModelFailPng));

                errorLog("Exports(dwg) pdf: " + FormatCounts(summary.DwgAttemptPdf, summary.DwgOkPdf, summary.DwgFailPdf));
                errorLog("Exports(dwg) edraw: " + FormatCounts(summary.DwgAttemptEdraw, summary.DwgOkEdraw, summary.DwgFailEdraw));
                errorLog("Exports(dwg) png: " + FormatCounts(summary.DwgAttemptPng, summary.DwgOkPng, summary.DwgFailPng));
                errorLog("Exports(dwg) dxf: " + FormatCounts(summary.DwgAttemptDxf, summary.DwgOkDxf, summary.DwgFailDxf));

                errorLog("Open docs: start=" + summary.InitialOpenDocs +
                         " afterRootClose=" + summary.OpenDocsAfterRootClose +
                         " end=" + summary.FinalOpenDocs);
                errorLog("Memory bytes: beforeRootClose=" + summary.MemoryBeforeRootClose +
                         " afterRootClose=" + summary.MemoryAfterRootClose +
                         " end=" + summary.FinalPrivateMemoryBytes);

                if (summary.BaselineVisibleDocIds != null)
                {
                    HashSet<string> finalVisible = null;
                    try
                    {
                        finalVisible = GetOpenVisibleDocumentIds();
                    }
                    catch
                    {
                        finalVisible = null;
                    }

                    if (finalVisible != null)
                    {
                        errorLog("Visible docs: baseline=" + summary.InitialVisibleDocs + " end=" + finalVisible.Count);

                        var extraVisible = new HashSet<string>(finalVisible, StringComparer.OrdinalIgnoreCase);
                        extraVisible.ExceptWith(summary.BaselineVisibleDocIds);

                        var missingVisible = new HashSet<string>(summary.BaselineVisibleDocIds, StringComparer.OrdinalIgnoreCase);
                        missingVisible.ExceptWith(finalVisible);

                        if (extraVisible.Count == 0 && missingVisible.Count == 0)
                        {
                            errorLog("Remaining-visible-docs delta: 0");
                        }
                        else
                        {
                            errorLog("WARN: Remaining-visible-docs delta extra=" + extraVisible.Count + " missing=" + missingVisible.Count);

                            int shown = 0;
                            foreach (string id in extraVisible)
                            {
                                if (shown++ >= 25)
                                {
                                    break;
                                }

                                errorLog("WARN: extra-visible-doc: " + (id ?? string.Empty));
                            }

                            LogVisibleDocuments(errorLog, "VISIBLE-FINAL");
                        }
                    }
                }

                if (summary.BaselineDocIds != null && finalDocIds != null)
                {
                    var extra = new HashSet<string>(finalDocIds, StringComparer.OrdinalIgnoreCase);
                    extra.ExceptWith(summary.BaselineDocIds);

                    var missing = new HashSet<string>(summary.BaselineDocIds, StringComparer.OrdinalIgnoreCase);
                    missing.ExceptWith(finalDocIds);

                    if (extra.Count == 0 && missing.Count == 0)
                    {
                        errorLog("Remaining-open-docs delta: 0");
                    }
                    else
                    {
                        errorLog("WARN: Remaining-open-docs delta extra=" + extra.Count + " missing=" + missing.Count);

                        int shown = 0;
                        foreach (string id in extra)
                        {
                            if (shown++ >= 25)
                            {
                                break;
                            }

                            errorLog("WARN: extra-open-doc: " + (id ?? string.Empty));
                        }
                    }
                }
            }
            catch
            {
                // ignore summary logging errors
            }
        }

        private int GetFailedExportCount(ExportSummary summary)
        {
            if (summary == null)
            {
                return 0;
            }

            return summary.ModelFail3mf + summary.ModelFailStl + summary.ModelFailPly +
                   summary.ModelFailStep + summary.ModelFailEdraw + summary.ModelFailPng +
                   summary.DwgFailPdf + summary.DwgFailEdraw + summary.DwgFailPng +
                   summary.DwgFailDxf;
        }

        private string FormatCounts(int attempted, int ok, int fail)
        {
            return "attempted=" + attempted + " ok=" + ok + " fail=" + fail;
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

        public void RequestPause()
        {
            _pauseRequested = true;
        }

        private void ResetCancel()
        {
            _cancelRequested = false;
        }

        private void ResetPause()
        {
            _pauseRequested = false;
        }

        private void ThrowIfCancelled()
        {
            if (_cancelRequested)
            {
                throw new OperationCanceledException();
            }
        }

        private void YieldAndCheckCancel()
        {
            ThrowIfCancelled();
            try
            {
                System.Windows.Forms.Application.DoEvents();
            }
            catch
            {
                // ignore UI pump errors
            }
            ThrowIfCancelled();
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

        private sealed class DocScope : IDisposable
        {
            private readonly TinyMrpPublisher _owner;
            private readonly HashSet<string> _keep;
            private readonly Action<string> _errorLog;
            private readonly string _context;
            private readonly HashSet<string> _baselineIds;
            private HashSet<string> _openedIds;

            public DocScope(TinyMrpPublisher owner, HashSet<string> keep, Action<string> errorLog, string context)
            {
                _owner = owner;
                _keep = keep;
                _errorLog = errorLog;
                _context = context ?? string.Empty;
                _baselineIds = owner != null
                    ? owner.SnapshotOpenDocIds()
                    : new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }

            public void AfterOpenSnapshot()
            {
                if (_owner == null || _openedIds != null)
                {
                    return;
                }

                HashSet<string> current = _owner.SnapshotOpenDocIds();
                _openedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

                foreach (string id in current)
                {
                    if (_baselineIds.Contains(id))
                    {
                        continue;
                    }

                    if (_keep != null && _keep.Contains(id))
                    {
                        continue;
                    }

                    _openedIds.Add(id);
                }
            }

            public void CloseOpenedDocs()
            {
                if (_owner == null)
                {
                    return;
                }

                AfterOpenSnapshot();
                _owner.CloseDocsByIdSet(_openedIds, _keep, _errorLog, _context);
            }

            public void Dispose()
            {
                try
                {
                    CloseOpenedDocs();
                }
                catch
                {
                    // ignore cleanup errors
                }
            }
        }

        private sealed class OpenTracker : IDisposable
        {
            private sealed class OpenedDoc
            {
                public ModelDoc2 Doc;
                public string Id;
                public string Title;
            }

            private readonly TinyMrpPublisher _owner;
            private readonly Action<string> _errorLog;
            private readonly Dictionary<string, OpenedDoc> _opened = new Dictionary<string, OpenedDoc>(StringComparer.OrdinalIgnoreCase);

            public OpenTracker(TinyMrpPublisher owner, Action<string> errorLog)
            {
                _owner = owner;
                _errorLog = errorLog;
            }

            public void Track(ModelDoc2 doc, string context)
            {
                if (_owner == null || doc == null)
                {
                    return;
                }

                string id = string.Empty;
                string title = string.Empty;
                try
                {
                    id = _owner.GetDocumentId(doc);
                }
                catch
                {
                    id = string.Empty;
                }

                try
                {
                    title = doc.GetTitle() ?? string.Empty;
                }
                catch
                {
                    title = string.Empty;
                }

                if (string.IsNullOrWhiteSpace(id))
                {
                    id = !string.IsNullOrWhiteSpace(title) ? title : Guid.NewGuid().ToString("N");
                }

                if (_opened.ContainsKey(id))
                {
                    return;
                }

                _opened[id] = new OpenedDoc { Doc = doc, Id = id, Title = title };
                if (_errorLog != null)
                {
                    _owner.SafeLog(_errorLog, "TRACK: " + (context ?? string.Empty) + " id=" + id + " title=" + (title ?? string.Empty));
                }
            }

            public void Untrack(ModelDoc2 doc)
            {
                if (_owner == null || doc == null)
                {
                    return;
                }

                string id = string.Empty;
                try
                {
                    id = _owner.GetDocumentId(doc);
                }
                catch
                {
                    id = string.Empty;
                }

                if (string.IsNullOrWhiteSpace(id))
                {
                    return;
                }

                _opened.Remove(id);
            }

            public void CloseAll(string context)
            {
                if (_owner == null || _opened.Count == 0)
                {
                    return;
                }

                var docs = new List<OpenedDoc>(_opened.Values);
                _opened.Clear();

                foreach (OpenedDoc opened in docs)
                {
                    if (opened == null)
                    {
                        continue;
                    }

                    try
                    {
                        _owner.ForceCloseDocNoSave(opened.Doc, _errorLog, context);
                    }
                    catch
                    {
                        try
                        {
                            if (!string.IsNullOrWhiteSpace(opened.Title))
                            {
                                _owner._swApp.QuitDoc(opened.Title);
                            }
                        }
                        catch
                        {
                            // ignore close errors
                        }
                    }

                    ComInteropUtil.TryFinalReleaseComObject(opened.Doc);
                }
            }

            public void Dispose()
            {
                try
                {
                    CloseAll("dispose");
                }
                catch
                {
                    // ignore dispose close errors
                }
            }
        }

        private void CloseDocsByIdSet(HashSet<string> idsToClose, HashSet<string> keep, Action<string> errorLog, string context)
        {
            if (idsToClose == null || idsToClose.Count == 0)
            {
                return;
            }

            using (new ExportDialogSuppressionScope(_swApp))
            using (new ExternalReferenceBatchOpenScope(_swApp))
            {
                const int maxPasses = 3;
                for (int pass = 0; pass < maxPasses; pass++)
                {
                    HashSet<string> openIds = SnapshotOpenDocIds();
                    var remaining = new HashSet<string>(idsToClose, StringComparer.OrdinalIgnoreCase);
                    remaining.IntersectWith(openIds);
                    if (remaining.Count == 0)
                    {
                        return;
                    }

                    foreach (ModelDoc2 doc in EnumerateOpenDocuments())
                    {
                        if (doc == null)
                        {
                            continue;
                        }

                        string id = GetDocumentId(doc);
                        if (string.IsNullOrWhiteSpace(id) || !remaining.Contains(id))
                        {
                            continue;
                        }

                        if (IsDocInKeepSet(doc, keep))
                        {
                            continue;
                        }

                        try
                        {
                            ForceCloseDocNoSave(doc, errorLog, context);
                        }
                        catch
                        {
                            // ignore close errors
                        }

                        ComInteropUtil.TryFinalReleaseComObject(doc);
                    }

                    System.Windows.Forms.Application.DoEvents();
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

            if (errorLog != null)
            {
                try
                {
                    HashSet<string> openIds = SnapshotOpenDocIds();
                    var remaining = new HashSet<string>(idsToClose, StringComparer.OrdinalIgnoreCase);
                    remaining.IntersectWith(openIds);
                    if (remaining.Count > 0)
                    {
                        errorLog("WARN: Unable to close some step-opened documents context=" + (context ?? string.Empty) +
                                 " remaining=" + remaining.Count);
                        LogOpenDocuments(errorLog, "WARN: still-open");
                    }
                }
                catch
                {
                    // ignore warn logging errors
                }
            }
        }

        private void CloseDocsNotInKeepSet(HashSet<string> keep, Action<string> errorLog, string context)
        {
            if (keep == null)
            {
                keep = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }

            using (new ExportDialogSuppressionScope(_swApp))
            using (new ExternalReferenceBatchOpenScope(_swApp))
            {
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
                        if (doc == null)
                        {
                            continue;
                        }

                        if (IsDocInKeepSet(doc, keep))
                        {
                            continue;
                        }

                        try
                        {
                            ForceCloseDocNoSave(doc, errorLog, context);
                        }
                        catch
                        {
                            // ignore close errors
                        }

                        ComInteropUtil.TryFinalReleaseComObject(doc);
                    }

                    System.Windows.Forms.Application.DoEvents();
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

            List<ModelDoc2> remainingDocs = GetOpenDocsNotInKeepSet(keep);
            if (remainingDocs.Count > 0)
            {
                try
                {
                    if (errorLog != null)
                    {
                        errorLog("WARN: Remaining non-keep documents after cleanup context=" + (context ?? string.Empty) +
                                 " count=" + remainingDocs.Count);
                        LogOpenDocuments(errorLog, "WARN: openDocs");
                    }
                }
                catch
                {
                    // ignore warn logging errors
                }
            }
        }

        private void LogOpenDocuments(Action<string> errorLog, string prefix)
        {
            if (errorLog == null)
            {
                return;
            }

            try
            {
                foreach (ModelDoc2 doc in EnumerateOpenDocuments())
                {
                    if (doc == null)
                    {
                        continue;
                    }

                    string title = string.Empty;
                    string path = string.Empty;
                    bool visible = true;
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

                    try
                    {
                        visible = doc.Visible;
                    }
                    catch
                    {
                        visible = true;
                    }

                    errorLog((prefix ?? string.Empty) + ": title=" + (title ?? string.Empty) +
                             " | path=" + (path ?? string.Empty) +
                             " | visible=" + visible);
                }
            }
            catch
            {
                // ignore enumeration errors
            }
        }

        private void LogVisibleDocuments(Action<string> errorLog, string prefix)
        {
            if (errorLog == null)
            {
                return;
            }

            try
            {
                foreach (ModelDoc2 doc in EnumerateOpenDocuments())
                {
                    if (doc == null)
                    {
                        continue;
                    }

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

                    SafeLog(errorLog,
                        (prefix ?? string.Empty) + ": title=" + (title ?? string.Empty) +
                        " | path=" + (path ?? string.Empty));
                }
            }
            catch
            {
                // ignore enumeration errors
            }
        }

        private List<ModelDoc2> GetVisibleDocuments()
        {
            var visibleDocs = new List<ModelDoc2>();
            foreach (ModelDoc2 doc in EnumerateOpenDocuments())
            {
                if (doc == null)
                {
                    continue;
                }

                bool visible = true;
                try
                {
                    visible = doc.Visible;
                }
                catch
                {
                    visible = true;
                }

                if (visible)
                {
                    visibleDocs.Add(doc);
                }
            }

            return visibleDocs;
        }

        private void LogVisibleDocDelta(HashSet<string> baselineVisibleDocs, Action<string> errorLog, string context)
        {
            if (errorLog == null || baselineVisibleDocs == null)
            {
                return;
            }

            HashSet<string> currentVisible = GetOpenVisibleDocumentIds();
            int delta = currentVisible.Count - baselineVisibleDocs.Count;
            string deltaText = (delta >= 0 ? "+" : string.Empty) + delta;

            var added = new HashSet<string>(currentVisible, StringComparer.OrdinalIgnoreCase);
            added.ExceptWith(baselineVisibleDocs);

            SafeLog(errorLog,
                "VISIBLE after [" + (context ?? string.Empty) + "]: delta=" + deltaText +
                " docs (baseline=" + baselineVisibleDocs.Count +
                " now=" + currentVisible.Count +
                " added=" + added.Count + ")");

            LogVisibleDocuments(errorLog, "VISIBLE");
        }

        private void EnforceVisibleDocBudget(
            HashSet<string> baselineVisibleIds,
            string rootDocId,
            string context,
            Action<string> log,
            int maxExtraVisible = 3)
        {
            if (baselineVisibleIds == null || log == null)
            {
                return;
            }

            // Snapshot visible docs/tabs and enforce a cap so batch exports never accumulate UI-visible documents.
            List<ModelDoc2> currentVisible = GetVisibleDocuments();
            var currentIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (ModelDoc2 doc in currentVisible)
            {
                if (doc == null)
                {
                    continue;
                }

                string id = string.Empty;
                try
                {
                    id = GetDocumentId(doc);
                }
                catch
                {
                    id = string.Empty;
                }

                if (!string.IsNullOrWhiteSpace(id))
                {
                    currentIds.Add(id);
                }
            }

            var extras = new List<string>();
            foreach (string id in currentIds)
            {
                if (baselineVisibleIds.Contains(id))
                {
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(rootDocId) &&
                    string.Equals(id, rootDocId, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                extras.Add(id);
            }

            if (extras.Count <= maxExtraVisible)
            {
                return;
            }

            SafeLog(log,
                "WATCHDOG [" + (context ?? string.Empty) + "]: " + extras.Count +
                " extra visible docs (threshold=" + maxExtraVisible + "), forcing cleanup");

            bool IsVisibleId(string id)
            {
                if (string.IsNullOrWhiteSpace(id))
                {
                    return false;
                }

                HashSet<string> visibleNow = GetOpenVisibleDocumentIds();
                return visibleNow.Contains(id);
            }

            int processed = 0;
            foreach (string extraId in extras)
            {
                ThrowIfCancelled();

                ModelDoc2 doc = null;
                foreach (ModelDoc2 d in currentVisible)
                {
                    if (d == null)
                    {
                        continue;
                    }

                    string did = string.Empty;
                    try
                    {
                        did = GetDocumentId(d);
                    }
                    catch
                    {
                        did = string.Empty;
                    }

                    if (!string.IsNullOrWhiteSpace(did) &&
                        string.Equals(did, extraId, StringComparison.OrdinalIgnoreCase))
                    {
                        doc = d;
                        break;
                    }
                }

                if (doc == null)
                {
                    continue;
                }

                string title = string.Empty;
                try
                {
                    title = doc.GetTitle() ?? string.Empty;
                }
                catch
                {
                    title = string.Empty;
                }

                bool hideAttempted = false;
                bool closeAttempted = false;
                bool quitAttempted = false;

                try
                {
                    hideAttempted = true;
                    doc.Visible = false;
                }
                catch
                {
                    // ignore hide errors
                }

                bool stillVisible = IsVisibleId(extraId);
                if (stillVisible)
                {
                    string closeTitle = NormalizeDocTitleForClose(title);
                    if (string.IsNullOrWhiteSpace(closeTitle))
                    {
                        closeTitle = title;
                    }

                    try
                    {
                        if (!string.IsNullOrWhiteSpace(closeTitle))
                        {
                            closeAttempted = true;
                            _swApp.CloseDoc(closeTitle);
                        }
                    }
                    catch
                    {
                        // ignore close errors
                    }

                    stillVisible = IsVisibleId(extraId);
                    if (stillVisible)
                    {
                        SafeLog(log,
                            "WARNING: " + (closeTitle ?? string.Empty) +
                            " still visible after CloseDoc, escalating to QuitDoc");
                        try
                        {
                            if (!string.IsNullOrWhiteSpace(closeTitle))
                            {
                                quitAttempted = true;
                                _swApp.QuitDoc(closeTitle);
                            }
                        }
                        catch
                        {
                            // ignore quit errors
                        }

                        stillVisible = IsVisibleId(extraId);
                    }
                }

                SafeLog(log,
                    "  WATCHDOG hid/closed: " + (string.IsNullOrWhiteSpace(title) ? extraId : title) +
                    " | hide=" + hideAttempted +
                    " close=" + closeAttempted +
                    " quit=" + quitAttempted +
                    " stillVisible=" + stillVisible);

                processed++;
                if (processed % 3 == 0)
                {
                    try
                    {
                        System.Windows.Forms.Application.DoEvents();
                    }
                    catch
                    {
                        // ignore UI pump errors
                    }
                    ThrowIfCancelled();
                }
            }

            // Re-activate root (best-effort).
            try
            {
                string rootTitle = string.Empty;
                if (!string.IsNullOrWhiteSpace(rootDocId))
                {
                    foreach (ModelDoc2 doc in EnumerateOpenDocuments())
                    {
                        if (doc == null)
                        {
                            continue;
                        }

                        string id = string.Empty;
                        try
                        {
                            id = GetDocumentId(doc);
                        }
                        catch
                        {
                            id = string.Empty;
                        }

                        if (string.IsNullOrWhiteSpace(id) ||
                            !string.Equals(id, rootDocId, StringComparison.OrdinalIgnoreCase))
                        {
                            continue;
                        }

                        try
                        {
                            rootTitle = doc.GetTitle() ?? string.Empty;
                        }
                        catch
                        {
                            rootTitle = string.Empty;
                        }
                        break;
                    }
                }

                if (!string.IsNullOrWhiteSpace(rootTitle))
                {
                    ActivateDocByTitle(rootTitle);
                }
            }
            catch
            {
                // ignore activation errors
            }
        }

        private void ActivateDocByTitle(string title)
        {
            if (_swApp == null || string.IsNullOrWhiteSpace(title))
            {
                return;
            }

            try
            {
                string activateTitle = NormalizeDocTitleForClose(title);
                if (string.IsNullOrWhiteSpace(activateTitle))
                {
                    activateTitle = title;
                }

                int errors = 0;
                _swApp.ActivateDoc3(activateTitle, true,
                    (int)swRebuildOnActivation_e.swDontRebuildActiveDoc, ref errors);
            }
            catch
            {
                // ignore activation errors
            }
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

        private string NormalizeTitle(string title)
        {
            return NormalizeDocTitleForClose(title);
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
             bool tempOrMissingFile = false;
             if (string.IsNullOrWhiteSpace(path))
             {
                 tempOrMissingFile = true;
             }
             else
             {
                 try
                 {
                     tempOrMissingFile = !File.Exists(path);
                 }
                 catch
                 {
                     tempOrMissingFile = true;
                 }
             }

             // SolidWorks can report the template path (e.g., *.asmdot) as the "document path" for a new, unsaved model.
             // Treat template-backed docs as temp/unsaved so closing never triggers Save/SaveAs UI.
             if (!tempOrMissingFile && !string.IsNullOrWhiteSpace(path))
             {
                 try
                 {
                     string ext = Path.GetExtension(path) ?? string.Empty;
                      if (string.Equals(ext, ".asmdot", StringComparison.OrdinalIgnoreCase) ||
                          string.Equals(ext, ".prtdot", StringComparison.OrdinalIgnoreCase) ||
                          string.Equals(ext, ".drwdot", StringComparison.OrdinalIgnoreCase))
                      {
                          tempOrMissingFile = true;
                          SafeLog(errorLog,
                              "ForceClose: treating doc as temp (template extension) context=" + (context ?? string.Empty) +
                              " type=" + docType +
                              " ext=" + (ext ?? string.Empty) +
                              " title=" + (title ?? string.Empty) +
                              " path=" + (path ?? string.Empty));
                      }
                  }
                  catch
                  {
                      // ignore extension errors
                 }
             }

             // Some installations use *.SLDASM/*.SLDPRT/*.SLDDRW files as templates; in that case, the new unsaved model
             // can still report the template file path as its "path". Treat it as temp if it matches the default template.
             if (!tempOrMissingFile && !string.IsNullOrWhiteSpace(path))
             {
                 try
                 {
                     int pref = 0;
                     if (docType == (int)swDocumentTypes_e.swDocASSEMBLY)
                     {
                         pref = (int)swUserPreferenceStringValue_e.swDefaultTemplateAssembly;
                     }
                     else if (docType == (int)swDocumentTypes_e.swDocPART)
                     {
                         pref = (int)swUserPreferenceStringValue_e.swDefaultTemplatePart;
                     }
                     else if (docType == (int)swDocumentTypes_e.swDocDRAWING)
                     {
                         pref = (int)swUserPreferenceStringValue_e.swDefaultTemplateDrawing;
                     }

                     if (pref != 0)
                     {
                         string defaultTemplate = _swApp.GetUserPreferenceStringValue(pref) ?? string.Empty;
                         if (!string.IsNullOrWhiteSpace(defaultTemplate) &&
                             string.Equals(path, defaultTemplate, StringComparison.OrdinalIgnoreCase))
                         {
                             tempOrMissingFile = true;
                             SafeLog(errorLog,
                                 "ForceClose: treating doc as temp (default template match) context=" + (context ?? string.Empty) +
                                 " type=" + docType +
                                 " title=" + (title ?? string.Empty) +
                                 " path=" + (path ?? string.Empty) +
                                 " template=" + (defaultTemplate ?? string.Empty));
                         }
                     }
                 }
                 catch
                 {
                     // ignore template detection errors
                 }
             }

             string pathFileName = string.Empty;
             try
             {
                 if (!string.IsNullOrWhiteSpace(path))
                 {
                    pathFileName = Path.GetFileName(path) ?? string.Empty;
                }
            }
            catch
            {
                pathFileName = string.Empty;
            }

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

                    if (tempOrMissingFile)
                    {
                        string[] candidates = new[] { title, closeTitle, pathFileName };
                        string used = string.Empty;
                        for (int i = 0; i < candidates.Length; i++)
                        {
                            string cand = candidates[i] ?? string.Empty;
                            if (string.IsNullOrWhiteSpace(cand))
                            {
                                continue;
                            }

                            // Skip duplicates (case-insensitive).
                            bool dup = false;
                            for (int j = 0; j < i; j++)
                            {
                                string prev = candidates[j] ?? string.Empty;
                                if (!string.IsNullOrWhiteSpace(prev) &&
                                    string.Equals(prev, cand, StringComparison.OrdinalIgnoreCase))
                                {
                                    dup = true;
                                    break;
                                }
                            }
                            if (dup)
                            {
                                continue;
                            }

                            SafeLog(errorLog,
                                "ForceClose: QuitDoc temp candidate pass=" + pass +
                                " context=" + (context ?? string.Empty) +
                                " cand=" + cand +
                                " title=" + (title ?? string.Empty) +
                                " closeTitle=" + (closeTitle ?? string.Empty) +
                                " fileName=" + (pathFileName ?? string.Empty) +
                                " path=" + (path ?? string.Empty));

                            try
                            {
                                _swApp.QuitDoc(cand);
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
                                used = cand;
                                break;
                            }
                        }

                        SafeLog(errorLog,
                            "ForceClose: temp close result context=" + (context ?? string.Empty) +
                            " used=" + (used ?? string.Empty) +
                            " stillOpen=" + IsStillOpen() +
                            " title=" + (title ?? string.Empty) +
                            " path=" + (path ?? string.Empty));

                        if (!IsStillOpen())
                        {
                            return;
                        }

                        // Temp/unsaved docs must never fall back to CloseDoc (can trigger save UI).
                        continue;
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

                    // Do NOT attempt CloseDoc("") (closes the active document) or ActivateDoc during cleanup.
                    // Unattended batch export must never change the active doc as part of a close attempt.
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
