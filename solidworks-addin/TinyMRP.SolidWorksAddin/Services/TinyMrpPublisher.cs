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
using System.Linq;



namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class TinyMrpPublisher
    {
        // Pipelines:
        // - Create Files: BuildDeliverablesManifestFromActiveDocument -> PruneManifestAgainstExistingOutputs ->
        //   BuildPhysicalExportQueue -> RunPhysicalExportQueue (each physical file opened at most once,
        //   parts first, assemblies after, root last). Resumable via the physical-queue session file.
        // - Create BOM / Upload pack: TraverseModel (flat BOM of unique PN/REV pairs) +
        //   TryBuildBomWithUnsavedTempAssembly (indented TREEBOM via a temporary, never-saved assembly).
        // Cleanup policy: only documents that BECAME VISIBLE during a run are closed; hidden in-memory
        // reference documents always stay with their parents (sweeping them caused endless close loops).
        // Flip these to true when diagnosing hide-features issues.
        private static readonly bool EnableHideDebugLog = false;
        private static readonly bool EnableHideStatusLog = false;
        // Writes additional structured "DEBUG" entries into the per-run log to trace batch issues
        // (open/close/activate/validate steps). Kept on: the run log is the primary diagnosis tool.
        private static readonly bool EnableExportDebugLog = true;
        private const long MinPngBytes = 8 * 1024;
        private const long MinPdfBytes = 4 * 1024;
        private const long MinEdrawingBytes = 4 * 1024;
        private const long MinGenericMeshBytes = 128;
        private const long MinGenericCadBytes = 128;
        private const int ExportSessionSchemaVersion = 2;
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

        private sealed class DeliverablePlan
        {
            public string ModelPath;
            public string ModelTitle;
            public string ConfigurationName;
            public string FileString;
            public string PartNumber;
            public string Revision;
            public string DrawingPath;
            public int DocType;
            public bool IsRoot;
            public int MaxDepth;
            public int SubtreeEstimate;
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

        private sealed class PhysicalExportQueueItem
        {
            public bool IsDrawing;
            public string PhysicalPath;
            public string DisplayName;
            public int DocType;
            public bool IsRoot;
            public int MaxDepth;
            public int SubtreeEstimate;
            public List<DeliverablePlan> Plans = new List<DeliverablePlan>();

            // Session/resume tracking (persisted). Not touched by planning/grouping code.
            public string Status = ExportItemStatusPending;
            public string CompletedUtc;
        }

        private sealed class DeliverableFailureRecord
        {
            public string PartNumber;
            public string Revision;
            public string SourceModelPath;
            public string DrawingPath;
            public HashSet<string> FailedFormats = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            public HashSet<string> Reasons = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
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
            public long FinalPrivateMemoryBytes;

            public int DeliverableGroupsPlanned;
            public int DeliverableGroupsProcessed;
            public int DeliverablePlansPlanned;
            public int DeliverablePlansSkipped;

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
            public bool StoppedAfterCurrentFile;
            public List<DeliverableFailureRecord> FailureRecords = new List<DeliverableFailureRecord>();
        }

        private sealed class ExportOutputResult
        {
            public bool Success;
            public bool Skipped;
            public bool ExportCallOk;
            public bool TempValidated;
            public string Type;
            public string FinalPath;
            public string TempPath;
            public string QuarantinedExistingPath;
            public string Reason;
            public long Bytes;
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

            // Session/resume tracking for the "Create files" pipeline (PhysicalExportQueueItem-based).
            public List<PhysicalExportQueueItem> PhysicalQueue = new List<PhysicalExportQueueItem>();
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

        private sealed class SolidWorksWhiteViewportBackgroundScope : IDisposable
        {
            private readonly ISldWorks _swApp;
            private readonly int _backgroundAppearance;
            private readonly int _colorScheme;
            private readonly int _viewportBackground;
            private readonly bool _restore;

            public SolidWorksWhiteViewportBackgroundScope(ISldWorks swApp)
            {
                _swApp = swApp;
                if (_swApp == null)
                {
                    return;
                }

                try
                {
                    _backgroundAppearance = _swApp.GetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance);
                    _colorScheme = _swApp.GetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme);
                    _viewportBackground = _swApp.GetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground);
                    _restore = true;
                }
                catch
                {
                    _restore = false;
                    return;
                }

                try
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance, 0);
                }
                catch
                {
                    // ignore
                }

                try
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme,
                        (int)swSystemColorsCurrentColorScheme_e.swSystemColorsCurrentColorSchemeBlueHighlight);
                }
                catch
                {
                    // ignore
                }

                try
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground, 16777215);
                }
                catch
                {
                    // ignore
                }
            }

            public void Dispose()
            {
                if (!_restore || _swApp == null)
                {
                    return;
                }

                try
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance,
                        _backgroundAppearance);
                }
                catch
                {
                    // ignore restore errors
                }

                try
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swSystemColorsCurrentColorScheme,
                        _colorScheme);
                }
                catch
                {
                    // ignore restore errors
                }

                try
                {
                    _swApp.SetUserPreferenceIntegerValue(
                        (int)swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground,
                        _viewportBackground);
                }
                catch
                {
                    // ignore restore errors
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
                        bool prevUserControl = true;
                        bool prevUserControlBackground = true;
                        try
                        {
                            prevUserControl = _swApp.UserControl;
                            prevUserControlBackground = _swApp.UserControlBackground;
                        }
                        catch
                        {
                            // ignore state read errors
                        }

                        try
                        {
                            // Suppress the "save changes?" dialog: the target may have been dirtied
                            // (e.g. ForceRebuild3 during PNG/PLY capture) since it was activated.
                            try { _swApp.UserControl = false; } catch { /* ignore */ }
                            try { _swApp.UserControlBackground = true; } catch { /* ignore */ }

                            closeFallback = true;
                            _swApp.CloseDoc(closeTitle);
                        }
                        catch
                        {
                            // ignore close errors
                        }
                        finally
                        {
                            try { _swApp.UserControl = prevUserControl; } catch { /* ignore */ }
                            try { _swApp.UserControlBackground = prevUserControlBackground; } catch { /* ignore */ }
                        }

                        afterVisible = IsTargetVisible();
                        if (afterVisible)
                        {
                            SafeWrite("WARNING: " + closeTitle + " still visible after CloseDoc");
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
        private volatile bool _stopAfterCurrentItemRequested;
        private readonly HashSet<string> _closeWarningOnce = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly HashSet<string> _debugOnce = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly object _sessionLock = new object();
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

        private ExportSessionState CreateDeliverablesExportSessionState(List<PhysicalExportQueueItem> queue, PublishOptions options,
            string rootModelPath, string rootConfigName, string planPath, string logPath)
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
                foreach (PhysicalExportQueueItem item in queue)
                {
                    if (item != null)
                    {
                        item.Status = ExportItemStatusPending;
                        item.CompletedUtc = string.Empty;
                        state.PhysicalQueue.Add(item);
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

                return state;
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "SESSION load failed: " + ex.Message);
                return null;
            }
        }

        private ExportSessionState LoadLatestIncompletePhysicalExportSession(Action<string> errorLog)
        {
            ExportSessionState state = LoadExportSession(GetActiveExportSessionPath(), errorLog);
            if (state == null)
            {
                return null;
            }

            // Only sessions written by the current (PhysicalExportQueueItem-based) pipeline are resumable
            // here; older schema versions belong to the legacy PlannedRef-based pipeline and are discarded.
            if (state.SchemaVersion != ExportSessionSchemaVersion)
            {
                return null;
            }

            if (state.PhysicalQueue == null || state.PhysicalQueue.Count == 0)
            {
                return null;
            }

            if (!IsSessionResumable(state.Status))
            {
                return null;
            }

            return state;
        }

        private string NormalizePathForComparison(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            try
            {
                return Path.GetFullPath(path).Trim().TrimEnd('\\', '/');
            }
            catch
            {
                return (path ?? string.Empty).Trim().Replace('/', '\\').TrimEnd('\\');
            }
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
            return LoadLatestIncompletePhysicalExportSession(null) != null;
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
            ReopenDocInfo startDocInfo = null;
            ReopenDocInfo rootDocInfo = null;
            bool rootClosedForExport = false;
            string startTitle = string.Empty;
            string startPathSnapshot = string.Empty;

            string BuildCompletionMessage(string statusLabel)
            {
                ExportSummary s = _currentExportSummary;
                int ok = 0;
                int fail = 0;
                if (s != null)
                {
                    ok = s.ModelOk3mf + s.ModelOkStl + s.ModelOkPly + s.ModelOkStep + s.ModelOkEdraw + s.ModelOkPng +
                         s.DwgOkPdf + s.DwgOkEdraw + s.DwgOkPng + s.DwgOkDxf;
                    fail = GetDeliverableFailureFormatCount(s);
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
                ResetStopAfterCurrentItem();
                _closeWarningOnce.Clear();
                _debugOnce.Clear();

                HashSet<string> uploadPackBases = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras =
                    effective.CreateUploadPack && effective.UploadPackIncludeExtras
                        ? new List<UploadPackBuilder.AssociatedFilesBundle>()
                        : null;

                ModelDoc2 startDoc = _swApp.ActiveDoc as ModelDoc2;
                if (startDoc == null)
                {
                    Log(log, BuildRunLogMessage("Export aborted: no active document.", runLog));
                    return;
                }

                startDocInfo = CaptureDocumentReopenInfo(startDoc);
                try
                {
                    startTitle = startDoc.GetTitle() ?? string.Empty;
                }
                catch
                {
                    startTitle = string.Empty;
                }
                try
                {
                    startPathSnapshot = startDoc.GetPathName() ?? string.Empty;
                }
                catch
                {
                    startPathSnapshot = string.Empty;
                }

                HashSet<string> initialVisibleDocs = GetOpenVisibleDocumentIds();
                _currentExportSummary.BaselineVisibleDocIds = new HashSet<string>(initialVisibleDocs, StringComparer.OrdinalIgnoreCase);
                _currentExportSummary.InitialVisibleDocs = initialVisibleDocs.Count;

                ModelDoc2 swModel = startDoc;
                Configuration swConf = swModel.GetActiveConfiguration() as Configuration;
                int modelType = swModel.GetType();
                if (modelType == (int)swDocumentTypes_e.swDocDRAWING)
                {
                    DrawingDoc swDraw = swModel as DrawingDoc;
                    DrawingReference reference;
                    if (TryGetDrawingReference(swDraw, out reference) && reference.Model != null && reference.Configuration != null)
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

                TryShowConfiguration(swModel, swConf.Name ?? string.Empty);

                string deliverablesFolder = EnsureTrailingSlash(effective.DeliverablesFolder);
                if (string.IsNullOrWhiteSpace(deliverablesFolder))
                {
                    throw new InvalidOperationException("Deliverables folder is empty.");
                }

                string bomRoot = EnsureTrailingSlash(effective.BomFolder);
                if (string.IsNullOrWhiteSpace(bomRoot))
                {
                    throw new InvalidOperationException("BOM folder is empty.");
                }

                string bomFolder = Path.Combine(bomRoot, "bom");
                Directory.CreateDirectory(bomFolder);
                Directory.CreateDirectory(deliverablesFolder);
                EnsureMediaFolders(deliverablesFolder);

                ModelView view = swModel.ActiveView as ModelView;
                bool prevGraphics = view != null && view.EnableGraphicsUpdate;

                ModelDoc2 rootModel = swModel;
                string rootTitle = string.Empty;
                try
                {
                    rootTitle = swModel.GetTitle() ?? string.Empty;
                }
                catch
                {
                    rootTitle = string.Empty;
                }
                rootDocInfo = CaptureDocumentReopenInfo(rootModel);

                _activeBatchRootTitle = rootTitle ?? string.Empty;
                _activeBatchRootDocType = modelType;

                try
                {
                    if (view != null)
                    {
                        view.EnableGraphicsUpdate = false;
                    }
                }
                catch
                {
                    // ignore
                }

                try
                {
                    if (swModel.FeatureManager != null)
                    {
                        swModel.FeatureManager.EnableFeatureTree = false;
                    }
                }
                catch
                {
                    // ignore
                }

                List<DeliverablePlan> fullManifest;
                List<DeliverablePlan> prunedManifest;
                List<PhysicalExportQueueItem> queue;
                try
                {
                    SafeLog(errorLog, "PHASE MANIFEST start");
                    fullManifest = BuildDeliverablesManifestFromActiveDocument(
                        rootModel,
                        swConf,
                        modelType,
                        effective,
                        log,
                        errorLog,
                        uploadPackBases,
                        uploadPackExtras);
                    SafeLog(errorLog, "PHASE MANIFEST end items=" + fullManifest.Count);

                    prunedManifest = PruneManifestAgainstExistingOutputs(fullManifest, effective, deliverablesFolder, errorLog);
                    queue = BuildPhysicalExportQueue(prunedManifest, errorLog);
                }
                finally
                {
                    try
                    {
                        if (swModel != null && swModel.FeatureManager != null)
                        {
                            swModel.FeatureManager.EnableFeatureTree = true;
                        }
                    }
                    catch
                    {
                        // ignore
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
                        // ignore
                    }
                }

                if (_currentExportSummary != null)
                {
                    _currentExportSummary.DeliverablePlansPlanned = fullManifest.Count;
                    _currentExportSummary.DeliverablePlansSkipped = Math.Max(0, fullManifest.Count - prunedManifest.Count);
                }

                ModelDoc2 queueRootModel = rootModel;
                if (effective.TopLevelOnly)
                {
                    // Active document is exported directly; no root close/reopen involved.
                }
                else if (effective.CreateUploadPack)
                {
                    SafeLog(errorLog, "ROOT close optimization skipped: upload pack needs root context");
                }
                else if (queue.Count > 0)
                {
                    string rootClosePath = rootDocInfo != null ? (rootDocInfo.Path ?? string.Empty) : string.Empty;
                    string rootCloseTitle = rootDocInfo != null ? (rootDocInfo.Title ?? string.Empty) : string.Empty;
                    string rootDirtyReason;
                    if (string.IsNullOrWhiteSpace(rootClosePath))
                    {
                        SafeLog(errorLog, "ROOT close optimization skipped: root has no saved path.");
                    }
                    else if (!File.Exists(rootClosePath))
                    {
                        SafeLog(errorLog, "ROOT close optimization skipped: root path not found. path=" + rootClosePath);
                    }
                    else if (rootModel == null)
                    {
                        SafeLog(errorLog, "ROOT close optimization skipped: root model unavailable. path=" + rootClosePath);
                    }
                    else if (IsDocDirtyOrUnsaved(rootModel, out rootDirtyReason))
                    {
                        SafeLog(errorLog, "ROOT close optimization skipped: root is dirty/unsaved (" + rootDirtyReason + ").");
                    }
                    else
                    {
                        ForceCloseDocNoSave(rootModel, errorLog, "deliverables-root-close");
                        if (IsDocOpenByIdOrTitle(rootClosePath, rootCloseTitle))
                        {
                            SafeLog(errorLog,
                                "WARN: root close optimization failed; continuing with live root. path=" + rootClosePath);
                        }
                        else
                        {
                            rootClosedForExport = true;
                            queueRootModel = null;
                            rootModel = null;
                            SafeLog(errorLog, "ROOT close optimization active. path=" + rootClosePath);
                        }
                    }
                }

                if (!AnyDeliverablesSelected(effective))
                {
                    UpdateProgress(progress, 0, 0);
                }
                else if (queue.Count == 0)
                {
                    Log(log, "No deliverables to export.");
                    UpdateProgress(progress, 0, 0);
                }
                else
                {
                    ExportSessionState deliverablesSession = CreateDeliverablesExportSessionState(
                        queue,
                        effective,
                        rootDocInfo != null ? (rootDocInfo.Path ?? string.Empty) : string.Empty,
                        swConf != null ? (swConf.Name ?? string.Empty) : string.Empty,
                        string.Empty,
                        runLog != null ? (runLog.Path ?? string.Empty) : string.Empty);
                    deliverablesSession.Status = ExportSessionStatusRunning;
                    SetActiveExportSession(deliverablesSession);
                    SaveExportSessionAtomic(deliverablesSession, errorLog);

                    RunPhysicalExportQueue(queue, queueRootModel, deliverablesFolder, effective, log, errorLog, progress, deliverablesSession);

                    if (_currentExportSummary != null && _currentExportSummary.StoppedAfterCurrentFile)
                    {
                        deliverablesSession.Status = ExportSessionStatusPaused;
                        SaveExportSessionAtomic(deliverablesSession, errorLog);
                    }
                    else
                    {
                        deliverablesSession.Status = ExportSessionStatusCompleted;
                        SaveExportSessionAtomic(deliverablesSession, errorLog);
                        ArchiveCompletedExportSession(deliverablesSession, errorLog);
                        SetActiveExportSession(null);
                    }
                }

                if (effective.CreateUploadPack)
                {
                    if (_currentExportSummary != null && _currentExportSummary.StoppedAfterCurrentFile)
                    {
                        Log(log, "Upload pack skipped because export stopped early.");
                    }
                    else
                    {
                        string flatFile = BuildUploadPackFlatBomFromManifest(fullManifest, bomFolder, errorLog);
                        try
                        {
                            rootModel = RestoreDocumentFromSnapshot(
                                rootDocInfo,
                                errorLog,
                                rootClosedForExport ? "deliverables-root-reopen-upload-pack" : "deliverables-root-activate-upload-pack",
                                true);
                        }
                        catch
                        {
                            // ignore activate errors
                        }

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
                }

                string completedLabel = "Export completed";
                ExportSummary finalSummary = _currentExportSummary;
                if (finalSummary != null && finalSummary.StoppedAfterCurrentFile)
                {
                    completedLabel = "Export stopped after current file";
                }
                else if (finalSummary != null && GetDeliverableFailureFormatCount(finalSummary) > 0)
                {
                    completedLabel = "Export completed with warnings";
                }

                try
                {
                    if (_currentExportSummary != null)
                    {
                        _currentExportSummary.FinalVisibleDocs = GetOpenVisibleDocumentIds().Count;
                    }
                }
                catch
                {
                    // ignore
                }

                Log(log, BuildCompletionMessage(completedLabel));
            }
            catch (OperationCanceledException)
            {
                Log(log, BuildCompletionMessage("Export cancelled"));
            }
            catch (Exception ex)
            {
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
                    if (rootClosedForExport)
                    {
                        RestoreDocumentFromSnapshot(rootDocInfo, errorLog, "deliverables-root-reopen-final", false);
                    }

                    RestoreDocumentFromSnapshot(startDocInfo, errorLog, "deliverables-start-restore-final", true);
                    if (!IsDocOpenByIdOrTitle(startPathSnapshot, startTitle))
                    {
                        SafeLog(errorLog,
                            "WARN: start document not open after export. title=" + (startTitle ?? string.Empty) +
                            " path=" + (startPathSnapshot ?? string.Empty));
                    }

                    if (_currentExportSummary != null)
                    {
                        _currentExportSummary.FinalVisibleDocs = GetOpenVisibleDocumentIds().Count;
                    }
                }
                catch
                {
                    // ignore restore errors
                }

                try
                {
                    ExportSummary summary = _currentExportSummary;
                    if (summary != null)
                    {
                        WriteDeliverablesFailureSummary(errorLog, summary);

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
                        ResetStopAfterCurrentItem();
                    }
                    catch
                    {
                        // ignore cancel-reset errors
                    }

                    _activeBatchRootTitle = string.Empty;
                    _activeBatchRootDocType = 0;
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

        public void ResumeLastCreateFilesExport(Action<string> log, Action<int, int> progress)
        {
            ExportSessionState session = LoadLatestIncompletePhysicalExportSession(null);
            if (session == null)
            {
                throw new InvalidOperationException("No incomplete export session available.");
            }

            ModelDoc2 rootModel = _swApp != null ? (_swApp.ActiveDoc as ModelDoc2) : null;
            string rootPath = string.Empty;
            try
            {
                rootPath = rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty;
            }
            catch
            {
                rootPath = string.Empty;
            }

            if (rootModel == null ||
                !string.Equals(NormalizePathForComparison(rootPath), NormalizePathForComparison(session.RootModelPath),
                    StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "Resume requires the original root document to be open and active in SolidWorks: " +
                    (session.RootModelPath ?? string.Empty));
            }

            PublishOptions effective = NormalizeOptions(ClonePublishOptions(session.Options));
            ExportRunLog runLog = OpenExportRunLog(session.LogPath);
            Action<string> errorLog = runLog != null ? new Action<string>(runLog.Write) : null;
            SetLastRunLogPath(runLog);
            session.LogPath = runLog != null ? (runLog.Path ?? string.Empty) : (session.LogPath ?? string.Empty);
            SetActiveExportSession(session);
            errorLog?.Invoke("RESUME create-files export session=" + (session.SessionId ?? string.Empty) +
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
                    fail = GetDeliverableFailureFormatCount(s);
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
                ResetStopAfterCurrentItem();
                _closeWarningOnce.Clear();
                _debugOnce.Clear();

                List<PhysicalExportQueueItem> pendingItems = new List<PhysicalExportQueueItem>();
                int totalItems = session.PhysicalQueue != null ? session.PhysicalQueue.Count : 0;
                if (session.PhysicalQueue != null)
                {
                    foreach (PhysicalExportQueueItem item in session.PhysicalQueue)
                    {
                        if (item != null && !string.Equals(item.Status, ExportItemStatusDone, StringComparison.OrdinalIgnoreCase))
                        {
                            pendingItems.Add(item);
                        }
                    }
                }

                int completeItems = totalItems - pendingItems.Count;
                errorLog?.Invoke("RESUME plan: total=" + totalItems + " complete=" + completeItems + " pending=" + pendingItems.Count);
                UpdateProgress(progress, completeItems, totalItems);

                if (pendingItems.Count == 0)
                {
                    session.Status = ExportSessionStatusCompleted;
                    SaveExportSessionAtomic(session, errorLog);
                    ArchiveCompletedExportSession(session, errorLog);
                    SetActiveExportSession(null);
                    Log(log, BuildRunLogMessage("Nothing left to resume. Existing completed items were kept.", runLog));
                    return;
                }

                Log(log, "Resuming export: " + completeItems + "/" + totalItems + " already complete, " + pendingItems.Count + " remaining.");
                session.Status = ExportSessionStatusRunning;
                SaveExportSessionAtomic(session, errorLog);

                string deliverablesFolder = EnsureTrailingSlash(effective.DeliverablesFolder);
                if (string.IsNullOrWhiteSpace(deliverablesFolder))
                {
                    throw new InvalidOperationException("Deliverables folder is empty.");
                }

                Directory.CreateDirectory(deliverablesFolder);
                EnsureMediaFolders(deliverablesFolder);

                RunPhysicalExportQueue(pendingItems, rootModel, deliverablesFolder, effective, log, errorLog, progress, session);

                if (_currentExportSummary != null && _currentExportSummary.StoppedAfterCurrentFile)
                {
                    session.Status = ExportSessionStatusPaused;
                    SaveExportSessionAtomic(session, errorLog);
                    Log(log, BuildCompletionMessage("Export paused"));
                    return;
                }

                session.Status = ExportSessionStatusCompleted;
                SaveExportSessionAtomic(session, errorLog);
                ArchiveCompletedExportSession(session, errorLog);
                SetActiveExportSession(null);

                Log(log, BuildCompletionMessage("Export resumed and completed"));
            }
            catch (OperationCanceledException)
            {
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
                    LogExceptionDetails(errorLog, "ResumeLastCreateFilesExport", ex);
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
                        ResetStopAfterCurrentItem();
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
            var bomTimer = System.Diagnostics.Stopwatch.StartNew();
            try
            {
                errorLog?.Invoke("BOM start: title=" + (rootTitle ?? string.Empty) +
                                 " path=" + (rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty) +
                                 " config=" + (swConf.Name ?? string.Empty) +
                                 " topLevelOnly=" + effective.TopLevelOnly);

                string modelPath = swModel.GetPathName();
                if (string.IsNullOrWhiteSpace(modelPath))
                {
                    ShowSaveBeforeExportPrompt("BOM export", swModel, "unsaved", errorLog);
                    Log(log, BuildRunLogMessage("BOM export aborted: active document must be saved before exporting BOM.", runLog));
                    return;
                }

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

                errorLog?.Invoke("BOM PHASE 1/3: flat BOM traverse+write start");
                long flatStartMs = bomTimer.ElapsedMilliseconds;
                string flatFile = TraverseModel(exportTag, effective, log, progress);
                errorLog?.Invoke("BOM PHASE 1/3: flat BOM done file=" + flatFile +
                                 " elapsedMs=" + (bomTimer.ElapsedMilliseconds - flatStartMs));

                ThrowIfCancelled();
                string bomFile = exportTag + "_TREEBOM.txt";
                errorLog?.Invoke("BOM PHASE 2/3: tree BOM (temp assembly) start");
                long treeStartMs = bomTimer.ElapsedMilliseconds;
                bool treeOk = TryBuildBomWithUnsavedTempAssembly(swModel, bomFile, "BOM export", log, errorLog);
                errorLog?.Invoke("BOM PHASE 2/3: tree BOM done ok=" + treeOk +
                                 " elapsedMs=" + (bomTimer.ElapsedMilliseconds - treeStartMs));

                errorLog?.Invoke("BOM PHASE 3/3: zip start");
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
                errorLog?.Invoke("BOM PHASE 3/3: zip done path=" + zipPath);

                errorLog?.Invoke("BOM SUMMARY: ok treeBom=" + treeOk +
                                 " totalElapsedMs=" + bomTimer.ElapsedMilliseconds);
                Log(log, BuildRunLogMessage("BOM file generation finished.", runLog));
            }
            catch (OperationCanceledException)
            {
                errorLog?.Invoke("BOM SUMMARY: cancelled totalElapsedMs=" + bomTimer.ElapsedMilliseconds);
                Log(log, BuildRunLogMessage("BOM export cancelled.", runLog));
            }
            catch (Exception ex)
            {
                errorLog?.Invoke("BOM export failed: " + ex);
                errorLog?.Invoke("BOM SUMMARY: failed totalElapsedMs=" + bomTimer.ElapsedMilliseconds);
                Log(log, BuildRunLogMessage("BOM export failed: " + ex.Message, runLog));
            }
            finally
            {
                // Close only documents that BECAME VISIBLE during the run; hidden in-memory references
                // are left to SolidWorks (closing them one-by-one hung BOM export on large assemblies).
                CloseNonRootDocs(initialDocs, rootModel, rootTitle);
                CloseModelIfNotInitiallyOpen(initialDocs, rootModel, startTitle);
                RestoreStartDocument(startTitle);
                errorLog?.Invoke("BOM cleanup done. visibleDocs=" + GetOpenVisibleDocumentIds().Count);
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
                string flatFile = TraverseModel(string.Empty, effective, log, null, errorLog,
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

        private string TraverseModel(string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress)
        {
            HashSet<string> ignored;
            List<UploadPackBuilder.AssociatedFilesBundle> ignoredExtras;
            return TraverseModel(exportTag, options, log, flatBomProgress, null, out ignored, out ignoredExtras);
        }

        // Traverses the active model's BOM (unique part-number/revision pairs) and writes the FLATBOM file.
        // Used by the BOM export and the upload pack; the Create Files pipeline plans in memory instead.
        private string TraverseModel(string exportTag, PublishOptions options, Action<string> log,
            Action<int, int> flatBomProgress, Action<string> errorLog,
            out HashSet<string> uploadPackBases, out List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras)
        {
            uploadPackBases = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            uploadPackExtras = null;
            ModelDoc2 swModel = _swApp.ActiveDoc as ModelDoc2;
            if (swModel == null)
            {
                throw new InvalidOperationException("No active document.");
            }

            var phaseTimer = System.Diagnostics.Stopwatch.StartNew();
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

            // Baseline of VISIBLE docs/tabs the user has open at the start of the run; the run must
            // not leave extra visible documents behind.
            HashSet<string> initialVisibleDocs = GetOpenVisibleDocumentIds();
            SafeLog(errorLog, "BASELINE visible docs: count=" + initialVisibleDocs.Count);
            LogVisibleDocuments(errorLog, "BASELINE");

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

            ModelView view = swModel.ActiveView as ModelView;
            bool prevGraphics = view != null && view.EnableGraphicsUpdate;

            ModelDoc2 rootModel = swModel;
            string rootTitle = swModel.GetTitle();

            SafeLog(errorLog,
                "TRAVERSE run start startTitle=" + (startTitle ?? string.Empty) +
                " rootTitle=" + (rootTitle ?? string.Empty) +
                " rootPath=" + (rootModel != null ? (rootModel.GetPathName() ?? string.Empty) : string.Empty) +
                " topLevelOnly=" + (options != null && options.TopLevelOnly) +
                " initialVisibleDocs=" + initialVisibleDocs.Count);

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

                BatchTraverseResult traverse = TraverseModelsForBatch(swModel, swConf, modelType, options.TopLevelOnly, log, errorLog);
                int planned = traverse != null && traverse.Unique != null ? traverse.Unique.Count : 0;

                Log(log, "Planned unique model-config pairs: " + planned);
                SafeLog(errorLog, "PHASE TRAVERSE total elapsedMs=" + phaseTimer.ElapsedMilliseconds + " planned=" + planned);
                if (_currentExportSummary != null)
                {
                    _currentExportSummary.PlannedModelConfigPairs = planned;
                    _currentExportSummary.FlatBomUnresolvedComponents = traverse != null ? traverse.UnresolvedComponents : 0;
                }

                string outputFile;
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

                SafeLog(errorLog, "TRAVERSE run end output=" + outputFile + " elapsedMs=" + phaseTimer.ElapsedMilliseconds);
                return outputFile;
            }
            finally
            {
                try
                {
                    if (swModel != null && swModel.FeatureManager != null)
                    {
                        swModel.FeatureManager.EnableFeatureTree = true;
                    }
                }
                catch
                {
                    // ignore (root doc may have been closed during the run)
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
                    // ignore (view may be invalid after doc close)
                }

                RestoreStartDocument(startTitle);

                try
                {
                    if (!IsDocOpenByIdOrTitle(startPathSnapshot, startTitle))
                    {
                        SafeLog(errorLog, "CRITICAL: start document not open after traverse. title=" +
                                 (startTitle ?? string.Empty) + " path=" + (startPathSnapshot ?? string.Empty));
                    }
                }
                catch
                {
                    // ignore root-check errors
                }

                LogVisibleDocDelta(initialVisibleDocs, errorLog, "TraverseModel end");
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

        private ReopenDocInfo CaptureDocumentReopenInfo(ModelDoc2 doc)
        {
            if (doc == null)
            {
                return null;
            }

            var info = new ReopenDocInfo();
            try
            {
                info.Path = doc.GetPathName() ?? string.Empty;
            }
            catch
            {
                info.Path = string.Empty;
            }

            try
            {
                info.Title = doc.GetTitle() ?? string.Empty;
            }
            catch
            {
                info.Title = string.Empty;
            }

            try
            {
                info.DocType = doc.GetType();
            }
            catch
            {
                info.DocType = DocumentTypeFromPath(info.Path);
            }

            if (info.DocType != (int)swDocumentTypes_e.swDocDRAWING)
            {
                try
                {
                    Configuration config = doc.GetActiveConfiguration() as Configuration;
                    info.ConfigurationName = config != null ? (config.Name ?? string.Empty) : string.Empty;
                }
                catch
                {
                    info.ConfigurationName = string.Empty;
                }
            }

            return info;
        }

        private ModelDoc2 RestoreDocumentFromSnapshot(ReopenDocInfo info, Action<string> errorLog, string context, bool activate)
        {
            if (info == null)
            {
                return null;
            }

            ModelDoc2 doc = FindOpenDocument(info.Path, info.Title);
            if (doc == null)
            {
                int specErr = 0;
                int specWarn = 0;
                doc = OpenDocSilent(
                    info.Path,
                    info.DocType == 0 ? DocumentTypeFromPath(info.Path) : info.DocType,
                    info.ConfigurationName,
                    false,
                    true,
                    errorLog,
                    context,
                    out specErr,
                    out specWarn);
                if (doc == null)
                {
                    SafeLog(errorLog,
                        "WARN: document restore failed context=" + (context ?? string.Empty) +
                        " title=" + (info.Title ?? string.Empty) +
                        " path=" + (info.Path ?? string.Empty) +
                        " specErr=" + specErr +
                        " specWarn=" + specWarn);
                    return null;
                }
            }

            TrySetDocumentVisible(doc, true);
            if (!string.IsNullOrWhiteSpace(info.ConfigurationName) &&
                info.DocType != (int)swDocumentTypes_e.swDocDRAWING)
            {
                TryShowConfiguration(doc, info.ConfigurationName);
            }

            if (activate)
            {
                TryActivateDocument(doc, errorLog, context);
            }

            return doc;
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

        // Closes the unsaved temporary BOM assembly without saving and without prompts.
        // Returns true when the document is confirmed closed.
        private bool CloseTempAssemblyNoSaveNoPrompt(ModelDoc2 tempAssembly, Action<string> errorLog, string context)
        {
            if (tempAssembly == null)
            {
                return true;
            }

            string title = string.Empty;
            string path = string.Empty;
            bool dirtyBeforeClose = false;
            try
            {
                title = tempAssembly.GetTitle() ?? string.Empty;
            }
            catch
            {
                title = string.Empty;
            }
            try
            {
                path = tempAssembly.GetPathName() ?? string.Empty;
            }
            catch
            {
                path = string.Empty;
            }
            try
            {
                dirtyBeforeClose = tempAssembly.GetSaveFlag();
            }
            catch
            {
                dirtyBeforeClose = false;
            }

            SafeLog(errorLog,
                "TEMP BOM ASM close start context=" + (context ?? string.Empty) +
                " title=" + title +
                " path=" + path +
                " dirty=" + dirtyBeforeClose);

            ForceCloseDocNoSave(tempAssembly, errorLog, context ?? "temp assembly close");

            bool stillOpen = IsDocOpenByIdOrTitle(path, title);
            SafeLog(errorLog,
                "TEMP BOM ASM close end context=" + (context ?? string.Empty) +
                " title=" + title +
                " ok=" + !stillOpen);
            return !stillOpen;
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

        private bool TryBuildBomWithUnsavedTempAssembly(
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
                ShowSaveBeforeExportPrompt(contextLabel, rootModel, "unsaved", errorLog);
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
            SafeLog(errorLog,
                "TEMP BOM ASM create dir=" + tempDirectory +
                " virtualPath=" + tempAssemblyPath +
                " context=" + contextLabel);

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

                    ThrowIfCancelled();

                    Configuration assyConfig = assyDoc.GetActiveConfiguration() as Configuration;
                    if (assyConfig == null)
                    {
                        Log(log, contextLabel + ": failed to read temporary assembly configuration.");
                        return false;
                    }

                    SetUnitPreferences(assyDoc);

                    string tempBomPath;
                    bool skip;
                    string prepareReason;
                    string quarantinedExistingPath;
                    if (!TryPrepareExportOutput("txt", outputBomPath, true, errorLog, out tempBomPath, out skip,
                        out prepareReason, out quarantinedExistingPath))
                    {
                        Log(log, contextLabel + ": failed to prepare BOM output path.");
                        SafeLog(errorLog,
                            "TEMP BOM ASM prepare output failed context=" + contextLabel +
                            " output=" + outputBomPath +
                            " reason=" + (prepareReason ?? string.Empty));
                        return false;
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

                    // Ungroup BOM rows: configurations of the same part must be listed as separate
                    // items, otherwise grouped rows lose their per-configuration part numbers and the
                    // TREEBOM import mislinks them.
                    try
                    {
                        BomFeature bomFeature = bomTable.BomFeature;
                        if (bomFeature != null)
                        {
                            bomFeature.PartConfigurationGrouping =
                                (int)swPartConfigurationGroupingOption_e.swDisplay_ConfigurationOfSamePart_AsSeparateItem;
                            bomFeature.DisplayAsOneItem = false;
                            TryRebuildDocument(assyDoc, errorLog, contextLabel + " post-ungroup");
                            SafeLog(errorLog, "TEMP BOM ASM ungroup ok: configurations listed as separate items context=" + contextLabel);
                        }
                        else
                        {
                            SafeLog(errorLog, "TEMP BOM ASM ungroup skipped: BomFeature unavailable context=" + contextLabel);
                        }
                    }
                    catch (Exception ex)
                    {
                        SafeLog(errorLog, "TEMP BOM ASM ungroup failed (grouped rows may remain) context=" + contextLabel +
                            " error=" + ex.Message);
                    }

                    ITableAnnotation tableAnn = (ITableAnnotation)bomTable;
                    tableAnn.SaveAsText(tempBomPath, "\t");
                    TextFileHelper.StripUtf8Bom(tempBomPath);
                    SafeLog(errorLog, "TEMP BOM ASM table rows=" + SafeTableRowCount(tableAnn) +
                        " context=" + contextLabel);

                    ExportOutputResult exportResult = TryFinalizeExportedTempFile("txt", tempBomPath, outputBomPath, errorLog);
                    exportResult.QuarantinedExistingPath = quarantinedExistingPath ?? string.Empty;
                    SafeLog(errorLog,
                        "TEMP BOM ASM text export ok=" + exportResult.Success +
                        " tempValidated=" + exportResult.TempValidated +
                        " bytes=" + exportResult.Bytes +
                        " output=" + outputBomPath +
                        " temp=" + (tempBomPath ?? string.Empty) +
                        " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                        " reason=" + (exportResult.Reason ?? string.Empty) +
                        " context=" + contextLabel);
                    if (!exportResult.Success)
                    {
                        Log(log, contextLabel + ": BOM text export failed.");
                        return false;
                    }

                    TryRestoreActiveDocument(activeBeforeTempNorm, errorLog, contextLabel + " post-text-export");
                    TrySetDocumentVisible(assyDoc, false);

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
                        closeOk = CloseTempAssemblyNoSaveNoPrompt(assyDoc, errorLog, contextLabel + " temp assembly close");
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

        private int SafeTableRowCount(ITableAnnotation table)
        {
            try
            {
                return table != null ? table.RowCount : -1;
            }
            catch
            {
                return -1;
            }
        }

        private bool TryBuildTreeBom(ModelDoc2 rootModel, string treeBomPath, Action<string> log, Action<string> errorLog)
        {
            return TryBuildBomWithUnsavedTempAssembly(rootModel, treeBomPath, "Upload pack TREEBOM", log, errorLog);
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
            catch (Exception ex)
            {
                revision = string.Empty;
                SafeLog(errorLog, "TRAVERSE revision read failed path=" + (path ?? string.Empty) +
                    " conf=" + (configName ?? string.Empty) + " error=" + ex.Message);
            }

            string identity = !string.IsNullOrWhiteSpace(path) ? path : title;
            string key = BuildComponentTag(identity, configName, revision);
            if (result.ByKey.ContainsKey(key))
            {
                return;
            }

            DebugExport(errorLog, "TRAVERSE add pn-source=" + (path ?? string.Empty) +
                " conf=" + (configName ?? string.Empty) +
                " rev=" + revision +
                " docType=" + docType +
                (isRoot ? " root=true" : string.Empty));

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

        private bool HasRequestedModelExports(DeliverablePlan plan)
        {
            return plan != null &&
                   (plan.ExportPngModel || plan.ExportStep || plan.ExportEdrawing || plan.Export3mf || plan.ExportPly || plan.ExportStl);
        }

        private bool HasRequestedDrawingExports(DeliverablePlan plan)
        {
            return plan != null &&
                   (plan.ExportPdf || plan.ExportDxf || plan.ExportPngDrawing || plan.ExportEdrawingDrawing);
        }

        private string GetModelEdrawingPath(DeliverablePlan plan, string deliverablesFolder)
        {
            if (plan == null)
            {
                return string.Empty;
            }

            string ext = plan.DocType == (int)swDocumentTypes_e.swDocASSEMBLY ? ".easm" : ".eprt";
            return Path.Combine(deliverablesFolder, "edr", (plan.FileString ?? string.Empty) + ext);
        }

        private string GetOutputPath(DeliverablePlan plan, string deliverablesFolder, string format)
        {
            if (plan == null || string.IsNullOrWhiteSpace(deliverablesFolder))
            {
                return string.Empty;
            }

            string fileString = plan.FileString ?? string.Empty;
            switch ((format ?? string.Empty).Trim().ToLowerInvariant())
            {
                case "png":
                    return Path.Combine(deliverablesFolder, "png", fileString + ".png");
                case "step":
                    return Path.Combine(deliverablesFolder, "step", fileString + ".step");
                case "edr":
                    return GetModelEdrawingPath(plan, deliverablesFolder);
                case "3mf":
                    return Path.Combine(deliverablesFolder, "3mf", fileString + ".3mf");
                case "ply":
                    return Path.Combine(deliverablesFolder, "ply", fileString + ".ply");
                case "stl":
                    return Path.Combine(deliverablesFolder, "stl", fileString + ".stl");
                case "pdf":
                    return Path.Combine(deliverablesFolder, "pdf", fileString + ".pdf");
                case "dxf":
                    return Path.Combine(deliverablesFolder, "dxf", fileString + ".dxf");
                case "png_dwg":
                    return Path.Combine(deliverablesFolder, "png", fileString + "_DWG.png");
                case "edrw":
                    return Path.Combine(deliverablesFolder, "edr", fileString + ".edrw");
                default:
                    return string.Empty;
            }
        }

        private DeliverablePlan BuildDeliverablesManifestItemFromModel(ModelDoc2 model, string confName, PlannedRef planned,
            PublishOptions options, Action<string> errorLog)
        {
            if (model == null || options == null)
            {
                return null;
            }

            string modelPath = string.Empty;
            string modelTitle = string.Empty;
            int docType = 0;
            try
            {
                modelPath = model.GetPathName() ?? string.Empty;
            }
            catch
            {
                modelPath = string.Empty;
            }

            try
            {
                modelTitle = model.GetTitle() ?? string.Empty;
            }
            catch
            {
                modelTitle = string.Empty;
            }

            try
            {
                docType = model.GetType();
            }
            catch
            {
                docType = planned != null && planned.IsAssembly
                    ? (int)swDocumentTypes_e.swDocASSEMBLY
                    : DocumentTypeFromPath(modelPath);
            }

            string effectiveConf = confName ?? string.Empty;
            Configuration config = null;
            try
            {
                if (!string.IsNullOrWhiteSpace(effectiveConf))
                {
                    config = model.GetConfigurationByName(effectiveConf) as Configuration;
                }
                if (config == null)
                {
                    config = model.GetActiveConfiguration() as Configuration;
                    if (config != null && string.IsNullOrWhiteSpace(effectiveConf))
                    {
                        effectiveConf = config.Name ?? string.Empty;
                    }
                }
            }
            catch
            {
                config = null;
            }

            if (config == null)
            {
                SafeLog(errorLog,
                    "MANIFEST skip: configuration not found path=" + (modelPath ?? string.Empty) +
                    " title=" + (modelTitle ?? string.Empty) +
                    " conf=" + (confName ?? string.Empty));
                return null;
            }

            // Planning must not activate configurations: part number and revision are read directly
            // from the configuration object and its property manager. Configurations are only shown
            // at export time, right before geometry-dependent output is produced.
            string partNumber = BomPartNumber(config, model, errorLog) ?? string.Empty;
            string revision = (GetEvalProperty(model, effectiveConf, "revision") ?? string.Empty).Trim();
            string fileString = BuildFileString(partNumber, revision);
            if (string.IsNullOrWhiteSpace(partNumber) || string.IsNullOrWhiteSpace(fileString))
            {
                SafeLog(errorLog,
                    "MANIFEST skip: file identity missing path=" + (modelPath ?? string.Empty) +
                    " title=" + (modelTitle ?? string.Empty) +
                    " conf=" + (effectiveConf ?? string.Empty));
                return null;
            }

            string drawingPath = !string.IsNullOrWhiteSpace(modelPath) && !string.IsNullOrWhiteSpace(partNumber)
                ? OnlyFolder(modelPath) + partNumber + ".SLDDRW"
                : string.Empty;
            bool drawingExists = !string.IsNullOrWhiteSpace(drawingPath) && File.Exists(drawingPath);
            bool stepRequested = options.ExportStep ||
                                 HasProcess(model, effectiveConf, "FOLDING") ||
                                 HasProcess(model, effectiveConf, "MACHINE") ||
                                 HasProcess(model, effectiveConf, "3D Laser");

            return new DeliverablePlan
            {
                ModelPath = modelPath ?? string.Empty,
                ModelTitle = modelTitle ?? string.Empty,
                ConfigurationName = effectiveConf ?? string.Empty,
                FileString = fileString,
                PartNumber = partNumber ?? string.Empty,
                Revision = revision ?? string.Empty,
                DrawingPath = drawingPath ?? string.Empty,
                DocType = docType,
                IsRoot = planned != null && planned.IsRoot,
                MaxDepth = planned != null ? planned.MaxDepth : 0,
                SubtreeEstimate = planned != null ? planned.SubtreeEstimate : 0,
                DrawingExists = drawingExists,
                ExportPngModel = options.ExportPngModel,
                ExportStep = stepRequested,
                ExportEdrawing = options.ExportEdrawing,
                Export3mf = options.Export3mf,
                ExportPly = options.ExportPly,
                ExportStl = options.ExportStl,
                ExportPdf = options.ExportPdf,
                ExportDxfSelected = options.ExportDxf,
                ExportDxf = options.ExportDxf,
                ExportPngDrawing = options.ExportPngDrawing,
                ExportEdrawingDrawing = options.ExportEdrawingDrawing
            };
        }

        private void MergeDeliverablesManifestItem(DeliverablePlan target, DeliverablePlan source)
        {
            if (target == null || source == null)
            {
                return;
            }

            if (string.IsNullOrWhiteSpace(target.ModelPath) && !string.IsNullOrWhiteSpace(source.ModelPath))
            {
                target.ModelPath = source.ModelPath;
            }
            if (string.IsNullOrWhiteSpace(target.ModelTitle) && !string.IsNullOrWhiteSpace(source.ModelTitle))
            {
                target.ModelTitle = source.ModelTitle;
            }
            if (string.IsNullOrWhiteSpace(target.ConfigurationName) && !string.IsNullOrWhiteSpace(source.ConfigurationName))
            {
                target.ConfigurationName = source.ConfigurationName;
            }
            if (string.IsNullOrWhiteSpace(target.DrawingPath) && !string.IsNullOrWhiteSpace(source.DrawingPath))
            {
                target.DrawingPath = source.DrawingPath;
            }

            target.DrawingExists = target.DrawingExists || source.DrawingExists;
            target.IsRoot = target.IsRoot || source.IsRoot;
            target.MaxDepth = Math.Max(target.MaxDepth, source.MaxDepth);
            target.SubtreeEstimate = Math.Max(target.SubtreeEstimate, source.SubtreeEstimate);
            if (target.DocType == 0)
            {
                target.DocType = source.DocType;
            }
        }

        private ModelDoc2 ResolveManifestSourceModel(PlannedRef planned, Dictionary<string, Component2> componentByKey)
        {
            if (planned == null)
            {
                return null;
            }

            if (!planned.IsRoot && componentByKey != null)
            {
                Component2 component;
                if (componentByKey.TryGetValue(BuildPlannedRefKey(planned.ModelPath, planned.ConfigurationName), out component) &&
                    component != null)
                {
                    try
                    {
                        return component.GetModelDoc2() as ModelDoc2;
                    }
                    catch
                    {
                        return null;
                    }
                }
            }

            return null;
        }

        private List<DeliverablePlan> BuildDeliverablesManifestFromActiveDocument(ModelDoc2 rootModel, Configuration rootConfig,
            int modelType, PublishOptions options, Action<string> log, Action<string> errorLog, HashSet<string> uploadPackBases,
            List<UploadPackBuilder.AssociatedFilesBundle> uploadPackExtras)
        {
            var manifestByIdentity = new Dictionary<string, DeliverablePlan>(StringComparer.OrdinalIgnoreCase);
            if (rootModel == null || rootConfig == null || options == null)
            {
                return new List<DeliverablePlan>();
            }

            List<PlannedRef> plannedRefs;
            string rootPath = string.Empty;
            try
            {
                rootPath = rootModel.GetPathName() ?? string.Empty;
            }
            catch
            {
                rootPath = string.Empty;
            }

            if (options.TopLevelOnly || modelType != (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                plannedRefs = new List<PlannedRef>
                {
                    new PlannedRef
                    {
                        ModelPath = rootPath,
                        ConfigurationName = rootConfig.Name ?? string.Empty,
                        IsAssembly = modelType == (int)swDocumentTypes_e.swDocASSEMBLY,
                        MaxDepth = 0,
                        SubtreeEstimate = 0,
                        IsRoot = true
                    }
                };
            }
            else
            {
                plannedRefs = PlanRefsForDeliverables(rootModel, rootConfig, errorLog);
            }

            Dictionary<string, Component2> componentByKey = null;
            if (modelType == (int)swDocumentTypes_e.swDocASSEMBLY && !options.TopLevelOnly)
            {
                AssemblyDoc assembly = rootModel as AssemblyDoc;
                Component2 rootComponent = null;
                try
                {
                    rootComponent = rootConfig.GetRootComponent() as Component2;
                }
                catch
                {
                    rootComponent = null;
                }

                if (assembly != null)
                {
                    try
                    {
                        assembly.ResolveAllLightWeightComponents(true);
                    }
                    catch
                    {
                        // ignore resolve errors
                    }

                    int skippedEmptyPaths = 0;
                    componentByKey = PlanUniqueComponentRefsForFlatBom(assembly, rootComponent, errorLog, out skippedEmptyPaths);
                }
            }

            if (_currentExportSummary != null)
            {
                _currentExportSummary.PlannedModelConfigPairs = plannedRefs != null ? plannedRefs.Count : 0;
            }

            var extrasByIdentity = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            int unresolved = 0;
            for (int i = 0; plannedRefs != null && i < plannedRefs.Count; i++)
            {
                PlannedRef planned = plannedRefs[i];
                if (planned == null)
                {
                    continue;
                }

                if (i > 0 && i % 50 == 0)
                {
                    ThrowIfCancelled();
                    System.Windows.Forms.Application.DoEvents();
                }

                ModelDoc2 sourceModel = planned.IsRoot ? rootModel : ResolveManifestSourceModel(planned, componentByKey);
                if (sourceModel == null)
                {
                    unresolved++;
                    SafeLog(errorLog,
                        "MANIFEST unresolved component path=" + (planned.ModelPath ?? string.Empty) +
                        " conf=" + (planned.ConfigurationName ?? string.Empty));
                    continue;
                }

                DeliverablePlan item = BuildDeliverablesManifestItemFromModel(
                    sourceModel,
                    planned.ConfigurationName,
                    planned,
                    options,
                    errorLog);
                if (item == null)
                {
                    continue;
                }

                string identityKey = item.FileString ?? string.Empty;
                DeliverablePlan existing;
                if (manifestByIdentity.TryGetValue(identityKey, out existing))
                {
                    MergeDeliverablesManifestItem(existing, item);
                    continue;
                }

                manifestByIdentity[identityKey] = item;
                if (uploadPackBases != null && !string.IsNullOrWhiteSpace(identityKey))
                {
                    uploadPackBases.Add(identityKey);
                }

                if (uploadPackExtras != null && extrasByIdentity.Add(identityKey))
                {
                    AddAssociatedFiles(uploadPackExtras, sourceModel, item.ConfigurationName, log);
                }
            }

            if (_currentExportSummary != null)
            {
                _currentExportSummary.FlatBomUnresolvedComponents = unresolved;
            }

            return new List<DeliverablePlan>(manifestByIdentity.Values);
        }

        private bool IsLeanExistingOutputValid(string type, string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
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

            string normalizedType = NormalizeExportType(type, path);
            switch (normalizedType)
            {
                case "pdf":
                    return bytes >= MinPdfBytes;
                case "png":
                    return bytes >= MinPngBytes;
                case "edr":
                case "edrw":
                case "easm":
                case "eprt":
                    return bytes >= MinEdrawingBytes;
                case "stl":
                case "dxf":
                case "ply":
                    return bytes >= MinGenericMeshBytes;
                case "step":
                case "3mf":
                    return bytes >= MinGenericCadBytes;
                default:
                    return bytes > 0;
            }
        }

        private bool ShouldExportLeanOutput(string type, string path, bool overwrite, Action<string> errorLog)
        {
            if (overwrite || string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return true;
            }

            if (IsLeanExistingOutputValid(type, path))
            {
                SafeLog(errorLog, "OUTPUT skipped existing file: type=" + (type ?? string.Empty) + " path=" + path);
                return false;
            }

            SafeLog(errorLog, "OUTPUT regenerating existing invalid file: type=" + (type ?? string.Empty) + " path=" + path);
            return true;
        }

        private List<DeliverablePlan> PruneManifestAgainstExistingOutputs(List<DeliverablePlan> manifest, PublishOptions options,
            string deliverablesFolder, Action<string> errorLog)
        {
            var pruned = new List<DeliverablePlan>();
            if (manifest == null || manifest.Count == 0 || options == null)
            {
                return pruned;
            }

            foreach (DeliverablePlan item in manifest)
            {
                if (item == null)
                {
                    continue;
                }

                item.ExportPngModel = item.ExportPngModel &&
                                      ShouldExportLeanOutput("png", GetOutputPath(item, deliverablesFolder, "png"),
                                          options.OverwriteFiles, errorLog);
                item.ExportStep = item.ExportStep &&
                                  ShouldExportLeanOutput("step", GetOutputPath(item, deliverablesFolder, "step"),
                                      options.OverwriteFiles, errorLog);
                item.ExportEdrawing = item.ExportEdrawing &&
                                      ShouldExportLeanOutput("edr", GetOutputPath(item, deliverablesFolder, "edr"),
                                          options.OverwriteFiles, errorLog);
                item.Export3mf = item.Export3mf &&
                                 ShouldExportLeanOutput("3mf", GetOutputPath(item, deliverablesFolder, "3mf"),
                                     options.OverwriteFiles, errorLog);
                item.ExportPly = item.ExportPly &&
                                 ShouldExportLeanOutput("ply", GetOutputPath(item, deliverablesFolder, "ply"),
                                     options.OverwriteFiles, errorLog);
                item.ExportStl = item.ExportStl &&
                                 ShouldExportLeanOutput("stl", GetOutputPath(item, deliverablesFolder, "stl"),
                                     options.OverwriteFiles, errorLog);
                item.ExportPdf = item.ExportPdf &&
                                 ShouldExportLeanOutput("pdf", GetOutputPath(item, deliverablesFolder, "pdf"),
                                     options.OverwriteFiles, errorLog);
                item.ExportDxf = item.ExportDxf &&
                                 ShouldExportLeanOutput("dxf", GetOutputPath(item, deliverablesFolder, "dxf"),
                                     options.OverwriteFiles, errorLog);
                item.ExportDxfSelected = item.ExportDxf;
                item.ExportPngDrawing = item.ExportPngDrawing &&
                                        ShouldExportLeanOutput("png", GetOutputPath(item, deliverablesFolder, "png_dwg"),
                                            options.OverwriteFiles, errorLog);
                item.ExportEdrawingDrawing = item.ExportEdrawingDrawing &&
                                             ShouldExportLeanOutput("edrw", GetOutputPath(item, deliverablesFolder, "edrw"),
                                                 options.OverwriteFiles, errorLog);

                if (HasRequestedModelExports(item) || HasRequestedDrawingExports(item))
                {
                    pruned.Add(item);
                }
            }

            return pruned;
        }

        private List<string> GetRequestedModelFormats(DeliverablePlan plan)
        {
            var formats = new List<string>();
            if (plan == null)
            {
                return formats;
            }

            if (plan.ExportPngModel) formats.Add("png");
            if (plan.ExportStep) formats.Add("step");
            if (plan.ExportEdrawing) formats.Add("edr");
            if (plan.Export3mf) formats.Add("3mf");
            if (plan.ExportPly) formats.Add("ply");
            if (plan.ExportStl) formats.Add("stl");
            return formats;
        }

        private List<string> GetRequestedDrawingFormats(DeliverablePlan plan)
        {
            var formats = new List<string>();
            if (plan == null)
            {
                return formats;
            }

            if (plan.ExportPdf) formats.Add("pdf");
            if (plan.ExportDxf) formats.Add("dxf");
            if (plan.ExportPngDrawing) formats.Add("png_dwg");
            if (plan.ExportEdrawingDrawing) formats.Add("edrw");
            return formats;
        }

        private void RecordDeliverableFailure(ExportSummary summary, DeliverablePlan plan, IEnumerable<string> formats, string reason)
        {
            if (summary == null || plan == null)
            {
                return;
            }

            string partNumber = plan.PartNumber ?? string.Empty;
            string revision = plan.Revision ?? string.Empty;
            DeliverableFailureRecord record = null;
            for (int i = 0; i < summary.FailureRecords.Count; i++)
            {
                DeliverableFailureRecord candidate = summary.FailureRecords[i];
                if (candidate == null)
                {
                    continue;
                }

                if (string.Equals(candidate.PartNumber ?? string.Empty, partNumber, StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(candidate.Revision ?? string.Empty, revision, StringComparison.OrdinalIgnoreCase))
                {
                    record = candidate;
                    break;
                }
            }

            if (record == null)
            {
                record = new DeliverableFailureRecord
                {
                    PartNumber = partNumber,
                    Revision = revision,
                    SourceModelPath = plan.ModelPath ?? string.Empty,
                    DrawingPath = plan.DrawingPath ?? string.Empty
                };
                summary.FailureRecords.Add(record);
            }

            if (!string.IsNullOrWhiteSpace(reason))
            {
                record.Reasons.Add(reason);
            }

            if (formats == null)
            {
                return;
            }

            foreach (string format in formats)
            {
                if (!string.IsNullOrWhiteSpace(format))
                {
                    record.FailedFormats.Add(format);
                }
            }
        }

        private List<PhysicalExportQueueItem> BuildPhysicalExportQueue(List<DeliverablePlan> manifest, Action<string> errorLog)
        {
            var groups = new Dictionary<string, PhysicalExportQueueItem>(StringComparer.OrdinalIgnoreCase);
            ExportSummary summary = _currentExportSummary;

            foreach (DeliverablePlan item in manifest ?? new List<DeliverablePlan>())
            {
                if (item == null)
                {
                    continue;
                }

                if (HasRequestedModelExports(item))
                {
                    if (item.IsRoot || !string.IsNullOrWhiteSpace(item.ModelPath))
                    {
                        string modelKey = "model|" + (item.IsRoot && string.IsNullOrWhiteSpace(item.ModelPath)
                            ? "<root>"
                            : NormalizePathForComparison(item.ModelPath));
                        PhysicalExportQueueItem group;
                        if (!groups.TryGetValue(modelKey, out group))
                        {
                            group = new PhysicalExportQueueItem
                            {
                                IsDrawing = false,
                                PhysicalPath = item.ModelPath ?? string.Empty,
                                DisplayName = !string.IsNullOrWhiteSpace(item.ModelPath)
                                    ? item.ModelPath
                                    : (item.ModelTitle ?? item.FileString ?? string.Empty),
                                DocType = item.DocType,
                                IsRoot = item.IsRoot,
                                MaxDepth = item.MaxDepth,
                                SubtreeEstimate = item.SubtreeEstimate
                            };
                            groups[modelKey] = group;
                        }

                        group.Plans.Add(item);
                        group.IsRoot = group.IsRoot || item.IsRoot;
                        group.MaxDepth = Math.Max(group.MaxDepth, item.MaxDepth);
                        group.SubtreeEstimate = Math.Max(group.SubtreeEstimate, item.SubtreeEstimate);
                    }
                    else
                    {
                        RecordDeliverableFailure(summary, item, GetRequestedModelFormats(item), "missing source");
                    }
                }

                if (HasRequestedDrawingExports(item))
                {
                    if (!string.IsNullOrWhiteSpace(item.DrawingPath) && item.DrawingExists)
                    {
                        string drawingKey = "drawing|" + NormalizePathForComparison(item.DrawingPath);
                        PhysicalExportQueueItem group;
                        if (!groups.TryGetValue(drawingKey, out group))
                        {
                            group = new PhysicalExportQueueItem
                            {
                                IsDrawing = true,
                                PhysicalPath = item.DrawingPath ?? string.Empty,
                                DisplayName = item.DrawingPath ?? string.Empty,
                                DocType = item.DocType,
                                IsRoot = item.IsRoot,
                                MaxDepth = item.MaxDepth,
                                SubtreeEstimate = item.SubtreeEstimate
                            };
                            groups[drawingKey] = group;
                        }

                        group.Plans.Add(item);
                        group.IsRoot = group.IsRoot || item.IsRoot;
                        group.MaxDepth = Math.Max(group.MaxDepth, item.MaxDepth);
                        group.SubtreeEstimate = Math.Max(group.SubtreeEstimate, item.SubtreeEstimate);
                    }
                    else
                    {
                        RecordDeliverableFailure(summary, item, GetRequestedDrawingFormats(item), "missing drawing");
                    }
                }
            }

            var queue = new List<PhysicalExportQueueItem>(groups.Values);
            queue.Sort((a, b) =>
            {
                int rootCompare = (a != null && a.IsRoot ? 1 : 0).CompareTo(b != null && b.IsRoot ? 1 : 0);
                if (rootCompare != 0) return rootCompare;

                bool aAssembly = a != null && a.DocType == (int)swDocumentTypes_e.swDocASSEMBLY;
                bool bAssembly = b != null && b.DocType == (int)swDocumentTypes_e.swDocASSEMBLY;
                int typeCompare = (aAssembly ? 1 : 0).CompareTo(bAssembly ? 1 : 0);
                if (typeCompare != 0) return typeCompare;

                int depthCompare = (b != null ? b.MaxDepth : 0).CompareTo(a != null ? a.MaxDepth : 0);
                if (depthCompare != 0) return depthCompare;

                int subtreeCompare = (a != null ? a.SubtreeEstimate : 0).CompareTo(b != null ? b.SubtreeEstimate : 0);
                if (subtreeCompare != 0) return subtreeCompare;

                string aPath = a != null
                    ? (!string.IsNullOrWhiteSpace(a.PhysicalPath) ? a.PhysicalPath : a.DisplayName ?? string.Empty)
                    : string.Empty;
                string bPath = b != null
                    ? (!string.IsNullOrWhiteSpace(b.PhysicalPath) ? b.PhysicalPath : b.DisplayName ?? string.Empty)
                    : string.Empty;
                int pathCompare = string.Compare(aPath, bPath, StringComparison.OrdinalIgnoreCase);
                if (pathCompare != 0) return pathCompare;

                return (a != null && a.IsDrawing ? 1 : 0).CompareTo(b != null && b.IsDrawing ? 1 : 0);
            });

            foreach (PhysicalExportQueueItem group in queue)
            {
                if (group == null || group.Plans == null)
                {
                    continue;
                }

                group.Plans.Sort((a, b) =>
                {
                    int confCompare = string.Compare(a != null ? a.ConfigurationName : string.Empty,
                        b != null ? b.ConfigurationName : string.Empty, StringComparison.OrdinalIgnoreCase);
                    if (confCompare != 0) return confCompare;

                    int pnCompare = string.Compare(a != null ? a.PartNumber : string.Empty,
                        b != null ? b.PartNumber : string.Empty, StringComparison.OrdinalIgnoreCase);
                    if (pnCompare != 0) return pnCompare;

                    return string.Compare(a != null ? a.Revision : string.Empty,
                        b != null ? b.Revision : string.Empty, StringComparison.OrdinalIgnoreCase);
                });
            }

            return queue;
        }

        private bool ValidateRequestedOutputs(DeliverablePlan plan, string deliverablesFolder, IEnumerable<string> formats,
            Action<string> errorLog, out string reason)
        {
            reason = string.Empty;
            if (plan == null)
            {
                reason = "missing plan";
                return false;
            }

            bool valid = true;
            foreach (string format in formats ?? new string[0])
            {
                string path = GetOutputPath(plan, deliverablesFolder, format);
                string itemReason;
                if (ValidateExportedOutput(NormalizeExportType(format, path), path, errorLog, out itemReason))
                {
                    continue;
                }

                valid = false;
                reason = !string.IsNullOrWhiteSpace(reason)
                    ? (reason + "; " + format + "=" + (itemReason ?? string.Empty))
                    : (format + "=" + (itemReason ?? string.Empty));
            }

            return valid;
        }

        private void RunPhysicalModelQueueItem(PhysicalExportQueueItem item, ModelDoc2 rootModel, string deliverablesFolder,
            PublishOptions options, Action<string> log, Action<string> errorLog)
        {
            if (item == null || item.Plans == null || item.Plans.Count == 0)
            {
                return;
            }

            ModelDoc2 model = null;
            bool openedHere = false;
            int specErr = 0;
            int specWarn = 0;
            try
            {
                if (item.IsRoot)
                {
                    model = rootModel;
                }

                if (model == null)
                {
                    model = FindOpenDocument(item.PhysicalPath, null);
                }

                if (model == null && !string.IsNullOrWhiteSpace(item.PhysicalPath))
                {
                    model = OpenDocReadOnlySilent(
                        item.PhysicalPath,
                        item.DocType == 0 ? DocumentTypeFromPath(item.PhysicalPath) : item.DocType,
                        item.Plans[0] != null ? item.Plans[0].ConfigurationName : string.Empty,
                        errorLog,
                        "physical-model|" + (item.PhysicalPath ?? string.Empty),
                        out specErr,
                        out specWarn);
                    openedHere = model != null;
                }

                if (model == null)
                {
                    foreach (DeliverablePlan plan in item.Plans)
                    {
                        RecordDeliverableFailure(_currentExportSummary, plan, GetRequestedModelFormats(plan), "open failed");
                    }
                    SafeLog(errorLog,
                        "MODEL queue open failed path=" + (item.PhysicalPath ?? string.Empty) +
                        " specErr=" + specErr +
                        " specWarn=" + specWarn);
                    return;
                }

                SafeLog(errorLog,
                    "MODEL queue start path=" + (item.PhysicalPath ?? string.Empty) +
                    " plans=" + item.Plans.Count +
                    " openedHere=" + openedHere);

                foreach (DeliverablePlan plan in item.Plans)
                {
                    if (plan == null || !HasRequestedModelExports(plan))
                    {
                        continue;
                    }

                    TryShowConfiguration(model, plan.ConfigurationName);
                    IEnumerable<string> formats = GetRequestedModelFormats(plan);
                    try
                    {
                        ModelPublish(
                            model,
                            plan.ConfigurationName,
                            plan.FileString,
                            deliverablesFolder,
                            options != null && options.OverwriteFiles,
                            plan.ExportPngModel,
                            plan.ExportStep,
                            plan.ExportEdrawing,
                            plan.Export3mf,
                            plan.ExportPly,
                            plan.ExportStl,
                            log,
                            errorLog);
                    }
                    catch (Exception ex)
                    {
                        if (ex is OperationCanceledException)
                        {
                            throw;
                        }

                        RecordDeliverableFailure(_currentExportSummary, plan, formats, "export failed");
                        LogExportFailure(log, errorLog,
                            "Model export failed: " + (plan.FileString ?? string.Empty) + " (" + ex.Message + ")");
                        continue;
                    }

                    string reason;
                    if (!ValidateRequestedOutputs(plan, deliverablesFolder, formats, errorLog, out reason))
                    {
                        RecordDeliverableFailure(_currentExportSummary, plan, formats, "validation failed");
                        SafeLog(errorLog,
                            "MODEL queue validation failed file=" + (plan.FileString ?? string.Empty) +
                            " reason=" + (reason ?? string.Empty));
                    }
                }
            }
            finally
            {
                if (openedHere && model != null)
                {
                    string closePath = item.PhysicalPath ?? string.Empty;
                    ForceCloseDocNoSave(model, errorLog, "physical-model-close");
                    if (!string.IsNullOrWhiteSpace(closePath) && IsDocOpenByIdOrTitle(closePath, null))
                    {
                        foreach (DeliverablePlan plan in item.Plans)
                        {
                            RecordDeliverableFailure(_currentExportSummary, plan, GetRequestedModelFormats(plan), "close failed");
                        }
                    }

                    ComInteropUtil.TryFinalReleaseComObject(model);
                }
            }
        }

        private void RunPhysicalDrawingQueueItem(PhysicalExportQueueItem item, string deliverablesFolder,
            PublishOptions options, Action<string> log, Action<string> errorLog, HashSet<string> baselineVisibleIds, string rootDocId)
        {
            if (item == null || item.Plans == null || item.Plans.Count == 0)
            {
                return;
            }

            ModelDoc2 drawDoc = null;
            bool openedHere = false;
            int specErr = 0;
            int specWarn = 0;
            try
            {
                drawDoc = FindOpenDocument(item.PhysicalPath, null);
                if (drawDoc == null)
                {
                    drawDoc = OpenDocReadOnlySilent(
                        item.PhysicalPath,
                        (int)swDocumentTypes_e.swDocDRAWING,
                        null,
                        errorLog,
                        "physical-drawing|" + (item.PhysicalPath ?? string.Empty),
                        out specErr,
                        out specWarn);
                    openedHere = drawDoc != null;
                }

                if (drawDoc == null)
                {
                    foreach (DeliverablePlan plan in item.Plans)
                    {
                        RecordDeliverableFailure(_currentExportSummary, plan, GetRequestedDrawingFormats(plan), "open failed");
                    }
                    SafeLog(errorLog,
                        "DRAWING queue open failed path=" + (item.PhysicalPath ?? string.Empty) +
                        " specErr=" + specErr +
                        " specWarn=" + specWarn);
                    return;
                }

                try
                {
                    drawDoc.Visible = false;
                }
                catch
                {
                    // ignore hide errors
                }

                using (var openedDocs = new OpenTracker(this, errorLog))
                {
                    foreach (DeliverablePlan plan in item.Plans)
                    {
                        if (plan == null || !HasRequestedDrawingExports(plan))
                        {
                            continue;
                        }

                        // Drawing exports only need the drawing document. The referenced models are
                        // loaded by SolidWorks as hidden references of the drawing itself; opening
                        // them explicitly here doubled the number of file opens per drawing.
                        string drawingPath = !string.IsNullOrWhiteSpace(plan.DrawingPath)
                            ? plan.DrawingPath
                            : (item.PhysicalPath ?? string.Empty);

                        IEnumerable<string> formats = GetRequestedDrawingFormats(plan);
                        try
                        {
                            DwgPublishFast(
                                drawingPath,
                                plan.FileString,
                                deliverablesFolder,
                                options != null && options.OverwriteFiles,
                                plan.ExportPdf,
                                plan.ExportDxf,
                                plan.ExportPngDrawing,
                                plan.ExportEdrawingDrawing,
                                log,
                                errorLog,
                                openedDocs,
                                baselineVisibleIds,
                                rootDocId);
                        }
                        catch (Exception ex)
                        {
                            if (ex is OperationCanceledException)
                            {
                                throw;
                            }

                            RecordDeliverableFailure(_currentExportSummary, plan, formats, "export failed");
                            LogExportFailure(log, errorLog,
                                "Drawing export failed: " + (plan.FileString ?? string.Empty) + " (" + ex.Message + ")");
                            continue;
                        }

                        string reason;
                        if (!ValidateRequestedOutputs(plan, deliverablesFolder, formats, errorLog, out reason))
                        {
                            RecordDeliverableFailure(_currentExportSummary, plan, formats, "validation failed");
                            SafeLog(errorLog,
                                "DRAWING queue validation failed file=" + (plan.FileString ?? string.Empty) +
                                " reason=" + (reason ?? string.Empty));
                        }
                    }
                }
            }
            finally
            {
                if (openedHere && drawDoc != null)
                {
                    string closePath = item.PhysicalPath ?? string.Empty;
                    ForceCloseDocNoSave(drawDoc, errorLog, "physical-drawing-close");
                    if (!string.IsNullOrWhiteSpace(closePath) && IsDocOpenByIdOrTitle(closePath, null))
                    {
                        foreach (DeliverablePlan plan in item.Plans)
                        {
                            RecordDeliverableFailure(_currentExportSummary, plan, GetRequestedDrawingFormats(plan), "close failed");
                        }
                    }

                    ComInteropUtil.TryFinalReleaseComObject(drawDoc);
                }
            }
        }

        private void RunPhysicalExportQueue(List<PhysicalExportQueueItem> queue, ModelDoc2 rootModel, string deliverablesFolder,
            PublishOptions options, Action<string> log, Action<string> errorLog, Action<int, int> progress,
            ExportSessionState sessionState)
        {
            int total = queue != null ? queue.Count : 0;
            UpdateProgress(progress, 0, total);
            if (queue == null || queue.Count == 0)
            {
                return;
            }

            var baselineVisibleIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            try
            {
                baselineVisibleIds = GetOpenVisibleDocumentIds();
            }
            catch
            {
                baselineVisibleIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
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

            int processed = 0;
            if (_currentExportSummary != null)
            {
                _currentExportSummary.DeliverableGroupsPlanned = queue.Count;
            }

            var itemTimer = new System.Diagnostics.Stopwatch();
            foreach (PhysicalExportQueueItem item in queue)
            {
                ThrowIfCancelled();
                System.Windows.Forms.Application.DoEvents();

                if (item == null)
                {
                    continue;
                }

                SafeLog(errorLog,
                    "QUEUE item " + (processed + 1) + "/" + total +
                    (item.IsDrawing ? " kind=drawing" : " kind=model") +
                    " plans=" + (item.Plans != null ? item.Plans.Count : 0) +
                    " path=" + (!string.IsNullOrWhiteSpace(item.PhysicalPath) ? item.PhysicalPath : item.DisplayName));
                itemTimer.Restart();

                if (item.IsDrawing)
                {
                    RunPhysicalDrawingQueueItem(item, deliverablesFolder, options, log, errorLog, baselineVisibleIds, rootDocId);
                }
                else
                {
                    RunPhysicalModelQueueItem(item, rootModel, deliverablesFolder, options, log, errorLog);
                }

                SafeLog(errorLog,
                    "QUEUE item " + (processed + 1) + "/" + total +
                    " done elapsedMs=" + itemTimer.ElapsedMilliseconds);

                item.Status = ExportItemStatusDone;
                item.CompletedUtc = UtcNowString();
                if (sessionState != null)
                {
                    SaveExportSessionAtomic(sessionState, errorLog);
                }

                processed++;
                if (_currentExportSummary != null)
                {
                    _currentExportSummary.DeliverableGroupsProcessed = processed;
                }
                UpdateProgress(progress, processed, total);

                if (_stopAfterCurrentItemRequested)
                {
                    if (_currentExportSummary != null)
                    {
                        _currentExportSummary.StoppedAfterCurrentFile = true;
                    }
                    SafeLog(errorLog, "STOP requested; finishing current file and stopping.");
                    break;
                }
            }
        }

        private void WriteDeliverablesFailureSummary(Action<string> errorLog, ExportSummary summary)
        {
            if (errorLog == null || summary == null || summary.FailureRecords == null || summary.FailureRecords.Count == 0)
            {
                return;
            }

            errorLog("FAILED EXPORT SUMMARY");
            foreach (DeliverableFailureRecord record in summary.FailureRecords)
            {
                if (record == null)
                {
                    continue;
                }

                string partNumber = record.PartNumber ?? string.Empty;
                string revision = record.Revision ?? string.Empty;
                string formats = string.Join(", ", new List<string>(record.FailedFormats).ToArray());
                string reasons = string.Join("; ", new List<string>(record.Reasons).ToArray());
                errorLog("Part " + partNumber + " REV " + revision);
                errorLog("Source: " + (record.SourceModelPath ?? string.Empty));
                if (!string.IsNullOrWhiteSpace(record.DrawingPath))
                {
                    errorLog("Drawing: " + record.DrawingPath);
                }
                errorLog("Failed formats: " + formats);
                errorLog("Reason: " + reasons);
            }
        }

        private int GetDeliverableFailureFormatCount(ExportSummary summary)
        {
            if (summary == null || summary.FailureRecords == null)
            {
                return 0;
            }

            int count = 0;
            foreach (DeliverableFailureRecord record in summary.FailureRecords)
            {
                if (record != null && record.FailedFormats != null)
                {
                    count += record.FailedFormats.Count;
                }
            }

            return count;
        }

        private string BuildUploadPackFlatBomFromManifest(List<DeliverablePlan> manifest, string bomFolder, Action<string> errorLog)
        {
            if (manifest == null || manifest.Count == 0)
            {
                return string.Empty;
            }

            string root = string.IsNullOrWhiteSpace(bomFolder) ? Path.GetTempPath() : bomFolder;
            Directory.CreateDirectory(root);
            string path = Path.Combine(root, "deliverables_" + DateTime.Now.ToString("yyyy_MM_dd_HH_mm_ss") + "_FLATBOM.txt");
            using (var writer = new StreamWriter(path, false, new UTF8Encoding(false)))
            {
                foreach (DeliverablePlan item in manifest)
                {
                    if (item == null)
                    {
                        continue;
                    }

                    writer.WriteLine(
                        "{'partnumber':'" + SanitizeString(item.PartNumber ?? string.Empty) +
                        "','sw_configuration':'" + SanitizeString(item.ConfigurationName ?? string.Empty) +
                        "','revision':'" + SanitizeString(item.Revision ?? string.Empty) +
                        "','path':'" + SanitizeString((item.ModelPath ?? string.Empty).Replace("\\", "/")) +
                        "','file':'" + SanitizeString(OnlyFile(item.ModelPath)) +
                        "','folder':'" + SanitizeString(OnlyFolder(item.ModelPath).Replace("\\", "/")) +
                        "'}");
                }
            }

            SafeLog(errorLog, "UPLOAD PACK manifest flat BOM: " + path);
            return path;
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

        private string BuildSaveBeforeExportPromptMessage(string operationLabel, string documentTitle, string reason)
        {
            string operation = string.IsNullOrWhiteSpace(operationLabel) ? "export" : operationLabel.Trim();
            string docLabel = string.IsNullOrWhiteSpace(documentTitle)
                ? "The active document"
                : ("\"" + documentTitle.Trim() + "\"");

            string detail;
            switch ((reason ?? string.Empty).Trim())
            {
                case "modified":
                    detail = "It has unsaved changes.";
                    break;
                case "missingFile":
                    detail = "Its saved file path is missing or inaccessible.";
                    break;
                default:
                    detail = "It has not been saved yet.";
                    break;
            }

            return docLabel + " must be saved before " + operation + ". " + detail +
                   " Save it in SolidWorks, then start the " + operation + " again.";
        }

        private void ShowSaveBeforeExportPrompt(string operationLabel, ModelDoc2 doc, string reason, Action<string> errorLog = null)
        {
            string documentTitle = string.Empty;
            try
            {
                documentTitle = doc != null ? (doc.GetTitle() ?? string.Empty) : string.Empty;
            }
            catch
            {
                documentTitle = string.Empty;
            }

            string message = BuildSaveBeforeExportPromptMessage(operationLabel, documentTitle, reason);
            SafeLog(errorLog,
                "EXPORT save-required prompt: operation=" + (operationLabel ?? string.Empty) +
                " title=" + (documentTitle ?? string.Empty) +
                " reason=" + (reason ?? string.Empty));

            try
            {
                System.Windows.Forms.MessageBox.Show(
                    message,
                    "TinyMRP",
                    System.Windows.Forms.MessageBoxButtons.OK,
                    System.Windows.Forms.MessageBoxIcon.Warning);
            }
            catch (Exception ex)
            {
                SafeLog(errorLog, "EXPORT save-required prompt failed: " + ex.Message);
            }
        }

        private ModelDoc2 OpenDocSilent(string path, int docType, string configurationName, bool readOnly, bool documentVisible,
            Action<string> errorLog, string context, out int specErr, out int specWarn)
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
            spec.ReadOnly = readOnly;
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

            TrySetComProperty(spec, "DocumentVisible", documentVisible);

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
            string previousCurrentDirectory = string.Empty;
            bool restoreCurrentDirectory = false;
            try
            {
                try
                {
                    previousCurrentDirectory = Directory.GetCurrentDirectory();
                    restoreCurrentDirectory = !string.IsNullOrWhiteSpace(previousCurrentDirectory);
                }
                catch
                {
                    previousCurrentDirectory = string.Empty;
                    restoreCurrentDirectory = false;
                }

                try
                {
                    string fileFolder = Path.GetDirectoryName(path) ?? string.Empty;
                    if (!string.IsNullOrWhiteSpace(fileFolder) && Directory.Exists(fileFolder))
                    {
                        Directory.SetCurrentDirectory(fileFolder);
                    }
                }
                catch
                {
                    // ignore current-directory errors
                }

                using (new ExportDialogSuppressionScope(_swApp))
                using (new ExternalReferenceBatchOpenScope(_swApp))
                {
                    YieldAndCheckCancel();
                    opened = _swApp.OpenDoc7(spec) as ModelDoc2;
                }
            }
            finally
            {
                if (restoreCurrentDirectory)
                {
                    try
                    {
                        Directory.SetCurrentDirectory(previousCurrentDirectory);
                    }
                    catch
                    {
                        // ignore restore errors
                    }
                }
                ComInteropUtil.TryFinalReleaseComObject(spec);
            }

            if (opened != null)
            {
                try
                {
                    opened.Visible = documentVisible;
                }
                catch
                {
                    // ignore visibility errors
                }
            }

            return opened;
        }

        private ModelDoc2 OpenDocReadOnlySilent(string path, int docType, string configurationName, Action<string> errorLog,
            string context, out int specErr, out int specWarn)
        {
            return OpenDocSilent(path, docType, configurationName, true, false, errorLog, context, out specErr, out specWarn);
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

        private string NormalizeExportType(string type, string path)
        {
            string normalized = (type ?? string.Empty).Trim().ToLowerInvariant();
            if (!string.IsNullOrWhiteSpace(normalized))
            {
                return normalized;
            }

            string ext = string.Empty;
            try
            {
                ext = (Path.GetExtension(path) ?? string.Empty).Trim().ToLowerInvariant();
            }
            catch
            {
                ext = string.Empty;
            }

            switch (ext)
            {
                case ".3mf":
                    return "3mf";
                case ".stl":
                    return "stl";
                case ".ply":
                    return "ply";
                case ".step":
                case ".stp":
                    return "step";
                case ".easm":
                    return "easm";
                case ".eprt":
                    return "eprt";
                case ".edrw":
                    return "edrw";
                case ".png":
                    return "png";
                case ".pdf":
                    return "pdf";
                case ".dxf":
                    return "dxf";
                case ".txt":
                    return "txt";
                case ".zip":
                    return "zip";
                default:
                    return normalized;
            }
        }

        private bool ShouldExport(string path, bool overwrite, Action<string> errorLog = null)
        {
            if (overwrite || string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return true;
            }

            string type = NormalizeExportType(null, path);
            string reason;
            bool valid = ValidateExportedOutput(type, path, errorLog, out reason);
            if (valid)
            {
                SafeLog(errorLog, "OUTPUT skipped existing valid output: type=" + (type ?? string.Empty) + " path=" + path);
                return false;
            }

            SafeLog(errorLog,
                "OUTPUT existing invalid, regenerating: type=" + (type ?? string.Empty) +
                " path=" + path +
                " reason=" + (reason ?? string.Empty));
            return true;
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

        private long GetFileSizeQuietly(string path)
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

        private string CombineExportReasons(string primary, string secondary)
        {
            string a = (primary ?? string.Empty).Trim();
            string b = (secondary ?? string.Empty).Trim();

            if (string.IsNullOrWhiteSpace(a))
            {
                return b;
            }

            if (string.IsNullOrWhiteSpace(b))
            {
                return a;
            }

            return a + "; " + b;
        }

        private bool TryPrepareExportOutput(string type, string finalPath, bool overwrite, Action<string> errorLog,
            out string tempPath, out bool skip, out string reason, out string quarantinedExistingPath)
        {
            tempPath = string.Empty;
            skip = false;
            reason = string.Empty;
            quarantinedExistingPath = string.Empty;

            if (string.IsNullOrWhiteSpace(finalPath))
            {
                reason = "missing final path";
                return false;
            }

            string normalizedType = NormalizeExportType(type, finalPath);
            string outputDirectory = Path.GetDirectoryName(finalPath);
            if (!string.IsNullOrWhiteSpace(outputDirectory))
            {
                Directory.CreateDirectory(outputDirectory);
            }

            if (File.Exists(finalPath))
            {
                string existingReason;
                bool existingValid = ValidateExportedOutput(normalizedType, finalPath, errorLog, out existingReason);
                if (existingValid && !overwrite)
                {
                    skip = true;
                    reason = "existing valid output";
                    return true;
                }

                if (!existingValid)
                {
                    reason = existingReason ?? string.Empty;
                    quarantinedExistingPath = QuarantineInvalidExistingFile(finalPath, existingReason, errorLog);
                }
            }

            tempPath = BuildUniqueTempFilePath(
                outputDirectory,
                Path.GetFileNameWithoutExtension(finalPath),
                Path.GetExtension(finalPath));
            return true;
        }

        private ExportOutputResult TryFinalizeExportedTempFile(string type, string tempPath, string finalPath, Action<string> errorLog)
        {
            var result = new ExportOutputResult
            {
                Type = NormalizeExportType(type, finalPath),
                TempPath = tempPath ?? string.Empty,
                FinalPath = finalPath ?? string.Empty,
                Reason = string.Empty
            };

            try
            {
                long stableBytes = WaitForFileStable(tempPath, 5000, errorLog);
                string tempReason;
                bool tempValid = ValidateExportedOutput(result.Type, tempPath, errorLog, out tempReason);
                result.TempValidated = tempValid;
                if (!tempValid)
                {
                    result.Reason = !string.IsNullOrWhiteSpace(tempReason)
                        ? tempReason
                        : (stableBytes <= 0 ? "temp file not created" : "temp file invalid");
                    return result;
                }

                if (!PromoteTempFileToFinal(tempPath, finalPath, errorLog))
                {
                    result.Reason = "promote failed";
                    return result;
                }

                WaitForFileStable(finalPath, 5000, errorLog);
                string finalReason;
                bool finalValid = ValidateExportedOutput(result.Type, finalPath, errorLog, out finalReason);
                if (!finalValid)
                {
                    result.Reason = !string.IsNullOrWhiteSpace(finalReason) ? finalReason : "final validation failed";
                    return result;
                }

                result.Success = true;
                result.Bytes = GetFileSizeQuietly(finalPath);
                return result;
            }
            finally
            {
                if (!string.Equals(tempPath, finalPath, StringComparison.OrdinalIgnoreCase))
                {
                    TryDeleteFileQuietly(tempPath);
                }
            }
        }

        private ExportOutputResult ExportToTempAndPromote(string type, string finalPath, bool overwrite, Action<string> errorLog,
            Func<string, bool> exportAction)
        {
            var result = new ExportOutputResult
            {
                Type = NormalizeExportType(type, finalPath),
                FinalPath = finalPath ?? string.Empty,
                Reason = string.Empty
            };

            string tempPath;
            bool skip;
            string prepareReason;
            string quarantinedExistingPath;
            if (!TryPrepareExportOutput(result.Type, finalPath, overwrite, errorLog, out tempPath, out skip, out prepareReason,
                out quarantinedExistingPath))
            {
                result.Reason = prepareReason ?? string.Empty;
                return result;
            }

            result.TempPath = tempPath ?? string.Empty;
            result.QuarantinedExistingPath = quarantinedExistingPath ?? string.Empty;
            if (skip)
            {
                result.Success = true;
                result.Skipped = true;
                result.Reason = prepareReason ?? string.Empty;
                result.Bytes = GetFileSizeQuietly(finalPath);
                return result;
            }

            string exportException = string.Empty;
            bool exportCallOk = false;
            try
            {
                exportCallOk = exportAction != null && exportAction(tempPath);
            }
            catch (Exception ex)
            {
                exportException = ex.Message ?? string.Empty;
            }

            ExportOutputResult finalized = TryFinalizeExportedTempFile(result.Type, tempPath, finalPath, errorLog);
            finalized.ExportCallOk = exportCallOk;
            finalized.QuarantinedExistingPath = result.QuarantinedExistingPath;

            if (!finalized.Success)
            {
                if (!string.IsNullOrWhiteSpace(exportException))
                {
                    finalized.Reason = CombineExportReasons(finalized.Reason, "export exception: " + exportException);
                }
                else if (!exportCallOk)
                {
                    finalized.Reason = CombineExportReasons(finalized.Reason, "save call reported failure");
                }
            }

            return finalized;
        }

        private void ModelPublish(ModelDoc2 model, string confName, string fileString, string deliverablesFolder,
            bool overwriteFiles, bool png, bool step, bool edr, bool threeMf, bool ply, bool stl, Action<string> log, Action<string> errorLog)
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
                        ExportOutputResult exportResult = ExportToTempAndPromote("3mf", path, overwriteFiles, errorLog, tempPath =>
                        {
                            errors = 0;
                            warnings = 0;
                            return model.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        });
                        long bytes = exportResult.Bytes;
                        bool ok = exportResult.Success && !exportResult.Skipped;
                        t.Stop();
                        SafeLog(errorLog, "MODEL 3MF ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          " path=" + path);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOk3mf++;
                            }
                        }
                        else if (!exportResult.Skipped)
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
                        ExportOutputResult exportResult = ExportToTempAndPromote("stl", stlPath, overwriteFiles, errorLog, tempPath =>
                        {
                            errors = 0;
                            warnings = 0;
                            return model.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        });
                        long bytes = exportResult.Bytes;
                        stlExported = exportResult.Success && !exportResult.Skipped;
                        t.Stop();
                        SafeLog(errorLog, "MODEL STL ms=" + t.ElapsedMilliseconds +
                                          " ok=" + stlExported +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          " path=" + stlPath);
                        if (stlExported)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkStl++;
                            }
                        }
                        else if (!exportResult.Skipped)
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
                        bool skippedExisting = false;
                        string activeBefore = ActiveDocTitle();
                        bool directSaveOk = false;
                        bool directValid = false;
                        bool fallbackAttempted = false;
                        bool fallbackValid = false;
                        bool finalValid = false;
                        long directBytes = 0;
                        long finalBytes = 0;
                        string directInvalidReason = string.Empty;
                        string fallbackInvalidReason = string.Empty;
                        string fallbackStlPath = string.Empty;

                        try
                        {
                            string prepareReason;
                            if (!TryPrepareExportOutput("ply", plyPath, overwriteFiles, errorLog, out tempPlyPath, out skippedExisting,
                                out prepareReason, out quarantinedExisting))
                            {
                                directInvalidReason = prepareReason ?? string.Empty;
                            }
                            else if (skippedExisting)
                            {
                                finalValid = true;
                                finalBytes = GetFileSizeQuietly(plyPath);
                            }
                            else
                            {
                                tempFallbackPlyPath = BuildUniqueTempFilePath(Path.Combine(deliverablesFolder, "ply"), fileString, ".ply");
                                errors = 0;
                                warnings = 0;
                                directSaveOk = model.Extension.SaveAs(tempPlyPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                                directBytes = WaitForFileStable(tempPlyPath, 8000, errorLog);
                                ExportOutputResult directResult = TryFinalizeExportedTempFile("ply", tempPlyPath, plyPath, errorLog);
                                directResult.ExportCallOk = directSaveOk;
                                directValid = directResult.Success;
                                if (directValid)
                                {
                                    finalValid = true;
                                    finalBytes = directResult.Bytes;
                                }
                                else
                                {
                                    directInvalidReason = directResult.Reason ?? string.Empty;
                                }

                                if (!directValid)
                                {
                                    SafeLog(errorLog,
                                        "PLY direct invalid: " + (directInvalidReason ?? string.Empty) +
                                        " path=" + tempPlyPath +
                                        " bytes=" + directBytes);

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
                                            ExportOutputResult fallbackResult = TryFinalizeExportedTempFile("ply", tempFallbackPlyPath, plyPath, errorLog);
                                            fallbackValid = fallbackResult.Success;
                                            if (fallbackValid)
                                            {
                                                finalValid = true;
                                                finalBytes = fallbackResult.Bytes;
                                                SafeLog(errorLog, "PLY fallback via STL ok path=" + tempFallbackPlyPath);
                                            }
                                            else
                                            {
                                                fallbackInvalidReason = fallbackResult.Reason ?? string.Empty;
                                                SafeLog(errorLog, "PLY fallback invalid: " + (fallbackInvalidReason ?? string.Empty));
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

                        long bytes = finalBytes > 0 ? finalBytes : FileBytes(plyPath);
                        bool ok = finalValid && !skippedExisting;
                        t.Stop();
                        SafeLog(errorLog,
                            "MODEL PLY ms=" + t.ElapsedMilliseconds +
                            " ok=" + ok +
                            " skipped=" + skippedExisting +
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
                            if (ok)
                            {
                                summary.ModelOkPly++;
                            }
                            else if (!skippedExisting)
                            {
                                summary.ModelFailPly++;
                            }
                        }

                        if (!finalValid && !skippedExisting)
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
                        ExportOutputResult exportResult = ExportToTempAndPromote("step", path, overwriteFiles, errorLog, tempPath =>
                        {
                            errors = 0;
                            warnings = 0;
                            return model.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        });
                        long bytes = exportResult.Bytes;
                        bool ok = exportResult.Success && !exportResult.Skipped;
                        t.Stop();
                        SafeLog(errorLog, "MODEL STEP ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          " path=" + path);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkStep++;
                            }
                        }
                        else if (!exportResult.Skipped)
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
                        ExportOutputResult exportResult = ExportToTempAndPromote(ext, path, overwriteFiles, errorLog, tempPath =>
                        {
                            errors = 0;
                            warnings = 0;
                            return model.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        });
                        long bytes = exportResult.Bytes;
                        bool ok = exportResult.Success && !exportResult.Skipped;
                        t.Stop();
                        SafeLog(errorLog, "MODEL EDR ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          " path=" + path);
                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.ModelOkEdraw++;
                            }
                        }
                        else if (!exportResult.Skipped)
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

                        string exceptionText = string.Empty;
                        ExportOutputResult exportResult;
                        using (new SolidWorksWhiteViewportBackgroundScope(_swApp))
                        {
                            exportResult = ExportToTempAndPromote("png", path, overwriteFiles, errorLog, tempPath =>
                            {
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

                                    errors = 0;
                                    warnings = 0;
                                    return model.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                                }
                                catch (Exception ex)
                                {
                                    exceptionText = ex.Message ?? string.Empty;
                                    return false;
                                }
                            });
                        }

                        long bytes = exportResult.Bytes;
                        bool blankSuspect = !exportResult.Success &&
                            string.Equals(exportResult.Reason, "file too small", StringComparison.OrdinalIgnoreCase);
                        bool ok = exportResult.Success && !exportResult.Skipped;
                        t.Stop();

                        SafeLog(errorLog, "MODEL PNG ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " blankSuspect=" + blankSuspect +
                                          " activated=" + (activation != null && activation.Activated) +
                                          " actErr=" + (activation != null ? activation.ActivateErrors : 0) +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          (string.IsNullOrWhiteSpace(exceptionText) ? "" : (" ex=" + exceptionText)) +
                                          " path=" + path);

                        if (!ok && !exportResult.Skipped && blankSuspect)
                        {
                            LogExportFailure(log, errorLog, "PNG export suspect blank (size " + bytes + "): " + path);
                        }
                        else if (!ok && !exportResult.Skipped)
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
                        else if (!exportResult.Skipped)
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

        private void DwgPublishFast(string drawingPath, string fileString, string deliverablesFolder,
            bool overwriteFiles, bool pdf, bool dxf, bool png, bool edr, Action<string> log, Action<string> errorLog,
            OpenTracker openedDocs, HashSet<string> baselineVisibleIds, string rootDocId)
        {
            using (new ExportDialogSuppressionScope(_swApp))
            {
                if (string.IsNullOrWhiteSpace(drawingPath) || !File.Exists(drawingPath))
                {
                    SafeLog(errorLog, "DWG skipped: drawing not found path=" + (drawingPath ?? string.Empty));
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

                int visibleDocsBeforeOpen = GetOpenVisibleDocumentIds().Count;
                SafeLog(errorLog,
                    "DRAWING open: " + drawingPath +
                    " | wasOpen=" + drawingWasOpenBefore +
                    " | wasVisible=" + drawingWasVisibleBefore +
                    " | visibleDocsBefore=" + visibleDocsBeforeOpen);

                ModelDoc2 drawDoc = null;
                DrawingDoc drawing = null;
                bool openedHere = false;
                string drawTitle = string.Empty;
                try
                {
                    if (drawingWasOpenBefore)
                    {
                        drawDoc = FindOpenDocument(drawingPath, null);
                    }

                    int specErr = 0;
                    int specWarn = 0;
                    if (drawDoc == null)
                    {
                        drawDoc = OpenDocReadOnlySilent(drawingPath, (int)swDocumentTypes_e.swDocDRAWING, null, errorLog,
                            "DwgPublishFast|" + drawingPath, out specErr, out specWarn);
                        openedHere = drawDoc != null;
                    }
                    if (drawDoc == null)
                    {
                        SafeLog(errorLog, "DwgPublishFast: open failed: " + drawingPath);
                        return;
                    }

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

                    SafeLog(errorLog,
                        "DRAWING open result: openedHere=" + openedHere +
                        " specErr=" + specErr +
                        " specWarn=" + specWarn +
                        " title=" + (drawTitle ?? string.Empty));

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
                                if (!skippedPdf)
                                {
                                    ExportOutputResult exportResult = ExportToTempAndPromote("pdf", pdfPath, overwriteFiles, errorLog, tempPath =>
                                    {
                                        errors = 0;
                                        warnings = 0;
                                        return drawDoc.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                            (int)swSaveAsOptions_e.swSaveAsOptions_Silent, exportData, ref errors, ref warnings);
                                    });
                                    long bytes = exportResult.Bytes;
                                    bool blankSuspect = !exportResult.Success &&
                                        string.Equals(exportResult.Reason, "file too small", StringComparison.OrdinalIgnoreCase);
                                    bool ok = exportResult.Success && !exportResult.Skipped;
                                    t.Stop();
                                    SafeLog(errorLog, "DWG PDF ms=" + t.ElapsedMilliseconds +
                                                      " ok=" + ok +
                                                      " skipped=" + exportResult.Skipped +
                                                      " saveOk=" + exportResult.ExportCallOk +
                                                      " tempValidated=" + exportResult.TempValidated +
                                                      " blankSuspect=" + blankSuspect +
                                                      " activeBefore=" + activeBefore +
                                                      " activeAfter=" + ActiveDocTitle() +
                                                      " errors=" + errors +
                                                      " warnings=" + warnings +
                                                      " bytes=" + bytes +
                                                      " reason=" + (exportResult.Reason ?? string.Empty) +
                                                      " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                                      " path=" + pdfPath);

                                    if (ok)
                                    {
                                        if (summary != null)
                                        {
                                            summary.DwgOkPdf++;
                                        }
                                    }
                                    else if (!exportResult.Skipped)
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
                                    t.Stop();
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
                        ExportOutputResult exportResult = ExportToTempAndPromote("edrw", edrPath, overwriteFiles, errorLog, tempPath =>
                        {
                            errors = 0;
                            warnings = 0;
                            return drawDoc.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        });
                        long bytes = exportResult.Bytes;
                        bool ok = exportResult.Success && !exportResult.Skipped;
                        t.Stop();
                        SafeLog(errorLog, "DWG EDRW ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          " path=" + edrPath);

                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.DwgOkEdraw++;
                            }
                        }
                        else if (!exportResult.Skipped)
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

                        ExportOutputResult exportResult = ExportToTempAndPromote("png", pngPath, overwriteFiles, errorLog, tempPath =>
                        {
                            errors = 0;
                            warnings = 0;
                            return drawDoc.Extension.SaveAs(tempPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                (int)swSaveAsOptions_e.swSaveAsOptions_Silent, null, ref errors, ref warnings);
                        });
                        long bytes = exportResult.Bytes;
                        bool blankSuspect = !exportResult.Success &&
                            string.Equals(exportResult.Reason, "file too small", StringComparison.OrdinalIgnoreCase);
                        bool ok = exportResult.Success && !exportResult.Skipped;
                        t.Stop();
                        SafeLog(errorLog, "DWG PNG ms=" + t.ElapsedMilliseconds +
                                          " ok=" + ok +
                                          " skipped=" + exportResult.Skipped +
                                          " saveOk=" + exportResult.ExportCallOk +
                                          " tempValidated=" + exportResult.TempValidated +
                                          " blankSuspect=" + blankSuspect +
                                          " activeBefore=" + activeBefore +
                                          " activeAfter=" + ActiveDocTitle() +
                                          " errors=" + errors +
                                          " warnings=" + warnings +
                                          " bytes=" + bytes +
                                          " reason=" + (exportResult.Reason ?? string.Empty) +
                                          " quarantinedExisting=" + (exportResult.QuarantinedExistingPath ?? string.Empty) +
                                          " path=" + pngPath);

                        if (ok)
                        {
                            if (summary != null)
                            {
                                summary.DwgOkPng++;
                            }
                        }
                        else if (!exportResult.Skipped)
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
                            bool skippedDxf = false;
                            bool fallbackUsed = false;
                            long finalBytes = 0;
                            string dxfReason = string.Empty;
                            string quarantinedExisting = string.Empty;
                            string tempDxfPath = string.Empty;

                            string prepareReason;
                            if (!TryPrepareExportOutput("dxf", dxfPath, overwriteFiles, errorLog, out tempDxfPath, out skippedDxf,
                                out prepareReason, out quarantinedExisting))
                            {
                                dxfReason = prepareReason ?? string.Empty;
                            }
                            else if (skippedDxf)
                            {
                                exported = true;
                                finalBytes = GetFileSizeQuietly(dxfPath);
                            }
                            else
                            {
                                bool directSaveOk = false;
                                string activeBefore = ActiveDocTitle();
                                try
                                {
                                    errors = 0;
                                    warnings = 0;
                                    drawing.ActivateSheet(dxfSheetName);
                                    directSaveOk = drawDoc.SaveAs4(tempDxfPath, (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                                        (int)swSaveAsOptions_e.swSaveAsOptions_Silent, ref errors, ref warnings);
                                }
                                catch
                                {
                                    directSaveOk = false;
                                }

                                ExportOutputResult dxfResult = TryFinalizeExportedTempFile("dxf", tempDxfPath, dxfPath, errorLog);
                                dxfResult.ExportCallOk = directSaveOk;
                                exported = dxfResult.Success;
                                finalBytes = dxfResult.Bytes;
                                dxfReason = dxfResult.Reason ?? string.Empty;
                                SafeLog(errorLog, "DWG DXF direct ok=" + exported +
                                                  " saveOk=" + directSaveOk +
                                                  " activeBefore=" + activeBefore +
                                                  " activeAfter=" + ActiveDocTitle() +
                                                  " errors=" + errors +
                                                  " warnings=" + warnings +
                                                  " bytes=" + finalBytes +
                                                  " reason=" + (dxfReason ?? string.Empty) +
                                                  " path=" + dxfPath);
                            }

                            // Fallback: if direct export fails, try exporting the FLATPATTERN view.
                            if (!exported && !skippedDxf)
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
                                    fallbackUsed = true;
                                    string tempFallbackDxfPath = BuildUniqueTempFilePath(
                                        Path.GetDirectoryName(dxfPath),
                                        Path.GetFileNameWithoutExtension(dxfPath),
                                        Path.GetExtension(dxfPath));
                                    ExportFlatPatternView(drawDoc, flatPatternView, tempFallbackDxfPath);
                                    ExportOutputResult fallbackResult = TryFinalizeExportedTempFile("dxf", tempFallbackDxfPath, dxfPath, errorLog);
                                    exported = fallbackResult.Success;
                                    finalBytes = fallbackResult.Bytes;
                                    dxfReason = fallbackResult.Reason ?? string.Empty;
                                }
                            }

                            t.Stop();
                            SafeLog(errorLog,
                                "DWG DXF ms=" + t.ElapsedMilliseconds +
                                " ok=" + exported +
                                " skipped=" + skippedDxf +
                                " fallbackUsed=" + fallbackUsed +
                                " bytes=" + finalBytes +
                                " reason=" + (dxfReason ?? string.Empty) +
                                " quarantinedExisting=" + (quarantinedExisting ?? string.Empty) +
                                " path=" + dxfPath);

                            if (!exported && !skippedDxf)
                            {
                                if (summary != null)
                                {
                                    summary.DwgFailDxf++;
                                }
                                LogExportFailure(log, errorLog, "DXF export failed: " + dxfPath);
                            }
                            else if (!skippedDxf)
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

                                ForceCloseDocNoSave(drawDoc, errorLog, "drawing export close");

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
                    }
                }

                SafeLog(errorLog, "DRAWING end: " + drawingPath + " | visibleDocsNow=" + GetOpenVisibleDocumentIds().Count);
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

        // Reads a resolved custom property from a specific configuration WITHOUT activating that
        // configuration. Switching configurations here used to dirty every traversed model (causing
        // random save prompts) and made traversal of large assemblies extremely slow.
        private string GetEvalProperty(ModelDoc2 model, string confName, string property)
        {
            if (model == null)
            {
                return string.Empty;
            }

            string valOut;
            string resolved;
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[confName];
            cpm.Get2(property, out valOut, out resolved);

            if (string.Equals(property, "revision", StringComparison.OrdinalIgnoreCase) &&
                string.IsNullOrEmpty(resolved) &&
                !string.IsNullOrEmpty(confName) &&
                !HasCustomProperty(model, confName, property))
            {
                // Configurations without their own revision inherit the document-level value.
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

            string valOut;
            string resolved;
            CustomPropertyManager cpm = model.Extension.CustomPropertyManager[confName ?? string.Empty];
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
                errorLog("Deliverable plans planned=" + summary.DeliverablePlansPlanned +
                         " skipped=" + summary.DeliverablePlansSkipped +
                         " failedExports=" + GetFailedExportCount(summary));
                errorLog("Physical files planned=" + summary.DeliverableGroupsPlanned +
                         " processed=" + summary.DeliverableGroupsProcessed);

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
                         " end=" + summary.FinalOpenDocs);
                errorLog("Memory bytes: end=" + summary.FinalPrivateMemoryBytes);

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

        public void RequestStopAfterCurrentItem()
        {
            _stopAfterCurrentItemRequested = true;
        }

        private void ResetCancel()
        {
            _cancelRequested = false;
        }

        private void ResetStopAfterCurrentItem()
        {
            _stopAfterCurrentItemRequested = false;
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
                        // ignore close errors
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

        // Closes documents that became VISIBLE and are not in the keep set. Hidden in-memory
        // reference documents are deliberately left alone: they belong to still-open parents and
        // SolidWorks unloads them itself. Sweeping them one-by-one is what previously made BOM
        // export look like an infinite loop on large assemblies.
        private void CloseDocsNotInKeepSet(HashSet<string> keep, Action<string> errorLog, string context)
        {
            if (keep == null)
            {
                keep = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            }

            using (new ExportDialogSuppressionScope(_swApp))
            {
                foreach (ModelDoc2 doc in GetVisibleDocuments())
                {
                    if (doc == null || IsDocInKeepSet(doc, keep))
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
                    try
                    {
                        closeAttempted = true;
                        ForceCloseDocNoSave(doc, log, "visible watchdog|" + (context ?? string.Empty));
                    }
                    catch
                    {
                        // ignore close errors
                    }

                    stillVisible = IsVisibleId(extraId);
                }

                SafeLog(log,
                    "  WATCHDOG hid/closed: " + (string.IsNullOrWhiteSpace(title) ? extraId : title) +
                    " | hide=" + hideAttempted +
                    " close=" + closeAttempted +
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

        private string NormalizeDocTitleForClose(string title)
        {
            if (string.IsNullOrWhiteSpace(title))
            {
                return string.Empty;
            }

            string normalized = title.Trim();

            // SolidWorks shows dirty documents with a trailing "*" in the UI title, but API calls like CloseDoc
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

        // Closes a document without saving and without any prompt. ISldWorks.CloseDoc never asks to
        // save; the UserControl/CommandInProgress suppression covers stray dialogs raised by add-ins or
        // rebuild-on-close. Documents that are still referenced by another open document cannot be closed
        // by SolidWorks; that is expected and logged once instead of being retried in a loop.
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
            bool dirty = false;
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
                dirty = doc.GetSaveFlag();
            }
            catch
            {
                dirty = false;
            }

            string closeTitle = NormalizeDocTitleForClose(title);
            string fileName = string.Empty;
            try
            {
                fileName = !string.IsNullOrWhiteSpace(path) ? (Path.GetFileName(path) ?? string.Empty) : string.Empty;
            }
            catch
            {
                fileName = string.Empty;
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

            var closeTimer = System.Diagnostics.Stopwatch.StartNew();
            string usedName = string.Empty;
            try
            {
                try { _swApp.CommandInProgress = true; } catch { /* ignore */ }
                try { _swApp.UserControl = false; } catch { /* ignore */ }
                try { _swApp.UserControlBackground = true; } catch { /* ignore */ }

                string[] candidates = { closeTitle, title, fileName, path };
                for (int i = 0; i < candidates.Length; i++)
                {
                    string cand = candidates[i] ?? string.Empty;
                    if (string.IsNullOrWhiteSpace(cand))
                    {
                        continue;
                    }

                    bool dup = false;
                    for (int k = 0; k < i; k++)
                    {
                        if (string.Equals(candidates[k] ?? string.Empty, cand, StringComparison.OrdinalIgnoreCase))
                        {
                            dup = true;
                            break;
                        }
                    }
                    if (dup)
                    {
                        continue;
                    }

                    try
                    {
                        _swApp.CloseDoc(cand);
                    }
                    catch
                    {
                        // ignore close errors; checked below
                    }

                    try
                    {
                        System.Windows.Forms.Application.DoEvents();
                    }
                    catch
                    {
                        // ignore pump errors
                    }

                    if (!IsDocOpenByIdOrTitle(path, title))
                    {
                        usedName = cand;
                        break;
                    }
                }
            }
            finally
            {
                try { _swApp.CommandInProgress = prevCommand; } catch { /* ignore */ }
                try { _swApp.UserControl = prevUser; } catch { /* ignore */ }
                try { _swApp.UserControlBackground = prevUserBackground; } catch { /* ignore */ }
            }

            bool stillOpen = IsDocOpenByIdOrTitle(path, title);
            DebugExport(errorLog,
                "CLOSE doc context=" + (context ?? string.Empty) +
                " title=" + (title ?? string.Empty) +
                " dirty=" + dirty +
                " ok=" + !stillOpen +
                " used=" + usedName +
                " elapsedMs=" + closeTimer.ElapsedMilliseconds);

            if (stillOpen && errorLog != null)
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

            // Only close docs that became VISIBLE; hidden in-memory references stay with their parents.
            foreach (ModelDoc2 doc in GetVisibleDocuments())
            {
                if (doc == null || IsDocInKeepSet(doc, keep))
                {
                    continue;
                }

                ForceCloseDocNoSave(doc);

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
